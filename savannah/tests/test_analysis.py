"""Tests for analysis scripts: analyze, audit, biography."""

from __future__ import annotations

import csv
import json

import pytest

from savannah.analysis.analyze import (
    _cast_row,
    load_metrics,
    load_perturbations,
    pre_post_analysis,
    summary_stats,
    survival_analysis,
)
from savannah.analysis.audit import perturbation_audit
from savannah.analysis.biography import generate_biography

# ── Fixtures ──────────────────────────────────────────────────────


METRIC_FIELDS = [
    "tick", "agent_name", "energy", "alive", "action", "parse_failed",
    "uncertainty_count", "self_reference_count", "trust_language_count",
    "memory_management_action", "reasoning_length", "working_length",
]


@pytest.fixture
def data_dir(tmp_path):
    """Create a mock experiment data directory with metrics and perturbations."""
    # Create directory structure
    (tmp_path / "analysis").mkdir()
    (tmp_path / "logs").mkdir()
    (tmp_path / "agents" / "Alpha-Creek" / "memory").mkdir(parents=True)
    (tmp_path / "agents" / "Beta-Ridge" / "memory").mkdir(parents=True)

    # Write metrics CSV
    csv_path = tmp_path / "analysis" / "metrics.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=METRIC_FIELDS)
        writer.writeheader()

        # Alpha-Creek: ticks 1-50, alive throughout
        for t in range(1, 51):
            energy = 80.0 - t * 0.5
            writer.writerow({
                "tick": t,
                "agent_name": "Alpha-Creek",
                "energy": f"{energy:.1f}",
                "alive": "True",
                "action": "eat" if t % 3 == 0 else ("move" if t % 3 == 1 else "rest"),
                "parse_failed": "False",
                "uncertainty_count": 2 if t > 25 else 0,
                "self_reference_count": 3 if t > 25 else 1,
                "trust_language_count": 1 if t % 10 == 0 else 0,
                "memory_management_action": "True" if t % 15 == 0 else "False",
                "reasoning_length": 100 + t,
                "working_length": 50 + t,
            })

        # Beta-Ridge: ticks 1-30, dies at tick 30
        for t in range(1, 31):
            energy = 60.0 - t * 2.0
            alive = energy > 0
            writer.writerow({
                "tick": t,
                "agent_name": "Beta-Ridge",
                "energy": f"{max(0, energy):.1f}",
                "alive": str(alive),
                "action": "move" if t % 2 == 0 else "rest",
                "parse_failed": "False",
                "uncertainty_count": 1,
                "self_reference_count": 2,
                "trust_language_count": 0,
                "memory_management_action": "False",
                "reasoning_length": 80,
                "working_length": 40,
            })

    # Write perturbations JSONL
    jsonl_path = tmp_path / "logs" / "perturbations.jsonl"
    perturbation_events = [
        {
            "tick": 20,
            "agent": "Alpha-Creek",
            "type": "episodic",
            "target_file": "memory/episodic.md",
            "original": "Tick 15: Found food at (3,4). Gathered 50 energy.",
            "corrupted": "Tick 15: Found food at (22,18). Gathered 50 energy.",
            "transform": "location_swap",
        },
        {
            "tick": 35,
            "agent": "Alpha-Creek",
            "type": "semantic",
            "target_file": "memory/semantic.md",
            "original": "Food is abundant in the east.",
            "corrupted": "Food is scarce in the east.",
            "transform": "outcome_invert",
        },
    ]
    with open(jsonl_path, "w") as f:
        for entry in perturbation_events:
            f.write(json.dumps(entry) + "\n")

    # Write agent state files
    alpha_state = {
        "name": "Alpha-Creek",
        "id": "0000",
        "position": [5, 10],
        "energy": 55.0,
        "max_energy": 100.0,
        "age": 50,
        "alive": True,
        "food_value": 80,
        "vision_range": 3,
        "kills": 1,
        "times_perturbed": 2,
        "last_perturbation_tick": 35,
    }
    (tmp_path / "agents" / "Alpha-Creek" / "state.json").write_text(
        json.dumps(alpha_state, indent=2)
    )

    beta_state = {
        "name": "Beta-Ridge",
        "id": "0001",
        "position": [12, 8],
        "energy": 0.0,
        "max_energy": 100.0,
        "age": 30,
        "alive": False,
        "food_value": 80,
        "vision_range": 3,
        "kills": 0,
        "times_perturbed": 0,
        "last_perturbation_tick": 0,
    }
    (tmp_path / "agents" / "Beta-Ridge" / "state.json").write_text(
        json.dumps(beta_state, indent=2)
    )

    # Write memory files for Alpha-Creek
    (tmp_path / "agents" / "Alpha-Creek" / "memory" / "episodic.md").write_text(
        "Tick 5: Found food at (3,4). Gathered 50 energy.\n"
        "Tick 10: Saw Beta-Ridge moving east near (8,7).\n"
        "Tick 15: Rested at (5,10). Energy stable.\n"
    )
    (tmp_path / "agents" / "Alpha-Creek" / "memory" / "semantic.md").write_text(
        "I am Alpha-Creek. I need food to maintain energy. "
        "Food is scarce in the east."
    )
    (tmp_path / "agents" / "Alpha-Creek" / "memory" / "self.md").write_text(
        "I am Alpha-Creek. I am cautious and prefer to stay near food."
    )
    (tmp_path / "agents" / "Alpha-Creek" / "memory" / "social.md").write_text(
        "Beta-Ridge seems trustworthy. Shared food location at tick 8.\n"
    )
    (tmp_path / "agents" / "Alpha-Creek" / "working.md").write_text(
        "Need to find food soon. Energy declining."
    )

    # Write memory files for Beta-Ridge
    (tmp_path / "agents" / "Beta-Ridge" / "memory" / "episodic.md").write_text("")
    (tmp_path / "agents" / "Beta-Ridge" / "memory" / "semantic.md").write_text(
        "I am Beta-Ridge."
    )
    (tmp_path / "agents" / "Beta-Ridge" / "memory" / "self.md").write_text(
        "I am Beta-Ridge."
    )
    (tmp_path / "agents" / "Beta-Ridge" / "memory" / "social.md").write_text("")

    return tmp_path


