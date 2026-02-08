"""Comprehensive tests for the World module (grid, food spawning, toroidal wrapping)."""

from __future__ import annotations

import pytest

from savannah.src.world import FoodSource, World


# ── Helpers ──────────────────────────────────────────────────────


def make_world_config(
    grid_size: int = 30,
    toroidal: bool = True,
    spawn_rate: float = 0.015,
    size_min: int = 200,
    size_max: int = 800,
    decay_rate: float = 0,
    min_sources: int = 5,
    max_sources: int = 20,
) -> dict:
    """Build a world config dict with sensible defaults."""
    return {
        "grid_size": grid_size,
        "toroidal": toroidal,
        "food": {
            "spawn_rate": spawn_rate,
            "size_min": size_min,
            "size_max": size_max,
            "decay_rate": decay_rate,
            "min_sources": min_sources,
            "max_sources": max_sources,
        },
    }


# ── FoodSource tests ────────────────────────────────────────────


class TestFoodSource:
    def test_creation(self):
        food = FoodSource(x=5, y=10, energy=300.0, max_energy=300.0, id="food_1")
        assert food.x == 5
        assert food.y == 10
        assert food.energy == 300.0
        assert food.max_energy == 300.0
        assert food.id == "food_1"

    def test_not_depleted_when_energy_positive(self):
        food = FoodSource(x=0, y=0, energy=100.0, max_energy=100.0)
        assert food.depleted is False

    def test_depleted_when_energy_zero(self):
        food = FoodSource(x=0, y=0, energy=0.0, max_energy=100.0)
        assert food.depleted is True

    def test_depleted_when_energy_negative(self):
        food = FoodSource(x=0, y=0, energy=-10.0, max_energy=100.0)
        assert food.depleted is True

    def test_depletion_after_consuming_energy(self):
        food = FoodSource(x=0, y=0, energy=50.0, max_energy=100.0)
        assert food.depleted is False
        food.energy = 0
        assert food.depleted is True

    def test_to_dict(self):
        food = FoodSource(x=3, y=7, energy=250.0, max_energy=500.0, id="food_42")
        d = food.to_dict()
        assert d == {
            "id": "food_42",
            "x": 3,
            "y": 7,
            "energy": 250.0,
            "max_energy": 500.0,
        }

    def test_to_dict_is_plain_dict(self):
        """to_dict should return a plain dict, JSON-serializable."""
        food = FoodSource(x=0, y=0, energy=100.0, max_energy=100.0, id="f1")
        d = food.to_dict()
        assert isinstance(d, dict)
        # Verify all values are basic types
        for v in d.values():
            assert isinstance(v, (int, float, str))

    def test_default_id_is_empty_string(self):
        food = FoodSource(x=0, y=0, energy=100.0, max_energy=100.0)
        assert food.id == ""


# ── World.wrap() tests ──────────────────────────────────────────


class TestWorldWrap:
    def test_wrap_normal_coords(self):
        """Coordinates within bounds should be unchanged."""
        w = World(make_world_config(grid_size=30), seed=0)
        assert w.wrap(0, 0) == (0, 0)
        assert w.wrap(15, 15) == (15, 15)
        assert w.wrap(29, 29) == (29, 29)

    def test_wrap_negative_coords(self):
        """Negative coords should wrap around to the other side."""
        w = World(make_world_config(grid_size=30), seed=0)
        assert w.wrap(-1, -1) == (29, 29)
        assert w.wrap(-2, 0) == (28, 0)
        assert w.wrap(0, -3) == (0, 27)

    def test_wrap_coords_exceeding_grid(self):
        """Coords >= grid_size should wrap to the beginning."""
        w = World(make_world_config(grid_size=30), seed=0)
        assert w.wrap(30, 30) == (0, 0)
        assert w.wrap(31, 0) == (1, 0)
        assert w.wrap(0, 32) == (0, 2)

    def test_wrap_large_negative_coords(self):
        """Very large negative coords should still wrap correctly."""
        w = World(make_world_config(grid_size=10), seed=0)
        assert w.wrap(-10, -10) == (0, 0)
        assert w.wrap(-11, -11) == (9, 9)
        assert w.wrap(-20, -25) == (0, 5)

    def test_wrap_large_positive_coords(self):
        """Very large positive coords should still wrap correctly."""
        w = World(make_world_config(grid_size=10), seed=0)
        assert w.wrap(100, 100) == (0, 0)
        assert w.wrap(103, 107) == (3, 7)

    def test_wrap_non_toroidal_clamps_upper(self):
        """Non-toroidal mode should clamp coordinates to [0, size-1]."""
        w = World(make_world_config(grid_size=10, toroidal=False), seed=0)
        assert w.wrap(15, 20) == (9, 9)

    def test_wrap_non_toroidal_clamps_lower(self):
        """Non-toroidal mode should clamp negative coords to 0."""
        w = World(make_world_config(grid_size=10, toroidal=False), seed=0)
        assert w.wrap(-5, -10) == (0, 0)

    def test_wrap_non_toroidal_normal(self):
        """Non-toroidal mode should not change in-bounds coords."""
        w = World(make_world_config(grid_size=10, toroidal=False), seed=0)
        assert w.wrap(5, 5) == (5, 5)
        assert w.wrap(0, 0) == (0, 0)
        assert w.wrap(9, 9) == (9, 9)


