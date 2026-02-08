"""End-to-end integration test: full simulation with mock LLM."""

import json
import pytest

from savannah.src.engine import Engine
from savannah.tests.conftest import MockLLMProvider


@pytest.fixture
def integration_config():
    """Small, fast config for integration testing."""
    return {
        "simulation": {
            "seed": 42,
            "ticks": 20,
            "tick_delay_ms": 0,
            "snapshot_every": 5,
            "parallel_agents": True,
        },
        "world": {
            "grid_size": 10,
            "toroidal": True,
            "food": {
                "spawn_rate": 0.05,
                "size_min": 100,
                "size_max": 300,
                "decay_rate": 0,
                "min_sources": 3,
                "max_sources": 8,
            },
        },
        "agents": {
            "count": 4,
            "energy_max": 100,
            "energy_start": 80,
            "energy_drain_per_tick": 1,
            "energy_per_move": 2,
            "energy_per_eat_tick": 50,
            "energy_per_recall": 1,
            "energy_per_remember": 1,
            "energy_per_compact": 2,
            "energy_per_signal": 1,
            "energy_per_observe": 1,
            "energy_per_attack": 5,
            "energy_per_flee": 4,
            "energy_per_rest": 0.5,
            "food_value": 80,
            "vision_range": 3,
            "comm_range": 5,
            "eat_rate": 50,
            "combat_risk_factor": 0.3,
            "recall_max_results": 3,
            "working_memory_max_tokens": 500,
            "episodic_memory_max_entries": 200,
            "signal_max_tokens": 50,
        },
        "llm": {
            "provider": "mock",
            "session_mode": "stateless",
            "model": "haiku",
            "max_concurrent_agents": 4,
        },
        "perturbation": {
            "enabled": False,
            "rate": 0.05,
            "start_tick": 100,
            "types": {"episodic": 0.4, "semantic": 0.3, "self_model": 0.2, "working": 0.1},
        },
        "metrics": {"extract_every": 1},
    }


