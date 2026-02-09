"""Terminal replay mode — play back a completed simulation tick by tick."""

from __future__ import annotations

import json
from pathlib import Path


def replay(
    data_dir: Path,
    agent_filter: str | None = None,
    tick_range: tuple[int, int] | None = None,
    format: str = "text",
) -> None:
    """Replay a completed simulation run to stdout.

    Parameters
    ----------
    data_dir : Path
        Root data directory of a completed run (e.g. data/exp_20250101_120000).
    agent_filter : str | None
        If set, only display this agent's state each tick.
    tick_range : tuple[int, int] | None
        If set, only replay ticks in [start, end] inclusive.
    format : str
        Output format. Currently only "text" is supported.
    """
    ticks_dir = data_dir / "logs" / "ticks"
    if not ticks_dir.exists():
        print(f"No tick snapshots found in {ticks_dir}")
        return

    # Load snapshot files in tick order
    snapshot_files = sorted(ticks_dir.glob("*.json"))
    if not snapshot_files:
        print(f"No snapshot files found in {ticks_dir}")
        return

    # Load perturbation log (if exists)
    perturbations_by_tick: dict[int, list[dict]] = {}
    perturbations_path = data_dir / "logs" / "perturbations.jsonl"
    if perturbations_path.exists():
        with open(perturbations_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                tick_num = entry.get("tick", 0)
                perturbations_by_tick.setdefault(tick_num, []).append(entry)

    # Load metrics (if exists) — indexed by (tick, agent_name)
    metrics_by_tick: dict[int, list[dict]] = {}
    metrics_path = data_dir / "analysis" / "metrics.csv"
    if metrics_path.exists():
        import csv

        with open(metrics_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                tick_num = int(row["tick"])
                metrics_by_tick.setdefault(tick_num, []).append(row)

    # Replay each snapshot
    for snapshot_file in snapshot_files:
        snapshot = json.loads(snapshot_file.read_text())
        tick_num = snapshot["tick"]

        # Apply tick range filter
        if tick_range is not None and (tick_num < tick_range[0] or tick_num > tick_range[1]):
            continue

        # Compute summary stats
        agents = snapshot.get("agents", [])
        world = snapshot.get("world", {})
        food_sources = world.get("food_sources", [])
        alive_count = sum(1 for a in agents if a.get("alive", False))
        total_food_count = len(food_sources)
        total_food_energy = sum(f.get("energy", 0) for f in food_sources)

        # Print tick header
        print(f"{'=' * 60}")
        print(
            f"Tick {tick_num:>6}  |  Alive: {alive_count}  |  "
            f"Food: {total_food_count} ({total_food_energy:.0f} energy)"
        )
        print(f"{'-' * 60}")

        # Print agents
        for agent in agents:
            name = agent.get("name", "?")
            if agent_filter and name != agent_filter:
                continue
            pos = agent.get("position", [0, 0])
            energy = agent.get("energy", 0)
            alive = agent.get("alive", False)
            status = "ALIVE" if alive else "DEAD"
            print(
                f"  {name:<20} pos=({pos[0]:>2},{pos[1]:>2})  "
                f"energy={energy:>6.1f}  [{status}]"
            )

        # Print perturbations at this tick
        if tick_num in perturbations_by_tick:
            print(f"  {'~' * 40}")
            print("  PERTURBATIONS:")
            for p in perturbations_by_tick[tick_num]:
                agent_name = p.get("agent", "?")
                if agent_filter and agent_name != agent_filter:
                    continue
                ptype = p.get("type", "?")
                transform = p.get("transform", "?")
                print(f"    {agent_name}: {ptype} ({transform})")

        print()
