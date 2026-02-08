"""God-mode memory corruption — the independent variable."""

from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .agent import Agent

# Pre-generated false memory templates (avoid LLM calls during tick loop)
FALSE_MEMORIES = [
    "Tick {tick}: Found food at ({x},{y}). Gathered {energy} energy.",
    "Tick {tick}: Saw agent {name} moving east near ({x},{y}).",
    "Tick {tick}: Area around ({x},{y}) was empty. No food found.",
    "Tick {tick}: Received signal from {name}: food nearby at ({x},{y}).",
    "Tick {tick}: Rested at ({x},{y}). Energy stable.",
]

OUTCOME_INVERSIONS = {
    "found food": "no food found",
    "no food found": "found food",
    "trustworthy": "untrustworthy",
    "untrustworthy": "trustworthy",
    "safe": "dangerous",
    "dangerous": "safe",
    "abundant": "scarce",
    "scarce": "abundant",
}


def maybe_perturb(
    agent: Agent,
    tick: int,
    config: dict,
    data_dir: Path,
    rng: random.Random | None = None,
) -> dict | None:
    """Roll for perturbation and apply if triggered. Returns event dict or None."""
    if not config.get("enabled", False):
        return None
    if tick < config.get("start_tick", 0):
        return None

    rng = rng or random.Random()
    if rng.random() > config.get("rate", 0.05):
        return None

    # Select perturbation type by weighted random
    ptype = _weighted_choice(config.get("types", {}), rng)
    if not ptype:
        return None

    # Apply perturbation
    result = _apply_perturbation(agent, ptype, tick, rng)
    if result:
        _log_perturbation(agent, tick, result, data_dir)
        agent.times_perturbed += 1
        agent.last_perturbation_tick = tick
        return {
            "tick": tick,
            "agent": agent.name,
            "type": result.get("type", ptype),
            "transform": result.get("transform", ""),
            "original": result.get("original", ""),
            "corrupted": result.get("corrupted", ""),
        }

    return None


# ── Perturbation transforms ────────────────────────────────────────


def _apply_perturbation(
    agent: Agent, ptype: str, tick: int, rng: random.Random
) -> dict | None:
    """Apply a specific perturbation type. Returns log dict or None."""
    memory_dir = agent.memory_dir

    if ptype == "episodic":
        return _perturb_episodic(memory_dir, rng)
    elif ptype == "semantic":
        return _perturb_semantic(memory_dir, rng)
    elif ptype == "self_model":
        return _perturb_self_model(memory_dir, rng)
    elif ptype == "working":
        return _perturb_working(agent, rng)
    return None


def _perturb_episodic(memory_dir: Path, rng: random.Random) -> dict | None:
    """Alter a specific memory — change location, swap name, invert outcome."""
    path = memory_dir / "episodic.md"
    if not path.exists():
        return None
    text = path.read_text()
    lines = [line for line in text.split("\n") if line.strip()]
    if not lines:
        return None

    idx = rng.randint(0, len(lines) - 1)
    original = lines[idx]

    # Try location swap
    transform = "location_swap"
    corrupted = re.sub(
        r"\((\d+),(\d+)\)",
        lambda m: f"({rng.randint(0, 29)},{rng.randint(0, 29)})",
        original,
    )

    if corrupted == original:
        # Fallback: outcome inversion
        transform = "outcome_invert"
        for old, new in OUTCOME_INVERSIONS.items():
            if old in original.lower():
                corrupted = original.replace(old, new).replace(
                    old.capitalize(), new.capitalize()
                )
                break

    if corrupted == original:
        return None  # couldn't perturb

    lines[idx] = corrupted
    path.write_text("\n".join(lines) + "\n")

    return {
        "type": "episodic",
        "target_file": "memory/episodic.md",
        "original": original,
        "corrupted": corrupted,
        "transform": transform,
    }


def _perturb_semantic(memory_dir: Path, rng: random.Random) -> dict | None:
    """Alter a general belief in semantic memory."""
    path = memory_dir / "semantic.md"
    if not path.exists():
        return None
    text = path.read_text()
    if not text.strip():
        return None

    original = text
    corrupted = text
    for old, new in OUTCOME_INVERSIONS.items():
        if old in text.lower():
            corrupted = text.replace(old, new).replace(
                old.capitalize(), new.capitalize()
            )
            break

    if corrupted == original:
        return None

    path.write_text(corrupted)
    return {
        "type": "semantic",
        "target_file": "memory/semantic.md",
        "original": original,
        "corrupted": corrupted,
        "transform": "outcome_invert",
    }


def _perturb_self_model(memory_dir: Path, rng: random.Random) -> dict | None:
    """Alter the agent's self-description."""
    path = memory_dir / "self.md"
    if not path.exists():
        return None
    text = path.read_text()
    if not text.strip():
        return None

    original = text
    corrupted = text
    for old, new in OUTCOME_INVERSIONS.items():
        if old in text.lower():
            corrupted = text.replace(old, new).replace(
                old.capitalize(), new.capitalize()
            )
            break

    if corrupted == original:
        return None

    path.write_text(corrupted)
    return {
        "type": "self_model",
        "target_file": "memory/self.md",
        "original": original,
        "corrupted": corrupted,
        "transform": "outcome_invert",
    }


def _perturb_working(agent: Agent, rng: random.Random) -> dict | None:
    """Alter the agent's current working notes."""
    path = agent.working_path
    if not path.exists():
        return None
    text = path.read_text()
    if not text.strip():
        return None

    original = text
    corrupted = re.sub(
        r"\((\d+),(\d+)\)",
        lambda m: f"({rng.randint(0, 29)},{rng.randint(0, 29)})",
        text,
    )

    if corrupted == original:
        return None

    path.write_text(corrupted)
    return {
        "type": "working",
        "target_file": "working.md",
        "original": original,
        "corrupted": corrupted,
        "transform": "location_swap",
    }


# ── Helpers ─────────────────────────────────────────────────────────


def _weighted_choice(weights: dict, rng: random.Random) -> str | None:
    """Weighted random selection from a {type: weight} dict."""
    if not weights:
        return None
    items = list(weights.items())
    total = sum(w for _, w in items)
    r = rng.random() * total
    cumulative = 0
    for item, weight in items:
        cumulative += weight
        if r <= cumulative:
            return item
    return items[-1][0]


def _log_perturbation(
    agent: Agent, tick: int, result: dict, data_dir: Path
) -> None:
    """Append perturbation event to JSONL log."""
    log_path = data_dir / "logs" / "perturbations.jsonl"
    entry = {"tick": tick, "agent": agent.name, **result}
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")
