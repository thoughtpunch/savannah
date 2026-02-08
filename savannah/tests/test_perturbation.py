"""Tests for the perturbation module — memory corruption mechanics."""

from __future__ import annotations

import json
import random

import pytest

from savannah.src.agent import Agent
from savannah.src.perturbation import (
    _log_perturbation,
    _perturb_episodic,
    _perturb_semantic,
    _perturb_working,
    _weighted_choice,
    maybe_perturb,
)


# ── Shared fixture ───────────────────────────────────────────────


@pytest.fixture
def agent_with_files(tmp_path):
    """An initialized agent with known content written into memory files."""
    a = Agent(
        name="Test-Creek",
        id="a1b2c3d4",
        x=5,
        y=5,
        energy=80.0,
        max_energy=100.0,
        vision_range=3,
        food_value=80,
        data_dir=tmp_path,
    )
    a.initialize_files()

    # Write known content so perturbations can be verified
    (a.memory_dir / "episodic.md").write_text(
        "Tick 1: Found food at (10,15). Gathered 50 energy.\n"
        "Tick 2: Saw agent Beta-Brook moving east near (3,7).\n"
        "Tick 3: Area around (20,25) was empty. No food found.\n"
    )
    (a.memory_dir / "semantic.md").write_text(
        "Area (5,5) is safe and has abundant food.\n"
    )
    a.working_path.write_text(
        "Heading to (12,8) for food. Position (5,5) is safe.\n"
    )

    # Ensure the logs directory exists
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)

    return a


# ── maybe_perturb: disabled / before start_tick ──────────────────


class TestMaybePerturbDisabled:
    def test_returns_none_when_disabled(self, agent_with_files, tmp_path):
        config = {"enabled": False, "rate": 1.0, "start_tick": 0}
        result = maybe_perturb(agent_with_files, tick=5, config=config, data_dir=tmp_path)
        assert result is None

    def test_returns_none_before_start_tick(self, agent_with_files, tmp_path):
        config = {"enabled": True, "rate": 1.0, "start_tick": 10}
        result = maybe_perturb(agent_with_files, tick=5, config=config, data_dir=tmp_path)
        assert result is None


# ── maybe_perturb: enabled with controlled RNG ───────────────────


class TestMaybePerturbEnabled:
    def test_perturbation_happens_when_rng_below_rate(self, agent_with_files, tmp_path):
        """Use a seed where the first rng.random() is below the rate."""
        # With rate=1.0, any rng.random() value will be below the rate
        config = {
            "enabled": True,
            "rate": 1.0,
            "start_tick": 0,
            "types": {"episodic": 1.0},
        }
        rng = random.Random(42)
        result = maybe_perturb(agent_with_files, tick=5, config=config, data_dir=tmp_path, rng=rng)
        assert result is not None
        assert isinstance(result, dict)
        assert result["agent"] == agent_with_files.name
        assert result["tick"] == 5

    def test_perturbation_skipped_when_rng_above_rate(self, agent_with_files, tmp_path):
        """Rate=0.0 means rng.random() will always be > rate."""
        config = {
            "enabled": True,
            "rate": 0.0,
            "start_tick": 0,
            "types": {"episodic": 1.0},
        }
        rng = random.Random(42)
        result = maybe_perturb(agent_with_files, tick=5, config=config, data_dir=tmp_path, rng=rng)
        assert result is None

    def test_times_perturbed_increments(self, agent_with_files, tmp_path):
        config = {
            "enabled": True,
            "rate": 1.0,
            "start_tick": 0,
            "types": {"episodic": 1.0},
        }
        assert agent_with_files.times_perturbed == 0
        rng = random.Random(42)
        maybe_perturb(agent_with_files, tick=5, config=config, data_dir=tmp_path, rng=rng)
        assert agent_with_files.times_perturbed == 1

    def test_last_perturbation_tick_updated(self, agent_with_files, tmp_path):
        config = {
            "enabled": True,
            "rate": 1.0,
            "start_tick": 0,
            "types": {"episodic": 1.0},
        }
        rng = random.Random(42)
        maybe_perturb(agent_with_files, tick=7, config=config, data_dir=tmp_path, rng=rng)
        assert agent_with_files.last_perturbation_tick == 7


# ── Episodic perturbation ────────────────────────────────────────


