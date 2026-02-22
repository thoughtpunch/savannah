"""CLI-callable tick operations for team-mode coordinator.

Two subcommands:
  prep  — load state, run perturbation, build prompts, write prompts JSON
  apply — read responses, parse/apply actions, drain/age/world tick, metrics
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

from .engine import Engine, apply_action
from .metrics import extract_metrics
from .parser import parse_action
from .perturbation import maybe_perturb


def _load_config(data_dir: Path) -> dict:
    """Load the resolved config saved by Engine.setup()."""
    config_path = data_dir / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def prep(data_dir: Path, tick: int) -> None:
    """Pre-LLM tick phase: load state, perturb, build prompts, write JSON.

    Writes data_dir/team/tick_{N}_prompts.json with structure:
        {"tick": N, "alive": ["name", ...], "prompts": {"name": "prompt", ...}}
    """
    config = _load_config(data_dir)
    engine = Engine.from_checkpoint(config, data_dir)
    engine.tick = tick

    alive = engine.alive_agents
    if not alive:
        # Write empty prompts — coordinator should detect and stop
        _write_prompts(data_dir, tick, [], {})
        return

    # Run perturbation for each alive agent
    for agent in alive:
        maybe_perturb(agent, tick, config["perturbation"], data_dir)

    # Build prompts
    prompts: dict[str, str] = {}
    for agent in alive:
        prompts[agent.name] = agent.build_prompt(engine.world, tick)

    alive_names = [a.name for a in alive]
    _write_prompts(data_dir, tick, alive_names, prompts)


def apply_responses(data_dir: Path, tick: int) -> dict:
    """Post-LLM tick phase: parse responses, apply actions, update world.

    Reads data_dir/team/tick_{N}_responses.json:
        {"agent_name": "response_text", ...}

    Returns status dict: {"tick": N, "alive": count, "dead": count}
    """
    config = _load_config(data_dir)
    engine = Engine.from_checkpoint(config, data_dir)
    engine.tick = tick

    # Read responses
    responses_path = data_dir / "team" / f"tick_{tick}_responses.json"
    responses: dict[str, str] = json.loads(responses_path.read_text())

    alive = engine.alive_agents
    parsed_actions: list[dict] = []

    # Parse and apply actions
    for agent in alive:
        response_text = responses.get(agent.name, "ACTION: rest\nWORKING: \nREASONING: no response")
        action = parse_action(response_text)
        apply_action(
            agent, action, engine.world, config,
            tick=tick, alive_agents=alive,
        )
        parsed_actions.append(action)

    # Passive energy drain
    for agent in alive:
        agent.drain(config["agents"]["energy_drain_per_tick"])

    # Age all alive agents
    for agent in alive:
        agent.age += 1

    # World tick (food spawning, decay, etc.)
    engine.world.tick_update(tick)

    # Metrics
    if tick % config["metrics"].get("extract_every", 1) == 0:
        extract_metrics(alive, tick, data_dir, parsed_actions)

    # Save agent state
    for agent in engine.agents:
        if agent.alive:
            agent.save_state()

    # Save snapshot
    if tick % config["simulation"].get("snapshot_every", 100) == 0:
        snapshot = {
            "tick": tick,
            "world": engine.world.to_dict(),
            "agents": [a.to_dict() for a in engine.agents],
        }
        snap_path = data_dir / "logs" / "ticks" / f"{tick:06d}.json"
        snap_path.write_text(json.dumps(snapshot, indent=2))

    # Status
    alive_count = sum(1 for a in engine.agents if a.alive)
    dead_count = len(engine.agents) - alive_count
    status = {"tick": tick, "alive": alive_count, "dead": dead_count}
    print(json.dumps(status))
    return status


def _write_prompts(data_dir: Path, tick: int, alive: list[str], prompts: dict[str, str]) -> None:
    """Write tick prompts JSON for the coordinator to read."""
    team_dir = data_dir / "team"
    team_dir.mkdir(exist_ok=True)
    output = {"tick": tick, "alive": alive, "prompts": prompts}
    path = team_dir / f"tick_{tick}_prompts.json"
    path.write_text(json.dumps(output, indent=2))


def main() -> None:
    """CLI entrypoint: tick_helpers.py <subcommand> <data_dir> <tick>"""
    if len(sys.argv) < 4:
        print(f"Usage: {sys.argv[0]} <prep|apply> <data_dir> <tick>", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]
    data_dir = Path(sys.argv[2])
    tick = int(sys.argv[3])

    if cmd == "prep":
        prep(data_dir, tick)
    elif cmd == "apply":
        apply_responses(data_dir, tick)
    else:
        print(f"Unknown subcommand: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