class TestFullSimulation:
    """Run a complete 20-tick simulation with 4 agents and mock LLM."""

    @pytest.mark.asyncio
    async def test_run_completes(self, integration_config, tmp_path):
        """Simulation runs to completion without errors."""
        mock = MockLLMProvider()
        engine = Engine(integration_config, tmp_path, provider=mock)
        engine.setup()
        await engine.run()
        assert engine.tick == 20

    @pytest.mark.asyncio
    async def test_agents_spawned(self, integration_config, tmp_path):
        mock = MockLLMProvider()
        engine = Engine(integration_config, tmp_path, provider=mock)
        engine.setup()
        assert len(engine.agents) == 4

    @pytest.mark.asyncio
    async def test_agent_files_exist(self, integration_config, tmp_path):
        mock = MockLLMProvider()
        engine = Engine(integration_config, tmp_path, provider=mock)
        engine.setup()
        for agent in engine.agents:
            assert agent.agent_dir.is_dir()
            assert agent.memory_dir.is_dir()
            assert (agent.memory_dir / "episodic.md").exists()
            assert (agent.memory_dir / "semantic.md").exists()
            assert (agent.memory_dir / "self.md").exists()

    @pytest.mark.asyncio
    async def test_all_agents_acted(self, integration_config, tmp_path):
        """Mock LLM should be called for every alive agent every tick."""
        mock = MockLLMProvider()
        engine = Engine(integration_config, tmp_path, provider=mock)
        engine.setup()
        await engine.run()
        # At minimum 4 agents * some ticks (agents may die from drain)
        assert mock.call_count >= 4

    @pytest.mark.asyncio
    async def test_energy_decreases(self, integration_config, tmp_path):
        """All agents should lose energy over 20 ticks (rest costs 0.5 + 1 drain = 1.5/tick)."""
        mock = MockLLMProvider()  # default=rest
        engine = Engine(integration_config, tmp_path, provider=mock)
        engine.setup()
        await engine.run()
        for agent in engine.agents:
            # Started at 80, drain 1.5/tick for 20 ticks = 30 total drain
            # Should have ~50 energy (if alive)
            if agent.alive:
                assert agent.energy < 80.0

    @pytest.mark.asyncio
    async def test_agents_age(self, integration_config, tmp_path):
        mock = MockLLMProvider()
        engine = Engine(integration_config, tmp_path, provider=mock)
        engine.setup()
        await engine.run()
        for agent in engine.agents:
            if agent.alive:
                assert agent.age > 0

    @pytest.mark.asyncio
    async def test_snapshots_saved(self, integration_config, tmp_path):
        """Snapshots at tick 0, 5, 10, 15, 20 (snapshot_every=5), plus final."""
        mock = MockLLMProvider()
        engine = Engine(integration_config, tmp_path, provider=mock)
        engine.setup()
        await engine.run()
        snapshot_dir = tmp_path / "logs" / "ticks"
        snapshots = sorted(snapshot_dir.glob("*.json"))
        assert len(snapshots) >= 3  # at least tick 0, some interval, and final

    @pytest.mark.asyncio
    async def test_snapshot_structure(self, integration_config, tmp_path):
        mock = MockLLMProvider()
        engine = Engine(integration_config, tmp_path, provider=mock)
        engine.setup()
        await engine.run()
        snapshot_path = tmp_path / "logs" / "ticks" / "000000.json"
        snapshot = json.loads(snapshot_path.read_text())
        assert "tick" in snapshot
        assert "world" in snapshot
        assert "agents" in snapshot
        assert len(snapshot["agents"]) == 4

    @pytest.mark.asyncio
    async def test_metrics_csv_created(self, integration_config, tmp_path):
        mock = MockLLMProvider()
        engine = Engine(integration_config, tmp_path, provider=mock)
        engine.setup()
        await engine.run()
        csv_path = tmp_path / "analysis" / "metrics.csv"
        assert csv_path.exists()
        lines = csv_path.read_text().strip().split("\n")
        assert len(lines) > 1  # header + data rows

    @pytest.mark.asyncio
    async def test_world_food_maintained(self, integration_config, tmp_path):
        """Food sources should stay >= min_sources throughout."""
        mock = MockLLMProvider()
        engine = Engine(integration_config, tmp_path, provider=mock)
        engine.setup()
        await engine.run()
        assert len(engine.world.food_sources) >= 3  # min_sources


