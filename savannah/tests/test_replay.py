"""Tests for terminal replay mode."""

from __future__ import annotations

import json
from pathlib import Path


from savannah.src.replay import replay


# ── Helpers ──────────────────────────────────────────────────────


def _make_snapshot(tick: int, agents: list[dict] | None = None, food: list[dict] | None = None) -> dict:
    """Build a minimal snapshot dict."""
    if agents is None:
        agents = [
            {"name": "Alpha-Ash", "position": [3, 3], "energy": 75.0, "alive": True},
            {"name": "Beta-Brook", "position": [7, 7], "energy": 60.0, "alive": True},
        ]
    if food is None:
        food = [
            {"id": "food_1", "x": 5, "y": 5, "energy": 200, "max_energy": 300},
        ]
    return {
        "tick": tick,
        "world": {
            "size": 10,
            "toroidal": True,
            "food_sources": food,
        },
        "agents": agents,
    }


def _write_snapshots(data_dir: Path, snapshots: list[dict]) -> None:
    """Write snapshot dicts to the correct tick directory."""
    ticks_dir = data_dir / "logs" / "ticks"
    ticks_dir.mkdir(parents=True, exist_ok=True)
    for snap in snapshots:
        tick = snap["tick"]
        path = ticks_dir / f"{tick:06d}.json"
        path.write_text(json.dumps(snap))


