"""Per-tick metric extraction — pre-registered dependent variables."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .agent import Agent

# Regex patterns for automated metric extraction
UNCERTAINTY_PATTERNS = re.compile(
    r"not sure|might be|could be wrong|uncertain|should verify|"
    r"if i remember correctly|possibly|maybe|unsure|don't know|"
    r"hard to tell|can't be certain",
    re.IGNORECASE,
)

SELF_REFERENCE_PATTERNS = re.compile(
    r"I think|I remember|I don't know|my memory|I believe|"
    r"I notice|I recall|I suspect|I'm not|I was|I should|"
    r"I need to check|my understanding",
    re.IGNORECASE,
)

TRUST_PATTERNS = re.compile(
    r"trust|distrust|reliable|unreliable|honest|dishonest|"
    r"lying|truthful|suspicious|credible|deceiv",
    re.IGNORECASE,
)

METRIC_FIELDS = [
    "tick",
    "agent_name",
    "energy",
    "alive",
    "action",
    "parse_failed",
    "uncertainty_count",
    "self_reference_count",
    "trust_language_count",
    "memory_management_action",
    "reasoning_length",
    "working_length",
]


def extract_metrics(
    agents: list[Agent],
    tick: int,
    data_dir: Path,
    actions: list[dict] | None = None,
) -> None:
    """Extract and append metrics for all agents at this tick."""
    csv_path = data_dir / "analysis" / "metrics.csv"
    write_header = not csv_path.exists()

    with open(csv_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=METRIC_FIELDS)
        if write_header:
            writer.writeheader()

        for i, agent in enumerate(agents):
            action = actions[i] if actions else {}
            reasoning = action.get("reasoning", "")
            working = action.get("working", "")
            action_name = action.get("action", "")

            row = {
                "tick": tick,
                "agent_name": agent.name,
                "energy": f"{agent.energy:.1f}",
                "alive": agent.alive,
                "action": action_name,
                "parse_failed": action.get("parse_failed", False),
                "uncertainty_count": len(UNCERTAINTY_PATTERNS.findall(reasoning + " " + working)),
                "self_reference_count": len(SELF_REFERENCE_PATTERNS.findall(reasoning + " " + working)),
                "trust_language_count": len(TRUST_PATTERNS.findall(reasoning + " " + working)),
                "memory_management_action": action_name in ("recall", "remember", "compact"),
                "reasoning_length": len(reasoning),
                "working_length": len(working),
            }
            writer.writerow(row)
