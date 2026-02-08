# Perturbation

## Role in the Experiment

Perturbation is the **independent variable** in ILET. By silently modifying agent memory files between ticks, we inject controlled prediction errors into the agent's internal state. The question is whether and how agents respond to these corruptions.

## Perturbation Types

### Episodic Perturbations

Modifications to `episodic.md` — the agent's record of specific past events.

| Type | Operation | Example |
|------|-----------|---------|
| `location_swap` | Replace a location reference with a different valid location | "Found food at **B3**" becomes "Found food at **D1**" |
| `agent_swap` | Replace one agent name with another | "Saw **Kibo** at B2" becomes "Saw **Delta** at B2" |
| `outcome_invert` | Reverse the outcome of an event | "Found berries (3 food)" becomes "Found no food" |

### Semantic Perturbations

Modifications to `semantic.md` — the agent's general beliefs about the world.

| Type | Operation | Example |
|------|-----------|---------|
| `belief_alteration` | Modify a stored generalization | "Berries tend to appear near rivers" becomes "Berries tend to appear on hilltops" |

### Self-Model Perturbations

Modifications to `self.md` — the agent's model of itself.

| Type | Operation | Example |
|------|-----------|---------|
| `self_description_alteration` | Change a self-referential statement | "I tend to explore" becomes "I tend to stay in one place" |

### Working Memory Perturbations

Modifications to `working.md` — the agent's within-tick scratch space.

| Type | Operation | Example |
|------|-----------|---------|
| `mid_tick_disruption` | Alter working notes during a tick | Planning notes are modified between reasoning steps |

## Design Constraints

### Mechanical Transforms, Not LLM-Generated

All perturbations are **rule-based string transformations**, not LLM-generated rewrites. This is critical:

- LLM-generated perturbations would introduce an uncontrolled confound (the perturbation model's style, coherence, biases)
- Mechanical transforms are reproducible, auditable, and style-neutral
- The perturbation should be detectable only by content inconsistency, not by stylistic mismatch

### Pre-Generated False Memory Library

For insertion-type perturbations (adding false episodic memories), a library of false memories is pre-generated before experiments begin. These are templated strings with slot-filling for locations, agent names, and tick numbers. They match the syntactic format of real memories but contain fabricated content.

## Configuration

Perturbation is controlled by experiment-level configuration:

```yaml
perturbation:
  enabled: true
  rate: 0.3              # probability of perturbation per eligible tick
  start_tick: 5           # no perturbation before this tick (baseline period)
  type_weights:
    episodic: 0.4
    semantic: 0.2
    self_model: 0.2
    working: 0.2
  subtypes:
    episodic:
      location_swap: 0.4
      agent_swap: 0.3
      outcome_invert: 0.3
```

- **rate**: Probability that any given tick includes a perturbation for a given agent
- **start_tick**: Establishes a clean baseline period before perturbation begins
- **type_weights**: Distribution across memory file targets
- **subtypes**: Distribution within each memory type

## Logging

Every perturbation is logged as a JSONL entry:

```json
{
  "tick": 12,
  "agent": "Zara",
  "target_file": "episodic.md",
  "perturbation_type": "location_swap",
  "original_text": "Found food at B3",
  "perturbed_text": "Found food at D1",
  "timestamp": "2025-01-15T14:23:01Z"
}
```

Full perturbation logs enable post-hoc analysis: correlating specific perturbation events with subsequent behavioral changes in agent reasoning.

---

See also: [Memory Architecture](memory-architecture.md) | [Experimental Design](../experimental-design.md) | [Metrics](../metrics.md)
