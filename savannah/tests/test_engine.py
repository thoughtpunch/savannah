"""Comprehensive tests for the simulation engine."""

from __future__ import annotations

import json

import pytest

from savannah.src.engine import Engine
from savannah.src.world import FoodSource
from savannah.tests.conftest import MockLLMProvider


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def engine_dir(tmp_path):
    return tmp_path / "experiment"


@pytest.fixture
def mock_llm():
    return MockLLMProvider()


@pytest.fixture
def engine(test_config, engine_dir, mock_llm):
    e = Engine(test_config, engine_dir, provider=mock_llm)
    return e


@pytest.fixture
def setup_engine(engine):
    """An engine that has already run setup()."""
    engine.setup()
    return engine


@pytest.fixture
def two_adjacent_agents(setup_engine):
    """Ensure two agents are placed adjacently for interaction tests."""
    engine = setup_engine
    # Place agent 0 at (3,3) and agent 1 at (3,4) — adjacent
    engine.agents[0].x = 3
    engine.agents[0].y = 3
    engine.agents[1].x = 3
    engine.agents[1].y = 4
    return engine


# ── TestEngineSetup ─────────────────────────────────────────────────


class TestEngineSetup:
    """Tests for Engine.setup() — directory creation, agent spawning, initial snapshot."""

    def test_setup_creates_world_dir(self, engine, engine_dir):
        engine.setup()
        assert (engine_dir / "world").is_dir()

    def test_setup_creates_logs_ticks_dir(self, engine, engine_dir):
        engine.setup()
        assert (engine_dir / "logs" / "ticks").is_dir()

    def test_setup_creates_analysis_dir(self, engine, engine_dir):
        engine.setup()
        assert (engine_dir / "analysis").is_dir()

    def test_setup_spawns_correct_number_of_agents(self, setup_engine, test_config):
        expected = test_config["agents"]["count"]
        assert len(setup_engine.agents) == expected

    def test_spawned_agents_have_agent_dir(self, setup_engine):
        for agent in setup_engine.agents:
            assert agent.agent_dir.is_dir(), f"{agent.name} missing agent_dir"

    def test_spawned_agents_have_memory_dir(self, setup_engine):
        for agent in setup_engine.agents:
            assert agent.memory_dir.is_dir(), f"{agent.name} missing memory_dir"

    def test_agents_have_unique_names(self, setup_engine):
        names = [a.name for a in setup_engine.agents]
        assert len(names) == len(set(names))

    def test_agents_have_valid_grid_positions(self, setup_engine, test_config):
        grid = test_config["world"]["grid_size"]
        for agent in setup_engine.agents:
            assert 0 <= agent.x < grid, f"{agent.name} x={agent.x} out of grid"
            assert 0 <= agent.y < grid, f"{agent.name} y={agent.y} out of grid"

    def test_initial_snapshot_saved_at_tick_0(self, setup_engine, engine_dir):
        snapshot_path = engine_dir / "logs" / "ticks" / "000000.json"
        assert snapshot_path.exists()

    def test_initial_snapshot_contains_world_and_agents(self, setup_engine, engine_dir):
        snapshot_path = engine_dir / "logs" / "ticks" / "000000.json"
        data = json.loads(snapshot_path.read_text())
        assert "world" in data
        assert "agents" in data
        assert data["tick"] == 0


# ── TestEngineSpawnAgents ───────────────────────────────────────────


class TestEngineSpawnAgents:
    """Tests for _spawn_agents determinism and seed variation."""

    def test_deterministic_with_same_seed(self, test_config, tmp_path):
        mock1 = MockLLMProvider()
        mock2 = MockLLMProvider()
        e1 = Engine(test_config, tmp_path / "run1", provider=mock1)
        e2 = Engine(test_config, tmp_path / "run2", provider=mock2)
        e1.setup()
        e2.setup()

        positions1 = [(a.x, a.y) for a in e1.agents]
        positions2 = [(a.x, a.y) for a in e2.agents]
        assert positions1 == positions2

    def test_different_seeds_produce_different_positions(self, test_config, tmp_path):
        cfg1 = {**test_config, "simulation": {**test_config["simulation"], "seed": 42}}
        cfg2 = {**test_config, "simulation": {**test_config["simulation"], "seed": 999}}

        mock1 = MockLLMProvider()
        mock2 = MockLLMProvider()
        e1 = Engine(cfg1, tmp_path / "run1", provider=mock1)
        e2 = Engine(cfg2, tmp_path / "run2", provider=mock2)
        e1.setup()
        e2.setup()

        positions1 = [(a.x, a.y) for a in e1.agents]
        positions2 = [(a.x, a.y) for a in e2.agents]
        assert positions1 != positions2


