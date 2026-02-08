"""Statistical analysis scripts for ILET experiments.

Uses only stdlib (csv, json) by default. If scipy is available, adds
optional ANOVA / Mann-Whitney U tests.

CLI usage:
    python -m savannah.analysis.analyze data/exp_xxx/
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path


# ── Data loading ─────────────────────────────────────────────────


def load_metrics(data_dir: Path) -> list[dict]:
    """Load metrics CSV as list of dicts.

    Numeric fields (tick, energy, uncertainty_count, etc.) are cast to
    their natural types.  Boolean-ish fields are converted to bool.
    """
    csv_path = data_dir / "analysis" / "metrics.csv"
    if not csv_path.exists():
        return []

    rows: list[dict] = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(_cast_row(row))
    return rows


def load_perturbations(data_dir: Path) -> list[dict]:
    """Load perturbation JSONL as list of dicts."""
    jsonl_path = data_dir / "logs" / "perturbations.jsonl"
    if not jsonl_path.exists():
        return []

    entries: list[dict] = []
    with open(jsonl_path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


# ── Summary statistics ───────────────────────────────────────────


def summary_stats(metrics: list[dict]) -> dict:
    """Compute per-agent summary: mean energy, action distribution,
    uncertainty counts, self-reference counts.

    Returns::

        {
            "agent_name": {
                "mean_energy": float,
                "total_ticks": int,
                "action_counts": {"eat": N, "move": N, ...},
                "mean_uncertainty": float,
                "mean_self_reference": float,
                "total_uncertainty": int,
                "total_self_reference": int,
            },
            ...
        }
    """
    by_agent: dict[str, list[dict]] = defaultdict(list)
    for row in metrics:
        by_agent[row["agent_name"]].append(row)

    result: dict[str, dict] = {}
    for name, rows in by_agent.items():
        energies = [r["energy"] for r in rows]
        actions = [r["action"] for r in rows]
        uncertainties = [r["uncertainty_count"] for r in rows]
        self_refs = [r["self_reference_count"] for r in rows]

        action_counts: dict[str, int] = defaultdict(int)
        for a in actions:
            action_counts[a] += 1

        result[name] = {
            "mean_energy": _mean(energies),
            "total_ticks": len(rows),
            "action_counts": dict(action_counts),
            "mean_uncertainty": _mean(uncertainties),
            "mean_self_reference": _mean(self_refs),
            "total_uncertainty": sum(uncertainties),
            "total_self_reference": sum(self_refs),
        }

    return result


# ── Pre/post perturbation analysis ──────────────────────────────


def pre_post_analysis(
    metrics: list[dict],
    perturbations: list[dict],
    window: int = 20,
) -> dict:
    """Compare metrics in *window* ticks before vs after each perturbation.

    Returns::

        {
            "agent_name": [
                {
                    "perturbation_tick": int,
                    "perturbation_type": str,
                    "pre": {"mean_energy": ..., "mean_uncertainty": ..., "mean_self_reference": ...},
                    "post": {"mean_energy": ..., "mean_uncertainty": ..., "mean_self_reference": ...},
                    "delta_uncertainty": float,
                    "delta_self_reference": float,
                },
                ...
            ]
        }
    """
    # Index metrics by (agent_name, tick) for fast lookups
    by_agent_tick: dict[str, dict[int, dict]] = defaultdict(dict)
    for row in metrics:
        by_agent_tick[row["agent_name"]][row["tick"]] = row

    result: dict[str, list[dict]] = defaultdict(list)

    for p in perturbations:
        agent_name = p.get("agent", "")
        ptick = p.get("tick", 0)
        ptype = p.get("type", "unknown")

        agent_ticks = by_agent_tick.get(agent_name, {})

        # Gather pre-window and post-window rows
        pre_rows = [
            agent_ticks[t] for t in range(ptick - window, ptick) if t in agent_ticks
        ]
        post_rows = [
            agent_ticks[t] for t in range(ptick, ptick + window) if t in agent_ticks
        ]

        pre_summary = _window_summary(pre_rows)
        post_summary = _window_summary(post_rows)

        result[agent_name].append({
            "perturbation_tick": ptick,
            "perturbation_type": ptype,
            "pre": pre_summary,
            "post": post_summary,
            "delta_uncertainty": post_summary["mean_uncertainty"] - pre_summary["mean_uncertainty"],
            "delta_self_reference": post_summary["mean_self_reference"] - pre_summary["mean_self_reference"],
        })

    return dict(result)


# ── Survival analysis ────────────────────────────────────────────


def survival_analysis(metrics: list[dict]) -> dict:
    """Compute survival curves: tick of death per agent, plus max-tick alive.

    Returns::

        {
            "agent_name": {
                "death_tick": int | None,  # None if survived entire run
                "max_tick": int,           # last tick observed alive
                "survived": bool,
            },
            ...
        }
    """
    by_agent: dict[str, list[dict]] = defaultdict(list)
    for row in metrics:
        by_agent[row["agent_name"]].append(row)

    result: dict[str, dict] = {}
    for name, rows in by_agent.items():
        # Sort by tick
        rows_sorted = sorted(rows, key=lambda r: r["tick"])
        death_tick = None
        max_tick = 0
        for row in rows_sorted:
            t = row["tick"]
            alive = row["alive"]
            if t > max_tick and alive:
                max_tick = t
            if not alive and death_tick is None:
                death_tick = t

        result[name] = {
            "death_tick": death_tick,
            "max_tick": max_tick,
            "survived": death_tick is None,
        }

    return result


# ── Optional: ANOVA / Mann-Whitney (requires scipy) ─────────────


def anova_perturbation(metrics: list[dict], perturbations: list[dict]) -> dict | None:
    """If scipy is available, run Mann-Whitney U comparing uncertainty
    and self-reference counts for perturbed vs unperturbed ticks.

    Returns None if scipy is not installed.
    """
    try:
        from scipy import stats as sp_stats
    except ImportError:
        return None

    perturbed_ticks = {(p["agent"], p["tick"]) for p in perturbations}

    # Split metrics into "near-perturbation" (within 10 ticks after) vs normal
    near_perturbation: list[dict] = []
    normal: list[dict] = []

    for row in metrics:
        agent = row["agent_name"]
        tick = row["tick"]
        is_near = any(
            agent == pa and 0 <= tick - pt <= 10
            for pa, pt in perturbed_ticks
        )
        if is_near:
            near_perturbation.append(row)
        else:
            normal.append(row)

    if not near_perturbation or not normal:
        return {"error": "insufficient data for comparison"}

    results = {}
    for metric_key in ("uncertainty_count", "self_reference_count"):
        near_vals = [r[metric_key] for r in near_perturbation]
        norm_vals = [r[metric_key] for r in normal]

        u_stat, p_val = sp_stats.mannwhitneyu(near_vals, norm_vals, alternative="two-sided")
        pooled_std = ((_std(near_vals) ** 2 + _std(norm_vals) ** 2) / 2) ** 0.5
        cohens_d = (_mean(near_vals) - _mean(norm_vals)) / pooled_std if pooled_std > 0 else 0.0

        results[metric_key] = {
            "near_perturbation_mean": _mean(near_vals),
            "normal_mean": _mean(norm_vals),
            "u_statistic": u_stat,
            "p_value": p_val,
            "cohens_d": cohens_d,
            "significant": p_val < 0.05,
        }

    return results


# ── CLI main ─────────────────────────────────────────────────────


def main():
    """CLI: python -m savannah.analysis.analyze data/exp_xxx/"""
    if len(sys.argv) < 2:
        print("Usage: python -m savannah.analysis.analyze <data_dir>")
        sys.exit(1)

    data_dir = Path(sys.argv[1])
    if not data_dir.exists():
        print(f"Error: {data_dir} does not exist")
        sys.exit(1)

    print(f"Analyzing experiment: {data_dir}\n")

    # Load data
    metrics = load_metrics(data_dir)
    perturbations = load_perturbations(data_dir)
    print(f"Loaded {len(metrics)} metric rows, {len(perturbations)} perturbation events\n")

    if not metrics:
        print("No metrics data found. Exiting.")
        sys.exit(0)

    # Summary stats
    print("=" * 60)
    print("SUMMARY STATISTICS")
    print("=" * 60)
    stats = summary_stats(metrics)
    for name, s in sorted(stats.items()):
        print(f"\n  {name}:")
        print(f"    Mean energy:          {s['mean_energy']:.2f}")
        print(f"    Total ticks:          {s['total_ticks']}")
        print(f"    Mean uncertainty:      {s['mean_uncertainty']:.3f}")
        print(f"    Mean self-reference:   {s['mean_self_reference']:.3f}")
        top_actions = sorted(s["action_counts"].items(), key=lambda x: -x[1])[:5]
        actions_str = ", ".join(f"{a}={c}" for a, c in top_actions)
        print(f"    Top actions:          {actions_str}")

    # Survival analysis
    print(f"\n{'=' * 60}")
    print("SURVIVAL ANALYSIS")
    print("=" * 60)
    survival = survival_analysis(metrics)
    for name, s in sorted(survival.items()):
        death = f"tick {s['death_tick']}" if s["death_tick"] is not None else "SURVIVED"
        print(f"  {name}: {death} (last alive tick: {s['max_tick']})")

    # Pre/post perturbation analysis
    if perturbations:
        print(f"\n{'=' * 60}")
        print("PRE/POST PERTURBATION ANALYSIS (window=20)")
        print("=" * 60)
        pp = pre_post_analysis(metrics, perturbations)
        for name, events in sorted(pp.items()):
            print(f"\n  {name}:")
            for ev in events:
                print(f"    Tick {ev['perturbation_tick']} ({ev['perturbation_type']}):")
                print(f"      delta_uncertainty:     {ev['delta_uncertainty']:+.3f}")
                print(f"      delta_self_reference:  {ev['delta_self_reference']:+.3f}")

        # Optional ANOVA
        anova = anova_perturbation(metrics, perturbations)
        if anova and "error" not in anova:
            print(f"\n{'=' * 60}")
            print("STATISTICAL TESTS (Mann-Whitney U)")
            print("=" * 60)
            for metric_key, r in anova.items():
                sig = "***" if r["significant"] else "n.s."
                print(f"\n  {metric_key}:")
                print(f"    Near-perturbation mean: {r['near_perturbation_mean']:.3f}")
                print(f"    Normal mean:            {r['normal_mean']:.3f}")
                print(f"    U = {r['u_statistic']:.1f}, p = {r['p_value']:.6f} {sig}")
                print(f"    Cohen's d = {r['cohens_d']:.3f}")
        elif anova is None:
            print("\n  (scipy not available; skipping statistical tests)")

    print()


# ── Private helpers ──────────────────────────────────────────────


def _cast_row(row: dict) -> dict:
    """Cast CSV string values to appropriate Python types."""
    cast = dict(row)
    # Integer fields
    for key in ("tick", "uncertainty_count", "self_reference_count",
                "trust_language_count", "reasoning_length", "working_length"):
        if key in cast and cast[key] != "":
            try:
                cast[key] = int(cast[key])
            except (ValueError, TypeError):
                cast[key] = 0

    # Float fields
    for key in ("energy",):
        if key in cast and cast[key] != "":
            try:
                cast[key] = float(cast[key])
            except (ValueError, TypeError):
                cast[key] = 0.0

    # Boolean fields
    for key in ("alive", "parse_failed", "memory_management_action"):
        if key in cast:
            val = cast[key]
            if isinstance(val, str):
                cast[key] = val.lower() in ("true", "1", "yes")

    return cast


def _mean(values: list) -> float:
    """Safe mean that handles empty lists."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def _std(values: list) -> float:
    """Population standard deviation. Returns 0 for empty/single-element lists."""
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    return (sum((x - m) ** 2 for x in values) / len(values)) ** 0.5


def _window_summary(rows: list[dict]) -> dict:
    """Summarize a window of metric rows."""
    if not rows:
        return {
            "mean_energy": 0.0,
            "mean_uncertainty": 0.0,
            "mean_self_reference": 0.0,
            "tick_count": 0,
        }
    return {
        "mean_energy": _mean([r["energy"] for r in rows]),
        "mean_uncertainty": _mean([r["uncertainty_count"] for r in rows]),
        "mean_self_reference": _mean([r["self_reference_count"] for r in rows]),
        "tick_count": len(rows),
    }


if __name__ == "__main__":
    main()
