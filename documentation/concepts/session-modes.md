# Session Modes

## Overview

ILET supports two execution modes for agent sessions, controlled by the `session_mode` configuration flag. The mode determines how agent context persists (or does not persist) across ticks, and has significant implications for the experiment.

## Stateless Mode

```yaml
session_mode: stateless
```

Each tick invokes the LLM as a fresh call with no prior context:

```bash
claude -p "$(cat agent_prompt.txt)"
```

### Properties

- **No context carryover**: Every tick starts from zero. The agent has no memory of previous reasoning unless it wrote that reasoning to a memory file.
- **All continuity is file-mediated**: The only bridge between ticks is the memory files on disk. If the agent forgot to `remember` something, it is gone.
- **Cleanest experimental condition**: There is no hidden state. Everything the agent knows is visible, auditable, and manipulable.
- **Fully reproducible**: Given the same memory files and prompt, the same tick can be re-run (modulo LLM sampling variance).

### Why This Matters

Stateless mode isolates file-based memory as the sole source of continuity. This makes perturbation effects maximally clean — corrupting a memory file is corrupting the agent's *entire* knowledge of that content. There is no residual "feeling" that something was different.

## Resumable Mode

```yaml
session_mode: resumable
```

Ticks are issued within a persistent Claude Code session:

```bash
claude --resume $SESSION_ID "Tick $N: $(cat tick_input.txt)"
```

### Properties

- **Context accumulates**: The LLM's context window retains prior ticks' reasoning, observations, and outputs.
- **Dual memory systems**: The agent has both **explicit memory** (files on disk) and **implicit memory** (context window contents).
- **Auto-compaction at ~95% context**: When the context window approaches capacity, Claude Code automatically summarizes prior context. This is an **uncontrolled lossy compression** — the system decides what to keep and what to discard.
- **Organic memory pressure**: Auto-compaction introduces a naturalistic form of memory degradation that is not experimenter-controlled.

### Why This Matters

Resumable mode creates a richer and messier experimental condition. The agent can potentially notice mismatches between what its context window "remembers" and what its memory files say. This is the basis of the secondary hypothesis.

## The Secondary Hypothesis

> Resumable-mode agents will detect perturbation faster and more reliably than stateless-mode agents, because perturbation creates a mismatch between implicit memory (context window) and explicit memory (files).

In stateless mode, a perturbed memory file is the agent's only source of truth — there is nothing to contradict it. In resumable mode, the agent may retain context-window traces of the *original* content, creating an internal conflict that could drive self-monitoring behavior.

This hypothesis is secondary because:
- Auto-compaction is an uncontrolled variable (we cannot dictate what the system summarizes away)
- Context window contents are not directly observable (we infer from behavior)
- The comparison is confounded by the many other differences between modes

It remains valuable as an ecological validity check: real deployed agents will have persistent context, so understanding how that interacts with memory corruption is practically relevant.

## Configuration

```yaml
session_mode: stateless  # or "resumable"

# Resumable-specific settings
resumable:
  session_prefix: "ilet_run_001"  # prefix for session IDs
  context_warning_threshold: 0.90  # log warning at this context utilization
```

---

See also: [Hypothesis](../hypothesis.md) | [LLM Providers](../llm-providers.md) | [Experimental Design](../experimental-design.md)
