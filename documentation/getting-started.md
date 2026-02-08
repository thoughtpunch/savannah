# Getting Started

How to set up and run your first ILET simulation.

## Quick Start

The fastest path from clone to running simulation:

```bash
git clone <repo-url>
cd savannah
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m savannah.run --live --mock
# Open http://localhost:8765 in browser
```

This launches a real-time browser visualization with a mock LLM (no API calls needed). Select a preset experiment in the browser lobby to begin.

## Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Python | 3.12+ | Simulation engine |
| Claude Code CLI | 1.x+ | Default LLM provider (`claude -p`) -- only needed for real (non-mock) runs |
| Beads (`bd`) | any | Issue tracking for Ralph workflow (optional) |

### Install with pip (recommended)

The project uses `pyproject.toml` for dependency management. All core dependencies (pyyaml, websockets) are installed automatically:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

For development (includes pytest, ruff):

```bash
pip install -e ".[dev]"
```

For analysis (pandas, scipy, matplotlib):

```bash
pip install -e ".[analysis]"
```

### Install Claude Code CLI (for real LLM runs only)

```bash
npm install -g @anthropic-ai/claude-code
```

Verify: `claude --version` should return a version number. You need an active Anthropic account. For the default `claude_code` provider, a Pro Max subscription eliminates per-inference costs.

This is **not** needed if you are using `--mock` mode for testing or demonstration.

### Install Beads (optional)

Beads (`bd`) is the issue tracker used by the Ralph autonomous agent loop. See the Beads repository for installation instructions. Verify: `bd --help` should show the beads help text.

Beads is only required if you intend to use the Ralph workflow for autonomous development. It is not required to run simulations.

## Project Structure

After cloning the repository:

```
savannah/
├── CLAUDE.md                  # AI assistant guide
├── IMPLEMENTATION_GUIDE.md    # Full specification
├── pyproject.toml             # Package config (pip install -e .)
├── savannah/
│   ├── run.py                 # CLI entrypoint
│   ├── config/
│   │   ├── default.yaml       # Base configuration
│   │   └── experiments/       # Preset experiment configs
│   │       ├── baseline.yaml
│   │       ├── perturbation.yaml
│   │       ├── social.yaml
│   │       └── full_pressure.yaml
│   ├── src/
│   │   ├── engine.py          # Simulation loop
│   │   ├── live_server.py     # WebSocket server for --live mode
│   │   └── ...                # Other engine modules
│   ├── viz/
│   │   ├── live.html          # Real-time browser UI (served by live_server.py)
│   │   └── index.html         # Static replay viewer
│   ├── data/                  # Runtime output (gitignored)
│   ├── tests/                 # Test suite
│   └── analysis/              # Statistical analysis scripts
├── scripts/
│   └── ralph/                 # Autonomous agent loop
└── documentation/             # This documentation
```

## Running Your First Test

### Option A: Live visualization with mock LLM (recommended for first run)

```bash
python -m savannah.run --live --mock
```

Open `http://localhost:8765` in your browser. You will see a lobby screen with four preset experiments: Baseline, Perturbation, Social Pressure, and Full Pressure. Click any preset card to start. The `--mock` flag uses an instant mock LLM that requires no API calls, so the simulation runs in seconds.

To skip the lobby and start immediately with a specific config:

```bash
python -m savannah.run --live --mock --config savannah/config/experiments/baseline.yaml --ticks 100
```

### Option B: Headless CLI run (with real LLM)

```bash
python -m savannah.run --config savannah/config/experiments/baseline.yaml --ticks 20
```

This runs:
- The baseline experiment (no perturbation, no social pressure)
- 20 ticks only (a few minutes wall time)
- Default 12 agents on a 30x30 grid
- Output goes to `data/exp_{timestamp}/`

Expected output:
- Log messages showing tick progression
- A data directory containing:
  - `agents/` -- one directory per agent with memory files and state
  - `logs/ticks/` -- snapshot JSON files
  - `analysis/metrics.csv` -- metric data for all agents across all ticks

### Common First-Run Issues

**`claude` command not found**: Install Claude Code CLI with `npm install -g @anthropic-ai/claude-code`. Not needed for `--mock` mode.

**Timeout errors**: If agents are timing out, check your network connection and Anthropic account status. The default timeout is 30 seconds per inference call. Use `--mock` for instant responses without API calls.

**Parse failures**: Some parse failures are expected (agents produce variable output formats). The system falls back to `rest` on parse failure. A parse rate above 95% is normal.

**Port conflict**: If port 8765 is in use, specify a different port: `--port 9000`.

## Running a Perturbation Experiment

To test the core hypothesis:

```bash
python savannah/run.py --config savannah/config/experiments/perturbation.yaml --ticks 200
```

This enables memory corruption at a 5% rate per agent per tick, starting at tick 100. The first 100 ticks are a baseline window with no perturbation.

## Running the Full Factorial

For the Phase 1 experimental design (4 conditions, 5 replications each):

```bash
python savannah/run.py --factorial --axes perturbation,session_mode --replications 5
```

This is a long run. See [Configuration Guide](configuration.md) for how to tune tick counts and other parameters. With the default 5000 ticks, 12 agents, and 6-way parallelism on Claude Code, expect roughly 4 days for the full factorial with 5 replications.

For a shorter validation run:

```bash
python savannah/run.py --factorial --axes perturbation,session_mode --replications 2 --ticks 500
```

## Visualization

### Real-time (live mode)

Use `--live` to watch the simulation in your browser as it runs:

```bash
python -m savannah.run --live --config savannah/config/experiments/baseline.yaml
```

Open `http://localhost:8765`. The browser UI shows a thought stream, minimap, sparkline charts, agent list, and event toasts in real time. See [Live Visualization](live-visualization.md) for the full guide.

### Replay past runs

From the live server lobby, click "View Past Runs" to browse and replay completed experiments with a timeline slider.

You can also replay from the CLI:

```bash
python -m savannah.run --replay data/exp_{timestamp}/
```

### Static replay viewer

For offline viewing without the live server:

```bash
cd savannah/viz && python -m http.server 8000
```

The static viewer loads tick snapshot JSON files and renders the grid with agents, food sources, and an interactive timeline scrubber.

## Examining Results

### Metrics CSV

The primary data output is `analysis/metrics.csv` inside the experiment data directory. Each row is one agent at one tick, with columns for:

- Energy, alive status, action taken
- Uncertainty language count, self-reference count, trust language count
- Whether the action was a memory management action
- Reasoning and working note lengths
- Parse failure flag

### Agent Memory Files

Browse `agents/{name}/memory/` to see what agents have written. Compare files between perturbation and baseline conditions to observe differences in self-model complexity and memory management patterns.

### Perturbation Log

When perturbation is enabled, `logs/perturbations.jsonl` records every corruption event with before/after text and the transform applied.

## Next Steps

- Read the [Live Visualization Guide](live-visualization.md) for the full browser UI reference
- Read the [Configuration Guide](configuration.md) to understand all tunable parameters
- Read [Ralph & Beads Workflow](ralph-workflow.md) to use the autonomous development loop
- Read [Experimental Design](experimental-design.md) to understand the factorial structure
- Read [Metrics & Analysis](metrics.md) to understand what the experiment measures
