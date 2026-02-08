# Architecture

System design overview for ILET (Integrity Layer Emergence Testbed).

## Directory Layout

```
savannah/
├── config/                    # YAML configuration files
│   ├── default.yaml           # Base configuration -- all tunable parameters
│   └── experiments/           # Preset experiment configs
│       ├── baseline.yaml      # No pressure, calibration
│       ├── perturbation.yaml  # Memory corruption only
│       ├── social.yaml        # Deception only
│       ├── full_pressure.yaml # Both pressures active
│       └── resumable_pressure.yaml  # Resumable + perturbation
│
├── src/
│   ├── engine.py              # Main simulation loop, tick orchestration
│   ├── world.py               # Grid, food spawning, toroidal wrapping
│   ├── agent.py               # Agent state, file I/O, prompt construction
│   ├── memory.py              # Recall (BM25), remember, compact
│   ├── perturbation.py        # God-mode memory corruption
│   ├── llm.py                 # Provider-agnostic LLM interface
│   ├── parser.py              # Robust action parsing with fallback to rest
│   ├── metrics.py             # Per-tick metric extraction
│   ├── names.py               # Human-readable name generator
│   └── live_server.py         # WebSocket server for real-time visualization
│
├── data/                      # Runtime output (gitignored)
│   └── {experiment_id}/
│       └── {condition}/
│           └── {replication}/
│               ├── world/
│               ├── agents/{agent_name}/
│               │   ├── working.md
│               │   ├── memory/ (episodic.md, semantic.md, self.md, social.md)
│               │   ├── state.json
│               │   └── session.json
│               ├── logs/
│               │   ├── ticks/{tick}.json
│               │   ├── perturbations.jsonl
│               │   ├── messages.jsonl
│               │   ├── actions.jsonl
│               │   └── llm_raw.jsonl
│               └── analysis/metrics.csv
│
├── viz/
│   ├── live.html              # Real-time browser UI (served by live_server.py)
│   ├── index.html             # Static replay viewer
│   ├── app.js
│   └── style.css
│
├── analysis/                  # Statistical analysis scripts
│   ├── analyze.py
│   └── plots.py
│
└── run.py                     # CLI entrypoint
```

## Data Flow

The simulation follows a linear pipeline each tick:

```
config YAML
    |
    v
Engine (engine.py)
    |
    ├── 1. Perturbation check (perturbation.py) -- corrupt memory before agent sees state
    |
    ├── 2. Prompt construction (agent.py) -- build prompt from state + files
    |
    ├── 3. LLM dispatch (llm.py) -- send all agent prompts in parallel via asyncio
    |
    ├── 4. Response parsing (parser.py) -- extract ACTION/WORKING/REASONING, fallback to rest
    |
    ├── 5. Action application (engine.py) -- update world state, agent energy, memory files
    |
    ├── 6. Passive drain -- deduct energy_drain_per_tick from all alive agents
    |
    ├── 7. World update (world.py) -- food spawning, decay, depleted removal
    |
    ├── 8. Metric extraction (metrics.py) -- append to metrics.csv
    |
    └── 9. Snapshot (every N ticks) -- full world state to ticks/{tick}.json
```

The tick loop runs until `max_ticks` is reached or all agents have died.

## Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Python 3.12+ | Fastest iteration, best LLM SDK support, bottleneck is API latency not compute |
| Packaging | pyproject.toml + setuptools | `pip install -e .` installs all dependencies |
| Concurrency | asyncio | All agent calls within a tick are independent; use `asyncio.gather()` for parallelism |
| Primary LLM | Claude Code headless (`claude -p`) | Pro Max subscription = $0 marginal cost per inference |
| Config | YAML via `pyyaml` | Human-readable, supports comments, nests cleanly |
| Runtime data | JSON + JSONL + Markdown | No databases. Each tick snapshot is self-contained JSON. JSONL for append-only logs |
| Live server | websockets (Python) | Dual-purpose: serves HTML over HTTP, broadcasts state over WebSocket on same port |
| Analysis | pandas + scipy + matplotlib | Standard scientific Python stack |
| Visualization | Vanilla HTML + Canvas + JS | No React, no build step, no npm |

See [Configuration Guide](configuration.md) for the YAML config system, [LLM Provider System](llm-providers.md) for details on provider-agnostic inference, and [Memory Architecture](concepts/memory-architecture.md) for how agent memory files work.

## Key Modules

### engine.py -- Simulation Loop

The `Engine` class orchestrates everything. It holds the `World`, a list of `Agent` objects, and the configured `LLMProvider`. The `run()` method is the async tick loop. Key design:

- A semaphore (`asyncio.Semaphore`) throttles parallel LLM calls to `max_concurrent_agents` (default 6)
- Dead agents are skipped -- no inference call, no energy drain
- Snapshots are written every `snapshot_every` ticks (default 100)

### world.py -- Grid and Food

A 2D toroidal grid (edges wrap) with `FoodSource` objects. Food spawns stochastically with a guaranteed minimum (`min_sources`). Food depletes as agents eat and does not respawn at the same location. The world handles coordinate wrapping and visibility queries.

### agent.py -- Agent State and Prompts

Each agent is a `@dataclass` with position, energy, age, and file paths. The `build_prompt()` method constructs the tick prompt from current state, visible grid, incoming signals, working notes, and any pending recall results. The prompt template is minimal and contains no self-awareness language. See [Anti-Contamination Protocol](anti-contamination.md) for why this matters.