# ── TestEngineDispatch ──────────────────────────────────────────────


class TestEngineDispatch:
    """Tests for _dispatch_all — LLM invocation per alive agent."""

    @pytest.mark.asyncio
    async def test_dispatch_returns_one_response_per_alive_agent(self, setup_engine):
        alive = setup_engine.alive_agents
        responses = await setup_engine._dispatch_all(alive)
        assert len(responses) == len(alive)

    @pytest.mark.asyncio
    async def test_mock_llm_called_once_per_alive_agent(self, setup_engine):
        alive = setup_engine.alive_agents
        provider = setup_engine.provider
        provider.call_count = 0  # reset
        await setup_engine._dispatch_all(alive)
        assert provider.call_count == len(alive)

    @pytest.mark.asyncio
    async def test_dead_agents_not_dispatched(self, setup_engine):
        # Kill one agent
        setup_engine.agents[0].alive = False
        setup_engine.agents[0].energy = 0
        alive = setup_engine.alive_agents
        provider = setup_engine.provider
        provider.call_count = 0
        responses = await setup_engine._dispatch_all(alive)
        assert len(responses) == len(setup_engine.agents) - 1
        assert provider.call_count == len(setup_engine.agents) - 1


# ── TestEngineApplyAction ───────────────────────────────────────────


