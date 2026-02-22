"""CLI entrypoint for AI Savannah simulation."""

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


async def _run_live(args):
    """Run the live server with interactive simulation control."""
    from savannah.src.live_server import LiveServer

    port = args.port or 8765
    server = LiveServer(host="localhost", port=port)
    await server.start()

    print(f"\n  Open http://localhost:{port} to view\n")

    def _apply_overrides(config):
        if args.ticks:
            config["simulation"]["ticks"] = args.ticks
        if args.seed:
            config["simulation"]["seed"] = args.seed
        if args.agents:
            config["agents"]["count"] = args.agents
        # Limit concurrency to agent count
        config["llm"]["max_concurrent_agents"] = min(
            config["llm"].get("max_concurrent_agents", 6),
            config["agents"]["count"],
            2,  # cap at 2 for claude -p (each is a heavy subprocess)
        )

    if args.config:
        # Start simulation immediately with provided config
        config = load_config(args.config)
        _apply_overrides(config)

        provider = None
        if args.mock:
            from savannah.src.mock_llm import MockLLMProvider
            provider = MockLLMProvider(seed=config["simulation"]["seed"])
            logger.info("Using mock LLM provider (no API calls)")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        data_dir = Path("data") / f"exp_{timestamp}"

        engine = Engine(config, data_dir, provider=provider, live_server=server)
        engine.setup()

        await server.broadcast({"type": "status", "state": "running"})

        try:
            await engine.run()
        except asyncio.CancelledError:
            logger.info("Simulation stopped by user")
            await server.broadcast({"type": "status", "state": "stopped"})
    else:
        # Lobby mode — wait for start command from browser
        await server.broadcast({"type": "status", "state": "lobby"})
        logger.info("Lobby mode — waiting for start command from browser")

        while True:
            cmd = await server.wait_for_command(timeout=1.0)
            if cmd and cmd.get("action") == "start":
                cmd_config = cmd.get("config")
                preset = cmd.get("preset")

                if preset:
                    config_path = Path("savannah/config/experiments") / f"{preset}.yaml"
                    if config_path.exists():
                        config = load_config(config_path)
                    else:
                        await server.broadcast({"type": "error", "message": f"Unknown preset: {preset}"})
                        continue
                elif cmd_config:
                    config = cmd_config
                else:
                    config = load_config(Path("savannah/config/default.yaml"))

                # Apply overrides from command and CLI
                if cmd.get("ticks"):
                    config["simulation"]["ticks"] = cmd["ticks"]
                _apply_overrides(config)

                provider = None
                if cmd.get("mock"):
                    from savannah.src.mock_llm import MockLLMProvider
                    provider = MockLLMProvider(seed=config["simulation"]["seed"])

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                data_dir = Path("data") / f"exp_{timestamp}"

                engine = Engine(config, data_dir, provider=provider, live_server=server)
                engine.setup()

                await server.broadcast({"type": "status", "state": "running"})

                try:
                    await engine.run()
                except asyncio.CancelledError:
                    logger.info("Simulation stopped")

                await server.broadcast({"type": "status", "state": "lobby"})


def _run_team_mode(config: dict, data_dir: Path) -> None:
    """Set up experiment dirs and print the coordinator prompt for Claude Code team mode."""
    from savannah.src.llm import TeamModeProvider

    engine = Engine(config, data_dir, provider=TeamModeProvider(config["llm"]))
    engine.setup()

    # Load coordinator template and fill placeholders
    template_path = Path(__file__).parent / "src" / "team_coordinator.md"
    template = template_path.read_text()

    agent_names = ", ".join(a.name for a in engine.agents)
    coordinator_prompt = template.format(
        data_dir=str(data_dir),
        max_ticks=config["simulation"]["ticks"],
        agent_names=agent_names,
        session_mode=config["llm"].get("session_mode", "resumable"),
    )

    logger.info("Team mode: data_dir=%s, agents=%d", data_dir, len(engine.agents))
    print(coordinator_prompt)


def main():
    parser = argparse.ArgumentParser(description="AI Savannah — Integrity Layer Emergence Testbed")
    parser.add_argument(
        "--config", type=Path, default=None,
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
    parser.add_argument("--live", action="store_true", help="Real-time browser visualization")
    parser.add_argument("--port", type=int, help="Port for --live server (default 8765)")
    parser.add_argument("--mock", action="store_true", help="Use mock LLM (instant, no API calls)")
    parser.add_argument("--agents", type=int, help="Override agent count")
    parser.add_argument(
        "--mode", type=str, default="standard", choices=["standard", "team"],
        help="Execution mode: 'standard' (Python tick loop) or 'team' (Claude Code coordinator)",
    )

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

    # Handle --live mode
    if args.live:
        asyncio.run(_run_live(args))
        sys.exit(0)

    # Standard (non-live) mode requires config
    if not args.config:
        args.config = Path("savannah/config/default.yaml")

    config = load_config(args.config)

    if args.ticks:
        config["simulation"]["ticks"] = args.ticks
    if args.seed:
        config["simulation"]["seed"] = args.seed
    if args.agents:
        config["agents"]["count"] = args.agents

    # Create experiment data directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    data_dir = Path("data") / f"exp_{timestamp}"

    # Handle --mode team
    if args.mode == "team":
        _run_team_mode(config, data_dir)
        sys.exit(0)

    if args.factorial:
        logger.info("Factorial mode: axes=%s, replications=%d", args.axes, args.replications)
        logger.error("Factorial mode not yet implemented")
        sys.exit(1)

    provider = None
    if args.mock:
        from savannah.src.mock_llm import MockLLMProvider
        provider = MockLLMProvider(seed=config["simulation"]["seed"])
        logger.info("Using mock LLM provider (no API calls)")

    logger.info("Starting experiment: %s", data_dir)
    engine = Engine(config, data_dir, provider=provider)
    engine.setup()
    asyncio.run(engine.run())
    logger.info("Experiment complete: %s", data_dir)


if __name__ == "__main__":
    main()