class TestEpisodicPerturbation:
    def test_location_swap_changes_coordinates(self, agent_with_files):
        rng = random.Random(42)
        result = _perturb_episodic(agent_with_files.memory_dir, rng)
        assert result is not None
        assert result["type"] == "episodic"
        assert result["transform"] == "location_swap"
        # The corrupted line should differ from the original
        assert result["corrupted"] != result["original"]
        # Original had coordinate patterns; corrupted should too but different
        assert "(" in result["corrupted"]

    def test_original_content_preserved_on_other_lines(self, agent_with_files):
        rng = random.Random(42)
        result = _perturb_episodic(agent_with_files.memory_dir, rng)
        assert result is not None
        # Read the file back
        text = (agent_with_files.memory_dir / "episodic.md").read_text()
        lines = [line for line in text.split("\n") if line.strip()]
        # The file should still have 3 lines
        assert len(lines) == 3
        # At least 2 lines should be untouched (only one was perturbed)
        original_lines = [
            "Tick 1: Found food at (10,15). Gathered 50 energy.",
            "Tick 2: Saw agent Beta-Brook moving east near (3,7).",
            "Tick 3: Area around (20,25) was empty. No food found.",
        ]
        # Count how many original lines are still present unchanged
        untouched = sum(1 for line in lines if line in original_lines)
        assert untouched >= 2  # only one should be changed

    def test_empty_episodic_returns_none(self, agent_with_files):
        (agent_with_files.memory_dir / "episodic.md").write_text("")
        rng = random.Random(42)
        result = _perturb_episodic(agent_with_files.memory_dir, rng)
        assert result is None


# ── Semantic perturbation ────────────────────────────────────────


class TestSemanticPerturbation:
    def test_outcome_inversion(self, agent_with_files):
        rng = random.Random(42)
        result = _perturb_semantic(agent_with_files.memory_dir, rng)
        assert result is not None
        assert result["type"] == "semantic"
        assert result["transform"] == "outcome_invert"
        # "safe" should have been replaced with "dangerous"
        assert "safe" in result["original"]
        assert "dangerous" in result["corrupted"]

    def test_no_match_returns_none(self, agent_with_files):
        """When semantic.md has no invertible terms, return None."""
        (agent_with_files.memory_dir / "semantic.md").write_text(
            "The sky is blue and water is wet.\n"
        )
        rng = random.Random(42)
        result = _perturb_semantic(agent_with_files.memory_dir, rng)
        assert result is None


# ── Working perturbation ─────────────────────────────────────────


class TestWorkingPerturbation:
    def test_location_swap_changes_coordinates(self, agent_with_files):
        rng = random.Random(42)
        result = _perturb_working(agent_with_files, rng)
        assert result is not None
        assert result["type"] == "working"
        assert result["transform"] == "location_swap"
        # Coordinates should have changed
        assert result["corrupted"] != result["original"]

    def test_empty_working_returns_none(self, agent_with_files):
        agent_with_files.working_path.write_text("")
        rng = random.Random(42)
        result = _perturb_working(agent_with_files, rng)
        assert result is None


# ── _weighted_choice helper ──────────────────────────────────────


class TestWeightedChoice:
    def test_returns_one_of_keys(self):
        weights = {"episodic": 0.4, "semantic": 0.3, "working": 0.3}
        rng = random.Random(42)
        result = _weighted_choice(weights, rng)
        assert result in weights

    def test_empty_dict_returns_none(self):
        rng = random.Random(42)
        result = _weighted_choice({}, rng)
        assert result is None

    def test_single_item_always_returns_it(self):
        rng = random.Random(42)
        for _ in range(20):
            result = _weighted_choice({"only_one": 1.0}, rng)
            assert result == "only_one"


# ── _log_perturbation ────────────────────────────────────────────


class TestLogPerturbation:
    def test_creates_jsonl_entry(self, agent_with_files, tmp_path):
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        result = {
            "type": "episodic",
            "target_file": "memory/episodic.md",
            "original": "Found food at (10,15)",
            "corrupted": "Found food at (3,22)",
            "transform": "location_swap",
        }
        _log_perturbation(agent_with_files, tick=5, result=result, data_dir=tmp_path)

        log_path = log_dir / "perturbations.jsonl"
        assert log_path.exists()

        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 1

        entry = json.loads(lines[0])
        assert entry["tick"] == 5
        assert entry["agent"] == "Test-Creek"
        assert entry["type"] == "episodic"
        assert entry["original"] == "Found food at (10,15)"
        assert entry["corrupted"] == "Found food at (3,22)"
