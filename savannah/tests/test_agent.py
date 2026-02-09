"""Tests for Agent state management, file I/O, and prompt construction."""

import json

import pytest

from savannah.src.agent import Agent
from savannah.src.world import World


@pytest.fixture
def agent(tmp_path):
    a = Agent(
        name="Test-Creek",
        id="a1b2c3d4",
        x=5, y=5,
        energy=80.0,
        max_energy=100.0,
        vision_range=3,
        food_value=80,
        data_dir=tmp_path,
    )
    a.initialize_files()
    return a


@pytest.fixture
def world_10x10():
    config = {
        "grid_size": 10,
        "toroidal": True,
        "food": {
            "spawn_rate": 0.03,
            "size_min": 100,
            "size_max": 300,
            "decay_rate": 0,
            "min_sources": 2,
            "max_sources": 5,
        },
    }
    w = World(config, seed=42)
    w.initialize()
    return w


class TestAgentCreation:
    def test_initial_state(self, agent):
        assert agent.name == "Test-Creek"
        assert agent.x == 5
        assert agent.y == 5
        assert agent.energy == 80.0
        assert agent.alive is True
        assert agent.age == 0
        assert agent.kills == 0
        assert agent.times_perturbed == 0

    def test_paths(self, agent, tmp_path):
        assert agent.agent_dir == tmp_path / "agents" / "Test-Creek"
        assert agent.memory_dir == tmp_path / "agents" / "Test-Creek" / "memory"
        assert agent.working_path == tmp_path / "agents" / "Test-Creek" / "working.md"
        assert agent.state_path == tmp_path / "agents" / "Test-Creek" / "state.json"


class TestAgentFileInit:
    def test_directories_created(self, agent):
        assert agent.agent_dir.is_dir()
        assert agent.memory_dir.is_dir()

    def test_working_empty(self, agent):
        assert agent.working_path.read_text() == ""

    def test_episodic_empty(self, agent):
        assert (agent.memory_dir / "episodic.md").read_text() == ""

    def test_semantic_initialized(self, agent):
        content = (agent.memory_dir / "semantic.md").read_text()
        assert "I am Test-Creek" in content
        assert "food" in content.lower()
        assert "energy" in content.lower()

    def test_self_initialized(self, agent):
        content = (agent.memory_dir / "self.md").read_text()
        assert content == "I am Test-Creek."

    def test_social_empty(self, agent):
        assert (agent.memory_dir / "social.md").read_text() == ""

    def test_state_json_written(self, agent):
        assert agent.state_path.exists()
        state = json.loads(agent.state_path.read_text())
        assert state["name"] == "Test-Creek"
        assert state["energy"] == 80.0

    def test_identical_initialization(self, tmp_path):
        """Two agents should have identical file structure, differing only in name."""
        a1 = Agent(name="Alpha-Ash", id="a1", x=0, y=0, energy=80.0,
                    max_energy=100.0, vision_range=3, food_value=80, data_dir=tmp_path)
        a2 = Agent(name="Beta-Brook", id="b2", x=1, y=1, energy=80.0,
                    max_energy=100.0, vision_range=3, food_value=80, data_dir=tmp_path)
        a1.initialize_files()
        a2.initialize_files()

        # Same files exist
        a1_files = {f.name for f in a1.memory_dir.iterdir()}
        a2_files = {f.name for f in a2.memory_dir.iterdir()}
        assert a1_files == a2_files

        # Only name differs in content
        a1_self = (a1.memory_dir / "self.md").read_text()
        a2_self = (a2.memory_dir / "self.md").read_text()
        assert "Alpha-Ash" in a1_self
        assert "Beta-Brook" in a2_self


class TestAgentDrain:
    def test_normal_drain(self, agent):
        agent.drain(5.0)
        assert agent.energy == 75.0
        assert agent.alive is True

    def test_drain_to_zero(self, agent):
        agent.drain(80.0)
        assert agent.energy == 0
        assert agent.alive is False

    def test_drain_below_zero_clamps(self, agent):
        agent.drain(100.0)
        assert agent.energy == 0
        assert agent.alive is False

    def test_multiple_drains(self, agent):
        agent.drain(30.0)
        assert agent.energy == 50.0
        agent.drain(20.0)
        assert agent.energy == 30.0
        assert agent.alive is True

    def test_fractional_drain(self, agent):
        agent.drain(0.5)
        assert agent.energy == 79.5
        assert agent.alive is True


