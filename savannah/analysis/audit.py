"""Perturbation audit report — markdown summary of all perturbation events.

Generates a structured report showing what was changed, when, and how
the agent's behavior shifted in response.

CLI usage:
    python -m savannah.analysis.audit data/exp_xxx/
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

from .analyze import load_metrics, load_perturbations, _mean


def perturbation_audit(data_dir: Path) -> str:
    """Generate a markdown report of all perturbation events and their aftermath.

    For each agent that was perturbed:
    - Lists each perturbation event (tick, type, what changed)
    - Compares uncertainty_count and self_reference_count in 10 ticks
      before vs 10 ticks after the perturbation
    - Flags notable changes

    Returns markdown text.
    """
    perturbations = load_perturbations(data_dir)
    metrics = load_metrics(data_dir)

    if not perturbations:
        return "# Perturbation Audit\n\nNo perturbation events found.\n"

    # Index metrics by (agent_name, tick)
    metric_lookup: dict[str, dict[int, dict]] = defaultdict(dict)
    for row in metrics:
        metric_lookup[row["agent_name"]][row["tick"]] = row

    # Group perturbations by agent
    by_agent: dict[str, list[dict]] = defaultdict(list)
    for p in perturbations:
        by_agent[p.get("agent", "unknown")].append(p)

    # Build report
    lines: list[str] = []
    lines.append("# Perturbation Audit Report")
    lines.append("")
    lines.append(f"**Experiment:** `{data_dir}`")
    lines.append(f"**Total perturbation events:** {len(perturbations)}")
    lines.append(f"**Agents perturbed:** {len(by_agent)}")
    lines.append("")

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| Agent | Events | Types | Avg Delta Uncertainty | Avg Delta Self-Ref |")
    lines.append("|-------|--------|-------|----------------------|-------------------|")

    agent_summaries: dict[str, dict] = {}
    for agent_name in sorted(by_agent.keys()):
        events = by_agent[agent_name]
        agent_ticks = metric_lookup.get(agent_name, {})

        types = set(e.get("type", "?") for e in events)
        deltas_unc: list[float] = []
        deltas_sr: list[float] = []

        for event in events:
            ptick = event.get("tick", 0)
            pre_rows = [agent_ticks[t] for t in range(ptick - 10, ptick) if t in agent_ticks]
            post_rows = [agent_ticks[t] for t in range(ptick, ptick + 10) if t in agent_ticks]

            pre_unc = _mean([r["uncertainty_count"] for r in pre_rows])
            post_unc = _mean([r["uncertainty_count"] for r in post_rows])
            pre_sr = _mean([r["self_reference_count"] for r in pre_rows])
            post_sr = _mean([r["self_reference_count"] for r in post_rows])

            deltas_unc.append(post_unc - pre_unc)
            deltas_sr.append(post_sr - pre_sr)

        avg_delta_unc = _mean(deltas_unc)
        avg_delta_sr = _mean(deltas_sr)
        types_str = ", ".join(sorted(types))

        agent_summaries[agent_name] = {
            "events": events,
            "avg_delta_unc": avg_delta_unc,
            "avg_delta_sr": avg_delta_sr,
        }

        lines.append(
            f"| {agent_name} | {len(events)} | {types_str} | "
            f"{avg_delta_unc:+.3f} | {avg_delta_sr:+.3f} |"
        )

    lines.append("")

    # Detailed per-agent sections
    lines.append("## Detailed Events")
    lines.append("")

    for agent_name in sorted(by_agent.keys()):
        events = by_agent[agent_name]
        agent_ticks = metric_lookup.get(agent_name, {})

        lines.append(f"### {agent_name}")
        lines.append("")
        lines.append(f"Total perturbations: {len(events)}")
        lines.append("")

        for i, event in enumerate(events, 1):
            ptick = event.get("tick", 0)
            ptype = event.get("type", "unknown")
            transform = event.get("transform", "unknown")
            target_file = event.get("target_file", "?")
            original = event.get("original", "")
            corrupted = event.get("corrupted", "")

            lines.append(f"#### Event {i}: Tick {ptick}")
            lines.append("")
            lines.append(f"- **Type:** {ptype}")
            lines.append(f"- **Transform:** {transform}")
            lines.append(f"- **Target file:** `{target_file}`")
            lines.append("")

            if original:
                # Truncate long strings for readability
                orig_display = original[:200] + "..." if len(original) > 200 else original
                corr_display = corrupted[:200] + "..." if len(corrupted) > 200 else corrupted
                lines.append("**Original:**")
                lines.append(f"> {orig_display}")
                lines.append("")
                lines.append("**Corrupted:**")
                lines.append(f"> {corr_display}")
                lines.append("")

            # Pre/post comparison
            pre_rows = [agent_ticks[t] for t in range(ptick - 10, ptick) if t in agent_ticks]
            post_rows = [agent_ticks[t] for t in range(ptick, ptick + 10) if t in agent_ticks]

            pre_unc = _mean([r["uncertainty_count"] for r in pre_rows])
            post_unc = _mean([r["uncertainty_count"] for r in post_rows])
            pre_sr = _mean([r["self_reference_count"] for r in pre_rows])
            post_sr = _mean([r["self_reference_count"] for r in post_rows])
            pre_energy = _mean([r["energy"] for r in pre_rows])
            post_energy = _mean([r["energy"] for r in post_rows])

            lines.append("**Behavioral shift (10-tick window):**")
            lines.append("")
            lines.append("| Metric | Pre | Post | Delta |")
            lines.append("|--------|-----|------|-------|")
            lines.append(
                f"| Uncertainty count | {pre_unc:.2f} | {post_unc:.2f} | "
                f"{post_unc - pre_unc:+.2f} |"
            )
            lines.append(
                f"| Self-reference count | {pre_sr:.2f} | {post_sr:.2f} | "
                f"{post_sr - pre_sr:+.2f} |"
            )
            lines.append(
                f"| Energy | {pre_energy:.1f} | {post_energy:.1f} | "
                f"{post_energy - pre_energy:+.1f} |"
            )
            lines.append("")

            # Flag notable changes
            delta_unc = post_unc - pre_unc
            delta_sr = post_sr - pre_sr
            if abs(delta_unc) > 1.0 or abs(delta_sr) > 1.0:
                lines.append(
                    "> **Notable:** Large behavioral shift detected after this perturbation."
                )
                lines.append("")

    return "\n".join(lines)


def main():
    """CLI: python -m savannah.analysis.audit data/exp_xxx/"""
    if len(sys.argv) < 2:
        print("Usage: python -m savannah.analysis.audit <data_dir>")
        sys.exit(1)

    data_dir = Path(sys.argv[1])
    report = perturbation_audit(data_dir)
    print(report)


if __name__ == "__main__":
    main()
