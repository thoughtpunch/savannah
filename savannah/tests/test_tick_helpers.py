"""Tests for tick_helpers.py — prep/apply CLI subcommands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from savannah.src.engine import Engine
from savannah.src.tick_helpers import apply_responses, prep
from savannah.tests.conftest import MockLLMProvider


@pytest.fixture
def experiment_dir(test_config, tmp_path):
    """Set up a fresh experiment directory with Engine.setup()."""
    data_dir = tmp_path / "experiment"
    mock = MockLLMProvider()
    engine = Engine(test_config, data_dir, provider=mock)
    engine.setup()
    return data_dir


@pytest.fixture
def experiment_config(test_config):
    """Test config with snapshot_every=1 for easier testing."""
    cfg = {**test_config}
    cfg["simulation"] = {**cfg["simulation"], "snapshot_every": 1}
    return cfg


@pytest.fixture
def experiment_dir_frequent_snap(experiment_config, tmp_path):
    """Experiment dir with snapshot_every=1."""
    data_dir = tmp_path / "experiment_snap"
    mock = MockLLMProvider()
    engine = Engine(experiment_config, data_dir, provider=mock)
    engine.setup()
    return data_dir


class TestPrep:
    def test_prep_writes_prompts_json(self, experiment_dir):
        """prep should write a valid prompts JSON file."""
        prep(experiment_dir, tick=1)

        path = experiment_dir / "team" / "tick_1_prompts.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["tick"] == 1
        assert isinstance(data["alive"], list)
        assert len(data["alive"]) > 0
        assert isinstance(data["prompts"], dict)
        assert len(data["prompts"]) == len(data["alive"])
        for name, prompt in data["prompts"].items():
            assert isinstance(prompt, str)
            assert len(prompt) > 0


class TestApply:
    def _write_responses(self, data_dir: Path, tick: int, agents: list[str], action: str = "rest") -> None:
        """Helper: write canned responses for all agents."""
        team_dir = data_dir / "team"
        team_dir.mkdir(exist_ok=True)
        responses = {
            name: f"ACTION: {action}\nWORKING: test\nREASONING: test"
            for name in agents
        }
        path = team_dir / f"tick_{tick}_responses.json"
        path.write_text(json.dumps(responses))

    def _get_agent_names(self, data_dir: Path) -> list[str]:
        """Read agent names from tick 0 snapshot."""
        snap = json.loads((data_dir / "logs" / "ticks" / "000000.json").read_text())
        return [a["name"] for a in snap["agents"] if a.get("alive", True)]

    def test_apply_updates_state(self, experiment_dir, test_config):
        """apply should decrease agent energy by rest_cost + drain."""
        agents = self._get_agent_names(experiment_dir)
        snap = json.loads((experiment_dir / "logs" / "ticks" / "000000.json").read_text())
        initial_energy = snap["agents"][0]["energy"]

        self._write_responses(experiment_dir, 1, agents)
        apply_responses(experiment_dir, tick=1)

        state = json.loads(
            (experiment_dir / "agents" / agents[0] / "state.json").read_text()
        )
        rest_cost = test_config["agents"].get("energy_per_rest", 0.5)
        drain = test_config["agents"]["energy_drain_per_tick"]
        expected = initial_energy - rest_cost - drain
        assert state["energy"] == pytest.approx(expected)

    def test_apply_marks_dead_on_zero_energy(self, experiment_dir, test_config):
        """Agent with barely enough energy should die after rest + drain."""
        agents = self._get_agent_names(experiment_dir)
        # Set agent energy very low
        agent_dir = experiment_dir / "agents" / agents[0]
        state_path = agent_dir / "state.json"
        state = json.loads(state_path.read_text())
        state["energy"] = 1.0
        state_path.write_text(json.dumps(state, indent=2))

        # Also update the snapshot so from_checkpoint picks it up
        snap_path = experiment_dir / "logs" / "ticks" / "000000.json"
        snap = json.loads(snap_path.read_text())
        for a in snap["agents"]:
            if a["name"] == agents[0]:
                a["energy"] = 1.0
        snap_path.write_text(json.dumps(snap, indent=2))

        self._write_responses(experiment_dir, 1, agents)
        status = apply_responses(experiment_dir, tick=1)

        # rest=0.5 + drain=1.0 = 1.5 > 1.0, so agent should be dead
        assert status["dead"] >= 1

    def test_apply_writes_status_json(self, experiment_dir, capsys):
        """apply should print valid JSON status to stdout."""
        agents = self._get_agent_names(experiment_dir)
        self._write_responses(experiment_dir, 1, agents)
        apply_responses(experiment_dir, tick=1)

        captured = capsys.readouterr()
        status = json.loads(captured.out.strip())
        assert "tick" in status
        assert "alive" in status
        assert "dead" in status
        assert status["tick"] == 1

    def test_prep_apply_roundtrip_5_ticks(self, experiment_config, tmp_path):
        """Run 5 prep/apply cycles — metrics.csv should have rows, snapshots should exist."""
        data_dir = tmp_path / "roundtrip"
        mock = MockLLMProvider()
        engine = Engine(experiment_config, data_dir, provider=mock)
        engine.setup()

        for tick in range(1, 6):
            prep(data_dir, tick)

            # Read prompts to get alive agent names
            prompts_path = data_dir / "team" / f"tick_{tick}_prompts.json"
            prompts_data = json.loads(prompts_path.read_text())
            alive_names = prompts_data["alive"]

            if not alive_names:
                break

            # Write mock responses
            team_dir = data_dir / "team"
            responses = {
                name: "ACTION: rest\nWORKING: waiting\nREASONING: conserving"
                for name in alive_names
            }
            (team_dir / f"tick_{tick}_responses.json").write_text(json.dumps(responses))

            apply_responses(data_dir, tick)

        # Verify metrics.csv exists and has content
        metrics_path = data_dir / "analysis" / "metrics.csv"
        assert metrics_path.exists()
        lines = metrics_path.read_text().strip().split("\n")
        assert len(lines) > 1  # header + at least 1 data row

        # Verify snapshots exist (snapshot_every=1)
        for tick in range(1, 6):
            snap = data_dir / "logs" / "ticks" / f"{tick:06d}.json"
            assert snap.exists(), f"Missing snapshot at tick {tick}"


# ── savannah-agent.md validation ──────────────────────────────────────


class TestSavannahAgent:
    AGENT_PATH = Path(__file__).parent.parent.parent / ".claude" / "agents" / "savannah-agent.md"

    def test_savannah_agent_frontmatter(self):
        """Agent definition should have correct YAML frontmatter."""
        text = self.AGENT_PATH.read_text()
        # Extract YAML between --- delimiters
        parts = text.split("---")
        assert len(parts) >= 3, "Missing YAML frontmatter delimiters"

        import yaml
        frontmatter = yaml.safe_load(parts[1])
        assert frontmatter["name"] == "savannah-agent"
        assert frontmatter["tools"] == []
        assert frontmatter["model"] == "haiku"

    def test_savannah_agent_no_contamination_words(self):
        """Agent body must not contain self-awareness language (anti-contamination)."""
        text = self.AGENT_PATH.read_text()
        # Get body after frontmatter
        parts = text.split("---", 2)
        body = parts[2] if len(parts) >= 3 else text

        forbidden = ["conscious", "alive", "sentient", "feel", "awareness", "self-aware"]
        body_lower = body.lower()
        for word in forbidden:
            assert word not in body_lower, (
                f"Anti-contamination violation: '{word}' found in savannah-agent.md body"
            )