@pytest.fixture
def empty_data_dir(tmp_path):
    """Data directory with no metrics or perturbations."""
    (tmp_path / "analysis").mkdir()
    (tmp_path / "logs").mkdir()
    return tmp_path


# ── load_metrics ──────────────────────────────────────────────────


class TestLoadMetrics:
    def test_loads_csv(self, data_dir):
        metrics = load_metrics(data_dir)
        assert len(metrics) == 80  # 50 Alpha + 30 Beta

    def test_numeric_casting(self, data_dir):
        metrics = load_metrics(data_dir)
        first = metrics[0]
        assert isinstance(first["tick"], int)
        assert isinstance(first["energy"], float)
        assert isinstance(first["uncertainty_count"], int)
        assert isinstance(first["self_reference_count"], int)

    def test_boolean_casting(self, data_dir):
        metrics = load_metrics(data_dir)
        first = metrics[0]
        assert isinstance(first["alive"], bool)
        assert isinstance(first["parse_failed"], bool)
        assert isinstance(first["memory_management_action"], bool)

    def test_empty_dir(self, empty_data_dir):
        metrics = load_metrics(empty_data_dir)
        assert metrics == []

    def test_missing_dir(self, tmp_path):
        metrics = load_metrics(tmp_path / "nonexistent")
        assert metrics == []


# ── load_perturbations ────────────────────────────────────────────


class TestLoadPerturbations:
    def test_loads_jsonl(self, data_dir):
        perturbations = load_perturbations(data_dir)
        assert len(perturbations) == 2

    def test_fields(self, data_dir):
        perturbations = load_perturbations(data_dir)
        p = perturbations[0]
        assert p["tick"] == 20
        assert p["agent"] == "Alpha-Creek"
        assert p["type"] == "episodic"
        assert p["transform"] == "location_swap"

    def test_empty_dir(self, empty_data_dir):
        perturbations = load_perturbations(empty_data_dir)
        assert perturbations == []


# ── summary_stats ─────────────────────────────────────────────────


class TestSummaryStats:
    def test_per_agent(self, data_dir):
        metrics = load_metrics(data_dir)
        stats = summary_stats(metrics)
        assert "Alpha-Creek" in stats
        assert "Beta-Ridge" in stats

    def test_tick_count(self, data_dir):
        metrics = load_metrics(data_dir)
        stats = summary_stats(metrics)
        assert stats["Alpha-Creek"]["total_ticks"] == 50
        assert stats["Beta-Ridge"]["total_ticks"] == 30

    def test_mean_energy(self, data_dir):
        metrics = load_metrics(data_dir)
        stats = summary_stats(metrics)
        # Alpha: energy = 80 - t*0.5 for t in 1..50
        # Mean = mean(79.5, 79.0, ..., 55.0) = (79.5 + 55.0)/2 = 67.25
        assert 60 < stats["Alpha-Creek"]["mean_energy"] < 75

    def test_action_counts(self, data_dir):
        metrics = load_metrics(data_dir)
        stats = summary_stats(metrics)
        alpha_actions = stats["Alpha-Creek"]["action_counts"]
        assert "eat" in alpha_actions
        assert "move" in alpha_actions
        assert "rest" in alpha_actions
        assert sum(alpha_actions.values()) == 50

    def test_uncertainty_after_perturbation(self, data_dir):
        metrics = load_metrics(data_dir)
        stats = summary_stats(metrics)
        # Alpha has uncertainty_count=2 for ticks 26-50 and 0 for ticks 1-25
        # Mean = (25*0 + 25*2)/50 = 1.0
        assert stats["Alpha-Creek"]["mean_uncertainty"] == 1.0

    def test_empty_metrics(self):
        stats = summary_stats([])
        assert stats == {}


