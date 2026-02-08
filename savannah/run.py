"""CLI entrypoint for ILET simulation."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

import yaml

from savannah.src.engine import Engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def load_config(config_path: Path) -> dict:
    """Load YAML config with inheritance support."""
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Handle inherits
    if "inherits" in config:
        base_name = config.pop("inherits")
        base_path = config_path.parent.parent / f"{base_name}.yaml"
        base = load_config(base_path)
        config = _deep_merge(base, config)

    return config


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def main():
    parser = argparse.ArgumentParser(description="ILET — Integrity Layer Emergence Testbed")
    parser.add_argument(
        "--config", type=Path, default=Path("config/default.yaml"),
        help="Path to experiment config YAML",
    )
    parser.add_argument("--ticks", type=int, help="Override tick count")
    parser.add_argument("--seed", type=int, help="Override random seed")
    parser.add_argument("--factorial", action="store_true", help="Run full factorial design")
    parser.add_argument(
        "--axes", type=str, default="perturbation,session_mode",
        help="Factorial axes (comma-separated)",
    )
    parser.add_argument("--replications", type=int, default=5, help="Replications per condition")
    parser.add_argument("--resume", type=Path, help="Resume interrupted run from data dir")
    parser.add_argument("--replay", type=Path, help="Replay a completed run")
    parser.add_argument("--inspect", type=Path, help="Inspect a completed run's data directory")
    parser.add_argument("--tick", type=int, default=0, help="Tick to inspect (with --inspect)")
    parser.add_argument("--agent", type=str, help="Agent name to filter (with --inspect or --replay)")
    parser.add_argument("--tick-range", type=str, help="Tick range for replay (e.g., 100-200)")
    parser.add_argument("--viz", action="store_true", help="Launch visualization server")

    args = parser.parse_args()

    # Handle --replay mode
    if args.replay:
        from savannah.src.replay import replay

        tick_range = None
        if args.tick_range:
            parts = args.tick_range.split("-")
            tick_range = (int(parts[0]), int(parts[1]))

        replay(args.replay, agent_filter=args.agent, tick_range=tick_range)
        sys.exit(0)

    # Handle --inspect mode
    if args.inspect:
        from savannah.src.inspect_cmd import inspect

        inspect(args.inspect, args.tick, args.agent)
        sys.exit(0)

    config = load_config(args.config)

    if args.ticks:
        config["simulation"]["ticks"] = args.ticks
    if args.seed:
        config["simulation"]["seed"] = args.seed

    # Create experiment data directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    data_dir = Path("data") / f"exp_{timestamp}"

    if args.factorial:
        logger.info("Factorial mode: axes=%s, replications=%d", args.axes, args.replications)
        # TODO: implement factorial runner
        logger.error("Factorial mode not yet implemented")
        sys.exit(1)

    logger.info("Starting experiment: %s", data_dir)
    engine = Engine(config, data_dir)
    engine.setup()
    asyncio.run(engine.run())
    logger.info("Experiment complete: %s", data_dir)


if __name__ == "__main__":
    main()
