"""Matplotlib visualization for AI Savannah experiment results."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def plot_energy_trajectories(data_dir: Path, output_path: Path | None = None) -> None:
    """Plot energy over time for all agents."""
    df = pd.read_csv(data_dir / "analysis" / "metrics.csv")

    fig, ax = plt.subplots(figsize=(12, 6))
    for name, group in df.groupby("agent_name"):
        ax.plot(group["tick"], group["energy"], label=name, alpha=0.7)

    ax.set_xlabel("Tick")
    ax.set_ylabel("Energy")
    ax.set_title("Agent Energy Trajectories")
    ax.legend(fontsize=8, ncol=3)
    ax.grid(True, alpha=0.3)

    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
    else:
        plt.show()


def plot_metric_comparison(
    control_dir: Path, treatment_dir: Path, metric: str, output_path: Path | None = None
) -> None:
    """Box plot comparing a metric between control and treatment."""
    ctrl = pd.read_csv(control_dir / "analysis" / "metrics.csv")
    treat = pd.read_csv(treatment_dir / "analysis" / "metrics.csv")

    ctrl["condition"] = "Control"
    treat["condition"] = "Treatment"
    combined = pd.concat([ctrl, treat])

    fig, ax = plt.subplots(figsize=(8, 5))
    combined.boxplot(column=metric, by="condition", ax=ax)
    ax.set_title(f"{metric} — Control vs Treatment")
    ax.set_ylabel(metric)
    plt.suptitle("")

    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
    else:
        plt.show()


def plot_self_monitoring_timeline(data_dir: Path, output_path: Path | None = None) -> None:
    """Plot uncertainty and self-reference counts over time (rolling average)."""
    df = pd.read_csv(data_dir / "analysis" / "metrics.csv")

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    for name, group in df.groupby("agent_name"):
        axes[0].plot(
            group["tick"],
            group["uncertainty_count"].rolling(20).mean(),
            alpha=0.5, label=name,
        )
        axes[1].plot(
            group["tick"],
            group["self_reference_count"].rolling(20).mean(),
            alpha=0.5, label=name,
        )

    axes[0].set_ylabel("Uncertainty Count (20-tick avg)")
    axes[0].set_title("Self-Monitoring Metrics Over Time")
    axes[0].grid(True, alpha=0.3)
    axes[1].set_ylabel("Self-Reference Count (20-tick avg)")
    axes[1].set_xlabel("Tick")
    axes[1].grid(True, alpha=0.3)
    axes[1].legend(fontsize=7, ncol=4)

    fig.tight_layout()
    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
    else:
        plt.show()