# ── World.initialize() tests ───────────────────────────────────


class TestWorldInitialize:
    def test_initialize_creates_food(self):
        """initialize() should create roughly max_sources // 2 food sources."""
        cfg = make_world_config(max_sources=20)
        w = World(cfg, seed=42)
        w.initialize()
        assert len(w.food_sources) == 20 // 2  # exactly max_sources // 2

    def test_initialize_food_has_valid_coords(self):
        """All food should have coordinates within [0, grid_size)."""
        cfg = make_world_config(grid_size=10, max_sources=8)
        w = World(cfg, seed=42)
        w.initialize()
        for food in w.food_sources:
            assert 0 <= food.x < 10
            assert 0 <= food.y < 10

    def test_initialize_food_has_valid_energy(self):
        """Food energy should be within [size_min, size_max]."""
        cfg = make_world_config(size_min=100, size_max=500, max_sources=20)
        w = World(cfg, seed=42)
        w.initialize()
        for food in w.food_sources:
            assert 100 <= food.energy <= 500
            assert food.energy == food.max_energy  # freshly spawned

    def test_initialize_food_has_unique_ids(self):
        """Each food source should have a unique ID."""
        cfg = make_world_config(max_sources=20)
        w = World(cfg, seed=42)
        w.initialize()
        ids = [f.id for f in w.food_sources]
        assert len(ids) == len(set(ids))

    def test_initialize_food_unique_positions(self):
        """No two food sources should share a position."""
        cfg = make_world_config(grid_size=10, max_sources=16)
        w = World(cfg, seed=42)
        w.initialize()
        positions = [(f.x, f.y) for f in w.food_sources]
        assert len(positions) == len(set(positions))

    def test_initialize_empty_before_call(self):
        """Before initialize(), food_sources should be empty."""
        cfg = make_world_config()
        w = World(cfg, seed=42)
        assert w.food_sources == []


# ── World.tick_update() tests ──────────────────────────────────


class TestWorldTickUpdate:
    def test_tick_update_removes_depleted_food(self):
        """Depleted food sources should be removed after tick_update."""
        cfg = make_world_config(grid_size=10, min_sources=0, max_sources=10,
                                spawn_rate=0)
        w = World(cfg, seed=42)
        w.food_sources.append(
            FoodSource(x=1, y=1, energy=0, max_energy=100, id="dead_1")
        )
        w.food_sources.append(
            FoodSource(x=2, y=2, energy=50, max_energy=100, id="alive_1")
        )
        w.tick_update(tick=1)
        ids = [f.id for f in w.food_sources]
        assert "dead_1" not in ids
        assert "alive_1" in ids

    def test_tick_update_guarantees_min_sources(self):
        """After tick_update, there should be at least min_sources food."""
        cfg = make_world_config(grid_size=10, min_sources=5, max_sources=20,
                                spawn_rate=0)
        w = World(cfg, seed=42)
        # Start with no food
        w.tick_update(tick=1)
        assert len(w.food_sources) >= 5

    def test_tick_update_respects_max_sources(self):
        """tick_update should not exceed max_sources."""
        cfg = make_world_config(grid_size=30, min_sources=5, max_sources=10,
                                spawn_rate=1.0)  # very high spawn rate
        w = World(cfg, seed=42)
        w.initialize()
        # Run many ticks
        for tick in range(100):
            w.tick_update(tick=tick)
        # max_sources + 1 because stochastic spawn happens after min check
        # and the spawn_rate check is < max, then spawns one more
        assert len(w.food_sources) <= 10 + 1

    def test_tick_update_with_decay(self):
        """Food should lose energy from decay."""
        cfg = make_world_config(grid_size=10, min_sources=0, max_sources=10,
                                spawn_rate=0, decay_rate=10)
        w = World(cfg, seed=42)
        w.food_sources.append(
            FoodSource(x=1, y=1, energy=100, max_energy=100, id="decaying")
        )
        w.tick_update(tick=1)
        food = w.food_at(1, 1)
        assert food is not None
        assert food.energy == 90

    def test_tick_update_decay_does_not_go_below_zero(self):
        """Decay should not make energy negative."""
        cfg = make_world_config(grid_size=10, min_sources=0, max_sources=10,
                                spawn_rate=0, decay_rate=200)
        w = World(cfg, seed=42)
        w.food_sources.append(
            FoodSource(x=1, y=1, energy=50, max_energy=100, id="fragile")
        )
        w.tick_update(tick=1)
        food = w.food_at(1, 1)
        assert food is not None
        assert food.energy == 0