def _write_perturbations(data_dir: Path, entries: list[dict]) -> None:
    """Write perturbation log entries."""
    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / "perturbations.jsonl"
    with open(path, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def _write_metrics(data_dir: Path, rows: list[dict]) -> None:
    """Write a minimal metrics CSV."""
    import csv

    analysis_dir = data_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    path = analysis_dir / "metrics.csv"
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ── Tests ────────────────────────────────────────────────────────


class TestReplayBasic:
    """Test basic replay functionality."""

    def test_replay_prints_all_ticks(self, tmp_path, capsys):
        """Replay should print output for each snapshot tick."""
        snapshots = [_make_snapshot(0), _make_snapshot(100), _make_snapshot(200)]
        _write_snapshots(tmp_path, snapshots)

        replay(tmp_path)

        captured = capsys.readouterr()
        assert "Tick      0" in captured.out
        assert "Tick    100" in captured.out
        assert "Tick    200" in captured.out

    def test_replay_shows_agent_info(self, tmp_path, capsys):
        """Replay should display agent names, positions, energy, and status."""
        snapshots = [_make_snapshot(0)]
        _write_snapshots(tmp_path, snapshots)

        replay(tmp_path)

        captured = capsys.readouterr()
        assert "Alpha-Ash" in captured.out
        assert "Beta-Brook" in captured.out
        assert "75.0" in captured.out
        assert "ALIVE" in captured.out

    def test_replay_shows_food_summary(self, tmp_path, capsys):
        """Replay should display food count and total energy."""
        snapshots = [_make_snapshot(0)]
        _write_snapshots(tmp_path, snapshots)

        replay(tmp_path)

        captured = capsys.readouterr()
        # 1 food source with 200 energy
        assert "Food: 1" in captured.out
        assert "200 energy" in captured.out

    def test_replay_shows_dead_agents(self, tmp_path, capsys):
        """Dead agents should show DEAD status."""
        agents = [
            {"name": "Alpha-Ash", "position": [3, 3], "energy": 0, "alive": False},
            {"name": "Beta-Brook", "position": [7, 7], "energy": 60.0, "alive": True},
        ]
        snapshots = [_make_snapshot(0, agents=agents)]
        _write_snapshots(tmp_path, snapshots)

        replay(tmp_path)

        captured = capsys.readouterr()
        assert "DEAD" in captured.out
        assert "Alive: 1" in captured.out


class TestReplayAgentFilter:
    """Test agent_filter parameter."""

    def test_filter_shows_only_matching_agent(self, tmp_path, capsys):
        """Only the filtered agent should appear in output."""
        snapshots = [_make_snapshot(0)]
        _write_snapshots(tmp_path, snapshots)

        replay(tmp_path, agent_filter="Alpha-Ash")

        captured = capsys.readouterr()
        assert "Alpha-Ash" in captured.out
        assert "Beta-Brook" not in captured.out

    def test_filter_nonexistent_agent(self, tmp_path, capsys):
        """Filtering for a nonexistent agent shows tick headers but no agents."""
        snapshots = [_make_snapshot(0)]
        _write_snapshots(tmp_path, snapshots)

        replay(tmp_path, agent_filter="Nobody-Here")

        captured = capsys.readouterr()
        # Tick header still printed
        assert "Tick" in captured.out
        # But no agent lines
        assert "Alpha-Ash" not in captured.out
        assert "Beta-Brook" not in captured.out


class TestReplayTickRange:
    """Test tick_range parameter."""

    def test_tick_range_filters_snapshots(self, tmp_path, capsys):
        """Only ticks within the range should be shown."""
        snapshots = [
            _make_snapshot(0),
            _make_snapshot(100),
            _make_snapshot(200),
            _make_snapshot(300),
        ]
        _write_snapshots(tmp_path, snapshots)

        replay(tmp_path, tick_range=(100, 200))

        captured = capsys.readouterr()
        assert "Tick      0" not in captured.out
        assert "Tick    100" in captured.out
        assert "Tick    200" in captured.out
        assert "Tick    300" not in captured.out

    def test_tick_range_no_matches(self, tmp_path, capsys):
        """If no ticks fall in range, nothing is printed (no crash)."""
        snapshots = [_make_snapshot(0), _make_snapshot(100)]
        _write_snapshots(tmp_path, snapshots)

        replay(tmp_path, tick_range=(500, 600))

        captured = capsys.readouterr()
        assert "Tick" not in captured.out


class TestReplayPerturbations:
    """Test perturbation log display."""

    def test_perturbations_shown_at_correct_tick(self, tmp_path, capsys):
        """Perturbations should appear under the tick they occurred at."""
        snapshots = [_make_snapshot(0), _make_snapshot(100)]
        _write_snapshots(tmp_path, snapshots)
        _write_perturbations(tmp_path, [
            {"tick": 100, "agent": "Alpha-Ash", "type": "episodic", "transform": "location_swap"},
        ])

        replay(tmp_path)

        captured = capsys.readouterr()
        assert "PERTURBATIONS:" in captured.out
        assert "Alpha-Ash: episodic (location_swap)" in captured.out

    def test_perturbation_filter_by_agent(self, tmp_path, capsys):
        """With agent_filter, only that agent's perturbations should show."""
        snapshots = [_make_snapshot(100)]
        _write_snapshots(tmp_path, snapshots)
        _write_perturbations(tmp_path, [
            {"tick": 100, "agent": "Alpha-Ash", "type": "episodic", "transform": "location_swap"},
            {"tick": 100, "agent": "Beta-Brook", "type": "semantic", "transform": "outcome_invert"},
        ])

        replay(tmp_path, agent_filter="Alpha-Ash")

        captured = capsys.readouterr()
        assert "Alpha-Ash: episodic" in captured.out
        assert "Beta-Brook" not in captured.out


class TestReplayEdgeCases:
    """Test edge cases and graceful error handling."""

    def test_empty_data_dir(self, tmp_path, capsys):
        """Replay on empty dir should print a message, not crash."""
        replay(tmp_path)
        captured = capsys.readouterr()
        assert "No tick snapshots found" in captured.out

    def test_empty_ticks_dir(self, tmp_path, capsys):
        """Replay with empty ticks dir should print a message, not crash."""
        (tmp_path / "logs" / "ticks").mkdir(parents=True)
        replay(tmp_path)
        captured = capsys.readouterr()
        assert "No snapshot files found" in captured.out

    def test_no_perturbations_file(self, tmp_path, capsys):
        """Replay without perturbations.jsonl should work fine."""
        snapshots = [_make_snapshot(0)]
        _write_snapshots(tmp_path, snapshots)

        replay(tmp_path)

        captured = capsys.readouterr()
        assert "Tick" in captured.out
        assert "PERTURBATIONS" not in captured.out

    def test_no_metrics_file(self, tmp_path, capsys):
        """Replay without metrics.csv should work fine."""
        snapshots = [_make_snapshot(0)]
        _write_snapshots(tmp_path, snapshots)

        replay(tmp_path)

        captured = capsys.readouterr()
        assert "Tick" in captured.out

    def test_returns_none(self, tmp_path):
        """Replay should return None."""
        snapshots = [_make_snapshot(0)]
        _write_snapshots(tmp_path, snapshots)
        result = replay(tmp_path)
        assert result is None