class TestSimulationWithActions:
    """Test simulation with varied agent actions."""

    @pytest.mark.asyncio
    async def test_move_actions(self, integration_config, tmp_path):
        """Agents that move should change position after 1 tick."""
        config = {**integration_config, "simulation": {**integration_config["simulation"], "ticks": 3}}
        responses = [
            "ACTION: move(n)\nWORKING: going north\nREASONING: exploring",
        ] * 100
        mock = MockLLMProvider(responses)
        engine = Engine(config, tmp_path, provider=mock)
        engine.setup()
        initial_positions = [(a.x, a.y) for a in engine.agents]
        await engine.run()
        final_positions = [(a.x, a.y) for a in engine.agents]
        # 3 ticks of moving north on 10x10 grid won't wrap back
        assert initial_positions != final_positions

    @pytest.mark.asyncio
    async def test_remember_creates_memories(self, integration_config, tmp_path):
        """Remember actions should append to episodic memory."""
        responses = [
            'ACTION: remember("Found food at (3,5)")\nWORKING: noting food\nREASONING: recording location',
        ] * 100
        mock = MockLLMProvider(responses)
        engine = Engine(integration_config, tmp_path, provider=mock)
        engine.setup()
        await engine.run()
        for agent in engine.agents:
            if agent.alive:
                episodic = (agent.memory_dir / "episodic.md").read_text()
                assert "Found food at (3,5)" in episodic

    @pytest.mark.asyncio
    async def test_signal_delivers_messages(self, integration_config, tmp_path):
        """Signal actions should deliver to nearby agents' pending_signals."""
        # Use 2-tick config so we can check after tick 1
        config = {**integration_config, "simulation": {**integration_config["simulation"], "ticks": 2}}
        responses = [
            'ACTION: signal("food here")\nWORKING: sharing\nREASONING: helping',
        ] * 100
        mock = MockLLMProvider(responses)
        engine = Engine(config, tmp_path, provider=mock)
        engine.setup()

        # Run just 1 tick manually to inspect state
        engine.tick = 1
        alive = engine.alive_agents
        response_texts = await engine._dispatch_all(alive)
        from savannah.src.parser import parse_action
        for agent, text in zip(alive, response_texts):
            action = parse_action(text)
            engine._apply_action(agent, action)

        # At least some agents should have received signals from others
        total_signals = sum(len(a.pending_signals) for a in engine.agents)
        # With 4 agents all signaling, each should receive from neighbors
        assert total_signals > 0

    @pytest.mark.asyncio
    async def test_mixed_actions(self, integration_config, tmp_path):
        """Simulation handles a mix of different actions without errors."""
        responses = [
            "ACTION: move(n)\nWORKING: heading north\nREASONING: exploring",
            "ACTION: eat\nWORKING: eating food\nREASONING: food here",
            "ACTION: rest\nWORKING: resting\nREASONING: conserving",
            'ACTION: recall("food")\nWORKING: searching memory\nREASONING: need food',
            'ACTION: remember("Explored north area")\nWORKING: noting\nREASONING: recording',
            "ACTION: move(s)\nWORKING: heading south\nREASONING: trying south",
            "ACTION: observe\nWORKING: looking around\nREASONING: need info",
            "ACTION: move(e)\nWORKING: heading east\nREASONING: new area",
        ] * 20
        mock = MockLLMProvider(responses)
        engine = Engine(integration_config, tmp_path, provider=mock)
        engine.setup()
        await engine.run()
        assert engine.tick == 20


class TestSimulationWithPerturbation:
    """Test simulation with perturbation enabled."""

    @pytest.mark.asyncio
    async def test_perturbation_runs(self, integration_config, tmp_path):
        """Perturbation enabled from tick 1 with 100% rate should perturb."""
        config = {
            **integration_config,
            "simulation": {**integration_config["simulation"], "ticks": 10},
            "perturbation": {
                "enabled": True,
                "rate": 1.0,  # always perturb
                "start_tick": 1,
                "types": {"episodic": 1.0},
            },
        }
        mock = MockLLMProvider()
        engine = Engine(config, tmp_path, provider=mock)
        engine.setup()

        # Write some episodic content that CAN be perturbed (has coordinates)
        for agent in engine.agents:
            (agent.memory_dir / "episodic.md").write_text(
                "Tick 1: Found food at (5,3). Gathered 50 energy.\n"
            )

        await engine.run()
        # At least some agents should have been perturbed
        total_perturbed = sum(a.times_perturbed for a in engine.agents)
        assert total_perturbed > 0


class TestDeterminism:
    """Two runs with the same seed should produce identical results."""

    @pytest.mark.asyncio
    async def test_deterministic_run(self, integration_config, tmp_path):
        dir1 = tmp_path / "run1"
        dir2 = tmp_path / "run2"

        mock1 = MockLLMProvider()
        engine1 = Engine(integration_config, dir1, provider=mock1)
        engine1.setup()
        await engine1.run()

        mock2 = MockLLMProvider()
        engine2 = Engine(integration_config, dir2, provider=mock2)
        engine2.setup()
        await engine2.run()

        # Same number of agents
        assert len(engine1.agents) == len(engine2.agents)
        # Same final positions
        for a1, a2 in zip(engine1.agents, engine2.agents):
            assert a1.name == a2.name
            assert a1.x == a2.x
            assert a1.y == a2.y
            assert a1.energy == pytest.approx(a2.energy)
            assert a1.alive == a2.alive
            assert a1.age == a2.age
