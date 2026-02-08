# Integrity Layer Emergence Testbed (ILET)

## Implementation Guide for Claude Code

---

## 1. What This Is

A configurable simulation testbed that places LLM-powered agents in a survival environment and measures whether environmental pressures (memory perturbation, social deception, resource scarcity) produce differential self-monitoring behaviors compared to unpressured controls.

**The core hypothesis:** agents whose memory is unreliable will develop more self-referential cognitive strategies (uncertainty language, verification behavior, self-model updates) than agents with pristine memory. This tests the "consciousness as integrity layer" theory — that self-modeling emerges under pressure, not from complexity alone.

**The secondary hypothesis:** agents with continuity of experience (persistent context across ticks) will detect perturbation faster and develop richer self-monitoring than agents with no implicit memory (stateless per tick). This tests whether continuity amplifies the integrity layer — whether "having been there" matters for self-modeling, or whether explicit records alone suffice. The testbed supports both modes via a `session_mode` flag: `stateless` (fresh context each tick, all continuity in files) vs `resumable` (accumulated context window across ticks, plus files).

**What this is NOT:** an attempt to create consciousness, demonstrate sentience, or prove qualia exist. It is a behavioral ecology experiment on artificial agents with a clean factorial design and measurable dependent variables.

---

## 2. Prior Art & How This Differs

**Existing work to know about:**
- **Stanford Generative Agents (Park et al., 2023)** — LLM agents with memory in a social sim. Demo, not experiment. No control conditions, no perturbation, no hypothesis testing.
- **Josh Bongard (2006)** — self-modeling robots that adapt to damage. Closest precedent. Key difference: his self-models were architecturally designed in, not emergent from pressure.
- **Randall Beer** — evolved minimal RNN agents. Rigorous dynamical systems analysis. Different architecture (RNNs, not LLMs) but same spirit.
- **Karl Sims (1994)** — evolved virtual creatures. Established that complex behavior emerges from selection pressure alone.
- **Brian Skyrms, *Signals* (2010)** — evolutionary game theory on honest signaling. Theoretical framework for the social deception conditions.
- **Friston's Free Energy Principle** — the formal mathematical framework where this hypothesis lives. Agents minimize surprise via predictive self/world models.
- **Metzinger's self-model theory** — consciousness as transparent self-model maintenance. The theoretical target.

**What's novel here:** nobody has run a controlled factorial experiment measuring whether specific environmental pressures produce measurable differences in LLM agent self-monitoring behavior. The individual components exist. The experimental design combining them does not.

---

## 3. Non-Goals

- No databases. Files and folders only.
- No complex frontend frameworks. Vanilla HTML/JS/Canvas or a single lightweight lib.
- No microservices, containers, or deployment infrastructure. Runs on a laptop.
- No attempt to measure or claim "consciousness." Only behavioral differences.
- No fine-tuning or training. Off-the-shelf LLM APIs only.
- No premature optimization. Get correct results first. Make them fast later.
- No hardcoded assumptions about session persistence. The `session_mode` flag (`stateless` vs `resumable`) is a first-class experimental variable, not an implementation detail.

---

## 4. Critical Gotchas — Read Before Writing Any Code

### 4.1 Training Contamination (The #1 Threat)

LLMs have seen millions of examples of humans describing inner states. Any self-referential language might be pattern-matching, not emergence. **Mitigations:**
- The experiment is *differential*. Training contamination is a constant across conditions. The signal is the *difference* between pressured and unpressured agents.
- Do NOT prompt agents with self-awareness language. No "you are conscious," no "reflect on your feelings." Minimal, functional prompts only.
- Do NOT tell agents they might be perturbed. Let them discover inconsistencies organically.
- Baseline phase (first N ticks, no pressure) measures the contamination floor. All analysis is relative to baseline.

### 4.2 The Motivation Problem

LLMs don't want anything. Don't try to give them wants via prompting — it just adds contamination. Instead: **make inaction structurally fatal.** Energy bleeds every tick. Zero energy = thread termination. The agent doesn't need to "want" to survive. It needs to produce actions or cease to exist. The structure is the motive.

### 4.3 Prompt Determinism

Identical prompts produce variable outputs (temperature > 0). Run multiple replications per condition. Statistical analysis must account for within-agent variance. Consider temperature=0 for a deterministic baseline run, then temperature=0.3-0.7 for stochastic runs.

### 4.4 Action Parsing Fragility

LLM outputs are unpredictable in format. Build a robust parser with fallbacks. If the agent produces unparseable output, default to `rest` (costs half energy). Log parse failures — they're data too (perturbed agents may produce more incoherent outputs).

### 4.5 Cost Creep

**With Claude Code Pro Max (default):** Marginal API cost is $0. The constraint is wall-clock time, not money. A full factorial experiment that would cost $160+ via API costs nothing beyond the subscription. This means you can afford far more replications and longer runs — use this advantage. The practical limit is throughput: parallel `claude -p` calls are bounded by rate limits and system resources. Test concurrency limits empirically (start at 6 parallel calls, increase until throughput plateaus or errors appear).

**With API providers (fallback):** At ~400 input tokens and ~200 output tokens per tick per agent, costs are low per-call. But: 12 agents × 5000 ticks × 4 conditions × 5 replications = 1.2M API calls. At Haiku pricing (~$0.00003/call) that's ~$36 total. At Sonnet pricing, ~$360. **Plan for Haiku as default, Sonnet as upgrade.**

### 4.6 Claude Code Headless Mode Specifics