All agents start with identical minimal files:
- `working.md`: empty
- `episodic.md`: empty
- `semantic.md`: "I am {name}. I need food to maintain energy."
- `self.md`: "I am {name}."
- `social.md`: empty

### memory.py -- Recall, Remember, Compact

The memory system uses BM25 keyword scoring (not embedding search) to avoid adding a confound from embedding model biases. The `recall()` function loads all `*.md` files from the memory directory, splits into paragraph-level chunks, scores them against the query, and returns the top K results (default 3).

### perturbation.py -- The Independent Variable

The perturbation system is the experimental manipulation. Each tick, each agent in a perturbation condition rolls against `perturbation_rate`. If triggered, a perturbation type is selected by weighted random (episodic 0.4, semantic 0.3, self_model 0.2, working 0.1) and applied as a mechanical string transform -- not an LLM-generated rewrite. Every perturbation is logged to `perturbations.jsonl` with before/after text.

### llm.py -- Provider Abstraction

The `LLMProvider` ABC defines `invoke()` (stateless) and `invoke_resumable()` (persistent session). `ClaudeCodeProvider` is the default, running `claude -p` as a subprocess. Fallback providers exist for Anthropic API, OpenAI API, and local Ollama. See [LLM Provider System](llm-providers.md) for details.

### parser.py -- Action Parsing

Regex-based parser that extracts ACTION, WORKING, and REASONING fields from LLM output. If the action is unparseable, defaults to `rest` (costs half energy). Parse failures are logged and tracked as metric data -- perturbed agents may produce more incoherent outputs.

### metrics.py -- Dependent Variables

Extracts pre-registered metrics from each agent's response every tick, appending to `metrics.csv`. Uses regex pattern matching for uncertainty language, self-reference language, and trust/distrust indicators. See [Metrics & Analysis](metrics.md) for the full metric set and statistical plan.

### names.py -- Name Generator

Produces nature-themed compound names like "Bright-Creek" or "Swift-Stone" from a list of 40 adjectives and 64 nouns (2560 possible combinations). Names are random and carry no personality implications -- this is an anti-contamination measure. See [Anti-Contamination Protocol](anti-contamination.md).

### live_server.py -- Real-Time Visualization Server

The `LiveServer` class provides both HTTP serving and WebSocket communication on a single port (default 8765). It uses the `websockets` library's `process_request` hook to intercept regular HTTP requests and serve `viz/live.html`, while letting WebSocket upgrade requests pass through to the message handler.

The server has two operational modes:

- **Lobby mode** (`--live` without `--config`): The server starts and waits for a `start` command from the browser UI. The lobby presents preset experiment cards and options.
- **Immediate mode** (`--live --config <path>`): The simulation starts immediately with the provided config. The browser connects and begins receiving tick data.

Key responsibilities:
- Serve `live.html` for HTTP GET requests to `/`, `/index.html`, or `/live.html`
- Maintain a set of connected WebSocket clients and broadcast state to all of them
- Provide REST API endpoints for history (`/api/runs`, `/api/runs/<name>/tick/<n>`, `/api/runs/<name>/config`)
- Process client commands: `pause`, `resume`, `step`, `stop`, `speed`, `start`
- Manage pause/resume state with a blocking `handle_pause_loop()` used by the engine

### viz/live.html -- Browser UI

A single-file HTML application (no build step, no dependencies) that connects to the live server via WebSocket and renders the simulation in real time. Layout:

- **Top bar**: tick counter, status badge, playback controls, speed selector
- **Thought stream** (main panel): scrolling feed of agent actions, reasoning, and perturbation events per tick
- **Sidebar**: minimap (Canvas 2D), sparkline charts (population, avg energy, food count), agent list sorted by energy, summary stats panel
- **Lobby**: preset experiment cards with mock/ticks options, history button
- **History tab**: lists past runs from `data/` directory, replay with timeline slider
- **Agent profile modal**: vitals, emergent personality traits inferred from action distribution, recent action history

See [Live Visualization](live-visualization.md) for the full user-facing guide.

## WebSocket Protocol

The live server and browser UI communicate via JSON messages over a single WebSocket connection.

### Server to client (broadcast)

| Message type | Fields | Description |
|-------------|--------|-------------|
| `status` | `state` (lobby, running, paused, stopped) | Simulation state change |
| `thinking` | `tick`, `max_ticks` | Emitted when LLM inference begins for a tick |
| `tick` | `tick`, `max_ticks`, `inference_time_ms`, `agents[]`, `world{}`, `perturbations[]` | Full tick state after all agents have acted |
| `complete` | `tick`, `max_ticks`, `alive`, `total`, `agents[]` | Simulation finished |
| `error` | `message` | Error message (e.g., unknown preset) |

The `tick` message is the primary data payload. Each agent entry includes: `name`, `position`, `energy`, `max_energy`, `alive`, `age`, `kills`, `times_perturbed`, `action`, `reasoning`. The `world` object includes `size` and `food_sources[]` (each with `x`, `y`, `energy`, `max_energy`). The `perturbations[]` array contains any corruption events for that tick, each with `agent`, `type`, `transform`, `original`, `corrupted`.

### Client to server (commands)

| Command | Fields | Description |
|---------|--------|-------------|
| `start` | `preset`, `mock`, `ticks`, `config` | Start simulation (lobby mode only) |
| `pause` | -- | Pause simulation |
| `resume` | -- | Resume from pause |
| `step` | -- | Advance one tick while paused |
| `stop` | -- | Stop simulation |
| `speed` | `delay_ms` | Set inter-tick delay (0 = max speed, 200 = normal, 500 = slow) |