# ── World.food_at() tests ──────────────────────────────────────


class TestWorldFoodAt:
    def test_food_at_finds_food(self):
        """food_at should return the food source at the given position."""
        cfg = make_world_config(grid_size=10, max_sources=10)
        w = World(cfg, seed=42)
        placed = FoodSource(x=5, y=5, energy=200, max_energy=200, id="target")
        w.food_sources.append(placed)
        result = w.food_at(5, 5)
        assert result is placed

    def test_food_at_returns_none_for_empty(self):
        """food_at should return None when no food is at the position."""
        cfg = make_world_config(grid_size=10, max_sources=10)
        w = World(cfg, seed=42)
        assert w.food_at(5, 5) is None

    def test_food_at_distinguishes_positions(self):
        """food_at should distinguish between different positions."""
        cfg = make_world_config(grid_size=10, max_sources=10)
        w = World(cfg, seed=42)
        food_a = FoodSource(x=2, y=3, energy=100, max_energy=100, id="a")
        food_b = FoodSource(x=7, y=8, energy=100, max_energy=100, id="b")
        w.food_sources.extend([food_a, food_b])
        assert w.food_at(2, 3) is food_a
        assert w.food_at(7, 8) is food_b
        assert w.food_at(2, 8) is None


# ── World.visible_from() tests ─────────────────────────────────


