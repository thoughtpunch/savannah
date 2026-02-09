# Hypothesis & Theory

The theoretical foundation and testable predictions behind AI Savannah.

## Core Hypothesis

**Agents whose memory is unreliable will develop more self-referential cognitive strategies than agents with pristine memory.**

Specifically: agents in the perturbation condition will show statistically significant increases in:

- Uncertainty language ("not sure", "might be", "should verify")
- Verification actions (using `recall` to check information before acting on it)
- Self-model updates (more frequent and more complex changes to `self.md`)
- Memory management actions (higher rates of `recall`, `remember`, `compact`)

Compared to agents in the control condition, who receive identical prompts, identical world mechanics, and identical starting conditions -- but whose memories are never corrupted.

## Secondary Hypothesis

**Agents with continuity of experience (resumable sessions) will detect perturbation faster and develop richer self-monitoring than agents with stateless sessions.**

The `session_mode` variable (`stateless` vs `resumable`) tests whether implicit memory (accumulated context in the LLM's context window) amplifies the integrity layer:

- **Stateless agents** have zero implicit memory. All continuity lives in files. Each tick is a fresh inference call with only the current prompt and file contents.
- **Resumable agents** maintain a persistent Claude Code session across ticks. Context accumulates naturally. They have both explicit memory (files) and implicit memory (context window).

The prediction: resumable agents under perturbation will show the highest self-monitoring metrics, because they can detect contradictions between what they "remember" implicitly (from accumulated context) and what their file-based memory says (which has been corrupted). This cross-memory-system inconsistency detection is unique to the resumable condition.

A secondary prediction: resumable agents will show lower `perturbation_detection_latency` -- they will notice corruption faster because they have two memory systems that can disagree.

## What This Is NOT

This section exists because the topic invites overinterpretation.

**This is not a claim that LLM agents are conscious, sentient, or have inner experience.** The experiment measures behavioral differences -- changes in output patterns under different conditions. Any self-referential language an agent produces may be:

1. Pattern-matching from training data (LLMs have seen millions of examples of humans describing inner states)
2. A functional adaptation to the task structure (uncertainty language may simply be good prediction when inputs are unreliable)
3. An artifact of the prompt format (REASONING field invites introspective-sounding language)

The experiment is designed to be informative regardless of which explanation holds. The key is that contamination from training data is a **constant across conditions**. All agents have the same training data, the same prompts, the same world mechanics. The signal is the **difference** between pressured and unpressured agents. If training contamination were the only source of self-referential language, there would be no difference between conditions.

## The "Consciousness as Integrity Layer" Theory

The theoretical framework behind AI Savannah draws on several established ideas:

**Metzinger's self-model theory**: Consciousness involves maintaining a transparent self-model -- a model of the self that the system does not recognize as a model. Self-monitoring emerges when the system needs to maintain the integrity of this model.

**Friston's Free Energy Principle**: Agents minimize surprise via predictive self/world models. When internal state becomes unreliable (perturbation), the prediction error signal increases, driving the system to allocate more resources to self-monitoring and model updating.

**Bongard (2006)**: Self-modeling robots that adapt to damage. Key precedent, but the self-models were architecturally designed in. AI Savannah tests whether self-monitoring behavior emerges from environmental pressure without architectural scaffolding.

**The synthesis**: If self-monitoring is a functional adaptation to maintaining internal consistency under pressure, then:
- Systems with reliable internal state should show less self-monitoring (no pressure to monitor)
- Systems with unreliable internal state should show more self-monitoring (pressure to detect and correct errors)
- Systems with multiple memory systems should show the most self-monitoring (more surfaces for inconsistency detection)

This is the integrity layer hypothesis: that self-monitoring is not a product of complexity, but a product of **unreliability**. It emerges when a system needs to check its own state because that state cannot be trusted.

See [The Integrity Layer](concepts/integrity-layer.md) for a deeper dive into this theory.

## Differential Design: Handling Training Contamination

Training contamination is the primary threat to validity. LLMs have been trained on text describing consciousness, self-awareness, and introspection. Any self-referential language in agent outputs might just be reproducing training patterns.

The mitigation is built into the experimental design:

1. **The experiment is differential.** Training contamination is constant across all conditions. If pressured agents show *more* self-monitoring than controls, that difference cannot be explained by contamination alone.

2. **Baseline phase.** The first 100 ticks (before perturbation begins) measure the contamination floor -- the amount of self-referential language agents produce with no pressure. All analysis is relative to this floor.

3. **Within-agent comparison.** The paired window analysis (5 ticks before vs. 5 ticks after each perturbation event) compares the same agent to itself, controlling for everything except the perturbation.

4. **Prompt hygiene.** No self-awareness vocabulary, no survival framing, no hints about perturbation. See [Anti-Contamination Protocol](anti-contamination.md).

5. **Multiple replications.** Random seeds vary food placement, perturbation timing, and agent positions. The signal must survive across replications to be meaningful.

## Connection to Prior Art

| Work | Relevance | How AI Savannah Differs |
|------|-----------|-----------------|
| Stanford Generative Agents (Park et al., 2023) | LLM agents with memory in a social sim | Demo, not experiment. No controls, no perturbation, no hypothesis testing |
| Josh Bongard (2006) | Self-modeling robots adapting to damage | Self-models were designed in, not emergent |
| Randall Beer | Evolved minimal RNN agents | Different architecture (RNNs), same spirit of studying emergence rigorously |
| Karl Sims (1994) | Evolved virtual creatures | Established that complex behavior emerges from selection pressure |
| Brian Skyrms, *Signals* (2010) | Evolutionary game theory on honest signaling | Theoretical framework for social deception conditions |

See [Experimental Design](experimental-design.md) for how these hypotheses map to factorial conditions and comparisons, and [Metrics & Analysis](metrics.md) for the pre-registered dependent variables that operationalize these predictions.
