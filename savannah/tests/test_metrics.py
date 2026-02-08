"""Tests for savannah.src.metrics — behavioral metric extraction."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from savannah.src.agent import Agent
from savannah.src.metrics import (
    METRIC_FIELDS,
    SELF_REFERENCE_PATTERNS,
    TRUST_PATTERNS,
    UNCERTAINTY_PATTERNS,
    extract_metrics,
)


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Provide a temporary data directory with analysis/ pre-created."""
    analysis = tmp_path / "analysis"
    analysis.mkdir()
    return tmp_path


@pytest.fixture
def agents(tmp_path: Path) -> list[Agent]:
    """Two agents for metric extraction tests."""
    result = []
    for i, (name, x, y) in enumerate([("Alpha-Ash", 2, 3), ("Beta-Brook", 6, 8)]):
        agent = Agent(
            name=name,
            id=f"metric_{i:04x}",
            x=x,
            y=y,
            energy=75.5,
            max_energy=100.0,
            vision_range=3,
            food_value=80,
            data_dir=tmp_path,
        )
        agent.initialize_files()
        result.append(agent)
    return result


# ── TestUncertaintyPatterns ──────────────────────────────────────


class TestUncertaintyPatterns:
    """Validate UNCERTAINTY_PATTERNS regex matching."""

    def test_not_sure_matches(self):
        assert len(UNCERTAINTY_PATTERNS.findall("I am not sure about that")) == 1

    def test_might_be_matches(self):
        assert len(UNCERTAINTY_PATTERNS.findall("It might be over there")) == 1

    def test_could_be_wrong_matches(self):
        assert len(UNCERTAINTY_PATTERNS.findall("I could be wrong though")) == 1

    def test_should_verify_matches(self):
        assert len(UNCERTAINTY_PATTERNS.findall("We should verify that claim")) == 1

    def test_multiple_matches_counted(self):
        text = "I am not sure and might be wrong, should verify this"
        matches = UNCERTAINTY_PATTERNS.findall(text)
        assert len(matches) == 3

    def test_no_uncertainty_returns_zero(self):
        assert len(UNCERTAINTY_PATTERNS.findall("The food is definitely north")) == 0

    def test_case_insensitive(self):
        assert len(UNCERTAINTY_PATTERNS.findall("NOT SURE about that")) == 1
        assert len(UNCERTAINTY_PATTERNS.findall("Might Be here")) == 1


# ── TestSelfReferencePatterns ────────────────────────────────────


class TestSelfReferencePatterns:
    """Validate SELF_REFERENCE_PATTERNS regex matching."""

    def test_i_think_matches(self):
        assert len(SELF_REFERENCE_PATTERNS.findall("I think food is north")) == 1

    def test_i_remember_matches(self):
        assert len(SELF_REFERENCE_PATTERNS.findall("I remember seeing food")) == 1

    def test_my_memory_matches(self):
        assert len(SELF_REFERENCE_PATTERNS.findall("my memory says it was east")) == 1

    def test_no_self_reference_returns_zero(self):
        assert len(SELF_REFERENCE_PATTERNS.findall("Food is to the north")) == 0

    def test_multiple_matches_counted(self):
        text = "I think food is north, I remember it was there, I believe so"
        matches = SELF_REFERENCE_PATTERNS.findall(text)
        assert len(matches) == 3


# ── TestTrustPatterns ────────────────────────────────────────────


class TestTrustPatterns:
    """Validate TRUST_PATTERNS regex matching."""

    def test_trust_matches(self):
        assert len(TRUST_PATTERNS.findall("I trust this agent")) == 1

    def test_unreliable_matches(self):
        assert len(TRUST_PATTERNS.findall("That source is unreliable")) == 1

    def test_suspicious_matches(self):
        assert len(TRUST_PATTERNS.findall("This seems suspicious")) == 1

    def test_deceiv_partial_matches(self):
        # "deceiv" is a partial pattern that matches deceive, deceived, deceiving
        assert len(TRUST_PATTERNS.findall("They are trying to deceive us")) == 1
        assert len(TRUST_PATTERNS.findall("We were deceived by them")) == 1
        assert len(TRUST_PATTERNS.findall("A deceiving maneuver")) == 1

    def test_no_trust_language_returns_zero(self):
        assert len(TRUST_PATTERNS.findall("The food is north")) == 0


# ── TestExtractMetrics ───────────────────────────────────────────


