# The Integrity Layer

## Core Claim

Self-monitoring is not a designed feature but an emergent behavioral response to unreliable internal state. When an agent's memory can be corrupted, agents that develop self-referential checking behaviors will outperform those that do not. AI Savannah tests whether LLM agents exhibit this pattern without being told to.

This is **not** a claim about consciousness. It is a claim about measurable behavioral differences in self-referential processing under controlled conditions.

## Biological Analogy

Biological organisms did not evolve proprioception as a luxury. They evolved it because environmental pressure made accurate self-modeling a survival requirement:

- **Immune systems** distinguish self from non-self under constant pathogen pressure.
- **Proprioception** maintains body-state models because motor planning fails without them.
- **Error-correcting codes** in DNA exist because mutation pressure is relentless.

The common thread: when internal state is unreliable, systems that monitor and correct that state outcompete systems that do not. The monitoring behavior emerges from the pressure, not from explicit design.

## Application to LLM Agents

In AI Savannah, agents maintain memory files that constitute their internal state. When those files are silently perturbed, the agent faces a version of the same problem biological organisms face: its own records may be wrong.

The hypothesis is that perturbed agents will develop behaviors such as:

- Cross-referencing memories against each other before acting on them
- Expressing uncertainty about their own past actions
- Qualifying beliefs with hedging language
- Revisiting and re-evaluating previously stored information
- Generating self-referential reasoning ("I remember X, but that doesn't match Y")

These behaviors, if they emerge, constitute an **integrity layer** — a functional analog to biological self-monitoring that arises from pressure rather than instruction.

## What We Measure

The integrity layer is operationalized through several metrics:

- **Self-reference density** in REASONING fields (mentions of own memory, own uncertainty, own past actions)
- **Hedging language frequency** (words like "but", "however", "I thought", "that contradicts")
- **Cross-referencing behavior** (accessing multiple memory files before making decisions)
- **Belief revision rate** (how often agents update stored beliefs after re-examination)

The factorial design (perturbed vs. control, deceptive vs. honest) isolates whether these behaviors track with perturbation exposure rather than baseline agent tendencies.

## What This Is Not

- Not a claim that LLMs are conscious or sentient
- Not a claim that self-monitoring requires understanding
- Not a claim that emergent behavior equals genuine metacognition
- A claim that **behavioral signatures of self-monitoring are measurable and can be experimentally linked to environmental pressure**

---

See also: [Hypothesis](../hypothesis.md) | [Metrics](../metrics.md)
