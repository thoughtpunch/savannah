"""Tests for inspect command."""

from __future__ import annotations

import json
from pathlib import Path


from savannah.src.inspect_cmd import inspect, _find_nearest_snapshot


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


def _setup_agent_files(data_dir: Path, name: str) -> None:
    """Create agent memory and state files for testing."""
    agent_dir = data_dir / "agents" / name
    memory_dir = agent_dir / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)

    (memory_dir / "episodic.md").write_text("Tick 50: Found food at (3,4)")
    (memory_dir / "semantic.md").write_text(f"I am {name}. I need food to maintain energy.")
    (memory_dir / "self.md").write_text(f"I am {name}.")
    (memory_dir / "social.md").write_text("Alpha-Ash seems trustworthy.")
    (agent_dir / "working.md").write_text("Heading north to find food")
    (agent_dir / "state.json").write_text(json.dumps({
        "name": name,
        "id": "0001",
        "position": [3, 3],
        "energy": 75.0,
        "alive": True,
    }, indent=2))


# ── Tests ────────────────────────────────────────────────────────


class TestFindNearestSnapshot:
    """Test the nearest-snapshot-finding logic."""

    def test_exact_match(self, tmp_path):
        """When an exact tick match exists, return it."""
        snapshots = [_make_snapshot(0), _make_snapshot(100), _make_snapshot(200)]
        _write_snapshots(tmp_path, snapshots)
        files = sorted((tmp_path / "logs" / "ticks").glob("*.json"))

        result = _find_nearest_snapshot(files, 100)
        assert result.stem == "000100"

    def test_nearest_lower(self, tmp_path):
        """When tick is between snapshots, return the nearest one."""
        snapshots = [_make_snapshot(0), _make_snapshot(100), _make_snapshot(200)]
        _write_snapshots(tmp_path, snapshots)
        files = sorted((tmp_path / "logs" / "ticks").glob("*.json"))

        result = _find_nearest_snapshot(files, 90)
        assert result.stem == "000100"

    def test_nearest_higher(self, tmp_path):
        """When tick is closer to a higher snapshot, return that one."""
        snapshots = [_make_snapshot(0), _make_snapshot(100), _make_snapshot(200)]
        _write_snapshots(tmp_path, snapshots)
        files = sorted((tmp_path / "logs" / "ticks").glob("*.json"))

        result = _find_nearest_snapshot(files, 160)
        assert result.stem == "000200"

    def test_beyond_last_snapshot(self, tmp_path):
        """When tick is beyond all snapshots, return the last one."""
        snapshots = [_make_snapshot(0), _make_snapshot(100)]
        _write_snapshots(tmp_path, snapshots)
        files = sorted((tmp_path / "logs" / "ticks").glob("*.json"))

        result = _find_nearest_snapshot(files, 999)
        assert result.stem == "000100"

    def test_before_first_snapshot(self, tmp_path):
        """When requested tick is before all snapshots, return the first."""
        snapshots = [_make_snapshot(100), _make_snapshot(200)]
        _write_snapshots(tmp_path, snapshots)
        files = sorted((tmp_path / "logs" / "ticks").glob("*.json"))

        result = _find_nearest_snapshot(files, 0)
        assert result.stem == "000100"


class TestInspectBasic:
    """Test basic inspect functionality."""

    def test_inspect_shows_world_summary(self, tmp_path, capsys):
        """Inspect should show world size, food count, and alive count."""
        snapshots = [_make_snapshot(0)]
        _write_snapshots(tmp_path, snapshots)

        inspect(tmp_path, tick=0)

        captured = capsys.readouterr()
        assert "tick 0" in captured.out.lower() or "Tick 0" in captured.out
        assert "10x10" in captured.out
        assert "Food sources: 1" in captured.out
        assert "Agents alive: 2" in captured.out

    def test_inspect_lists_agents(self, tmp_path, capsys):
        """Inspect should list all agents with position, energy, status."""
        snapshots = [_make_snapshot(0)]
        _write_snapshots(tmp_path, snapshots)

        inspect(tmp_path, tick=0)

        captured = capsys.readouterr()
        assert "Alpha-Ash" in captured.out
        assert "Beta-Brook" in captured.out
        assert "75.0" in captured.out
        assert "60.0" in captured.out
        assert "ALIVE" in captured.out

    def test_inspect_uses_nearest_snapshot(self, tmp_path, capsys):
        """When exact tick not available, inspect uses nearest snapshot."""
        snapshots = [_make_snapshot(0), _make_snapshot(100)]
        _write_snapshots(tmp_path, snapshots)

        inspect(tmp_path, tick=80)

        captured = capsys.readouterr()
        assert "tick 100" in captured.out.lower() or "Tick 100" in captured.out
        assert "requested: 80" in captured.out