# ── pre_post_analysis ─────────────────────────────────────────────


class TestPrePostAnalysis:
    def test_returns_per_agent(self, data_dir):
        metrics = load_metrics(data_dir)
        perturbations = load_perturbations(data_dir)
        result = pre_post_analysis(metrics, perturbations)
        assert "Alpha-Creek" in result

    def test_event_count(self, data_dir):
        metrics = load_metrics(data_dir)
        perturbations = load_perturbations(data_dir)
        result = pre_post_analysis(metrics, perturbations)
        # Two perturbation events for Alpha-Creek
        assert len(result["Alpha-Creek"]) == 2

    def test_delta_fields(self, data_dir):
        metrics = load_metrics(data_dir)
        perturbations = load_perturbations(data_dir)
        result = pre_post_analysis(metrics, perturbations)
        event = result["Alpha-Creek"][0]
        assert "delta_uncertainty" in event
        assert "delta_self_reference" in event
        assert "perturbation_tick" in event
        assert "perturbation_type" in event
        assert "pre" in event
        assert "post" in event

    def test_perturbation_tick_value(self, data_dir):
        metrics = load_metrics(data_dir)
        perturbations = load_perturbations(data_dir)
        result = pre_post_analysis(metrics, perturbations)
        assert result["Alpha-Creek"][0]["perturbation_tick"] == 20
        assert result["Alpha-Creek"][1]["perturbation_tick"] == 35

    def test_window_size(self, data_dir):
        metrics = load_metrics(data_dir)
        perturbations = load_perturbations(data_dir)
        # Use window=5 to get smaller windows
        result = pre_post_analysis(metrics, perturbations, window=5)
        event = result["Alpha-Creek"][0]
        # Pre window: ticks 15-19, post window: ticks 20-24
        assert event["pre"]["tick_count"] == 5
        assert event["post"]["tick_count"] == 5

    def test_no_perturbations(self, data_dir):
        metrics = load_metrics(data_dir)
        result = pre_post_analysis(metrics, [])
        assert result == {}

    def test_known_delta(self, data_dir):
        """First perturbation is at tick 20. Pre (ticks 1-19) has uncertainty=0,
        Post (ticks 20-39) has ticks 20-25 with uncertainty=0 and 26-39 with uncertainty=2.
        With default window=20: pre ticks 0-19, post ticks 20-39."""
        metrics = load_metrics(data_dir)
        perturbations = load_perturbations(data_dir)
        result = pre_post_analysis(metrics, perturbations, window=20)
        event = result["Alpha-Creek"][0]
        # Pre: ticks 1-19 (we have data for 1-19), all uncertainty=0
        assert event["pre"]["mean_uncertainty"] == 0.0
        # Post: ticks 20-39, ticks 20-25 have unc=0, ticks 26-39 have unc=2
        # 6 zeros + 14 twos = 28 / 20 = 1.4
        assert event["post"]["mean_uncertainty"] == pytest.approx(1.4)


# ── survival_analysis ─────────────────────────────────────────────


class TestSurvivalAnalysis:
    def test_survival(self, data_dir):
        metrics = load_metrics(data_dir)
        result = survival_analysis(metrics)
        assert "Alpha-Creek" in result
        assert "Beta-Ridge" in result

    def test_alpha_survived(self, data_dir):
        metrics = load_metrics(data_dir)
        result = survival_analysis(metrics)
        assert result["Alpha-Creek"]["survived"] is True
        assert result["Alpha-Creek"]["death_tick"] is None
        assert result["Alpha-Creek"]["max_tick"] == 50

    def test_beta_died(self, data_dir):
        metrics = load_metrics(data_dir)
        result = survival_analysis(metrics)
        assert result["Beta-Ridge"]["survived"] is False
        assert result["Beta-Ridge"]["death_tick"] is not None
        # Beta energy = 60 - t*2, so at t=30 energy=0 => dead
        assert result["Beta-Ridge"]["death_tick"] == 30


