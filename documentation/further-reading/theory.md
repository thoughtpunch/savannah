# Theoretical Foundations

## Friston's Free Energy Principle

Karl Friston's Free Energy Principle (FEP) proposes that all adaptive systems — from cells to brains — can be described as minimizing variational free energy, which is an upper bound on surprise (negative log-likelihood of sensory states given a generative model).

In practice, this means adaptive agents maintain **predictive models** of both themselves and their environment, and they act to minimize the discrepancy between predictions and observations.

**AI Savannah connection**: Memory perturbation injects prediction error directly into the agent's internal state. If the agent has formed expectations about what its memories should contain (even implicitly, via context-window traces in resumable mode), perturbation creates exactly the kind of surprise that FEP predicts should drive model-updating behavior. Self-monitoring *is* free energy minimization applied to the self-model.

## Metzinger's Self-Model Theory

Thomas Metzinger's self-model theory of subjectivity (SMT) proposes that consciousness arises from the maintenance of a **transparent self-model** — a model so seamlessly integrated that the system does not recognize it as a model. The system mistakes the map for the territory.

Key concepts:
- **Phenomenal Self-Model (PSM)**: The internal representation of the system as a whole
- **Transparency**: The self-model is transparent when the system cannot introspect the modeling process itself
- **Opacity**: When the modeling process becomes visible (e.g., during error or disruption), self-awareness increases

**AI Savannah connection**: AI Savannah does not claim to test consciousness. But Metzinger's framework predicts a specific behavioral signature: when a self-model is disrupted (made opaque), the system should exhibit increased self-referential processing. This is precisely what AI Savannah measures — whether perturbation (disruption of the agent's self-model file and other memory files) drives increased self-referential reasoning.

## Predictive Processing

Andy Clark, Jakob Hohwy, and others have developed the **predictive processing** framework: the brain as a hierarchical prediction engine that continuously generates top-down predictions and updates them based on bottom-up prediction errors.

Core principles:
- **Prediction**: The system constantly generates expectations about incoming information
- **Prediction error**: Mismatches between prediction and observation propagate upward
- **Precision weighting**: The system modulates how much weight to give prediction errors based on estimated reliability of the signal

**AI Savannah connection**: An agent that has accumulated memories over many ticks has implicitly formed predictions about what its memories contain. Perturbation violates these predictions. The question is whether the agent exhibits precision-weighting-like behavior — does it begin to treat its own memories as less reliable after encountering inconsistencies?

## Active Inference

Active inference extends predictive processing from perception to action. Agents do not just passively update models — they act on the world to bring observations in line with predictions. An agent that predicts it will see food at location B3 will *move toward B3* to confirm that prediction.

**AI Savannah connection**: Self-monitoring behavior can be understood as active inference turned inward. An agent that "predicts" its memories are consistent may engage in cross-referencing behavior (reading multiple memory files) as an active inference strategy — acting to confirm or disconfirm its prediction about its own internal consistency.

## Anil Seth — The Beast Machine

Anil Seth's work frames consciousness as **controlled hallucination** — perception is a process of active construction constrained by sensory signals. The self, in this view, is the most controlled hallucination of all: a predictive model of the organism's own body and internal states.

**AI Savannah connection**: If an LLM agent's "self" is constituted by its self.md file and the implicit patterns in its reasoning, then perturbation of self.md is perturbation of the agent's self-model. The question is whether the agent's behavior changes in ways consistent with a disrupted self-model — increased uncertainty, increased self-reference, increased model-maintenance behavior.

## How AI Savannah Operationalizes These Theories

| Theoretical Concept | AI Savannah Operationalization |
|---------------------|------------------------|
| Prediction error | Memory perturbation (inserting content that contradicts the agent's experience) |
| Free energy minimization | Self-monitoring behavior (cross-referencing, hedging, belief revision) |
| Self-model maintenance | Updates to self.md, self-referential REASONING content |
| Precision weighting | Changes in how confidently agents act on memory-derived information |
| Active inference (inward) | Cross-referencing multiple memory files before acting |
| Transparency/opacity | Whether agents begin to treat their own memories as objects of scrutiny rather than transparent facts |

AI Savannah does not prove or disprove any of these theories. It tests a specific, operationalized prediction derived from their convergence: **that memory perturbation should drive measurable increases in self-referential processing behavior**.

---

See also: [Prior Art](prior-art.md) | [Integrity Layer](../concepts/integrity-layer.md) | [Hypothesis](../hypothesis.md)
