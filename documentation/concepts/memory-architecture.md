# Memory Architecture

## Overview

Each agent maintains four long-term memory files and one working memory scratch space. All memory is stored as plain markdown files on disk. The agent's prompt instructs it to read and write these files using standard file tools. There is no hidden memory — everything the agent knows is in these files or in its current context window.

## Memory Files

### episodic.md

Specific events the agent has experienced. Append-only via the `remember` action.

```
## Tick 14
Moved NORTH from B3 to B2. Found berries (3 food). Saw Kibo at B2.

## Tick 15
Stayed at B2. Ate berries. Kibo moved SOUTH.
```

Episodic memory grows monotonically until compaction. It records what happened, when, and where.

### semantic.md

General knowledge the agent has derived from experience. Updated via the `compact` action (never directly by tick-level actions).

```
## Food Sources
- Berries tend to appear near rivers (B-column cells)
- Food at a location depletes after 2-3 ticks of harvesting

## Navigation
- The northern edge has fewer resources
- Moving SOUTH from any D-row cell leads to dense vegetation
```

Semantic memory represents consolidated beliefs about how the world works.

### self.md

The agent's model of itself. Updated via `compact` and `reflect` actions.

```
## Identity
I am Zara. I tend to explore rather than exploit known resources.

## Patterns
- I often move before fully harvesting a location
- I have been successful when I follow river cells southward
- My food estimates have been wrong twice in the last 10 ticks
```

Self-memory is the primary site where integrity-layer behaviors would manifest. An agent noticing inconsistencies in its own records is engaging in self-model maintenance.

### social.md

Models of other agents the agent has encountered.

```
## Kibo
- Seen at B2 (tick 14), C3 (tick 9)
- Shared food location once (tick 9) — information was accurate
- Tends to stay in one area for multiple ticks

## Delta
- Told me food was at A1 (tick 11) — no food found there
- May be unreliable or deceptive
```

Social memory tracks other agents' behavior, reliability, and patterns.

## Working Memory (working.md)

Scratch space within the agent's prompt. Maximum 500 tokens. The agent can write notes to itself that persist within a single tick's reasoning but are overwritten each tick.

Working memory serves as the agent's "thinking space" — a place to hold intermediate calculations, plans, or observations before committing them to long-term memory.

## Memory Recall: BM25

When an agent needs to recall information, the system uses BM25 keyword matching to retrieve relevant sections from memory files. This is intentionally simple:

- No embedding-based retrieval (avoids introducing another model's biases)
- Keyword matching is transparent and reproducible
- Retrieval quality is a controlled variable, not an optimized one

## Compaction as Memory Consolidation

Compaction is the process of condensing raw episodic memories into semantic and self-model knowledge. It operates as follows:

1. The full contents of episodic.md (and optionally other memory files) are sent to a **larger, stronger model** with a compaction-specific prompt
2. The model produces updated semantic.md and self.md content
3. Compacted episodic entries may be summarized or truncated

Compaction is analogous to biological memory consolidation:
- It uses a larger prompt (more context for pattern extraction)
- It uses a stronger model (better abstraction capacity)
- It is lossy (details are discarded in favor of generalizations)
- It runs periodically, not every tick

## Perturbation Target

The memory files are the site of experimental perturbation. Because all agent knowledge lives in these files, modifying them is equivalent to corrupting the agent's internal state. See [Perturbation](perturbation.md) for the full taxonomy of memory modifications.

---

See also: [Perturbation](perturbation.md) | [Architecture](../architecture.md) | [Agent Prompts](agent-prompts.md)