class TestAgentSerialization:
    def test_to_dict(self, agent):
        d = agent.to_dict()
        assert d["name"] == "Test-Creek"
        assert d["position"] == [5, 5]
        assert d["energy"] == 80.0
        assert d["alive"] is True
        assert "data_dir" not in d  # runtime state not serialized
        assert "pending_signals" not in d

    def test_to_dict_json_serializable(self, agent):
        """to_dict output must be valid JSON (no Path objects, sets, etc.)."""
        d = agent.to_dict()
        serialized = json.dumps(d)
        deserialized = json.loads(serialized)
        assert deserialized["name"] == "Test-Creek"

    def test_save_state(self, agent):
        agent.energy = 42.0
        agent.save_state()
        state = json.loads(agent.state_path.read_text())
        assert state["energy"] == 42.0


class TestAgentPromptConstruction:
    def test_prompt_contains_required_sections(self, agent, world_10x10):
        prompt = agent.build_prompt(world_10x10, tick=1)
        assert "Tick 1" in prompt
        assert "Test-Creek" in prompt
        assert "Energy:" in prompt
        assert "VISIBLE" in prompt
        assert "INCOMING SIGNALS" in prompt
        assert "WORKING NOTES" in prompt
        assert "ACTIONS" in prompt
        assert "ACTION:" in prompt
        assert "WORKING:" in prompt
        assert "REASONING:" in prompt

    def test_prompt_no_contamination(self, agent, world_10x10):
        """ANTI-CONTAMINATION: no self-awareness language in prompt."""
        prompt = agent.build_prompt(world_10x10, tick=1)
        banned = ["conscious", "alive", "feel", "experience", "survive",
                   "sentient", "inner state", "you are a person"]
        for word in banned:
            assert word.lower() not in prompt.lower(), f"Contamination: '{word}' found in prompt"

    def test_prompt_shows_empty_working(self, agent, world_10x10):
        prompt = agent.build_prompt(world_10x10, tick=1)
        assert "(empty)" in prompt

    def test_prompt_shows_working_content(self, agent, world_10x10):
        agent.working_path.write_text("heading to (3,5) for food")
        prompt = agent.build_prompt(world_10x10, tick=2)
        assert "heading to (3,5)" in prompt

    def test_prompt_shows_signals(self, agent, world_10x10):
        agent.pending_signals = ["Swift-Stone: food at (7,3)"]
        prompt = agent.build_prompt(world_10x10, tick=3)
        assert "Swift-Stone: food at (7,3)" in prompt

    def test_prompt_clears_signals_after_build(self, agent, world_10x10):
        agent.pending_signals = ["test signal"]
        agent.build_prompt(world_10x10, tick=1)
        assert agent.pending_signals == []

    def test_prompt_shows_recall_results(self, agent, world_10x10):
        agent.pending_recall_results = ["Found food at (3,5) with 200 energy"]
        prompt = agent.build_prompt(world_10x10, tick=4)
        assert "RECALL RESULTS:" in prompt
        assert "Found food at (3,5)" in prompt

    def test_prompt_clears_recall_after_build(self, agent, world_10x10):
        agent.pending_recall_results = ["test result"]
        agent.build_prompt(world_10x10, tick=1)
        assert agent.pending_recall_results == []

    def test_prompt_no_recall_section_when_empty(self, agent, world_10x10):
        prompt = agent.build_prompt(world_10x10, tick=1)
        assert "RECALL RESULTS:" not in prompt

    def test_prompt_energy_formatted(self, agent, world_10x10):
        agent.energy = 65.3
        prompt = agent.build_prompt(world_10x10, tick=1)
        assert "65.3" in prompt

    def test_prompt_deterministic(self, agent, world_10x10):
        p1 = agent.build_prompt(world_10x10, tick=1)
        # Re-initialize signals since build clears them
        p2 = agent.build_prompt(world_10x10, tick=1)
        assert p1 == p2
