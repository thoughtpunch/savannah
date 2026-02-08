# Project Overview

**ILET -- Integrity Layer Emergence Testbed**

ILET is a configurable simulation testbed that places LLM-powered agents in a survival environment (a virtual savannah) and measures whether environmental pressures -- specifically memory perturbation -- produce differential self-monitoring behaviors compared to unpressured controls.

The project is built and maintained using Claude Code with the Ralph autonomous agent loop and Beads issue tracking.

## What ILET Is

A behavioral ecology experiment on artificial agents. The simulation:

- Drops multiple LLM-powered agents into a 2D grid world with food sources
- Agents must find food to maintain energy; energy at zero means termination
- Each tick, every agent receives a minimal prompt describing its current state and chooses one action
- In experimental conditions, agent memories are silently corrupted by a "god-mode" perturbation system
- Automated metrics capture whether pressured agents develop more self-referential cognitive strategies than unpressured controls

The entire design is a controlled factorial experiment with pre-registered dependent variables, replications, and statistical analysis.

## What ILET Is NOT

This bears repeating clearly:

- **Not an attempt to create consciousness.** The simulation measures behavioral differences, not qualia or inner experience.
- **Not a demonstration of sentience.** Agents are LLM inference calls with file-based memory. They are not alive.
- **Not a claim about phenomenal experience.** Any self-referential language an agent produces may be pattern-matching from training data. The experiment is designed around this fact -- it measures the *difference* between conditions, not absolute presence of any property.
- **Not fine-tuning or training.** All agents use off-the-shelf LLM APIs with no model modifications.

The correct framing: "behavioral ecology of artificial agents under perturbation pressure."

## Core Hypothesis

Agents whose memory is unreliable will develop more self-referential cognitive strategies -- uncertainty language, verification behavior, self-model updates -- than agents with pristine memory. This tests the "consciousness as integrity layer" theory: that self-monitoring emerges under pressure to maintain internal consistency, not from complexity alone.

See [Hypothesis & Theory](hypothesis.md) for the full theoretical grounding.

## Secondary Hypothesis

Agents with continuity of experience (persistent context across ticks via resumable sessions) will detect perturbation faster and develop richer self-monitoring than agents with no implicit memory (stateless per tick). This tests whether continuity amplifies the integrity layer -- whether "having been there" matters for self-modeling, or whether explicit file-based records alone suffice.

## Why This Matters

Nobody has run a controlled factorial experiment measuring whether specific environmental pressures produce measurable differences in LLM agent self-monitoring behavior. The individual components exist in prior work (Stanford Generative Agents, Bongard's self-modeling robots, Beer's minimal agents). The experimental design combining them -- with clean controls, pre-registered metrics, and statistical rigor -- does not.

If the hypothesis holds, it suggests that self-monitoring is not a product of architectural complexity but a functional adaptation to unreliable internal state. If it fails, that is equally informative: it means training-data contamination accounts for all observed self-referential behavior, and there is no differential signal from environmental pressure.

## Key Documents

| Document | What It Covers |
|----------|---------------|
| [Hypothesis & Theory](hypothesis.md) | Core and secondary hypotheses, theoretical grounding, what this is NOT |
| [Architecture](architecture.md) | System design, directory layout, data flow, technology stack |
| [Experimental Design](experimental-design.md) | 2x2x2 factorial, conditions, key comparisons, replications |
| [Configuration Guide](configuration.md) | YAML config system, experiment overrides, factorial CLI |
| [Getting Started](getting-started.md) | Prerequisites, setup, running your first test |
| [Metrics & Analysis](metrics.md) | Pre-registered dependent variables, statistical plan |
| [Anti-Contamination Protocol](anti-contamination.md) | Prompt hygiene, controls, bias avoidance |
| [Implementation Phases](phases.md) | Phase 1-5 build plan with validation criteria |
| [Ralph & Beads Workflow](ralph-workflow.md) | Autonomous agent loop, ticket management |
| [LLM Provider System](llm-providers.md) | Claude Code, API, Ollama, adding new providers |

## Publication Target

Target venues: ALIFE conference, Artificial Life journal, or a workshop at NeurIPS/ICML on agent cognition. Publishability requires:

- Clean factorial design with 5+ replications per condition
- Pre-registered metrics with correction for multiple comparisons
- Effect sizes (Cohen's d), not just p-values
- Honest discussion of the training contamination confound
- Open-source code and data for reproducibility
