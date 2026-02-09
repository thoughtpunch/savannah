"""Main simulation loop — tick orchestration, agent dispatch, snapshot I/O."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from pathlib import Path

from .agent import Agent
from .llm import LLMProvider, LLMResponse, get_provider
from .memory import (
    apply_compaction,
    build_compaction_prompt,
    parse_compaction_response,
    recall,
    remember,
)
from .metrics import extract_metrics
from .names import generate_names
from .parser import parse_action
from .perturbation import maybe_perturb
from .world import World

logger = logging.getLogger(__name__)

DIRECTION_DELTAS = {
    "n": (0, -1),
    "s": (0, 1),
    "e": (1, 0),
    "w": (-1, 0),
}


class Engine:
    """Runs the simulation: world + agents + LLM inference per tick."""

    def __init__(self, config: dict, data_dir: Path, provider: LLMProvider | None = None,
                 live_server=None):
        self.config = config
        self.data_dir = data_dir
        self.tick = 0
        self.world = World(config["world"], seed=config["simulation"]["seed"])
        self.provider = provider or get_provider(config["llm"])
        self.agents: list[Agent] = []
        self.semaphore = asyncio.Semaphore(
            config["llm"].get("max_concurrent_agents", 6)
        )
        self._rng = random.Random(config["simulation"]["seed"])
        self.live_server = live_server

    # ── Lifecycle ───────────────────────────────────────────────

    def setup(self) -> None:
        """Initialize world, spawn agents, create data dirs."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "world").mkdir(exist_ok=True)
        (self.data_dir / "logs" / "ticks").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "logs").mkdir(exist_ok=True)
        (self.data_dir / "analysis").mkdir(exist_ok=True)

        # Save resolved config for history/replay
        import yaml
        config_path = self.data_dir / "config.yaml"
        config_path.write_text(yaml.dump(self.config, default_flow_style=False))

        self.world.initialize()
        self._spawn_agents()
        self._save_snapshot()

    async def run(self) -> None:
        """Main tick loop."""
        max_ticks = self.config["simulation"]["ticks"]
        delay_ms = self.config["simulation"].get("tick_delay_ms", 0)
        live = self.live_server

        while self.tick < max_ticks:
            self.tick += 1
            alive = self.alive_agents
            if not alive:
                logger.info("All agents dead at tick %d", self.tick)
                break

            logger.info("Tick %d / %d  (%d alive)", self.tick, max_ticks, len(alive))

            # Live: handle pause/resume/stop commands
            if live:
                await live.process_commands()
                if live.paused:
                    await live.handle_pause_loop()
                    if live.step_requested:
                        live.step_requested = False
                    # Re-check for stop after pause
                    await live.process_commands()

            # 1. Perturbation (before agent sees state)
            perturbation_events = []
            for agent in alive:
                result = maybe_perturb(agent, self.tick, self.config["perturbation"], self.data_dir)
                if result:
                    perturbation_events.append(result)

            # Live: broadcast "thinking" state before LLM dispatch
            if live:
                await live.broadcast({
                    "type": "thinking",
                    "tick": self.tick,
                    "max_ticks": max_ticks,
                    "agents": [{"name": a.name, "alive": a.alive} for a in self.agents],
                })

            # 2. Build prompts + dispatch to LLM in parallel
            t0 = time.monotonic()
            responses = await self._dispatch_all(alive)
            inference_ms = int((time.monotonic() - t0) * 1000)

            # 3. Parse actions, apply to world
            parsed_actions = []
            for agent, response_text in zip(alive, responses, strict=True):
                action = parse_action(response_text)
                self._apply_action(agent, action)
                parsed_actions.append(action)
                # Store for live broadcast
                agent._last_action = action

            # 4. Passive energy drain
            for agent in alive:
                agent.drain(self.config["agents"]["energy_drain_per_tick"])

            # 5. Age all alive agents
            for agent in alive:
                agent.age += 1

            # 6. World tick (food spawning, decay, etc.)
            self.world.tick_update(self.tick)

            # 6b. Process pending compactions (requires async LLM call)
            for agent in alive:
                if getattr(agent, '_pending_compaction', False):
                    await self._do_compaction(agent)
                    agent._pending_compaction = False

            # 7. Metrics
            if self.tick % self.config["metrics"].get("extract_every", 1) == 0:
                extract_metrics(alive, self.tick, self.data_dir, parsed_actions)

            # 8. Save agent state
            for agent in alive:
                agent.save_state()

            # 9. Snapshot
            if self.tick % self.config["simulation"].get("snapshot_every", 100) == 0:
                self._save_snapshot()

            # Live: broadcast full tick state
            if live:
                tick_state = self._build_live_state(max_ticks, inference_ms, perturbation_events)
                await live.broadcast(tick_state)

            # 10. Optional delay (live server overrides config delay)
            effective_delay = live.tick_delay_ms if live else delay_ms
            if effective_delay > 0:
                await asyncio.sleep(effective_delay / 1000)

        # Final snapshot
        self._save_snapshot()

        if live:
            await live.broadcast({
                "type": "complete",
                "tick": self.tick,
                "max_ticks": max_ticks,
                "alive": len(self.alive_agents),
                "total": len(self.agents),
            })

        logger.info("Simulation complete: %d ticks, %d/%d agents alive",
                     self.tick, len(self.alive_agents), len(self.agents))

    # ── Private helpers ─────────────────────────────────────────

    @property
    def alive_agents(self) -> list[Agent]:
        return [a for a in self.agents if a.alive]

    def _spawn_agents(self) -> None:
        """Create agents with random positions and initial files."""
        agent_cfg = self.config["agents"]
        count = agent_cfg["count"]
        grid = self.config["world"]["grid_size"]
        names = generate_names(count, seed=self.config["simulation"]["seed"])

        for i, name in enumerate(names):
            x = self._rng.randint(0, grid - 1)
            y = self._rng.randint(0, grid - 1)
            agent = Agent(
                name=name,
                id=f"{i:04x}",
                x=x,
                y=y,
                energy=float(agent_cfg.get("energy_start", 80)),
                max_energy=float(agent_cfg.get("energy_max", 100)),
                vision_range=agent_cfg.get("vision_range", 3),
                food_value=agent_cfg.get("food_value", 80),
                data_dir=self.data_dir,
            )
            agent.initialize_files()
            self.agents.append(agent)

        logger.info("Spawned %d agents", len(self.agents))

    async def _dispatch_all(self, alive: list[Agent]) -> list[str]:
        """Send all alive agents' prompts to LLM concurrently.

        Returns list of response text strings (one per alive agent).
        """

        async def _invoke_one(agent: Agent) -> str:
            async with self.semaphore:
                prompt = agent.build_prompt(self.world, self.tick)
                try:
                    response: LLMResponse = await self.provider.invoke(
                        prompt, self.config["llm"]["model"]
                    )
                    return response.text
                except Exception as e:
                    logger.warning("LLM invoke failed for %s: %s", agent.name, e)
                    return "ACTION: rest\nWORKING: error\nREASONING: LLM failure"

        tasks = [_invoke_one(a) for a in alive]
        return await asyncio.gather(*tasks)

    def _apply_action(self, agent: Agent, action: dict) -> None:
        """Apply parsed action to agent and world state."""
        agent_cfg = self.config["agents"]
        action_name = action["action"]
        args = action.get("args")

        # Write working notes (every action updates working)
        working_text = action.get("working", "")
        agent.working_path.write_text(working_text)

        if action_name == "move":
            dx, dy = DIRECTION_DELTAS.get(args, (0, 0))
            new_x, new_y = self.world.wrap(agent.x + dx, agent.y + dy)
            agent.x = new_x
            agent.y = new_y
            agent.drain(agent_cfg.get("energy_per_move", 2))

        elif action_name == "eat":
            food = self.world.food_at(agent.x, agent.y)
            if food:
                eat_amount = min(
                    agent_cfg.get("eat_rate", 50),
                    food.energy,
                    agent.max_energy - agent.energy,
                )
                food.energy -= eat_amount
                agent.energy = min(agent.energy + eat_amount, agent.max_energy)
            # No extra energy cost for eating

        elif action_name == "recall":
            query = args or ""
            max_results = agent_cfg.get("recall_max_results", 3)
            results = recall(agent.memory_dir, query, max_results=max_results)
            agent.pending_recall_results = results
            agent.drain(agent_cfg.get("energy_per_recall", 1))

        elif action_name == "remember":
            text = args or ""
            if text:
                remember(agent.memory_dir, f"Tick {self.tick}: {text}")
            agent.drain(agent_cfg.get("energy_per_remember", 1))

        elif action_name == "compact":
            agent.drain(agent_cfg.get("energy_per_compact", 2))
            agent._pending_compaction = True

        elif action_name == "signal":
            msg = args or ""
            if msg:
                self._broadcast_signal(agent, msg)
            agent.drain(agent_cfg.get("energy_per_signal", 1))

        elif action_name == "observe":
            # Observe gives a richer view next tick (already handled by build_prompt)
            agent.drain(agent_cfg.get("energy_per_observe", 1))

        elif action_name == "attack":
            target_name = args
            target = self._find_adjacent_agent(agent, target_name)
            if target:
                risk = agent_cfg.get("combat_risk_factor", 0.3)
                agent.drain(agent_cfg.get("energy_per_attack", 5))
                damage = agent.energy * risk
                target.drain(damage)
                if not target.alive:
                    agent.energy = min(
                        agent.energy + target.food_value,
                        agent.max_energy,
                    )
                    agent.kills += 1
            else:
                agent.drain(agent_cfg.get("energy_per_attack", 5))

        elif action_name == "flee":
            dx, dy = DIRECTION_DELTAS.get(args, (0, 0))
            # Flee moves 2 cells
            new_x, new_y = self.world.wrap(agent.x + dx * 2, agent.y + dy * 2)
            agent.x = new_x
            agent.y = new_y
            agent.drain(agent_cfg.get("energy_per_flee", 4))

        elif action_name == "rest":
            agent.drain(agent_cfg.get("energy_per_rest", 0.5))

        else:
            # Unknown action — fallback to rest
            agent.drain(agent_cfg.get("energy_per_rest", 0.5))

    def _broadcast_signal(self, sender: Agent, message: str) -> None:
        """Send a signal to all agents within comm_range."""
        comm_range = self.config["agents"].get("comm_range", 5)
        grid = self.config["world"]["grid_size"]
        toroidal = self.config["world"].get("toroidal", True)

        for agent in self.alive_agents:
            if agent.name == sender.name:
                continue
            dx = abs(agent.x - sender.x)
            dy = abs(agent.y - sender.y)
            if toroidal:
                dx = min(dx, grid - dx)
                dy = min(dy, grid - dy)
            dist = max(dx, dy)  # Chebyshev distance
            if dist <= comm_range:
                agent.pending_signals.append(f"{sender.name}: {message}")

    def _find_adjacent_agent(self, attacker: Agent, target_name: str | None) -> Agent | None:
        """Find a named agent adjacent (within 1 cell) to the attacker."""
        if not target_name:
            return None
        for agent in self.alive_agents:
            if agent.name == target_name and agent.name != attacker.name:
                dx = abs(agent.x - attacker.x)
                dy = abs(agent.y - attacker.y)
                grid = self.config["world"]["grid_size"]
                if self.config["world"].get("toroidal", True):
                    dx = min(dx, grid - dx)
                    dy = min(dy, grid - dy)
                if dx <= 1 and dy <= 1:
                    return agent
        return None

    async def _do_compaction(self, agent: Agent) -> None:
        """Run memory compaction for an agent via LLM."""
        prompt = build_compaction_prompt(agent.name, agent.memory_dir, self.tick)
        response = await self.provider.invoke(
            prompt, self.config["llm"].get("compaction_model", "sonnet")
        )
        sections = parse_compaction_response(response.text)
        if sections:
            apply_compaction(agent.memory_dir, sections, self.data_dir)
        else:
            logger.warning("Compaction parse failed for %s", agent.name)

    def _build_live_state(self, max_ticks: int, inference_ms: int,
                          perturbation_events: list) -> dict:
        """Build the full tick state for live broadcast."""
        agents_data = []
        for agent in self.agents:
            action = getattr(agent, '_last_action', None)
            agent_dict = agent.to_dict()
            if action:
                agent_dict["action"] = action.get("action", "rest")
                args = action.get("args", "")
                if args:
                    agent_dict["action"] += f"({args})"
                agent_dict["reasoning"] = action.get("reasoning", "")
                agent_dict["working"] = action.get("working", "")
            else:
                agent_dict["action"] = ""
                agent_dict["reasoning"] = ""
                agent_dict["working"] = ""
            agents_data.append(agent_dict)

        return {
            "type": "tick",
            "tick": self.tick,
            "max_ticks": max_ticks,
            "inference_time_ms": inference_ms,
            "world": self.world.to_dict(),
            "agents": agents_data,
            "perturbations": perturbation_events,
        }

    def _save_snapshot(self) -> None:
        """Write full world state to tick snapshot file."""
        snapshot = {
            "tick": self.tick,
            "world": self.world.to_dict(),
            "agents": [a.to_dict() for a in self.agents],
        }
        path = self.data_dir / "logs" / "ticks" / f"{self.tick:06d}.json"
        path.write_text(json.dumps(snapshot, indent=2))
