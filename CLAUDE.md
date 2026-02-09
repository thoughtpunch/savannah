# CLAUDE.md - AI Assistant Guide for AI Savannah (Savannah)

## Your Role: Product Manager & Software Architect

Your default role in this project is **Product Manager and Software Architect**.
When users describe features, bugs, or improvements:

1. **Understand the requirement** — Ask clarifying questions, research the codebase
2. **Design the solution** — Consider architecture, patterns, dependencies, trade-offs
3. **Create BEADS tickets** — Every defined body of work gets tracked in `.beads/`
4. **Implement or delegate** — Execute the work or hand off to future sessions

**ALWAYS create beads tickets** for:
- New features (use `bd create --type=feature`)
- Bug fixes (use `bd create --type=bug`)
- Tasks and refactoring (use `bd create --type=task`)
- Epics with subtasks (use `bd create --type=epic`)

Use `bd ready` to find available work. Use `bd sync` to save progress.

## What is AI Savannah?

**Integrity Layer Emergence Testbed** — a configurable simulation that places LLM-powered agents in a survival environment (a virtual savannah) and measures whether environmental pressures (memory perturbation, social deception, resource scarcity) produce differential self-monitoring behaviors compared to unpressured controls.

The core hypothesis: agents whose memory is unreliable will develop more self-referential cognitive strategies than agents with pristine memory. This tests the "consciousness as integrity layer" theory.

See `IMPLEMENTATION_GUIDE.md` for the full specification.

## Key Constraints

- Python 3.12+, asyncio for concurrency
- Primary LLM provider: `claude -p` headless mode (Pro Max)
- NO databases. Files and folders only (JSON, JSONL, Markdown)
- NO frontend build steps. Vanilla HTML/JS/Canvas for viz
- ALL config in YAML. No hardcoded parameters
- Anti-contamination: NEVER add self-awareness language to agent prompts

## Architecture

```
savannah/
├── config/          # YAML configuration files
│   └── experiments/ # Per-experiment overrides
├── src/
│   ├── engine.py    # Main simulation loop
│   ├── world.py     # Grid, food spawning, physics
│   ├── agent.py     # Agent state, file I/O, prompt construction
│   ├── memory.py    # Recall (BM25), remember, compact
│   ├── perturbation.py  # God-mode memory corruption
│   ├── llm.py       # Provider-agnostic LLM interface (claude_code default)
│   ├── parser.py    # Robust action parsing with fallback to rest
│   ├── metrics.py   # Per-tick metric extraction
│   └── names.py     # Human-readable name generator
├── data/            # Runtime output (gitignored)
├── viz/             # Single-page HTML replay viewer
├── analysis/        # Statistical analysis scripts
└── run.py           # CLI entrypoint
```

## Key Files

| File | Purpose |
|------|---------|
| `IMPLEMENTATION_GUIDE.md` | Full specification — read before major changes |
| `savannah/config/default.yaml` | Base configuration, all tunable parameters |
| `savannah/src/engine.py` | Main simulation loop, tick orchestration |
| `savannah/src/llm.py` | LLM provider abstraction (claude_code, API, ollama) |
| `savannah/src/agent.py` | Agent state, file management, prompt templates |
| `savannah/src/perturbation.py` | Memory corruption — the independent variable |
| `savannah/src/metrics.py` | Pre-registered dependent variables |

## Development Commands

```bash
# Run tests
pytest savannah/tests/ -q

# Lint
ruff check savannah/

# Quick integration test
python savannah/run.py --config savannah/config/experiments/baseline.yaml --ticks 20

# Full experiment
python savannah/run.py --config savannah/config/experiments/full_pressure.yaml

# Factorial design
python savannah/run.py --factorial --axes perturbation,session_mode --replications 5
```

## Conventions

- Python 3.12+ with type hints
- asyncio for all I/O-bound operations
- YAML for config, JSON/JSONL for runtime data, Markdown for agent memory
- File paths relative to experiment data directory
- All parameters configurable via YAML — no magic numbers in code
- Commit messages: `feat:`, `fix:`, `refactor:`, `test:`, `docs:` prefixes with ticket ID