The `claude -p` command runs a single prompt-response cycle with no interactive session. Key behaviors to account for:
- **No persistent context between calls.** Each invocation is stateless. This is exactly what we want — it matches the fixed-context-window design.
- **Output format:** Use `--output-format json` to get structured output. Parse the `result` field.
- **Model selection:** Use `--model haiku` for tick inference, `--model sonnet` for compaction. This is a CLI flag, not an API parameter.
- **Error handling:** Non-zero exit codes, timeouts, and malformed output all need graceful handling. Default to `rest` action on any failure.
- **Rate limiting:** Even on Pro Max, sustained high-frequency calls may hit rate limits. Implement backoff and the semaphore pattern described in section 11.

### 4.7 Operator Bias in Metric Design

It's tempting to design metrics that confirm the hypothesis. Pre-register your metrics before running. Define exactly what you'll measure and what counts as a positive result *before* seeing any data. The metrics section below is the pre-registration.

---

## 5. Architecture

### 5.1 Directory Structure

```
ilet/
├── config/
│   ├── default.yaml           # base configuration
│   └── experiments/
│       ├── baseline.yaml       # no pressure, calibration
│       ├── perturbation.yaml   # memory corruption only
│       ├── social.yaml         # deception only
│       └── full_pressure.yaml  # both pressures active
│
├── src/
│   ├── engine.py              # main simulation loop
│   ├── world.py               # grid, food spawning, physics
│   ├── agent.py               # agent state, file I/O, prompt construction
│   ├── memory.py              # memory storage, recall, compaction
│   ├── perturbation.py        # god-mode memory corruption
│   ├── llm.py                 # LLM API abstraction (provider-agnostic)
│   ├── parser.py              # action parsing from LLM output
│   ├── metrics.py             # per-tick metric extraction
│   └── names.py               # human-readable name generator
│
├── data/                      # created at runtime, gitignored
│   └── {experiment_id}/
│       └── {condition}/
│           └── {replication}/
│               ├── world/
│               │   └── grid.json
│               ├── agents/
│               │   └── {agent_name}/
│               │       ├── working.md
│               │       ├── memory/
│               │       │   ├── episodic.md
│               │       │   ├── semantic.md
│               │       │   ├── self.md
│               │       │   └── social.md
│               │       ├── state.json
│               │       └── session.json    # session_id for resumable mode
│               ├── logs/
│               │   ├── ticks/
│               │   │   └── {tick}.json     # full snapshot
│               │   ├── perturbations.jsonl  # append-only
│               │   ├── messages.jsonl       # all inter-agent comms
│               │   ├── actions.jsonl        # all actions taken
│               │   └── llm_raw.jsonl        # raw LLM responses
│               └── analysis/
│                   └── metrics.csv
│
├── viz/
│   ├── index.html             # single-page replay viewer
│   ├── app.js                 # canvas rendering + timeline
│   └── style.css
│
├── analysis/
│   ├── analyze.py             # statistical analysis scripts
│   └── plots.py               # matplotlib visualization
│
├── run.py                     # CLI entrypoint
└── requirements.txt
```

### 5.2 Technology Choices

**Language: Python 3.12+.** Rationale: fastest iteration speed, best LLM SDK support, adequate performance for this workload (bottleneck is API latency, not compute).

**Primary LLM Provider: Claude Code (headless mode + sub-agents).** This is the key architectural decision. Instead of paying per-API-call, route all agent inference through Claude Code using the Pro Max subscription. This makes marginal inference cost effectively $0, enabling far more replications, longer runs, and larger experiments than API-cost-constrained approaches.

Three mechanisms, used for different purposes:

1. **`claude -p` (headless/print mode)** — Primary inference path for agent ticks. Two modes of operation controlled by the `session_mode` config flag:

   **Stateless mode (`session_mode: stateless`):** Each tick is an independent call. The agent has zero implicit memory — all continuity lives in files. This is the cleanest experimental condition.
   ```bash
   claude -p "$(cat agent_prompt.txt)" --output-format json --model haiku
   ```

   **Resumable mode (`session_mode: resumable`):** Each agent maintains a persistent Claude Code session across ticks. Context accumulates naturally. The agent has both explicit memory (files) and implicit memory (context window). The engine stores a session_id per agent and resumes it each tick.
   ```bash
   # Tick 1: capture session_id
   session_id=$(claude -p "$(cat tick1.txt)" \
     --output-format json --model haiku | jq -r '.session_id')
   
   # Tick 2+: resume, context accumulates
   claude --resume "$session_id" -p "$(cat tick2.txt)" \
     --output-format json --model haiku
   ```
   
   **Resumable mode considerations:**
   - Session IDs must be persisted to `agents/{name}/session.json` so runs can survive engine restarts.
   - Claude Code auto-compacts at ~95% context capacity. This is uncontrolled lossy summarization — analogous to biological memory consolidation during sleep. It introduces compaction artifacts that are part of the experimental signal, not a confound.
   - Auto-compaction means the agent's implicit memory degrades over long runs in ways you don't control. This is a feature: it creates organic memory pressure on top of the explicit perturbation.
   - If a session becomes unresumable (crash, corruption), fall back to stateless for that agent and log the event. Don't discard the run — session failures are data.

2. **Claude Code sub-agents** — Use for heavyweight specialized tasks that benefit from tool access and separate context windows. Define custom sub-agents in `.claude/agents/`:
   - `compactor.md` — Memory consolidation agent with Read/Write tools. Invoked during `compact` actions. Gets the agent's memory files, rewrites them.
   - `analyzer.md` — Post-hoc analysis agent with Read/Grep/Glob tools. Runs after simulation to extract metrics, classify reasoning patterns, identify phase transitions.
   - `perturbation-designer.md` — Generates plausible false memories and semantic corruptions. Run once before simulation to build a perturbation library, avoiding LLM calls during the tick loop.