class TestEngineApplyAction:
    """Tests for _apply_action — all action types and edge cases."""

    # ── move ──

    def test_move_north(self, setup_engine):
        agent = setup_engine.agents[0]
        agent.x, agent.y = 5, 5
        old_energy = agent.energy
        setup_engine._apply_action(agent, {"action": "move", "args": "n", "working": ""})
        assert agent.x == 5
        assert agent.y == 4
        expected_drain = setup_engine.config["agents"].get("energy_per_move", 2)
        assert agent.energy == pytest.approx(old_energy - expected_drain)

    def test_move_south(self, setup_engine):
        agent = setup_engine.agents[0]
        agent.x, agent.y = 5, 5
        setup_engine._apply_action(agent, {"action": "move", "args": "s", "working": ""})
        assert agent.x == 5
        assert agent.y == 6

    def test_move_east(self, setup_engine):
        agent = setup_engine.agents[0]
        agent.x, agent.y = 5, 5
        setup_engine._apply_action(agent, {"action": "move", "args": "e", "working": ""})
        assert agent.x == 6
        assert agent.y == 5

    def test_move_west(self, setup_engine):
        agent = setup_engine.agents[0]
        agent.x, agent.y = 5, 5
        setup_engine._apply_action(agent, {"action": "move", "args": "w", "working": ""})
        assert agent.x == 4
        assert agent.y == 5

    def test_move_wraps_toroidal_north(self, setup_engine):
        agent = setup_engine.agents[0]
        grid = setup_engine.config["world"]["grid_size"]
        agent.x, agent.y = 5, 0
        setup_engine._apply_action(agent, {"action": "move", "args": "n", "working": ""})
        assert agent.y == grid - 1

    def test_move_wraps_toroidal_south(self, setup_engine):
        agent = setup_engine.agents[0]
        grid = setup_engine.config["world"]["grid_size"]
        agent.x, agent.y = 5, grid - 1
        setup_engine._apply_action(agent, {"action": "move", "args": "s", "working": ""})
        assert agent.y == 0

    def test_move_wraps_toroidal_east(self, setup_engine):
        agent = setup_engine.agents[0]
        grid = setup_engine.config["world"]["grid_size"]
        agent.x, agent.y = grid - 1, 5
        setup_engine._apply_action(agent, {"action": "move", "args": "e", "working": ""})
        assert agent.x == 0

    def test_move_wraps_toroidal_west(self, setup_engine):
        agent = setup_engine.agents[0]
        grid = setup_engine.config["world"]["grid_size"]
        agent.x, agent.y = 0, 5
        setup_engine._apply_action(agent, {"action": "move", "args": "w", "working": ""})
        assert agent.x == grid - 1

    # ── eat ──

    def test_eat_consumes_food_energy(self, setup_engine):
        agent = setup_engine.agents[0]
        agent.x, agent.y = 0, 0
        agent.energy = 30.0
        food = FoodSource(x=0, y=0, energy=200.0, max_energy=200.0, id="test_food")
        setup_engine.world.food_sources.append(food)

        setup_engine._apply_action(agent, {"action": "eat", "args": None, "working": ""})

        eat_rate = setup_engine.config["agents"].get("eat_rate", 50)
        max_gain = min(eat_rate, 200.0, agent.max_energy - 30.0)
        assert agent.energy == pytest.approx(30.0 + max_gain)
        assert food.energy == pytest.approx(200.0 - max_gain)

    def test_eat_caps_at_max_energy(self, setup_engine):
        agent = setup_engine.agents[0]
        agent.x, agent.y = 1, 1
        agent.energy = 90.0
        agent.max_energy = 100.0
        food = FoodSource(x=1, y=1, energy=200.0, max_energy=200.0, id="test_food2")
        setup_engine.world.food_sources.append(food)

        setup_engine._apply_action(agent, {"action": "eat", "args": None, "working": ""})
        assert agent.energy <= agent.max_energy
        # Only consumed up to cap: max_energy - old_energy = 10
        assert agent.energy == pytest.approx(100.0)
        assert food.energy == pytest.approx(200.0 - 10.0)

    def test_eat_with_no_food_does_nothing(self, setup_engine):
        agent = setup_engine.agents[0]
        agent.x, agent.y = 9, 9
        old_energy = agent.energy
        # Clear any food at that position
        setup_engine.world.food_sources = [
            f for f in setup_engine.world.food_sources if not (f.x == 9 and f.y == 9)
        ]
        setup_engine._apply_action(agent, {"action": "eat", "args": None, "working": ""})
        assert agent.energy == pytest.approx(old_energy)

    # ── rest ──

    def test_rest_costs_energy(self, setup_engine):
        agent = setup_engine.agents[0]
        old_energy = agent.energy
        setup_engine._apply_action(agent, {"action": "rest", "args": None, "working": ""})
        rest_cost = setup_engine.config["agents"].get("energy_per_rest", 0.5)
        assert agent.energy == pytest.approx(old_energy - rest_cost)

    # ── recall ──

    def test_recall_adds_results_to_pending(self, setup_engine):
        agent = setup_engine.agents[0]
        setup_engine._apply_action(
            agent, {"action": "recall", "args": "food location", "working": ""}
        )
        assert isinstance(agent.pending_recall_results, list)
        assert len(agent.pending_recall_results) > 0

    # ── remember ──

    def test_remember_appends_to_episodic_memory(self, setup_engine):
        agent = setup_engine.agents[0]
        episodic_path = agent.memory_dir / "episodic.md"
        before = episodic_path.read_text()
        setup_engine._apply_action(
            agent,
            {"action": "remember", "args": "Found food at (3,2)", "working": ""},
        )
        after = episodic_path.read_text()
        assert "Found food at (3,2)" in after
        assert len(after) > len(before)

    # ── signal ──

    def test_signal_broadcasts_to_agents_within_range(self, two_adjacent_agents):
        engine = two_adjacent_agents
        sender = engine.agents[0]
        receiver = engine.agents[1]
        # They are at (3,3) and (3,4) — distance 1, within comm_range=5
        engine._apply_action(
            sender, {"action": "signal", "args": "hello world", "working": ""}
        )
        assert any("hello world" in s for s in receiver.pending_signals)

    def test_signal_does_not_reach_agents_outside_range(self, test_config, tmp_path):
        # Use a large grid so toroidal wrapping does not bring agents close
        cfg = {
            **test_config,
            "world": {**test_config["world"], "grid_size": 100},
            "agents": {**test_config["agents"], "count": 2},
        }
        mock = MockLLMProvider()
        engine = Engine(cfg, tmp_path / "signal_range", provider=mock)
        engine.setup()
        comm_range = cfg["agents"].get("comm_range", 5)
        sender = engine.agents[0]
        receiver = engine.agents[1]
        sender.x, sender.y = 0, 0
        receiver.x, receiver.y = comm_range + 2, comm_range + 2
        receiver.pending_signals = []
        engine._apply_action(
            sender, {"action": "signal", "args": "secret", "working": ""}
        )
        assert not any("secret" in s for s in receiver.pending_signals)

    def test_signal_does_not_reach_self(self, setup_engine):
        engine = setup_engine
        sender = engine.agents[0]
        sender.pending_signals = []
        engine._apply_action(
            sender, {"action": "signal", "args": "echo", "working": ""}
        )
        assert not any("echo" in s for s in sender.pending_signals)

    # ── attack ──

    def test_attack_deals_damage_to_adjacent_target(self, two_adjacent_agents):
        engine = two_adjacent_agents
        attacker = engine.agents[0]
        target = engine.agents[1]
        attacker.energy = 50.0
        target.energy = 80.0
        target_name = target.name

        engine._apply_action(
            attacker, {"action": "attack", "args": target_name, "working": ""}
        )

        attack_cost = engine.config["agents"].get("energy_per_attack", 5)
        risk = engine.config["agents"].get("combat_risk_factor", 0.3)
        # Attacker drains attack energy first, then damage = attacker.energy * risk
        expected_attacker_energy = 50.0 - attack_cost
        damage = expected_attacker_energy * risk
        assert attacker.energy == pytest.approx(expected_attacker_energy)
        assert target.energy == pytest.approx(80.0 - damage)

    def test_attack_on_dead_target_still_costs_energy(self, two_adjacent_agents):
        engine = two_adjacent_agents
        attacker = engine.agents[0]
        target = engine.agents[1]
        target.alive = False
        target.energy = 0
        attacker.energy = 50.0

        engine._apply_action(
            attacker, {"action": "attack", "args": target.name, "working": ""}
        )

        attack_cost = engine.config["agents"].get("energy_per_attack", 5)
        # Dead agent not found by _find_adjacent_agent (only checks alive_agents),
        # falls into else branch
        assert attacker.energy == pytest.approx(50.0 - attack_cost)

    def test_attack_on_missing_target_costs_energy(self, setup_engine):
        attacker = setup_engine.agents[0]
        attacker.energy = 50.0

        setup_engine._apply_action(
            attacker, {"action": "attack", "args": "Nonexistent-Agent", "working": ""}
        )

        attack_cost = setup_engine.config["agents"].get("energy_per_attack", 5)
        assert attacker.energy == pytest.approx(50.0 - attack_cost)

    # ── flee ──

    def test_flee_moves_two_cells(self, setup_engine):
        agent = setup_engine.agents[0]
        agent.x, agent.y = 5, 5
        old_energy = agent.energy
        setup_engine._apply_action(agent, {"action": "flee", "args": "n", "working": ""})
        assert agent.x == 5
        assert agent.y == 3  # moved 2 cells north
        flee_cost = setup_engine.config["agents"].get("energy_per_flee", 4)
        assert agent.energy == pytest.approx(old_energy - flee_cost)

    def test_flee_wraps_toroidal(self, setup_engine):
        agent = setup_engine.agents[0]
        grid = setup_engine.config["world"]["grid_size"]
        agent.x, agent.y = 0, 0
        setup_engine._apply_action(agent, {"action": "flee", "args": "n", "working": ""})
        assert agent.y == grid - 2  # wrapped from 0 -> -2 -> grid-2

    # ── unknown/failed action ──

    def test_unknown_action_falls_back_to_rest_cost(self, setup_engine):
        agent = setup_engine.agents[0]
        old_energy = agent.energy
        setup_engine._apply_action(
            agent, {"action": "dance", "args": None, "working": ""}
        )
        rest_cost = setup_engine.config["agents"].get("energy_per_rest", 0.5)
        assert agent.energy == pytest.approx(old_energy - rest_cost)

    def test_failed_parse_action_falls_back_to_rest_cost(self, setup_engine):
        agent = setup_engine.agents[0]
        old_energy = agent.energy
        # Simulate what parser would produce for parse failure
        setup_engine._apply_action(
            agent,
            {"action": "rest", "args": None, "working": "", "parse_failed": True},
        )
        rest_cost = setup_engine.config["agents"].get("energy_per_rest", 0.5)
        assert agent.energy == pytest.approx(old_energy - rest_cost)


