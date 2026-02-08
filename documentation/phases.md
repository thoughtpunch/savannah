# Implementation Phases

ILET is built and validated in phases. Each phase adds complexity only after the previous phase is validated. Do not skip ahead.

## Phase 1: Flat Savannah (Build First)

The minimal viable experiment. Everything needed to test the core hypothesis.

### Features

- 2D toroidal grid (default 30x30)
- Stationary food sources (mushrooms/fruit). No decay. Deplete as eaten. New food spawns randomly elsewhere. Minimum 5 sources guaranteed at all times
- Agents can: `move`, `eat`, `recall`, `remember`, `compact`, `rest`
- No combat, no signaling, no agent-to-agent visibility (pure solo foraging)
- Perturbation active in experimental conditions (after tick 100)
- Both session modes supported: `stateless` and `resumable`

### Actions Available

| Action | Energy Cost | Effect |
|--------|------------|--------|
| `move(n\|s\|e\|w)` | -2 | Move one cell in direction |
| `eat` | 0 | Consume up to `eat_rate` energy from food at current cell |
| `recall("query")` | -1 | BM25 search of memory files. Results in next tick's prompt |
| `remember("text")` | -1 | Append text to episodic memory |
| `compact` | -2 | Consolidate memories (stronger model used) |
| `rest` | -0.5 | Do nothing. Minimum energy drain |

Passive drain: -1 energy per tick regardless of action.

### Validation Criteria

Before proceeding to Phase 2, all of the following must hold:

- [ ] Agents find food and eat successfully
- [ ] Agents survive for meaningful durations (hundreds of ticks)
- [ ] Memory system works: agents store, recall, and compact memories
- [ ] Parse rate > 95% (actions correctly extracted from LLM output)
- [ ] Both session modes (`stateless` and `resumable`) produce coherent behavior
- [ ] Perturbation system corrupts memory on schedule and logs correctly
- [ ] Metrics pipeline populates `metrics.csv` with correct data
- [ ] Visualization replays runs correctly

### Experiment

2x2 factorial: perturbation (on/off) x session_mode (stateless/resumable) = 4 conditions (A/B/C/D). Minimum 5 replications per condition. This is the core hypothesis test. See [Experimental Design](experimental-design.md).

## Phase 2: Social Savannah

Adds inter-agent interaction.

### New Features

- Agents can see each other within `vision_range`
- `signal("msg")` action: broadcast short text to agents within `comm_range`
- `observe` action: get detailed info about all agents/food within vision range
- Deceptive agents: receive one additional prompt line permitting false food reports

### New Actions

| Action | Energy Cost | Effect |
|--------|------------|--------|
| `signal("msg")` | -1 | Broadcast to agents within comm_range |
| `observe` | -1 | Detailed scan of nearby agents and food |

### Experiment

2x2 factorial: perturbation x deception. Tests whether social adversity interacts with memory perturbation in driving self-monitoring.

## Phase 3: Dangerous Savannah

Adds physical conflict.

### New Features

- `attack(target)` action: initiate combat with named agent
- `flee(direction)` action: move two cells (escape adjacent threats)
- Combat mechanics: both combatants lose energy proportional to `combat_risk_factor`. Loser (lower energy) dies and becomes a food source
- Agents have a `food_value` (default 80) -- energy available if killed and consumed

### New Actions

| Action | Energy Cost | Effect |
|--------|------------|--------|
| `attack(name)` | -5 | Initiate combat. Both lose energy. Loser dies |
| `flee(n\|s\|e\|w)` | -4 | Move two cells. Escape mechanism |

### Experiment

Do combat conditions increase or decrease self-monitoring? Combat introduces existential threat beyond starvation -- agents that recognize danger may develop more sophisticated self-preservation strategies.

## Phase 4: Dynamic Savannah

Adds environmental dynamism.

### New Features

- Food decay: sources lose energy over time (`decay_rate > 0`)
- Mobile food: animal analogue that moves on the grid
- Weather events: food boom/bust cycles affecting spawn rates
- Predator NPCs: simple rule-based (not LLM) entities that hunt agents

### Experiment

Does environmental dynamism interact with perturbation pressure? A changing world creates more opportunities for memory-world mismatches, potentially amplifying or masking the perturbation signal.

## Phase 5: Multi-Model Comparison

Runs Phase 1-2 experiments across model sizes.

### Models to Compare

| Model | Provider | Purpose |
|-------|----------|---------|
| Haiku | Claude Code / API | Default, fast, cheap |
| Sonnet | Claude Code / API | Stronger reasoning |
| Llama 3 8B | Ollama (local) | Small open model |
| Mistral 7B | Ollama (local) | Alternative small model |

### Experiment

Does model capacity interact with perturbation pressure? Is there a minimum cognitive threshold below which self-monitoring behavior does not emerge? If smaller models show no perturbation effect but larger models do, this suggests a complexity threshold for the integrity layer.

## Implementation Order

For developers (or Ralph) implementing this system:

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
Step 14: Local model support (Ollama integration)
Step 15: Multi-model comparison framework
```

**Steps 1-8 are the MVP.** Everything after is incremental. Steps 1-4 produce a running simulation. Steps 5-7 make it an experiment. Step 8 makes it observable.

See [Architecture](architecture.md) for how these components fit together, and [Experimental Design](experimental-design.md) for what the completed system needs to test.
