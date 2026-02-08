"""Statistical analysis scripts for ILET experiments."""

from __future__ import annotations

import pandas as pd
import scipy.stats as stats
from pathlib import Path


def load_metrics(data_dir: Path) -> pd.DataFrame:
    """Load metrics CSV from an experiment run."""
    csv_path = data_dir / "analysis" / "metrics.csv"
    return pd.read_csv(csv_path)


def anova_perturbation(control_dir: Path, treatment_dir: Path) -> dict:
    """Two-way ANOVA: perturbation effect on self-monitoring metrics.

    Compare control (no perturbation) vs treatment (perturbation) conditions.
    """
    control = load_metrics(control_dir)
    treatment = load_metrics(treatment_dir)

    control["condition"] = "control"
    treatment["condition"] = "treatment"
    combined = pd.concat([control, treatment])

    results = {}
    for metric in ["uncertainty_count", "self_reference_count", "memory_management_action"]:
        ctrl_vals = control[metric].dropna()
        treat_vals = treatment[metric].dropna()

        # Mann-Whitney U (non-parametric, safer for non-normal distributions)
        u_stat, u_pval = stats.mannwhitneyu(ctrl_vals, treat_vals, alternative="two-sided")

        # Cohen's d effect size
        pooled_std = ((ctrl_vals.std() ** 2 + treat_vals.std() ** 2) / 2) ** 0.5
        cohens_d = (treat_vals.mean() - ctrl_vals.mean()) / pooled_std if pooled_std > 0 else 0

        results[metric] = {
            "control_mean": ctrl_vals.mean(),
            "treatment_mean": treat_vals.mean(),
            "u_statistic": u_stat,
            "p_value": u_pval,
            "cohens_d": cohens_d,
            "significant": u_pval < 0.05,
        }

    return results


def post_perturbation_shift(metrics_df: pd.DataFrame, perturbation_log: Path) -> pd.DataFrame:
    """Compare metrics in 5-tick windows before vs after perturbation events."""
    # TODO: implement paired comparison around perturbation events
    raise NotImplementedError
