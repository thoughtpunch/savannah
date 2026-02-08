# Getting Started

How to set up and run your first ILET simulation.

## Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Python | 3.12+ | Simulation engine |
| pyyaml | any | YAML config parsing |
| Claude Code CLI | 1.x+ | Default LLM provider (`claude -p`) |
| Beads (`bd`) | any | Issue tracking for Ralph workflow |

### Install Python dependencies

```bash
pip install pyyaml
```

For analysis (optional, not needed for running simulations):

```bash
pip install pandas scipy matplotlib
```

### Install Claude Code CLI

```bash
npm install -g @anthropic-ai/claude-code
```

Verify: `claude --version` should return a version number. You need an active Anthropic account. For the default `claude_code` provider, a Pro Max subscription eliminates per-inference costs.

### Install Beads

Beads (`bd`) is the issue tracker used by the Ralph autonomous agent loop. See the Beads repository for installation instructions. Verify: `bd --help` should show the beads help text.

Beads is only required if you intend to use the Ralph workflow for autonomous development. It is not required to run simulations.

## Project Structure

After cloning the repository:

```
savannah/
├── CLAUDE.md                  # AI assistant guide
├── IMPLEMENTATION_GUIDE.md    # Full specification
├── savannah/
│   ├── run.py                 # CLI entrypoint
│   ├── config/
│   │   ├── default.yaml       # Base configuration
│   │   └── experiments/       # Experiment-specific overrides
│   ├── src/                   # Simulation engine source
│   ├── data/                  # Runtime output (gitignored)
│   ├── viz/                   # HTML replay viewer
│   └── analysis/              # Statistical analysis scripts
├── scripts/
│   └── ralph/                 # Autonomous agent loop
└── documentation/             # This documentation
```

## Running Your First Test

The quickest way to verify the system works:

```bash
python savannah/run.py --config savannah/config/experiments/baseline.yaml --ticks 20
```

This runs:
- The baseline experiment (no perturbation, no social pressure)
- 20 ticks only (a few minutes wall time)
- Default 12 agents on a 30x30 grid
- Output goes to `savannah/data/exp_{timestamp}/`

Expected output:
- Log messages showing tick progression
- A data directory containing:
  - `agents/` -- one directory per agent with memory files and state
  - `logs/ticks/` -- snapshot JSON files
  - `analysis/metrics.csv` -- metric data for all agents across all ticks

### Common First-Run Issues

**`claude` command not found**: Install Claude Code CLI with `npm install -g @anthropic-ai/claude-code`.

**Timeout errors**: If agents are timing out, check your network connection and Anthropic account status. The default timeout is 30 seconds per inference call.

**Parse failures**: Some parse failures are expected (agents produce variable output formats). The system falls back to `rest` on parse failure. A parse rate above 95% is normal.

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

After a run completes, open the replay viewer:

```bash
# Option 1: Serve the viz directory and load data manually
cd savannah/viz && python -m http.server 8000

# Option 2: Use the --viz flag (if implemented)
python savannah/run.py --replay savannah/data/exp_{timestamp}/ --viz
```

The viewer loads tick snapshot JSON files and renders the grid with agents, food sources, and an interactive timeline scrubber.

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

- Read the [Configuration Guide](configuration.md) to understand all tunable parameters
- Read [Ralph & Beads Workflow](ralph-workflow.md) to use the autonomous development loop
- Read [Experimental Design](experimental-design.md) to understand the factorial structure
- Read [Metrics & Analysis](metrics.md) to understand what the experiment measures