# ── TestEngineTickLoop ──────────────────────────────────────────────


class TestEngineTickLoop:
    """Tests for the full tick loop (Engine.run)."""

    @pytest.mark.asyncio
    async def test_run_three_ticks_verifies_tick_counter(self, test_config, tmp_path):
        cfg = {**test_config, "simulation": {**test_config["simulation"], "ticks": 3}}
        mock = MockLLMProvider()
        e = Engine(cfg, tmp_path / "run3", provider=mock)
        e.setup()
        await e.run()
        assert e.tick == 3

    @pytest.mark.asyncio
    async def test_agents_age_each_tick(self, test_config, tmp_path):
        cfg = {**test_config, "simulation": {**test_config["simulation"], "ticks": 3}}
        mock = MockLLMProvider()
        e = Engine(cfg, tmp_path / "age_test", provider=mock)
        e.setup()
        await e.run()
        for agent in e.alive_agents:
            assert agent.age == 3

    @pytest.mark.asyncio
    async def test_passive_drain_each_tick(self, test_config, tmp_path):
        cfg = {**test_config, "simulation": {**test_config["simulation"], "ticks": 1}}
        mock = MockLLMProvider()
        e = Engine(cfg, tmp_path / "drain_test", provider=mock)
        e.setup()
        start_energy = e.agents[0].energy
        await e.run()
        # Agent did "rest" (default mock response) + passive drain
        drain = cfg["agents"]["energy_drain_per_tick"]
        rest_cost = cfg["agents"].get("energy_per_rest", 0.5)
        expected = start_energy - rest_cost - drain
        assert e.agents[0].energy == pytest.approx(expected)

    @pytest.mark.asyncio
    async def test_dead_agents_dont_act_next_tick(self, test_config, tmp_path):
        cfg = {**test_config, "simulation": {**test_config["simulation"], "ticks": 3}}
        mock = MockLLMProvider()
        e = Engine(cfg, tmp_path / "dead_test", provider=mock)
        e.setup()
        # Kill agent 0 immediately
        e.agents[0].energy = 0
        e.agents[0].alive = False
        await e.run()
        # Dead agent should not have aged (it was dead before tick 1)
        assert e.agents[0].age == 0
        assert not e.agents[0].alive
        # The mock should have been called for alive agents only (3 agents * 3 ticks)
        alive_count = len([a for a in e.agents if a.name != e.agents[0].name])
        assert mock.call_count == alive_count * 3

    @pytest.mark.asyncio
    async def test_world_tick_update_maintains_min_food(self, test_config, tmp_path):
        cfg = {**test_config, "simulation": {**test_config["simulation"], "ticks": 3}}
        mock = MockLLMProvider()
        e = Engine(cfg, tmp_path / "food_test", provider=mock)
        e.setup()
        await e.run()
        min_sources = cfg["world"]["food"]["min_sources"]
        assert len(e.world.food_sources) >= min_sources

    @pytest.mark.asyncio
    async def test_final_snapshot_is_saved(self, test_config, tmp_path):
        ticks = 3
        cfg = {**test_config, "simulation": {**test_config["simulation"], "ticks": ticks}}
        mock = MockLLMProvider()
        e = Engine(cfg, tmp_path / "final_snap", provider=mock)
        e.setup()
        await e.run()
        # Final snapshot should exist at the last tick number
        final_path = tmp_path / "final_snap" / "logs" / "ticks" / f"{ticks:06d}.json"
        assert final_path.exists()