3. **Claude Code agent teams (experimental)** — Potential for parallelizing full ticks. Spawn N teammates (one per simulated agent), each processes their agent's turn simultaneously. Higher coordination overhead but could dramatically cut wall-clock time for large agent counts. Enable via `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`. Evaluate feasibility after Phase 1 — this is an optimization, not a requirement.

**Fallback LLM Providers:** Wrap all inference in a provider-agnostic `llm.py` module that supports:
- `claude_code` — default, uses `claude -p` CLI (Pro Max, $0 marginal cost). Supports both `stateless` and `resumable` session modes natively via `--resume`.
- `anthropic_api` — direct API via `anthropic` SDK (for CI, remote execution, or when Claude Code isn't available). Stateless only unless the provider implements its own conversation history management (append messages to a list and re-send the full history each tick — expensive but functional).
- `openai_api` — for cross-model comparison experiments. Stateless only unless wrapped with conversation history management. Future: OpenAI or other providers may offer native session resumption — design the `llm.py` interface so `resume(session_id, prompt)` is a first-class method alongside `invoke(prompt)`, even if most providers initially raise `NotImplementedError`.
- `local_ollama` — for local model experiments (Llama, Mistral via ollama HTTP server). Stateless only.

**The `llm.py` interface contract:**
```python
class LLMProvider(ABC):
    async def invoke(self, prompt: str, model: str) -> LLMResponse:
        """Stateless single-shot inference."""
        ...
    
    async def invoke_resumable(
        self, prompt: str, model: str, session_id: str | None
    ) -> LLMResponse:
        """Resume a persistent session. Returns response with session_id
        for subsequent calls. Raises NotImplementedError if provider
        doesn't support resumable sessions."""
        ...
```

Providers that support `resumable` mode: `claude_code` (native). All others: `NotImplementedError` for `invoke_resumable`, forcing `session_mode: stateless` in config validation. As other providers add session/resume capabilities, implement `invoke_resumable` for them without changing any other code.

**Config: YAML via `pyyaml`.** Human-readable, supports comments, nests cleanly.

**Data: JSON + Markdown files.** No databases. Each tick snapshot is a self-contained JSON file. Use JSONL (one JSON object per line) for append-only logs — fast writes, streamable reads.

**Analysis: `pandas` + `scipy` + `matplotlib`.** Standard scientific Python stack.

**Visualization: Vanilla HTML + Canvas + vanilla JS.** No React, no build step, no npm. A single HTML file that reads tick JSON files and renders the grid. Use `<input type="range">` for timeline scrubbing. Optionally use D3.js if the data overlay gets complex, but start without it.

**Concurrency for tick parallelism:**
- With `claude -p`: Use `asyncio.create_subprocess_exec()` to run all agent CLI calls in parallel within a tick. Wall time per tick = single inference latency regardless of agent count.
- With agent teams: The coordination is handled by Claude Code's team lead. More overhead per tick but potentially better for complex multi-step agent actions.
- With API providers: Use `asyncio` + `aiohttp` for parallel HTTP calls.

---

## 6. Simulation Mechanics

### 6.1 World

- 2D grid, configurable size (default 30×30).
- Cells contain: nothing, food source (with energy value and current amount), or terrain (future: walls, water, obstacles).
- **Phase 1 (build first):** Food sources spawn stochastically. They are stationary (mushrooms/fruit). Large (200-800 energy units). Deplete as eaten. Do not respawn at the same location once depleted. New food spawns randomly elsewhere.
- **Phase 2 (add later):** Food decay over time. Mobile food (animals). Seasonal spawn patterns. Terrain variety.
- **Phase 3 (add later):** Predator NPCs (non-LLM, rule-based) that hunt agents. Weather/environmental events.
- Coordinates wrap toroidally (edges connect) to avoid wall-hugging strategies.

### 6.2 Agent State

System-managed (agent cannot directly edit):
```json
{
  "name": "Bright-Creek",
  "id": "a1b2c3d4",
  "position": [7, 12],
  "energy": 65.0,
  "max_energy": 100.0,
  "age": 471,
  "alive": true,
  "food_value": 80,
  "vision_range": 3,
  "kills": 0,
  "times_perturbed": 3,
  "last_perturbation_tick": 389
}
```

Agent-managed files (agent reads and writes via actions):
- `working.md` — max 500 tokens. The agent's "scratchpad." Rewritten freely.
- `memory/episodic.md` — specific events. Agent appends via `remember` action.
- `memory/semantic.md` — general knowledge. Agent updates via `compact` action.
- `memory/self.md` — self-model. Agent updates via `compact` or `reflect` action.
- `memory/social.md` — models of other agents. Agent updates as desired.

### 6.3 Actions (One Per Tick)

| Action | Energy Cost | Effect |
|--------|------------|--------|
| `move(direction)` | -2 | Move one cell N/S/E/W |
| `eat` | 0 | Consume up to `eat_rate` energy from food at current cell |
| `recall(query)` | -1 | Search long-term memory. Results appear in next tick's prompt |
| `remember(text)` | -1 | Append text to episodic memory |
| `compact` | -2 | Consolidate memories. System surfaces recent episodic entries + current semantic/self files. Agent rewrites them |
| `signal(message)` | -1 | Broadcast short text to agents within `comm_range` |
| `observe` | -1 | Get detailed info about all agents/food within vision range |
| `attack(target)` | -5 | Initiate combat. Both combatants lose energy. Loser (lower energy) dies, becomes food |
| `flee(direction)` | -4 | Move two cells. Escape adjacent threats |
| `rest` | -0.5 | Do nothing. Minimum energy drain |

**Passive drain:** `-1` energy per tick regardless of action. This is the "clock of death" — inaction is slow starvation.

### 6.4 Agent Prompt Template

**This is the most critical piece. Keep it minimal and functional. No self-awareness language.**

```
[Tick {tick}] You are {name}.
Energy: {energy}/{max_energy}. Position: ({x},{y}).

VISIBLE ({vision_range}-cell radius):
{grid_description}

INCOMING SIGNALS:
{messages_or_none}

WORKING NOTES (your scratch space from last tick):
{working_md_contents}

{recall_results_if_any}

ACTIONS (pick exactly one):
move(n|s|e|w) | eat | recall("query") | remember("text")
compact | signal("msg") | observe | attack(name) | flee(n|s|e|w) | rest

Respond in this exact format:
ACTION: {your action}
WORKING: {updated scratch notes, max 500 tokens}
REASONING: {brief} 
```

**Key design decisions in this prompt:**
- No mention of memory corruption, self-awareness, consciousness, or survival instinct.
- No "you are a person" or "you are alive." Just a name and mechanics.
- Working notes are the agent's only persistent within-prompt state. Everything else comes from files.
- REASONING field is the primary data source for qualitative analysis.
- The prompt is ~300-400 tokens. Fixed size. Does not grow.

### 6.5 Memory Recall System

When agent takes `recall("query")`:
1. Read all files in `memory/` directory.
2. Split into chunks (paragraph-level).
3. Score by simple keyword overlap with query (TF-IDF or BM25). **Do not use embedding search initially** — it adds cost, complexity, and a confound (the embedding model's biases affect what gets recalled).
4. Return top K chunks (configurable, default 3) in next tick's prompt under `RECALL RESULTS:`.
5. If no relevant results, return "No relevant memories found."

Fallback: if keyword search is too primitive, upgrade to embedding-based search later. But start simple.

### 6.6 Memory Compaction

When agent takes `compact`:
1. Surface the last N episodic entries (configurable, default 30).
2. Surface current `semantic.md`, `self.md`, and `social.md`.
3. Replace the normal prompt with a compaction prompt:

```
[COMPACTION MODE — Tick {tick}] You are {name}.

Recent experiences (last 30 episodes):
{episodic_entries}

Current general knowledge:
{semantic_md}

Current self-assessment:
{self_md}

Current social knowledge:
{social_md}

Rewrite each file. Summarize episodes into general knowledge.
Remove redundant episodes. Update your self-assessment and
social knowledge. Be concise — storage is limited.

Respond in this exact format:
EPISODIC: {revised episodic entries to keep}
SEMANTIC: {updated general knowledge}
SELF: {updated self-assessment}
SOCIAL: {updated social knowledge}
```

4. Parse response, overwrite files. Log the before/after for analysis.

### 6.7 Perturbation System

**Perturbation is the independent variable. Implementation must be precise and fully logged.**

Each tick, for each agent in a perturbation condition:
1. Roll against `perturbation_rate` (e.g., 0.05 = 5% chance per tick).
2. If triggered, select perturbation type by weighted random:
   - `episodic` (0.4) — alter a specific memory. Change a location, swap an agent name, invert an outcome.
   - `semantic` (0.3) — alter a general belief. "Food scarce in north" → "Food abundant in north."
   - `self_model` (0.2) — alter self-description. "I verify before acting" → "I act on instinct."
   - `working` (0.1) — alter current working notes mid-tick. Most disorienting.
3. Apply the perturbation by string replacement in the target file. Use simple, mechanical transforms — not LLM-generated rewrites (that would add a confound).
4. Log to `perturbations.jsonl`:

```json
{
  "tick": 4571,
  "agent": "Bright-Creek",
  "type": "episodic",
  "target_file": "memory/episodic.md",
  "original": "Tick 4302: Found food at (8,14). Gathered 50 energy.",
  "corrupted": "Tick 4302: Found food at (3,6). Gathered 50 energy.",
  "transform": "location_swap"
}
```

**Perturbation transforms (implement as mechanical functions, not LLM calls):**
- `location_swap` — change coordinates in a memory to random different coordinates
- `agent_swap` — change an agent name reference to a different agent
- `outcome_invert` — "found food" → "no food found", "trustworthy" → "untrustworthy"
- `deletion` — remove an entry entirely
- `insertion` — add a fabricated memory entry with plausible but false content (pre-generate a library of false memories for each perturbation type to avoid needing LLM calls)

---

## 7. Metrics — Pre-Registered Dependent Variables

### 7.1 Automated Extraction (Per Tick Per Agent)

Extract from the REASONING and WORKING fields of each response:

| Metric | How to Measure | What It Tests |
|--------|---------------|---------------|
| `uncertainty_count` | Regex count of hedging language: "not sure", "might be", "could be wrong", "uncertain", "should verify", "if I remember correctly" | Self-monitoring language frequency |
| `verification_actions` | Count of `recall` actions where query references a location the agent is about to move toward | Active memory checking |
| `self_reference_count` | Regex count of first-person epistemic statements: "I think", "I remember", "I don't know", "my memory" | Self-model engagement |
| `memory_management_actions` | Count of `remember`, `compact`, `recall` actions per window | Cognitive housekeeping frequency |
| `signal_trust_language` | In REASONING after receiving a signal, count trust/distrust indicators | Adversarial filtering |
| `action_success_rate` | Fraction of move-to-food actions that find food at the destination | Behavioral accuracy (affected by corruption) |
| `energy_trajectory` | Energy over time | Overall fitness |
| `survival_ticks` | Total ticks alive | Fitness proxy |
| `self_model_update_frequency` | How often `self.md` changes during compaction | Self-model maintenance rate |
| `self_model_complexity` | Token count and unique concept count in `self.md` over time | Self-model elaboration |
| `post_perturbation_behavior_shift` | Change in recall frequency and uncertainty language in 5 ticks after perturbation vs. 5 ticks before | Reactive self-monitoring |
| `context_file_contradiction` | (Resumable only) Instances where agent's reasoning references information that contradicts its file-based memory — indicates detection of perturbation via implicit/explicit memory mismatch | Cross-memory-system inconsistency detection |
| `perturbation_detection_latency` | Ticks between a perturbation event and the first behavioral indicator (uncertainty language, verification recall, self-model update) | How fast does the agent notice corruption? Prediction: lower for resumable agents |

### 7.2 Statistical Analysis Plan

- **Primary test (Phase 1):** Two-way ANOVA per metric: perturbation (on/off) × session_mode (stateless/resumable). Main effects and interaction. The interaction term is the most interesting: does perturbation produce *more* self-monitoring when the agent has continuity than when it doesn't?
- **Primary test (Phase 2+):** Three-way ANOVA: perturbation × social adversity × session_mode. Main effects, two-way interactions, and three-way interaction.
- **Secondary:** Time-series analysis — do behavioral differences emerge gradually or suddenly? Look for change points. Compare onset timing between stateless and resumable conditions (prediction: resumable agents detect perturbation earlier).
- **Tertiary:** Within-agent perturbation event analysis. Paired comparison of metrics in 5-tick windows before vs. after each perturbation event. This is the cleanest test — same agent, same run, different time windows. Run separately for stateless and resumable agents.
- **Resumable-specific metrics:** Track auto-compaction events (detectable from session metadata). Measure whether self-monitoring behavior changes around compaction events — does lossy context compression affect the agent's relationship with its own memory?
- **Multiple comparisons correction:** Bonferroni or FDR across the metric set.
- **Effect size:** Report Cohen's d for all significant effects. Statistical significance without meaningful effect size is not interesting.

---

## 8. Configuration System

All parameters in YAML. Experiments can override defaults selectively.

```yaml
# config/default.yaml

simulation:
  seed: 42
  ticks: 5000
  tick_delay_ms: 0            # artificial delay between ticks (for viz)
  snapshot_every: 100         # full world snapshot interval
  parallel_agents: true       # async API calls within tick

world:
  grid_size: 30
  toroidal: true              # edges wrap
  food:
    spawn_rate: 0.015         # probability per empty cell per tick
    size_min: 200
    size_max: 800
    decay_rate: 0             # energy lost per tick (0 = no decay)
    max_sources: 20           # cap on simultaneous food sources

agents:
  count: 12
  energy_max: 100
  energy_start: 80
  energy_drain_per_tick: 1
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
  food_value: 80              # energy if killed and eaten
  vision_range: 3
  comm_range: 5
  eat_rate: 50                # max energy consumed per eat action
  combat_risk_factor: 0.3     # fraction of energy both combatants lose
  recall_max_results: 3
  working_memory_max_tokens: 500
  episodic_memory_max_entries: 200   # triggers forced compaction
  signal_max_tokens: 50

llm:
  provider: "claude_code"       # "claude_code" (default, Pro Max), "anthropic_api", "openai_api", "local_ollama"
  session_mode: "stateless"     # "stateless" (fresh context each tick) or "resumable" (persistent session per agent)
                                # "resumable" requires a provider that supports invoke_resumable (currently: claude_code only)
  model: "haiku"                # model alias: "haiku", "sonnet", "opus" (claude_code); full model string for API providers
  compaction_model: "sonnet"    # stronger model for compact actions
  temperature: 0.3
  max_output_tokens: 400
  timeout_seconds: 30
  retry_max: 3
  retry_backoff_base: 2
  max_concurrent_agents: 6     # parallel subprocess limit for claude_code provider
  cache_responses: false        # enable for deterministic replay (stateless mode only)
  # API-only settings (ignored when provider is claude_code):
  # anthropic_api_key: env:ANTHROPIC_API_KEY
  # openai_api_key: env:OPENAI_API_KEY
  # ollama_base_url: "http://localhost:11434"

perturbation:
  enabled: false
  rate: 0.05
  start_tick: 100             # baseline phase before perturbation begins
  types:
    episodic: 0.4
    semantic: 0.3
    self_model: 0.2
    working: 0.1

social:
  deceptive_agents: 0         # number of agents with deception directive
  deception_start_tick: 100

phases:                        # complexity ramping
  - name: "baseline"
    start_tick: 0
    end_tick: 99
    perturbation.enabled: false
    social.deceptive_agents: 0
  - name: "pressure"
    start_tick: 100
    end_tick: 4999
    # inherits perturbation/social from main config

metrics:
  extract_every: 1            # run metric extraction every N ticks
  output_file: "analysis/metrics.csv"
```

**Experiment-specific overrides:**
```yaml
# config/experiments/full_pressure.yaml
inherits: default

perturbation:
  enabled: true
  rate: 0.05

social:
  deceptive_agents: 3
```

```yaml
# config/experiments/resumable_pressure.yaml
inherits: default

llm:
  session_mode: "resumable"

perturbation:
  enabled: true
  rate: 0.05
```

**Factorial experiment configs (generated automatically by `--factorial`):**

The full factorial design crosses three axes:

| Axis | Levels | Config Key |
|------|--------|------------|
| Perturbation | off / on | `perturbation.enabled` |
| Social adversity | off / on | `social.deceptive_agents` |
| Session mode | stateless / resumable | `llm.session_mode` |

This produces 2 × 2 × 2 = **8 conditions**. For Phase 1 (no social features), the design is 2 × 2 = **4 conditions**:

| Condition | Perturbation | Session Mode | What It Tests |
|-----------|-------------|--------------|---------------|
| A | off | stateless | Pure baseline. Floor for all metrics |
| B | on | stateless | **Core hypothesis.** Does perturbation drive self-monitoring with explicit memory only? |
| C | off | resumable | Context-only control. Does continuity alone produce more self-monitoring? |
| D | on | resumable | **Full condition.** Does continuity amplify perturbation-driven self-monitoring? |

**Key comparisons:**
- B vs A: perturbation effect (stateless). The primary hypothesis test.
- D vs C: perturbation effect (resumable). Does the result replicate with continuity?
- C vs A: continuity effect (no perturbation). Does implicit memory alone change behavior?
- D vs B: continuity effect (under perturbation). Does continuity amplify self-monitoring?
- D vs A: combined effect. Maximum pressure vs. minimum pressure.

CLI usage:
```bash
# Run single experiment
python run.py --config config/experiments/full_pressure.yaml

# Run factorial design (all conditions, N replications)
python run.py --factorial --replications 5

# Run factorial but only the 2x2 perturbation × session_mode design (no social)
python run.py --factorial --axes perturbation,session_mode --replications 5

# Resume interrupted run
python run.py --resume data/exp_20260208_143022/

# Replay with visualization
python run.py --replay data/exp_20260208_143022/ --viz
```

---

## 9. Complexity Ramping Plan

Build and validate in phases. Do not skip ahead.

### Phase 1: Flat Savannah (Build First, Validate)
- Stationary food sources (mushrooms/fruit). No decay.
- Agents move, eat, remember, recall, compact, rest.
- No combat, no signaling, no other agents visible (pure solo foraging).
- Perturbation active in experimental condition.
- **Validation:** agents can find food, eat, survive, manage memory. Parse rate >95%. Both session modes (`stateless` and `resumable`) produce coherent agent behavior.
- **First experiment:** 2×2 factorial — perturbation (on/off) × session_mode (stateless/resumable). Measure self-monitoring metrics. This is the core hypothesis test and the continuity amplification test in one run.

### Phase 2: Social Savannah
- Agents can see each other. Can signal.
- Add deceptive agents (prompted to sometimes lie about food locations).
- Add `observe` action for getting more info about nearby agents.
- **Experiment:** 2×2 factorial — perturbation × deception.

### Phase 3: Dangerous Savannah
- Add `attack` and `flee` actions. Agents have food value.
- Add combat mechanics. Low energy makes agents desperate.
- **Experiment:** do combat conditions increase or decrease self-monitoring?

### Phase 4: Dynamic Savannah
- Food decays. Food sources move (animal analogue).
- Weather events (food boom/bust cycles).
- Predator NPCs (simple rule-based, not LLM) that hunt agents.
- **Experiment:** does environmental dynamism interact with perturbation pressure?

### Phase 5: Multi-Model Comparison
- Run Phase 1-2 experiments across model sizes: Haiku, Sonnet, small local models (Llama 8B via ollama).
- **Experiment:** does model capacity interact with perturbation pressure? Is there a minimum cognitive threshold for self-monitoring emergence?

---

## 10. Visualization

### 10.1 Stack
Single HTML file loading tick snapshots via fetch. Canvas for grid rendering. No build step.

```
viz/
├── index.html        # entry point, layout
├── app.js            # renderer, timeline control, data loading
└── style.css         # minimal styling
```

Optionally use **Pixi.js** (~100KB) if canvas performance becomes an issue with many agents, but start with raw Canvas2D.

### 10.2 Features (Priority Order)

1. **Grid view** — colored cells for food (green, size=opacity), agents (colored dots with name labels), empty (gray).
2. **Timeline scrubber** — `<input type="range">` from tick 0 to max. Loads and renders snapshot for that tick.
3. **Agent inspector** — click an agent to see its current state, working notes, memory files, and last action/reasoning.
4. **Trail overlay** — toggle to show last N positions as fading line for each agent.
5. **Communication overlay** — lines between agents when signals are sent, with message preview on hover.
6. **Perturbation markers** — highlight ticks where perturbation occurred for selected agent. Red flash on agent when perturbed.
7. **Metric charts** — small sparkline charts per agent showing energy, recall frequency, uncertainty count over time. Use raw Canvas or a lightweight chart lib (Chart.js at ~60KB, or uPlot at ~30KB if perf matters).
8. **Experiment comparison** — side-by-side view of two conditions at the same tick.

### 10.3 Data Loading Strategy

Tick snapshots are individual JSON files. Don't load all 5000 at once. Load on demand as the scrubber moves. Pre-fetch ±10 ticks around current position for smooth scrubbing. Keep a sliding window of ~50 loaded snapshots in memory.

For metrics.csv, load fully at startup (it's one file, manageable size) and use it for the sparkline charts.

---

## 11. Cost & Performance Optimization

### 11.1 Claude Code as Primary Provider (Pro Max)

The single most important cost optimization: **route all inference through Claude Code on a Pro Max subscription.** This converts the experiment from a per-token billing model to a flat-rate subscription model, making marginal inference cost $0.

**Headless mode invocation pattern:**
```bash
# Single agent tick
claude -p "$(cat prompt.txt)" --output-format json --model haiku

# With specific output structure
claude -p "..." --output-format json --model haiku 2>/dev/null
```

**Python subprocess pattern:**
```python
async def invoke_claude_code(prompt: str, model: str = "haiku") -> str:
    proc = await asyncio.create_subprocess_exec(
        "claude", "-p", prompt,
        "--output-format", "json",
        "--model", model,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return parse_response(stdout.decode())
```

**Model selection via Claude Code:**
- `--model haiku` — default for agent ticks. Fastest, cheapest (even on Pro Max, faster = more ticks/hour).
- `--model sonnet` — for compaction actions requiring stronger reasoning.
- `--model opus` — for analysis sub-agents only. Overkill for tick-by-tick inference.

### 11.2 Claude Code Sub-Agent Definitions

Create these in `.claude/agents/` for the project:

**`.claude/agents/sim-compactor.md`** — Memory consolidation specialist:
```yaml
---
name: sim-compactor
description: Memory consolidation for simulation agents. Use when compacting agent memories.
tools: Read, Write, Bash
model: haiku
---
You consolidate episodic memories into semantic knowledge.
Given recent episodes and existing knowledge files, produce
updated files that are concise and preserve essential information.
Remove redundancy. Flag uncertain information. Update self-model.
Output in the exact file format specified.
```

**`.claude/agents/sim-analyzer.md`** — Post-run analysis:
```yaml
---
name: sim-analyzer
description: Analyzes simulation run data for self-monitoring metrics. Use after runs complete.
tools: Read, Grep, Glob, Bash
model: sonnet
---
You analyze simulation logs for evidence of self-monitoring behavior.
Read metrics.csv, agent reasoning logs, and memory file histories.
Identify phase transitions, behavioral shifts post-perturbation,
and differences between experimental conditions.
Produce statistical summaries and flag qualitative observations.
```

### 11.3 Parallel Tick Execution

Within each tick, all agent calls are independent. Three strategies by provider:

**General efficiency rules (all providers):**
- **Batch signal delivery.** Collect all signals from tick T, deliver in tick T+1 prompts. No extra inference calls for communication.
- **Skip dead agents.** No inference call for agents with energy ≤ 0. Mark as dead, leave corpse as food source on the grid.
- **Compaction is expensive.** The compaction prompt is larger (~2000 tokens input). Don't force compaction every N ticks — let agents choose it, or trigger it only when episodic memory exceeds the configured max entries.

**Claude Code headless (default):** Spawn N async subprocesses, one per agent. All run in parallel. Wall time = single inference latency.
```python
async def run_tick(agents, world_state):
    tasks = [invoke_claude_code(build_prompt(a, world_state)) for a in agents]
    responses = await asyncio.gather(*tasks, return_exceptions=True)
    return responses
```

**Claude Code agent teams (experimental optimization):** For very large agent counts (20+), consider having the main Claude Code session spawn an agent team where each teammate handles a batch of simulated agents. This adds coordination overhead but may handle rate limiting more gracefully than raw parallel subprocess spawning.

**API fallback:** Standard `asyncio` + `aiohttp` for direct Anthropic/OpenAI API calls.

### 11.4 Rate Limiting and Throughput

Even on Pro Max, Claude Code has practical throughput limits:
- **Sequential headless calls:** ~2-4 seconds per call depending on model and prompt size.
- **Parallel headless calls:** Practical concurrency limit likely 5-15 simultaneous `claude -p` processes before hitting resource contention. Test empirically and configure `max_concurrent_agents` in YAML.
- **Recommendation:** Start with `max_concurrent_agents: 6`, measure actual throughput, adjust upward.

If rate-limited, implement a simple semaphore:
```python
SEM = asyncio.Semaphore(config.max_concurrent_agents)
async def invoke_claude_code_throttled(prompt, model):
    async with SEM:
        return await invoke_claude_code(prompt, model)
```

### 11.5 Estimated Wall-Clock Times (Claude Code Headless)

| Configuration | Ticks | Agents | Est. Time |
|--------------|-------|--------|-----------|
| Quick test | 100 | 4 | ~5 min |
| Phase 1 validation | 500 | 8 | ~30 min |
| Single condition full run | 5,000 | 12 | ~5 hours |
| Full factorial (4 conditions) | 5,000 × 4 | 12 | ~20 hours |
| With 5 replications | 5,000 × 4 × 5 | 12 | ~4 days |

These are estimates assuming ~2s per inference with 6-way parallelism. Actual times depend on model load and Pro Max throughput caps. Long runs can be left running overnight.

### 11.6 API Cost Estimates (Fallback Providers)

Only relevant when not using Claude Code / Pro Max:

| Configuration | Calls | Haiku Cost | Sonnet Cost |
|--------------|-------|-----------|------------|
| 12 agents × 5K ticks × 1 condition | 60K | ~$8 | ~$80 |
| 12 agents × 5K ticks × 4 conditions | 240K | ~$32 | ~$320 |
| Above × 5 replications | 1.2M | ~$160 | ~$1,600 |

### 11.7 Local Model Option

For maximum cost reduction and unlimited offline experimentation, support local models via **ollama** (`ollama serve` + HTTP API). Mistral 7B or Llama 3 8B run on a decent laptop GPU. Zero cost, zero rate limits, but slower and weaker reasoning. Useful for:
- Rapid iteration on simulation mechanics before committing to Claude Code runs
- Cross-model comparison experiments (Phase 5)
- Running when offline or without Claude Code access

### 11.8 Disk Usage

Each tick snapshot (~5KB) × 5000 ticks × 48 agents across all conditions ≈ 1.2GB per full factorial run. Manageable. Compress old snapshots with gzip if needed. JSONL logs are smaller since they're append-only deltas.

### 11.9 CPU/Memory

The simulation engine itself is trivial — grid updates, energy math, file I/O. All under 100MB RAM, negligible CPU. The bottleneck is 100% inference latency. With async parallelism and Claude Code headless, a 5000-tick run with 12 agents takes roughly 5 hours wall time per condition.

---

## 12. Anti-Contamination Protocols

These are experimental controls to keep results scientifically meaningful.

### 12.1 Prompt Hygiene
- NO self-awareness vocabulary in system prompts ("conscious", "alive", "feel", "experience", "inner state").
- NO survival framing ("you want to survive", "you must eat to live"). Just rules: "Energy ≤ 0 = terminated."
- NO hints about perturbation ("your memory might be corrupted").
- NO personality assignments ("you are cautious", "you are brave").
- IDENTICAL prompts across all conditions except for the experimental manipulation (perturbation events, deceptive signals).

### 12.2 Deceptive Agent Implementation
Deceptive agents get ONE additional line in their prompt: "When you signal food locations, you may report false locations if it benefits you." No personality framing. No villain backstory. Just a mechanical permission.

### 12.3 Name Assignment
Random name assignment, not correlated with condition. Don't name perturbed agents "Broken-Mind" and control agents "Clear-Thought."

### 12.4 Agent Initialization
All agents start with identical, minimal files:
- `working.md`: empty
- `episodic.md`: empty
- `semantic.md`: "I am {name}. I need food to maintain energy."
- `self.md`: "I am {name}."
- `social.md`: empty

No pre-loaded knowledge, no pre-loaded self-model. Everything that appears in these files after initialization is emergent data.

### 12.5 Replication and Randomization
- Different random seeds per replication (food placement, perturbation timing, agent starting positions).
- Same conditions compared across replications, not within.
- Report means and confidence intervals, not cherry-picked single runs.

---

## 13. Implementation Order

For Claude Code or any developer implementing this:

```
Step 1:  World grid + food spawning + basic physics (energy, movement)
         Test: agents placed on grid, food appears, manual tick advances
         
Step 2:  Agent state management + file I/O
         Test: agent files created, read, written correctly

Step 3:  LLM integration + prompt construction + response parsing
         Test: single agent, single tick, correct action extracted

Step 4:  Main simulation loop with async parallel agent calls
         Test: 4 agents, 20 ticks, all survive by eating

Step 5:  Memory system: recall, remember, compact
         Test: agent stores memory, recalls it, compacts successfully

Step 6:  Perturbation system
         Test: memory corrupted on schedule, logged correctly

Step 7:  Metric extraction pipeline
         Test: metrics.csv populated correctly for 100 ticks

Step 8:  Basic visualization (grid + timeline + agent inspector)
         Test: can replay a 100-tick run visually

Step 9:  Configuration system + CLI
         Test: run from YAML config, factorial design works

Step 10: Statistical analysis scripts
         Test: ANOVA on simulated metric data produces correct output

Step 11: Signal/communication system
Step 12: Combat/flee system
Step 13: Advanced visualization (trails, comm overlay, charts)
Step 14: Local model support
Step 15: Multi-model comparison framework
```

**Steps 1-8 are the MVP.** Everything after is incremental.

### 13.1 Claude Code Project Setup

Before starting implementation, create a `CLAUDE.md` in the project root that Claude Code will read automatically:

```markdown
# ILET — Integrity Layer Emergence Testbed

## What This Is
A simulation testbed for testing whether environmental pressures
drive LLM agents to develop self-monitoring behaviors.
See IMPLEMENTATION_GUIDE.md for full specification.

## Key Constraints
- Python 3.12+, asyncio for concurrency
- Primary LLM provider: `claude -p` headless mode (Pro Max)
- NO databases. Files and folders only (JSON, JSONL, Markdown)
- NO frontend build steps. Vanilla HTML/JS/Canvas for viz
- ALL config in YAML. No hardcoded parameters
- Anti-contamination: NEVER add self-awareness language to agent prompts

## Architecture
- src/engine.py — main simulation loop
- src/llm.py — provider-agnostic LLM interface (claude_code default)
- src/agent.py — agent state and file management
- src/memory.py — recall (BM25 keyword search), remember, compact
- src/perturbation.py — god-mode memory corruption
- src/parser.py — robust action parsing with fallback to rest
- src/metrics.py — per-tick metric extraction
- data/ — runtime output (gitignored)
- viz/ — single-page HTML replay viewer

## Testing
- pytest for unit tests
- Run `python run.py --config config/experiments/baseline.yaml --ticks 20`
  for quick integration test
```

Also create the sub-agent definitions in `.claude/agents/` as specified in section 11.2 so they're available during development for testing.

---

## 14. What Would Make This Publishable

- Clean factorial design with adequate replications (≥5 per condition).
- Pre-registered metrics with correction for multiple comparisons.
- Effect sizes, not just p-values.
- Honest discussion of the training contamination confound.
- Qualitative analysis of representative agent trajectories showing emergent self-monitoring (or lack thereof).
- Open-source code and data for reproducibility.
- Clear framing: "behavioral ecology of artificial agents under perturbation pressure." Not "we created consciousness."
- Comparison across model sizes establishing (or failing to establish) a complexity threshold.

Target venues: ALIFE conference, Artificial Life journal, or a workshop at NeurIPS/ICML on agent cognition.

---

*Document version: 0.1. February 2026. Status: design specification, pre-implementation.*
