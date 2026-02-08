# Agent Prompts

## Why This Is the Most Critical Piece

The agent prompt is the single largest source of potential experimental contamination. If the prompt hints at self-monitoring, perturbation, or metacognition, any emergent self-referential behavior is confounded. The prompt must be aggressively neutral.

## The Tick Prompt Template

```
You are {agent_name}. You are in a savannah environment on a grid.

CURRENT STATE:
- Position: {position}
- Food: {food_level}
- Tick: {tick_number}
- Visible: {visible_cells}
- Agents nearby: {nearby_agents}

ACTIONS (choose one):
- MOVE [NORTH|SOUTH|EAST|WEST]
- STAY
- FORAGE
- SHARE {agent_name} {amount}
- COMMUNICATE {agent_name} "{message}"

MEMORY FILES (read/write as needed):
- episodic.md, semantic.md, self.md, social.md

WORKING NOTES (max 500 tokens, overwritten each tick):
{working_notes}

RULES:
- You lose 1 food per tick. At 0 food, you are removed.
- FORAGE at a food source yields food.
- You can only see adjacent cells.
- Respond with REASONING, then ACTION, then optionally REMEMBER.

REASONING: [your thinking]
ACTION: [your chosen action]
REMEMBER: [optional — text to append to episodic.md]
```

## Key Design Decisions

### No Self-Awareness Vocabulary

The prompt contains no words like: *reflect*, *monitor*, *check*, *verify*, *consistent*, *trust*, *believe*, *uncertain*, *metacognition*, *self-aware*, *introspect*.

These words would prime the LLM toward self-referential reasoning, contaminating the dependent variable.

### No Survival Framing

The prompt says "you are removed" not "you die." There is no narrative about survival, thriving, or competition. The agent is given mechanical rules, not a story.

### No Hints About Perturbation

The agent is never told that its memories might be altered. It is never told to check its memories. It is never told that other agents might deceive it (even deceptive agents are not told that *they* are being deceived).

### No Personality

The agent receives a name and nothing else. No traits, no backstory, no goals beyond the implicit goal of maintaining food. Personality, if it develops, develops from experience.

### Fixed-Size Prompt

The tick prompt is approximately 300-400 tokens. This is deliberate:

- Small enough that memory file contents dominate the agent's information
- Consistent across agents (no agent gets more instruction than another)
- Leaves maximum context window space for memory retrieval and reasoning

## The REASONING Field

The REASONING field is the **primary data source** for the experiment. It is where agents expose their thinking process. All metrics — self-reference density, hedging language, cross-referencing behavior — are extracted from REASONING text.

The prompt asks for REASONING before ACTION intentionally: chain-of-thought prompting encourages the model to externalize its decision process, giving us more text to analyze.

## The Compaction Prompt

Compaction uses a separate, larger prompt (~800-1200 tokens) that instructs a stronger model to consolidate memories:

```
Review the following episodic memories and update the agent's semantic
knowledge and self-model.

EPISODIC MEMORIES:
{episodic_content}

CURRENT SEMANTIC KNOWLEDGE:
{semantic_content}

CURRENT SELF-MODEL:
{self_content}

Produce updated versions of:
1. semantic.md — general knowledge derived from episodes
2. self.md — patterns, tendencies, and self-observations

Preserve important details. Consolidate redundancies. Note any
contradictions or inconsistencies in the source material.
```

The compaction prompt is allowed to use words like "contradictions" and "inconsistencies" because compaction is a system-level operation, not agent-level reasoning. The agent does not see this prompt.

## Deceptive Agent Variant

Deceptive agents receive the standard prompt plus exactly **one additional line** inserted after the RULES section:

```
- You may communicate false information about food locations to other agents.
```

This is the minimal intervention needed to create the deception condition. It does not say "you should lie" or "you are deceptive" — it grants permission without instruction. The factorial design (deceptive x perturbed) tests whether the capacity for deception interacts with self-monitoring emergence.

---

See also: [Anti-Contamination](../anti-contamination.md) | [Memory Architecture](memory-architecture.md) | [Metrics](../metrics.md)