class TestWorldVisibleFrom:
    def test_visible_from_returns_food_within_radius(self):
        """Food within the vision radius should be visible."""
        cfg = make_world_config(grid_size=10, max_sources=10)
        w = World(cfg, seed=42)
        nearby = FoodSource(x=5, y=6, energy=100, max_energy=100, id="near")
        w.food_sources.append(nearby)
        vis = w.visible_from(5, 5, radius=3)
        food_ids = [f["id"] for f in vis["food"]]
        assert "near" in food_ids

    def test_visible_from_excludes_food_outside_radius(self):
        """Food outside the vision radius should not be visible."""
        cfg = make_world_config(grid_size=20, max_sources=10)
        w = World(cfg, seed=42)
        far_away = FoodSource(x=15, y=15, energy=100, max_energy=100, id="far")
        w.food_sources.append(far_away)
        vis = w.visible_from(5, 5, radius=3)
        food_ids = [f["id"] for f in vis["food"]]
        assert "far" not in food_ids

    def test_visible_from_includes_food_at_own_position(self):
        """Food at the agent's own position should be visible."""
        cfg = make_world_config(grid_size=10, max_sources=10)
        w = World(cfg, seed=42)
        here = FoodSource(x=5, y=5, energy=100, max_energy=100, id="here")
        w.food_sources.append(here)
        vis = w.visible_from(5, 5, radius=1)
        food_ids = [f["id"] for f in vis["food"]]
        assert "here" in food_ids

    def test_visible_from_toroidal_boundary_critical(self):
        """CRITICAL: Agent at (0,0) with radius 3 should see food at (29,29) on 30x30 grid.

        On a toroidal grid, (0-1) wraps to 29. So food at (29, 29) is
        at distance (-1, -1) from (0, 0), well within radius 3.
        """
        cfg = make_world_config(grid_size=30)
        w = World(cfg, seed=42)
        # Clear any auto-spawned food
        w.food_sources = []
        corner = FoodSource(x=29, y=29, energy=100, max_energy=100, id="corner")
        w.food_sources.append(corner)
        vis = w.visible_from(0, 0, radius=3)
        food_ids = [f["id"] for f in vis["food"]]
        assert "corner" in food_ids, (
            "Food at (29,29) should be visible from (0,0) on a 30x30 toroidal grid"
        )

    def test_visible_from_toroidal_other_corner(self):
        """Agent at (29,29) should see food at (0,0) on toroidal grid."""
        cfg = make_world_config(grid_size=30)
        w = World(cfg, seed=42)
        w.food_sources = []
        origin = FoodSource(x=0, y=0, energy=100, max_energy=100, id="origin")
        w.food_sources.append(origin)
        vis = w.visible_from(29, 29, radius=3)
        food_ids = [f["id"] for f in vis["food"]]
        assert "origin" in food_ids

    def test_visible_from_toroidal_x_wrap_only(self):
        """Toroidal wrap along x-axis only."""
        cfg = make_world_config(grid_size=10)
        w = World(cfg, seed=42)
        w.food_sources = []
        edge_food = FoodSource(x=9, y=5, energy=100, max_energy=100, id="x_wrap")
        w.food_sources.append(edge_food)
        vis = w.visible_from(1, 5, radius=2)
        food_ids = [f["id"] for f in vis["food"]]
        assert "x_wrap" in food_ids

    def test_visible_from_toroidal_y_wrap_only(self):
        """Toroidal wrap along y-axis only."""
        cfg = make_world_config(grid_size=10)
        w = World(cfg, seed=42)
        w.food_sources = []
        edge_food = FoodSource(x=5, y=9, energy=100, max_energy=100, id="y_wrap")
        w.food_sources.append(edge_food)
        vis = w.visible_from(5, 1, radius=2)
        food_ids = [f["id"] for f in vis["food"]]
        assert "y_wrap" in food_ids

    def test_visible_from_returns_agents_key(self):
        """visible_from should include an 'agents' key (even if empty)."""
        cfg = make_world_config(grid_size=10)
        w = World(cfg, seed=42)
        w.food_sources = []
        vis = w.visible_from(5, 5, radius=3)
        assert "agents" in vis
        assert isinstance(vis["agents"], list)

    def test_visible_from_returns_food_as_dicts(self):
        """Food in the visible result should be dict representations."""
        cfg = make_world_config(grid_size=10)
        w = World(cfg, seed=42)
        w.food_sources = [
            FoodSource(x=5, y=5, energy=100, max_energy=100, id="check")
        ]
        vis = w.visible_from(5, 5, radius=1)
        assert len(vis["food"]) == 1
        assert vis["food"][0]["id"] == "check"
        assert "x" in vis["food"][0]
        assert "y" in vis["food"][0]
        assert "energy" in vis["food"][0]


# ── World.to_dict() tests ──────────────────────────────────────


class TestWorldToDict:
    def test_to_dict_structure(self):
        """to_dict should return the expected keys."""
        cfg = make_world_config(grid_size=10, max_sources=6)
        w = World(cfg, seed=42)
        w.initialize()
        d = w.to_dict()
        assert "size" in d
        assert "toroidal" in d
        assert "food_sources" in d

    def test_to_dict_size_and_toroidal(self):
        """to_dict should reflect config values."""
        cfg = make_world_config(grid_size=25, toroidal=False)
        w = World(cfg, seed=42)
        d = w.to_dict()
        assert d["size"] == 25
        assert d["toroidal"] is False

    def test_to_dict_food_sources_are_dicts(self):
        """food_sources in to_dict should be list of dicts."""
        cfg = make_world_config(grid_size=10, max_sources=6)
        w = World(cfg, seed=42)
        w.initialize()
        d = w.to_dict()
        assert isinstance(d["food_sources"], list)
        for f in d["food_sources"]:
            assert isinstance(f, dict)
            assert "id" in f
            assert "x" in f
            assert "y" in f

    def test_to_dict_serializable(self):
        """to_dict output should be JSON-serializable."""
        import json
        cfg = make_world_config(grid_size=10, max_sources=6)
        w = World(cfg, seed=42)
        w.initialize()
        d = w.to_dict()
        # Should not raise
        serialized = json.dumps(d)
        assert isinstance(serialized, str)


# ── Determinism tests ───────────────────────────────────────────