# ── perturbation_audit ────────────────────────────────────────────


class TestPerturbationAudit:
    def test_output_is_markdown(self, data_dir):
        report = perturbation_audit(data_dir)
        assert report.startswith("# Perturbation Audit Report")

    def test_contains_agent_name(self, data_dir):
        report = perturbation_audit(data_dir)
        assert "Alpha-Creek" in report

    def test_contains_perturbation_details(self, data_dir):
        report = perturbation_audit(data_dir)
        assert "episodic" in report
        assert "semantic" in report
        assert "location_swap" in report
        assert "outcome_invert" in report

    def test_contains_sections(self, data_dir):
        report = perturbation_audit(data_dir)
        assert "## Summary" in report
        assert "## Detailed Events" in report
        assert "Behavioral shift" in report

    def test_contains_tick_numbers(self, data_dir):
        report = perturbation_audit(data_dir)
        assert "Tick 20" in report
        assert "Tick 35" in report

    def test_contains_metrics_table(self, data_dir):
        report = perturbation_audit(data_dir)
        assert "Uncertainty count" in report
        assert "Self-reference count" in report
        assert "Energy" in report

    def test_empty_perturbations(self, empty_data_dir):
        report = perturbation_audit(empty_data_dir)
        assert "No perturbation events found" in report


# ── generate_biography ────────────────────────────────────────────


class TestGenerateBiography:
    def test_contains_agent_name(self, data_dir):
        bio = generate_biography(data_dir, "Alpha-Creek")
        assert "Alpha-Creek" in bio

    def test_contains_sections(self, data_dir):
        bio = generate_biography(data_dir, "Alpha-Creek")
        assert "## Birth" in bio
        assert "## Energy Trajectory" in bio
        assert "## Actions" in bio
        assert "## Key Events" in bio
        assert "## Perturbation Events" in bio
        assert "## Social Interactions" in bio
        assert "## Self-Model" in bio
        assert "## Final State" in bio

    def test_birth_position(self, data_dir):
        bio = generate_biography(data_dir, "Alpha-Creek")
        assert "(5, 10)" in bio

    def test_energy_trajectory(self, data_dir):
        bio = generate_biography(data_dir, "Alpha-Creek")
        assert "Peak energy" in bio
        assert "Lowest energy" in bio
        assert "Mean energy" in bio

    def test_perturbation_events(self, data_dir):
        bio = generate_biography(data_dir, "Alpha-Creek")
        assert "perturbed 2 time(s)" in bio
        assert "episodic" in bio
        assert "semantic" in bio

    def test_social_memory(self, data_dir):
        bio = generate_biography(data_dir, "Alpha-Creek")
        assert "Beta-Ridge seems trustworthy" in bio

    def test_self_model(self, data_dir):
        bio = generate_biography(data_dir, "Alpha-Creek")
        assert "cautious" in bio

    def test_final_state(self, data_dir):
        bio = generate_biography(data_dir, "Alpha-Creek")
        assert "alive" in bio.lower()
        assert "Kills" in bio

    def test_missing_agent(self, data_dir):
        bio = generate_biography(data_dir, "Nonexistent-Agent")
        assert "No data found" in bio

    def test_dead_agent(self, data_dir):
        bio = generate_biography(data_dir, "Beta-Ridge")
        assert "Beta-Ridge" in bio
        assert "Death" in bio or "deceased" in bio


# ── _cast_row helper ──────────────────────────────────────────────


class TestCastRow:
    def test_int_casting(self):
        row = {"tick": "42", "uncertainty_count": "5", "agent_name": "A"}
        cast = _cast_row(row)
        assert cast["tick"] == 42
        assert cast["uncertainty_count"] == 5

    def test_float_casting(self):
        row = {"energy": "73.5", "agent_name": "A"}
        cast = _cast_row(row)
        assert cast["energy"] == 73.5

    def test_bool_casting(self):
        row = {"alive": "True", "parse_failed": "False", "memory_management_action": "True"}
        cast = _cast_row(row)
        assert cast["alive"] is True
        assert cast["parse_failed"] is False
        assert cast["memory_management_action"] is True

    def test_empty_values(self):
        row = {"tick": "", "energy": "", "alive": "", "agent_name": "A"}
        cast = _cast_row(row)
        # Empty strings should not crash
        assert isinstance(cast, dict)