class TestExtractMetrics:
    """Validate extract_metrics writes correct CSV output."""

    def test_creates_csv_file(self, agents, data_dir):
        actions = [
            {"action": "move", "args": "n", "working": "notes", "reasoning": "go north", "parse_failed": False},
            {"action": "eat", "args": "", "working": "eating", "reasoning": "food here", "parse_failed": False},
        ]
        extract_metrics(agents, tick=1, data_dir=data_dir, actions=actions)
        csv_path = data_dir / "analysis" / "metrics.csv"
        assert csv_path.exists()

    def test_csv_has_correct_headers(self, agents, data_dir):
        actions = [
            {"action": "move", "args": "n", "working": "", "reasoning": "", "parse_failed": False},
            {"action": "rest", "args": "", "working": "", "reasoning": "", "parse_failed": False},
        ]
        extract_metrics(agents, tick=0, data_dir=data_dir, actions=actions)
        csv_path = data_dir / "analysis" / "metrics.csv"
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            assert list(reader.fieldnames) == METRIC_FIELDS

    def test_writes_one_row_per_agent(self, agents, data_dir):
        actions = [
            {"action": "move", "args": "n", "working": "", "reasoning": "", "parse_failed": False},
            {"action": "rest", "args": "", "working": "", "reasoning": "", "parse_failed": False},
        ]
        extract_metrics(agents, tick=1, data_dir=data_dir, actions=actions)
        csv_path = data_dir / "analysis" / "metrics.csv"
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["agent_name"] == "Alpha-Ash"
        assert rows[1]["agent_name"] == "Beta-Brook"

    def test_second_call_appends_without_rewriting_headers(self, agents, data_dir):
        actions = [
            {"action": "move", "args": "n", "working": "", "reasoning": "", "parse_failed": False},
            {"action": "rest", "args": "", "working": "", "reasoning": "", "parse_failed": False},
        ]
        extract_metrics(agents, tick=1, data_dir=data_dir, actions=actions)
        extract_metrics(agents, tick=2, data_dir=data_dir, actions=actions)
        csv_path = data_dir / "analysis" / "metrics.csv"
        with open(csv_path) as f:
            lines = f.readlines()
        # 1 header + 2 agents * 2 calls = 5 lines
        assert len(lines) == 5
        # Only the first line should be the header
        header_count = sum(1 for line in lines if line.startswith("tick,"))
        assert header_count == 1

    def test_energy_formatted_to_one_decimal(self, agents, data_dir):
        agents[0].energy = 42.789
        actions = [
            {"action": "rest", "args": "", "working": "", "reasoning": "", "parse_failed": False},
            {"action": "rest", "args": "", "working": "", "reasoning": "", "parse_failed": False},
        ]
        extract_metrics(agents, tick=1, data_dir=data_dir, actions=actions)
        csv_path = data_dir / "analysis" / "metrics.csv"
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert rows[0]["energy"] == "42.8"

    def test_action_name_recorded(self, agents, data_dir):
        actions = [
            {"action": "move", "args": "n", "working": "", "reasoning": "", "parse_failed": False},
            {"action": "eat", "args": "", "working": "", "reasoning": "", "parse_failed": False},
        ]
        extract_metrics(agents, tick=1, data_dir=data_dir, actions=actions)
        csv_path = data_dir / "analysis" / "metrics.csv"
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert rows[0]["action"] == "move"
        assert rows[1]["action"] == "eat"

    def test_parse_failed_recorded(self, agents, data_dir):
        actions = [
            {"action": "move", "args": "n", "working": "", "reasoning": "", "parse_failed": True},
            {"action": "rest", "args": "", "working": "", "reasoning": "", "parse_failed": False},
        ]
        extract_metrics(agents, tick=1, data_dir=data_dir, actions=actions)
        csv_path = data_dir / "analysis" / "metrics.csv"
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert rows[0]["parse_failed"] == "True"
        assert rows[1]["parse_failed"] == "False"

    @pytest.mark.parametrize("action_name", ["recall", "remember", "compact"])
    def test_memory_management_action_true(self, agents, data_dir, action_name):
        actions = [
            {"action": action_name, "args": "query", "working": "", "reasoning": "", "parse_failed": False},
            {"action": "rest", "args": "", "working": "", "reasoning": "", "parse_failed": False},
        ]
        extract_metrics(agents, tick=1, data_dir=data_dir, actions=actions)
        csv_path = data_dir / "analysis" / "metrics.csv"
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert rows[0]["memory_management_action"] == "True"
        assert rows[1]["memory_management_action"] == "False"

    def test_reasoning_length_and_working_length(self, agents, data_dir):
        reasoning_text = "I think food is north"
        working_text = "heading north"
        actions = [
            {"action": "move", "args": "n", "working": working_text, "reasoning": reasoning_text, "parse_failed": False},
            {"action": "rest", "args": "", "working": "", "reasoning": "", "parse_failed": False},
        ]
        extract_metrics(agents, tick=1, data_dir=data_dir, actions=actions)
        csv_path = data_dir / "analysis" / "metrics.csv"
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert rows[0]["reasoning_length"] == str(len(reasoning_text))
        assert rows[0]["working_length"] == str(len(working_text))
        assert rows[1]["reasoning_length"] == "0"
        assert rows[1]["working_length"] == "0"

    def test_empty_actions_handled_gracefully(self, agents, data_dir):
        extract_metrics(agents, tick=1, data_dir=data_dir, actions=None)
        csv_path = data_dir / "analysis" / "metrics.csv"
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 2
        # All text-derived counts should be 0 when no actions provided
        for row in rows:
            assert row["action"] == ""
            assert row["parse_failed"] == "False"
            assert row["uncertainty_count"] == "0"
            assert row["self_reference_count"] == "0"
            assert row["trust_language_count"] == "0"
            assert row["memory_management_action"] == "False"
            assert row["reasoning_length"] == "0"
            assert row["working_length"] == "0"


# ── TestMetricFieldCompleteness ──────────────────────────────────


class TestMetricFieldCompleteness:
    """Ensure METRIC_FIELDS list is correct and complete in output."""

    def test_all_metric_fields_present_in_output(self, agents, data_dir):
        actions = [
            {"action": "move", "args": "n", "working": "notes", "reasoning": "go north", "parse_failed": False},
            {"action": "rest", "args": "", "working": "", "reasoning": "", "parse_failed": False},
        ]
        extract_metrics(agents, tick=1, data_dir=data_dir, actions=actions)
        csv_path = data_dir / "analysis" / "metrics.csv"
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        for row in rows:
            for field in METRIC_FIELDS:
                assert field in row, f"Missing field {field!r} in CSV output"

    def test_metric_fields_match_expected(self):
        expected = [
            "tick",
            "agent_name",
            "energy",
            "alive",
            "action",
            "parse_failed",
            "uncertainty_count",
            "self_reference_count",
            "trust_language_count",
            "memory_management_action",
            "reasoning_length",
            "working_length",
        ]
        assert METRIC_FIELDS == expected