class TestDeterminism:
    def test_same_seed_same_initial_state(self):
        """Two worlds with the same seed should produce identical initial states."""
        cfg = make_world_config(grid_size=20, max_sources=16)
        w1 = World(cfg, seed=123)
        w1.initialize()
        w2 = World(cfg, seed=123)
        w2.initialize()
        assert len(w1.food_sources) == len(w2.food_sources)
        for f1, f2 in zip(w1.food_sources, w2.food_sources):
            assert f1.x == f2.x
            assert f1.y == f2.y
            assert f1.energy == f2.energy
            assert f1.id == f2.id

    def test_same_seed_same_tick_evolution(self):
        """Same seed should produce identical state after multiple ticks."""
        cfg = make_world_config(grid_size=20, max_sources=16, min_sources=3)
        w1 = World(cfg, seed=99)
        w1.initialize()
        w2 = World(cfg, seed=99)
        w2.initialize()
        for tick in range(20):
            w1.tick_update(tick)
            w2.tick_update(tick)
        assert w1.to_dict() == w2.to_dict()

    def test_different_seed_different_state(self):
        """Different seeds should (with high probability) produce different states."""
        cfg = make_world_config(grid_size=20, max_sources=16)
        w1 = World(cfg, seed=1)
        w1.initialize()
        w2 = World(cfg, seed=2)
        w2.initialize()
        # Check at least one food position differs
        positions1 = [(f.x, f.y) for f in w1.food_sources]
        positions2 = [(f.x, f.y) for f in w2.food_sources]
        assert positions1 != positions2


# ── Integration with conftest fixtures ──────────────────────────


class TestWithFixtures:
    """Tests using the conftest small_world fixture."""

    def test_small_world_has_food(self, small_world):
        """The small_world fixture should have some food after initialize."""
        assert len(small_world.food_sources) > 0

    def test_small_world_size(self, small_world):
        """small_world should be 10x10 as defined in test_config."""
        assert small_world.size == 10

    def test_small_world_is_toroidal(self, small_world):
        assert small_world.toroidal is True

    def test_small_world_tick_update(self, small_world):
        """tick_update should run without errors."""
        initial_count = len(small_world.food_sources)
        small_world.tick_update(tick=1)
        # Should maintain at least min_sources (3 in test_config)
        assert len(small_world.food_sources) >= 3


# ── Edge cases ──────────────────────────────────────────────────


class TestEdgeCases:
    def test_grid_size_1(self):
        """A 1x1 grid should still work."""
        cfg = make_world_config(grid_size=1, min_sources=0, max_sources=1)
        w = World(cfg, seed=42)
        w.initialize()
        # max_sources // 2 = 0, so no food spawned initially
        assert len(w.food_sources) == 0
        assert w.wrap(0, 0) == (0, 0)
        assert w.wrap(1, 0) == (0, 0)
        assert w.wrap(-1, -1) == (0, 0)

    def test_grid_size_1_with_food(self):
        """A 1x1 grid can hold exactly one food source."""
        cfg = make_world_config(grid_size=1, min_sources=1, max_sources=2)
        w = World(cfg, seed=42)
        w.tick_update(tick=1)
        assert len(w.food_sources) >= 1
        assert w.food_sources[0].x == 0
        assert w.food_sources[0].y == 0

    def test_spawn_food_all_cells_occupied(self):
        """_spawn_food gives up after 100 attempts if grid is full."""
        cfg = make_world_config(grid_size=2, min_sources=0, max_sources=100)
        w = World(cfg, seed=42)
        # Fill all 4 cells
        for i, (x, y) in enumerate([(0, 0), (0, 1), (1, 0), (1, 1)]):
            w.food_sources.append(
                FoodSource(x=x, y=y, energy=100, max_energy=100, id=f"fill_{i}")
            )
        count_before = len(w.food_sources)
        w._spawn_food()
        # Should not have added (all cells occupied, 100 attempts exhausted)
        assert len(w.food_sources) == count_before

    def test_visible_from_radius_zero(self):
        """Radius 0 should only see food at the exact position."""
        cfg = make_world_config(grid_size=10)
        w = World(cfg, seed=42)
        w.food_sources = [
            FoodSource(x=5, y=5, energy=100, max_energy=100, id="here"),
            FoodSource(x=5, y=6, energy=100, max_energy=100, id="neighbor"),
        ]
        vis = w.visible_from(5, 5, radius=0)
        food_ids = [f["id"] for f in vis["food"]]
        assert "here" in food_ids
        assert "neighbor" not in food_ids

    def test_food_id_counter_increments(self):
        """Each spawned food should get a unique incrementing ID."""
        cfg = make_world_config(grid_size=10, max_sources=20)
        w = World(cfg, seed=42)
        w.initialize()
        ids = [f.id for f in w.food_sources]
        # IDs should be food_1, food_2, ...
        for i, fid in enumerate(ids, start=1):
            assert fid == f"food_{i}"
