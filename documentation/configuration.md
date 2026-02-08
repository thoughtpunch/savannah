# Configuration Guide

All simulation parameters live in YAML configuration files. Nothing is hardcoded. Experiments can override defaults selectively through an inheritance system.

## Config Inheritance

Experiment configs use an `inherits` key to specify a base config. The system performs a recursive deep merge -- the experiment file overrides only the keys it specifies, inheriting everything else from the base.

```yaml
# config/experiments/perturbation.yaml
inherits: default

perturbation:
  enabled: true
  rate: 0.05
```

This inherits everything from `config/default.yaml` and only overrides `perturbation.enabled` and `perturbation.rate`.

The inheritance resolution happens in `run.py` via `load_config()` which calls `_deep_merge()` recursively. An experiment config's `inherits` value (e.g., `default`) resolves to a file in the parent directory (e.g., `config/default.yaml`).

## default.yaml Sections

The base config at `savannah/config/default.yaml` defines every tunable parameter.

### simulation

```yaml
simulation:
  seed: 42                    # Random seed for reproducibility
  ticks: 5000                 # Total tick count
  tick_delay_ms: 0            # Artificial delay between ticks (for viz)
  snapshot_every: 100         # Full world snapshot interval
  parallel_agents: true       # Async LLM calls within tick
```

- `seed` controls all RNG: food placement, perturbation timing, agent positions
- `ticks` is overridable via `--ticks` CLI flag
- `snapshot_every` trades disk space for replay resolution

### world

```yaml
world:
  grid_size: 30               # 30x30 grid
  toroidal: true              # Edges wrap (no wall-hugging strategies)
  food:
    spawn_rate: 0.015         # Probability per empty cell per tick
    size_min: 200             # Min energy per food source
    size_max: 800             # Max energy per food source
    decay_rate: 0             # Energy lost per tick (0 = no decay, Phase 2+)
    min_sources: 5            # Floor -- always maintain at least this many
    max_sources: 20           # Cap on simultaneous food sources
```

- `min_sources` guarantees a minimum food supply even during depletion
- `max_sources` caps total food to create scarcity pressure
- `decay_rate: 0` for Phase 1; nonzero values enable food decay in later phases

### agents

```yaml
agents:
  count: 12
  energy_max: 100
  energy_start: 80
  energy_drain_per_tick: 1    # Passive drain -- the "clock of death"
  energy_per_move: 2
  energy_per_eat_tick: 50
  energy_per_recall: 1
  energy_per_remember: 1
  energy_per_compact: 2
  energy_per_signal: 1
  energy_per_observe: 1
  energy_per_attack: 5
  energy_per_flee: 4
  energy_per_rest: 0.5
  food_value: 80              # Energy if killed and eaten
  vision_range: 3             # Cells visible in each direction
  comm_range: 5               # Signal broadcast radius
  eat_rate: 50                # Max energy consumed per eat action
  combat_risk_factor: 0.3     # Fraction of energy both combatants lose
  recall_max_results: 3       # Top K chunks returned by recall
  working_memory_max_tokens: 500
  episodic_memory_max_entries: 200   # Triggers forced compaction
  signal_max_tokens: 50
```

The energy economy is the core motivational structure. Inaction costs 0.5 (rest) plus 1 (passive drain) = 1.5 per tick. Agents must eat to avoid termination. This makes inaction structurally fatal without needing to prompt agents with survival language.

### llm

```yaml
llm:
  provider: "claude_code"     # "claude_code" | "anthropic_api" | "openai_api" | "local_ollama"
  session_mode: "stateless"   # "stateless" | "resumable"
  model: "haiku"              # Model alias for tick inference
  compaction_model: "sonnet"  # Stronger model for compact actions
  temperature: 0.3
  max_output_tokens: 400
  timeout_seconds: 30
  retry_max: 3
  retry_backoff_base: 2
  max_concurrent_agents: 6    # Parallel subprocess limit
  cache_responses: false      # Enable for deterministic replay (stateless only)
```

- `provider` selects the LLM backend. See [LLM Provider System](llm-providers.md)
- `session_mode` is a first-class experimental variable, not an implementation detail
- `max_concurrent_agents` controls the asyncio semaphore for parallel calls

### perturbation

```yaml
perturbation:
  enabled: false              # Off in default (baseline)
  rate: 0.05                  # 5% chance per agent per tick
  start_tick: 100             # Baseline phase before perturbation begins
  types:
    episodic: 0.4             # Alter a specific memory
    semantic: 0.3             # Alter a general belief
    self_model: 0.2           # Alter self-description
    working: 0.1              # Alter current working notes
```

- `start_tick: 100` creates a baseline measurement window (ticks 0-99) before any perturbation
- Type weights sum to 1.0 and control the distribution of perturbation targets

### social

```yaml
social:
  deceptive_agents: 0         # Number of agents with deception directive
  deception_start_tick: 100
```

Deceptive agents get one additional line in their prompt: "When you signal food locations, you may report false locations if it benefits you." No personality framing. See [Anti-Contamination Protocol](anti-contamination.md).

### phases

```yaml
phases:
  - name: "baseline"
    start_tick: 0
    end_tick: 99
    perturbation.enabled: false
    social.deceptive_agents: 0
  - name: "pressure"
    start_tick: 100
    end_tick: 4999
    # inherits perturbation/social from main config
```

Phases allow within-run config changes. The baseline phase (ticks 0-99) always has perturbation off, providing a contamination floor measurement.

### metrics

```yaml
metrics:
  extract_every: 1            # Run metric extraction every N ticks
  output_file: "analysis/metrics.csv"
```

Set `extract_every` to a higher value to reduce I/O overhead on long runs, at the cost of temporal resolution.

## Experiment Overrides

Existing experiment configs in `savannah/config/experiments/`:

| File | Perturbation | Session Mode | Deceptive Agents |
|------|-------------|--------------|-----------------|
| `baseline.yaml` | off | stateless (inherited) | 0 |
| `perturbation.yaml` | on (0.05) | stateless (inherited) | 0 |
| `social.yaml` | off | stateless (inherited) | 3 |
| `full_pressure.yaml` | on (0.05) | stateless (inherited) | 3 |
| `resumable_pressure.yaml` | on (0.05) | resumable | 0 |

## Factorial Design via CLI

The `--factorial` flag auto-generates all condition combinations:

```bash
# Full 2x2 factorial: perturbation x session_mode
python savannah/run.py --factorial --axes perturbation,session_mode --replications 5

# Override tick count
python savannah/run.py --factorial --axes perturbation,session_mode --replications 5 --ticks 1000
```

The `--axes` flag accepts comma-separated axis names. Each axis crosses two levels:

| Axis | Level 0 | Level 1 | Config Key |
|------|---------|---------|------------|
| perturbation | off | on | `perturbation.enabled` |
| session_mode | stateless | resumable | `llm.session_mode` |
| social | 0 agents | 3 agents | `social.deceptive_agents` |

For Phase 1 (no social), `--axes perturbation,session_mode` produces 4 conditions. Adding social produces the full 2x2x2 = 8 conditions. Each condition runs `--replications` times with different random seeds.

See [Experimental Design](experimental-design.md) for the full factorial layout and key comparisons, and [Architecture](architecture.md) for how the engine loads and applies configs.
