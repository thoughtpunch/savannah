"""Main simulation loop — tick orchestration, agent dispatch, snapshot I/O."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

from .world import World
from .agent import Agent
from .llm import get_provider
from .parser import parse_action
from .perturbation import maybe_perturb
from .metrics import extract_metrics

logger = logging.getLogger(__name__)


class Engine:
    """Runs the simulation: world + agents + LLM inference per tick."""

    def __init__(self, config: dict, data_dir: Path):
        self.config = config
        self.data_dir = data_dir
        self.tick = 0
        self.world = World(config["world"], seed=config["simulation"]["seed"])
        self.provider = get_provider(config["llm"])
        self.agents: list[Agent] = []
        self.semaphore = asyncio.Semaphore(
            config["llm"].get("max_concurrent_agents", 6)
        )

    # ── Lifecycle ───────────────────────────────────────────────

    def setup(self) -> None:
        """Initialize world, spawn agents, create data dirs."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "world").mkdir(exist_ok=True)
        (self.data_dir / "logs" / "ticks").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "analysis").mkdir(exist_ok=True)

        self.world.initialize()
        self._spawn_agents()
        self._save_snapshot()

    async def run(self) -> None:
        """Main tick loop."""
        max_ticks = self.config["simulation"]["ticks"]
        delay_ms = self.config["simulation"].get("tick_delay_ms", 0)

        while self.tick < max_ticks:
            self.tick += 1
            logger.info("Tick %d / %d", self.tick, max_ticks)

            # 1. Perturbation (before agent sees state)
            for agent in self.alive_agents:
                maybe_perturb(agent, self.tick, self.config["perturbation"], self.data_dir)

            # 2. Build prompts + dispatch to LLM in parallel
            responses = await self._dispatch_all()

            # 3. Parse actions, apply to world
            for agent, response in zip(self.alive_agents, responses):
                action = parse_action(response)
                self._apply_action(agent, action)

            # 4. Passive energy drain
            for agent in self.alive_agents:
                agent.drain(self.config["agents"]["energy_drain_per_tick"])

            # 5. World tick (food spawning, decay, etc.)
            self.world.tick_update(self.tick)

            # 6. Metrics
            if self.tick % self.config["metrics"].get("extract_every", 1) == 0:
                extract_metrics(self.alive_agents, self.tick, self.data_dir)

            # 7. Snapshot
            if self.tick % self.config["simulation"].get("snapshot_every", 100) == 0:
                self._save_snapshot()

            # 8. Optional delay
            if delay_ms > 0:
                await asyncio.sleep(delay_ms / 1000)

    # ── Private helpers ─────────────────────────────────────────

    @property
    def alive_agents(self) -> list[Agent]:
        return [a for a in self.agents if a.alive]

    def _spawn_agents(self) -> None:
        """Create agents with random positions and initial files."""
        # TODO: implement agent spawning with name generator
        raise NotImplementedError

    async def _dispatch_all(self) -> list[str]:
        """Send all alive agents' prompts to LLM concurrently."""

        async def _invoke_one(agent: Agent) -> str:
            async with self.semaphore:
                prompt = agent.build_prompt(self.world, self.tick)
                return await self.provider.invoke(
                    prompt, self.config["llm"]["model"]
                )

        tasks = [_invoke_one(a) for a in self.alive_agents]
        return await asyncio.gather(*tasks, return_exceptions=True)

    def _apply_action(self, agent: Agent, action: dict) -> None:
        """Apply parsed action to agent and world state."""
        # TODO: implement action application
        raise NotImplementedError

    def _save_snapshot(self) -> None:
        """Write full world state to tick snapshot file."""
        snapshot = {
            "tick": self.tick,
            "world": self.world.to_dict(),
            "agents": [a.to_dict() for a in self.agents],
        }
        path = self.data_dir / "logs" / "ticks" / f"{self.tick:06d}.json"
        path.write_text(json.dumps(snapshot, indent=2))