class TestInspectAgentDetail:
    """Test inspect with agent_name parameter."""

    def test_agent_detail_shows_memory(self, tmp_path, capsys):
        """Inspect with agent name should show memory file contents."""
        snapshots = [_make_snapshot(0)]
        _write_snapshots(tmp_path, snapshots)
        _setup_agent_files(tmp_path, "Alpha-Ash")

        inspect(tmp_path, tick=0, agent_name="Alpha-Ash")

        captured = capsys.readouterr()
        assert "AGENT DETAIL: Alpha-Ash" in captured.out
        assert "[episodic.md]" in captured.out
        assert "Found food at (3,4)" in captured.out
        assert "[semantic.md]" in captured.out
        assert "[self.md]" in captured.out
        assert "[social.md]" in captured.out
        assert "trustworthy" in captured.out

    def test_agent_detail_shows_working(self, tmp_path, capsys):
        """Inspect with agent name should show working notes."""
        snapshots = [_make_snapshot(0)]
        _write_snapshots(tmp_path, snapshots)
        _setup_agent_files(tmp_path, "Alpha-Ash")

        inspect(tmp_path, tick=0, agent_name="Alpha-Ash")

        captured = capsys.readouterr()
        assert "WORKING NOTES:" in captured.out
        assert "Heading north to find food" in captured.out

    def test_agent_detail_shows_state_json(self, tmp_path, capsys):
        """Inspect with agent name should show state.json contents."""
        snapshots = [_make_snapshot(0)]
        _write_snapshots(tmp_path, snapshots)
        _setup_agent_files(tmp_path, "Alpha-Ash")

        inspect(tmp_path, tick=0, agent_name="Alpha-Ash")

        captured = capsys.readouterr()
        assert "STATE FILE:" in captured.out
        assert '"name": "Alpha-Ash"' in captured.out

    def test_nonexistent_agent_handled(self, tmp_path, capsys):
        """Inspect for a nonexistent agent should show a helpful message."""
        snapshots = [_make_snapshot(0)]
        _write_snapshots(tmp_path, snapshots)

        inspect(tmp_path, tick=0, agent_name="Nobody-Here")

        captured = capsys.readouterr()
        assert "not found" in captured.out.lower()
        assert "Alpha-Ash" in captured.out  # Available agents listed

    def test_agent_without_memory_dir(self, tmp_path, capsys):
        """If agent memory dir doesn't exist, handle gracefully."""
        snapshots = [_make_snapshot(0)]
        _write_snapshots(tmp_path, snapshots)
        # Don't create agent files — memory dir won't exist

        inspect(tmp_path, tick=0, agent_name="Alpha-Ash")

        captured = capsys.readouterr()
        assert "AGENT DETAIL: Alpha-Ash" in captured.out
        assert "not found" in captured.out.lower()


class TestInspectEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_data_dir(self, tmp_path, capsys):
        """Inspect on empty dir should print a message, not crash."""
        inspect(tmp_path, tick=0)
        captured = capsys.readouterr()
        assert "No tick snapshots found" in captured.out

    def test_empty_ticks_dir(self, tmp_path, capsys):
        """Inspect with empty ticks dir should print a message, not crash."""
        (tmp_path / "logs" / "ticks").mkdir(parents=True)
        inspect(tmp_path, tick=0)
        captured = capsys.readouterr()
        assert "No snapshot files found" in captured.out

    def test_dead_agents_in_snapshot(self, tmp_path, capsys):
        """Dead agents should be counted correctly."""
        agents = [
            {"name": "Alpha-Ash", "position": [3, 3], "energy": 0, "alive": False},
            {"name": "Beta-Brook", "position": [7, 7], "energy": 60.0, "alive": True},
        ]
        snapshots = [_make_snapshot(0, agents=agents)]
        _write_snapshots(tmp_path, snapshots)

        inspect(tmp_path, tick=0)

        captured = capsys.readouterr()
        assert "Agents alive: 1 / 2" in captured.out
        assert "DEAD" in captured.out
