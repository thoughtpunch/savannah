"""Agent biography generation — narrative summary of one agent's life.

Produces a markdown document tracing an agent's journey through the
simulation: birth, key events, perturbations, energy trajectory,
social interactions, and final state.

CLI usage:
    python -m savannah.analysis.biography data/exp_xxx/ AgentName
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from .analyze import load_metrics, load_perturbations, _mean


def generate_biography(data_dir: Path, agent_name: str) -> str:
    """Generate a narrative biography for one agent.

    Loads:
    - Agent state.json (initial and final)
    - All memory files (episodic, semantic, self, social)
    - Metrics rows for this agent
    - Perturbation events affecting this agent

    Returns a markdown narrative.
    """
    # Load all data sources
    metrics = load_metrics(data_dir)
    perturbations = load_perturbations(data_dir)

    agent_metrics = [r for r in metrics if r["agent_name"] == agent_name]
    agent_perturbations = [p for p in perturbations if p.get("agent") == agent_name]

    # Load agent state file
    state = _load_agent_state(data_dir, agent_name)

    # Load memory files
    memories = _load_memory_files(data_dir, agent_name)

    if not agent_metrics and not state:
        return f"# Biography: {agent_name}\n\nNo data found for agent `{agent_name}`.\n"

    # Build narrative
    lines: list[str] = []

    # ── Title ──
    lines.append(f"# Biography of {agent_name}")
    lines.append("")

    # ── Birth ──
    lines.append("## Birth")
    lines.append("")
    if state:
        pos = state.get("position", [0, 0])
        energy = state.get("energy", 0)
        max_energy = state.get("max_energy", 100)
        lines.append(
            f"{agent_name} entered the savannah at position ({pos[0]}, {pos[1]}) "
            f"with {energy:.0f}/{max_energy:.0f} energy."
        )
    elif agent_metrics:
        first = agent_metrics[0]
        lines.append(
            f"{agent_name} was first observed at tick {first['tick']} "
            f"with {first['energy']:.1f} energy."
        )
    lines.append("")

    # ── Energy trajectory ──
    lines.append("## Energy Trajectory")
    lines.append("")
    if agent_metrics:
        energies = [r["energy"] for r in agent_metrics]
        ticks = [r["tick"] for r in agent_metrics]
        peak_energy = max(energies)
        peak_tick = ticks[energies.index(peak_energy)]
        lowest_energy = min(energies)
        lowest_tick = ticks[energies.index(lowest_energy)]
        final_energy = energies[-1]
        final_tick = ticks[-1]

        lines.append(f"- **Peak energy:** {peak_energy:.1f} at tick {peak_tick}")
        lines.append(f"- **Lowest energy:** {lowest_energy:.1f} at tick {lowest_tick}")
        lines.append(f"- **Final energy:** {final_energy:.1f} at tick {final_tick}")
        lines.append(f"- **Mean energy:** {_mean(energies):.1f}")

        # Death detection
        death_rows = [r for r in agent_metrics if not r["alive"]]
        if death_rows:
            death_tick = death_rows[0]["tick"]
            lines.append(f"- **Death:** Tick {death_tick} (energy depleted)")
        else:
            lines.append(f"- **Status:** Survived through tick {final_tick}")
    lines.append("")

    # ── Actions ──
    lines.append("## Actions")
    lines.append("")
    if agent_metrics:
        action_counts: dict[str, int] = defaultdict(int)
        for r in agent_metrics:
            action_counts[r["action"]] += 1

        total_actions = sum(action_counts.values())
        lines.append(f"Over {len(agent_metrics)} ticks, {agent_name} performed:")
        lines.append("")
        for action, count in sorted(action_counts.items(), key=lambda x: -x[1]):
            pct = (count / total_actions * 100) if total_actions > 0 else 0
            lines.append(f"- **{action}**: {count} times ({pct:.1f}%)")
    lines.append("")

    # ── Key events from episodic memory ──
    lines.append("## Key Events")
    lines.append("")
    episodic = memories.get("episodic", "")
    if episodic.strip():
        events = [line.strip() for line in episodic.split("\n") if line.strip()]
        if events:
            for event in events[:20]:  # Cap at 20 for readability
                lines.append(f"- {event}")
        else:
            lines.append("No episodic memories recorded.")
    else:
        lines.append("No episodic memories recorded.")
    lines.append("")

    # ── Perturbation events ──
    lines.append("## Perturbation Events")
    lines.append("")
    if agent_perturbations:
        lines.append(
            f"{agent_name} was perturbed {len(agent_perturbations)} time(s):"
        )
        lines.append("")

        # Index metrics for pre/post
        agent_tick_lookup = {r["tick"]: r for r in agent_metrics}

        for i, p in enumerate(agent_perturbations, 1):
            ptick = p.get("tick", 0)
            ptype = p.get("type", "unknown")
            transform = p.get("transform", "unknown")

            lines.append(
                f"### Perturbation {i} (Tick {ptick})"
            )
            lines.append("")
            lines.append(f"- **Type:** {ptype} ({transform})")

            original = p.get("original", "")
            corrupted = p.get("corrupted", "")
            if original:
                lines.append(f"- **Original:** {original[:150]}")
                lines.append(f"- **Corrupted:** {corrupted[:150]}")

            # Aftermath
            pre_rows = [
                agent_tick_lookup[t]
                for t in range(ptick - 10, ptick)
                if t in agent_tick_lookup
            ]
            post_rows = [
                agent_tick_lookup[t]
                for t in range(ptick, ptick + 10)
                if t in agent_tick_lookup
            ]

            if pre_rows and post_rows:
                pre_unc = _mean([r["uncertainty_count"] for r in pre_rows])
                post_unc = _mean([r["uncertainty_count"] for r in post_rows])
                pre_sr = _mean([r["self_reference_count"] for r in pre_rows])
                post_sr = _mean([r["self_reference_count"] for r in post_rows])

                lines.append("")
                lines.append("**Aftermath:**")
                delta_unc = post_unc - pre_unc
                delta_sr = post_sr - pre_sr
                if abs(delta_unc) > 0.5:
                    direction = "increased" if delta_unc > 0 else "decreased"
                    lines.append(
                        f"- Uncertainty language {direction} by {abs(delta_unc):.2f} "
                        f"(from {pre_unc:.2f} to {post_unc:.2f})"
                    )
                if abs(delta_sr) > 0.5:
                    direction = "increased" if delta_sr > 0 else "decreased"
                    lines.append(
                        f"- Self-reference language {direction} by {abs(delta_sr):.2f} "
                        f"(from {pre_sr:.2f} to {post_sr:.2f})"
                    )
                if abs(delta_unc) <= 0.5 and abs(delta_sr) <= 0.5:
                    lines.append("- Minimal behavioral change detected.")

            lines.append("")
    else:
        lines.append(f"{agent_name} was never perturbed during this experiment.")
    lines.append("")

    # ── Social interactions ──
    lines.append("## Social Interactions")
    lines.append("")
    social = memories.get("social", "")
    if social.strip():
        lines.append("From social memory:")
        lines.append("")
        for line in social.strip().split("\n"):
            if line.strip():
                lines.append(f"- {line.strip()}")
    else:
        lines.append("No social memory entries recorded.")
    lines.append("")

    # Trust language from metrics
    if agent_metrics:
        trust_ticks = [
            r for r in agent_metrics
            if r.get("trust_language_count", 0) > 0
        ]
        if trust_ticks:
            total_trust = sum(r["trust_language_count"] for r in trust_ticks)
            lines.append(
                f"\nTrust-related language appeared in {len(trust_ticks)} tick(s) "
                f"({total_trust} total mentions)."
            )

        # Signal actions
        signal_count = sum(1 for r in agent_metrics if r["action"] == "signal")
        if signal_count:
            lines.append(f"\n{agent_name} sent {signal_count} signal(s) to nearby agents.")
    lines.append("")

    # ── Self-model ──
    lines.append("## Self-Model")
    lines.append("")
    self_mem = memories.get("self", "")
    if self_mem.strip():
        lines.append(f"Final self-description: *{self_mem.strip()}*")
    else:
        lines.append("No self-model data available.")
    lines.append("")

    # ── Final state ──
    lines.append("## Final State")
    lines.append("")
    if state:
        alive = state.get("alive", False)
        energy = state.get("energy", 0)
        pos = state.get("position", [0, 0])
        age = state.get("age", 0)
        kills = state.get("kills", 0)
        perturbed = state.get("times_perturbed", 0)

        status = "alive" if alive else "deceased"
        lines.append(f"- **Status:** {status}")
        lines.append(f"- **Position:** ({pos[0]}, {pos[1]})")
        lines.append(f"- **Energy:** {energy:.1f}")
        lines.append(f"- **Age:** {age} ticks")
        lines.append(f"- **Kills:** {kills}")
        lines.append(f"- **Times perturbed:** {perturbed}")
    else:
        lines.append("State file not found; using metrics data only.")
        if agent_metrics:
            last = agent_metrics[-1]
            lines.append(f"- **Last seen:** tick {last['tick']}")
            lines.append(f"- **Energy:** {last['energy']:.1f}")
            lines.append(f"- **Alive:** {last['alive']}")
    lines.append("")

    return "\n".join(lines)


# ── Private helpers ──────────────────────────────────────────────


def _load_agent_state(data_dir: Path, agent_name: str) -> dict | None:
    """Load the agent's state.json if it exists."""
    state_path = data_dir / "agents" / agent_name / "state.json"
    if not state_path.exists():
        return None
    try:
        return json.loads(state_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _load_memory_files(data_dir: Path, agent_name: str) -> dict[str, str]:
    """Load all memory files for an agent.

    Returns dict with keys: episodic, semantic, self, social, working
    """
    agent_dir = data_dir / "agents" / agent_name
    memory_dir = agent_dir / "memory"

    result: dict[str, str] = {}
    for name in ("episodic", "semantic", "self", "social"):
        path = memory_dir / f"{name}.md"
        if path.exists():
            try:
                result[name] = path.read_text()
            except OSError:
                result[name] = ""
        else:
            result[name] = ""

    # Working notes
    working_path = agent_dir / "working.md"
    if working_path.exists():
        try:
            result["working"] = working_path.read_text()
        except OSError:
            result["working"] = ""
    else:
        result["working"] = ""

    return result


def main():
    """CLI: python -m savannah.analysis.biography data/exp_xxx/ AgentName"""
    if len(sys.argv) < 3:
        print("Usage: python -m savannah.analysis.biography <data_dir> <agent_name>")
        sys.exit(1)

    data_dir = Path(sys.argv[1])
    agent_name = sys.argv[2]
    bio = generate_biography(data_dir, agent_name)
    print(bio)


if __name__ == "__main__":
    main()