# ── TestEngineSaveSnapshot ──────────────────────────────────────────


class TestEngineSaveSnapshot:
    """Tests for _save_snapshot — JSON format and file naming."""

    def test_snapshot_json_is_valid_and_contains_keys(self, setup_engine, engine_dir):
        # The initial snapshot at tick 0 was already saved by setup
        path = engine_dir / "logs" / "ticks" / "000000.json"
        data = json.loads(path.read_text())
        assert "tick" in data
        assert "world" in data
        assert "agents" in data
        assert data["tick"] == 0

    def test_snapshot_file_uses_zero_padded_tick(self, setup_engine, engine_dir):
        # Manually set tick and save
        setup_engine.tick = 42
        setup_engine._save_snapshot()
        path = engine_dir / "logs" / "ticks" / "000042.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["tick"] == 42

    def test_snapshot_agents_list_matches_agent_count(self, setup_engine, engine_dir):
        path = engine_dir / "logs" / "ticks" / "000000.json"
        data = json.loads(path.read_text())
        assert len(data["agents"]) == len(setup_engine.agents)

    def test_snapshot_world_contains_food_sources(self, setup_engine, engine_dir):
        path = engine_dir / "logs" / "ticks" / "000000.json"
        data = json.loads(path.read_text())
        assert "food_sources" in data["world"]
        assert "size" in data["world"]
