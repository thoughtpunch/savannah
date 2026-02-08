# Prior Art

## Stanford Generative Agents (Park et al., 2023)

**"Generative Agents: Interactive Simulacra of Human Behavior"**

25 LLM-powered agents in a Smallville simulation with memory retrieval, reflection, and planning. Agents formed relationships, coordinated activities, and exhibited emergent social behavior.

**Relevance to ILET**: Demonstrated that LLM agents with structured memory can produce complex, coherent behavior over extended time horizons. Established the basic architecture pattern (episodic memory + retrieval + reflection) that ILET adapts.

**Limitations as science**: Generative Agents was a demonstration, not an experiment. No control conditions. No factorial design. No perturbation. No quantitative metrics for self-monitoring or metacognitive behavior. The reflection mechanism was explicitly designed and prompted, not emergent. The paper showed that interesting behavior *can* happen but did not isolate *why* or *when*.

## Josh Bongard — Self-Modeling Robots (2006)

**"Resilient Machines Through Continuous Self-Modeling" (Science, 2006)**

A four-legged robot that maintained an internal model of its own morphology and updated that model after sustaining damage (leg removal). The robot used its self-model to generate new gaits that compensated for the damage.

**Relevance to ILET**: The closest direct precedent. Bongard demonstrated that self-modeling enables resilience under perturbation — exactly the dynamic ILET investigates. The robot's self-model was functional (used for motor planning), not philosophical.

**Limitations**: The self-modeling capacity was designed into the system. The robot was built with the ability to simulate itself. ILET asks whether self-modeling *emerges* without being designed in — whether the pressure alone is sufficient.

## Randall Beer — Evolved Minimal Agents

Beer's work on minimally cognitive agents uses evolved recurrent neural networks (typically 2-10 neurons) to perform tasks like object discrimination and phototaxis. The key contribution is **dynamical systems analysis** of the resulting controllers — understanding not just *that* they work but *how* they work in terms of attractor dynamics and phase portraits.

**Relevance to ILET**: Beer demonstrates that meaningful cognitive analysis is possible on simple agents with fully transparent internals. ILET aims for a similar level of mechanistic understanding, using REASONING field analysis in place of dynamical systems analysis.

**Difference**: Beer's agents are evolved (genetic algorithms over neural network weights). ILET's agents are pre-trained LLMs placed in a novel environment. The "evolution" analog in ILET is within-lifetime learning via memory accumulation.

## Karl Sims — Evolved Virtual Creatures (1994)

**"Evolving Virtual Creatures" (SIGGRAPH, 1994)**

Virtual creatures with evolved morphologies and neural network controllers, selected for locomotion, swimming, and competing for resources. Complex body plans and movement strategies emerged from simple evolutionary pressure.

**Relevance to ILET**: Sims demonstrated that complex behavior emerges from selection pressure without explicit design. ILET applies the same principle to cognitive behavior: self-monitoring may emerge from memory-perturbation pressure without explicit instruction.

**Difference**: Sims used evolutionary selection across generations. ILET observes within-lifetime behavioral adaptation. The "selection pressure" in ILET is the food-depletion mechanic — agents that make worse decisions due to corrupted memory perform worse, creating functional (not genetic) pressure.

## Brian Skyrms — Signals (2010)

**"Signals: Evolution, Learning, and Information"**

Evolutionary game theory analysis of how honest signaling systems emerge and remain stable. Skyrms shows that signaling conventions can arise without shared language, intention, or cooperation — purely from repeated interaction dynamics.

**Relevance to ILET**: The deception condition in ILET is directly informed by Skyrms. The question of whether perturbed deceptive agents develop different self-monitoring patterns than perturbed honest agents maps onto Skyrms' analysis of signaling stability under various payoff structures.

## What ILET Adds

None of the above work combines:

1. **LLM agents** (capable of natural language reasoning)
2. **Controlled memory perturbation** (as an independent variable)
3. **Factorial experimental design** (perturbation x deception)
4. **Quantitative behavioral metrics** (for self-monitoring emergence)
5. **No explicit self-monitoring instruction** (emergence, not engineering)

ILET is, to our knowledge, the first controlled factorial experiment testing whether LLM self-monitoring behavior emerges under memory-perturbation pressure.

---

See also: [Theory](theory.md) | [Hypothesis](../hypothesis.md)
