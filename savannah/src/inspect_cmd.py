"""Inspect simulation state at a specific tick."""

from __future__ import annotations

import json
from pathlib import Path


def inspect(
    data_dir: Path,
    tick: int,
    agent_name: str | None = None,
) -> None:
    """Inspect a completed simulation's state at a given tick.

    Parameters
    ----------
    data_dir : Path
        Root data directory of a completed run.
    tick : int
        The tick number to inspect. The nearest available snapshot will be used.
    agent_name : str | None
        If set, show detailed memory and state for this specific agent.
    """
    ticks_dir = data_dir / "logs" / "ticks"
    if not ticks_dir.exists():
        print(f"No tick snapshots found in {ticks_dir}")
        return

    # Find nearest snapshot to requested tick
    snapshot_files = sorted(ticks_dir.glob("*.json"))
    if not snapshot_files:
        print(f"No snapshot files found in {ticks_dir}")
        return

    nearest_file = _find_nearest_snapshot(snapshot_files, tick)
    snapshot = json.loads(nearest_file.read_text())
    actual_tick = snapshot["tick"]

    # Print world summary
    world = snapshot.get("world", {})
    agents = snapshot.get("agents", [])
    food_sources = world.get("food_sources", [])
    alive_count = sum(1 for a in agents if a.get("alive", False))
    world_size = world.get("size", "?")

    print(f"{'=' * 60}")
    print(f"Snapshot at tick {actual_tick}" + (
        f"  (requested: {tick})" if actual_tick != tick else ""
    ))
    print(f"{'=' * 60}")
    print(f"  World size: {world_size}x{world_size}")
    print(f"  Food sources: {len(food_sources)}")
    print(f"  Agents alive: {alive_count} / {len(agents)}")
    print()

    # Print agent list
    print(f"{'─' * 60}")
    print("AGENTS:")
    print(f"{'─' * 60}")
    for agent in agents:
        name = agent.get("name", "?")
        pos = agent.get("position", [0, 0])
        energy = agent.get("energy", 0)
        alive = agent.get("alive", False)
        status = "ALIVE" if alive else "DEAD"
        print(
            f"  {name:<20} pos=({pos[0]:>2},{pos[1]:>2})  "
            f"energy={energy:>6.1f}  [{status}]"
        )
    print()

    # If agent_name specified, show detailed agent info
    if agent_name:
        _inspect_agent(data_dir, agents, agent_name)


def _find_nearest_snapshot(snapshot_files: list[Path], tick: int) -> Path:
    """Find the snapshot file closest to the requested tick number."""
    best_file = snapshot_files[0]
    best_distance = float("inf")

    for f in snapshot_files:
        # Extract tick number from filename (e.g., 000100.json -> 100)
        try:
            file_tick = int(f.stem)
        except ValueError:
            continue
        distance = abs(file_tick - tick)
        if distance < best_distance:
            best_distance = distance
            best_file = f
    return best_file


def _inspect_agent(data_dir: Path, agents: list[dict], agent_name: str) -> None:
    """Print detailed state and memory for a specific agent."""
    # Find agent in snapshot
    agent_data = None
    for a in agents:
        if a.get("name") == agent_name:
            agent_data = a
            break

    if agent_data is None:
        print(f"Agent '{agent_name}' not found in snapshot.")
        print(f"Available agents: {', '.join(a.get('name', '?') for a in agents)}")
        return

    print(f"{'=' * 60}")
    print(f"AGENT DETAIL: {agent_name}")
    print(f"{'=' * 60}")

    # Print all snapshot fields
    for key, value in agent_data.items():
        print(f"  {key}: {value}")
    print()

    # Load agent files from disk
    agent_dir = data_dir / "agents" / agent_name

    # Memory files
    memory_dir = agent_dir / "memory"
    memory_files = ["episodic.md", "semantic.md", "self.md", "social.md"]

    if memory_dir.exists():
        print(f"{'─' * 60}")
        print("MEMORY FILES:")
        print(f"{'─' * 60}")
        for mf in memory_files:
            mpath = memory_dir / mf
            if mpath.exists():
                content = mpath.read_text().strip()
                print(f"\n  [{mf}]")
                if content:
                    for line in content.split("\n"):
                        print(f"    {line}")
                else:
                    print("    (empty)")
            else:
                print(f"\n  [{mf}] — file not found")
        print()
    else:
        print(f"  Memory directory not found: {memory_dir}")
        print()

    # Working notes
    working_path = agent_dir / "working.md"
    print(f"{'─' * 60}")
    print("WORKING NOTES:")
    print(f"{'─' * 60}")
    if working_path.exists():
        content = working_path.read_text().strip()
        if content:
            for line in content.split("\n"):
                print(f"  {line}")
        else:
            print("  (empty)")
    else:
        print("  working.md not found")
    print()

    # State file
    state_path = agent_dir / "state.json"
    print(f"{'─' * 60}")
    print("STATE FILE:")
    print(f"{'─' * 60}")
    if state_path.exists():
        state = json.loads(state_path.read_text())
        print(f"  {json.dumps(state, indent=2)}")
    else:
        print("  state.json not found")
    print()
