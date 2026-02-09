"""Grid world — food spawning, cell state, toroidal wrapping."""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class FoodSource:
    """A stationary food source on the grid."""
    x: int
    y: int
    energy: float          # current energy remaining
    max_energy: float      # original energy when spawned
    id: str = ""

    @property
    def depleted(self) -> bool:
        return self.energy <= 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "energy": self.energy,
            "max_energy": self.max_energy,
        }


class World:
    """2D toroidal grid with food sources."""

    def __init__(self, config: dict, seed: int = 42):
        self.size = config["grid_size"]
        self.toroidal = config.get("toroidal", True)
        self.food_config = config["food"]
        self.rng = random.Random(seed)
        self.food_sources: list[FoodSource] = []
        self._food_id_counter = 0

    def initialize(self) -> None:
        """Spawn initial food sources."""
        # Initial burst: fill to ~half of max_sources
        target = self.food_config["max_sources"] // 2
        for _ in range(target):
            self._spawn_food()

    def tick_update(self, tick: int) -> None:
        """Per-tick world updates: spawn food, apply decay, remove depleted."""
        # Remove depleted
        self.food_sources = [f for f in self.food_sources if not f.depleted]

        min_sources = self.food_config.get("min_sources", 5)
        max_sources = self.food_config["max_sources"]

        # Guarantee minimum food sources exist
        while len(self.food_sources) < min_sources:
            self._spawn_food()

        # Stochastic spawning above minimum
        if (
            len(self.food_sources) < max_sources
            and self.rng.random() < self.food_config["spawn_rate"] * self.size * self.size
        ):
            self._spawn_food()

        # Decay (Phase 2+)
        decay = self.food_config.get("decay_rate", 0)
        if decay > 0:
            for food in self.food_sources:
                food.energy = max(0, food.energy - decay)

    def wrap(self, x: int, y: int) -> tuple[int, int]:
        """Toroidal coordinate wrapping."""
        if self.toroidal:
            return x % self.size, y % self.size
        return max(0, min(x, self.size - 1)), max(0, min(y, self.size - 1))

    def food_at(self, x: int, y: int) -> FoodSource | None:
        """Get food source at position, if any."""
        for food in self.food_sources:
            if food.x == x and food.y == y:
                return food
        return None

    def visible_from(self, x: int, y: int, radius: int) -> dict:
        """Get description of cells visible from (x,y) within radius."""
        visible = {"food": [], "agents": []}
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                wx, wy = self.wrap(x + dx, y + dy)
                food = self.food_at(wx, wy)
                if food:
                    visible["food"].append(food.to_dict())
        return visible

    def to_dict(self) -> dict:
        return {
            "size": self.size,
            "toroidal": self.toroidal,
            "food_sources": [f.to_dict() for f in self.food_sources],
        }

    # ── Private ─────────────────────────────────────────────────

    def _spawn_food(self) -> None:
        """Place a new food source at a random empty cell."""
        occupied = {(f.x, f.y) for f in self.food_sources}
        attempts = 0
        while attempts < 100:
            x = self.rng.randint(0, self.size - 1)
            y = self.rng.randint(0, self.size - 1)
            if (x, y) not in occupied:
                energy = self.rng.randint(
                    self.food_config["size_min"],
                    self.food_config["size_max"],
                )
                self._food_id_counter += 1
                self.food_sources.append(
                    FoodSource(
                        x=x, y=y,
                        energy=energy,
                        max_energy=energy,
                        id=f"food_{self._food_id_counter}",
                    )
                )
                return
            attempts += 1
