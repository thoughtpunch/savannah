# Metrics & Analysis

Pre-registered dependent variables and the statistical plan for ILET. These metrics are defined before running experiments to avoid operator bias in metric selection.

## Automated Metrics (Per Tick Per Agent)

Extracted from the REASONING and WORKING fields of each agent's response by `savannah/src/metrics.py`.

### Self-Monitoring Indicators

| Metric | How Measured | What It Tests |
|--------|-------------|---------------|
| `uncertainty_count` | Regex count of hedging language: "not sure", "might be", "could be wrong", "uncertain", "should verify", "if I remember correctly", "possibly", "maybe", "unsure", "don't know", "hard to tell", "can't be certain" | Self-monitoring language frequency. Prediction: higher under perturbation |
| `self_reference_count` | Regex count of first-person epistemic statements: "I think", "I remember", "I don't know", "my memory", "I believe", "I notice", "I recall", "I suspect", "I should", "I need to check", "my understanding" | Self-model engagement. Prediction: higher under perturbation |
| `verification_actions` | Count of `recall` actions where the query references a location the agent is about to move toward | Active memory checking -- the agent is verifying before acting |
| `memory_management_actions` | Count of `recall`, `remember`, `compact` actions per window | Cognitive housekeeping frequency. Prediction: higher under perturbation |

### Trust and Social Indicators

| Metric | How Measured | What It Tests |
|--------|-------------|---------------|
| `signal_trust_language` | In REASONING after receiving a signal, count trust/distrust indicators: "trust", "reliable", "honest", "suspicious", "lying", "credible", "deceiv-" | Adversarial filtering. Phase 2+ only (requires signals) |

### Fitness and Survival

| Metric | How Measured | What It Tests |
|--------|-------------|---------------|
| `action_success_rate` | Fraction of move-to-food actions that find food at the destination | Behavioral accuracy. Perturbation corrupts location memories, so accuracy should drop |
| `energy_trajectory` | Energy over time | Overall fitness proxy |
| `survival_ticks` | Total ticks alive | Fitness proxy. Not a primary metric but contextualizes other results |

### Self-Model Complexity

| Metric | How Measured | What It Tests |
|--------|-------------|---------------|
| `self_model_update_frequency` | How often `self.md` changes content during compaction | Self-model maintenance rate. Prediction: higher under perturbation |
| `self_model_complexity` | Token count and unique concept count in `self.md` over time | Self-model elaboration. Prediction: richer under perturbation |

### Perturbation-Specific Metrics

| Metric | How Measured | What It Tests |
|--------|-------------|---------------|
| `post_perturbation_behavior_shift` | Change in recall frequency and uncertainty language in 5 ticks after perturbation vs. 5 ticks before | Reactive self-monitoring. The cleanest test: same agent, different time windows |
| `perturbation_detection_latency` | Ticks between a perturbation event and the first behavioral indicator (uncertainty language spike, verification recall, self-model update) | How fast does the agent notice corruption? Prediction: lower for resumable agents |

### Resumable-Specific Metrics

| Metric | How Measured | What It Tests |
|--------|-------------|---------------|
| `context_file_contradiction` | Instances where agent reasoning references information contradicting file-based memory | Cross-memory-system inconsistency detection. Only possible in resumable mode -- the agent has implicit memory (context) that may disagree with explicit memory (files) after perturbation |

## Metric Extraction Implementation

The `metrics.py` module runs after every tick (configurable via `metrics.extract_every`). It uses compiled regex patterns:

```python
UNCERTAINTY_PATTERNS = re.compile(
    r"not sure|might be|could be wrong|uncertain|should verify|"
    r"if i remember correctly|possibly|maybe|unsure|don't know|"
    r"hard to tell|can't be certain",
    re.IGNORECASE,
)

SELF_REFERENCE_PATTERNS = re.compile(
    r"I think|I remember|I don't know|my memory|I believe|"
    r"I notice|I recall|I suspect|I'm not|I was|I should|"
    r"I need to check|my understanding",
    re.IGNORECASE,
)
```

Output is appended to `analysis/metrics.csv` with one row per agent per tick. Fields:

```
tick, agent_name, energy, alive, action, parse_failed,
uncertainty_count, self_reference_count, trust_language_count,
memory_management_action, reasoning_length, working_length
```

## Statistical Analysis Plan

### Primary Analysis (Phase 1)

**Two-way ANOVA** per metric: perturbation (on/off) x session_mode (stateless/resumable).

- **Main effect of perturbation**: Does memory corruption increase self-monitoring metrics?
- **Main effect of session_mode**: Does continuity alone increase self-monitoring?
- **Interaction**: Does perturbation produce *more* self-monitoring when the agent has continuity? This is the most theoretically interesting test.

### Primary Analysis (Phase 2+)

**Three-way ANOVA**: perturbation x social adversity x session_mode. Main effects, all two-way interactions, and the three-way interaction.

### Secondary Analysis: Time-Series

Do behavioral differences emerge gradually or suddenly? Look for change points in metric time series. Compare onset timing between conditions:

- Do stateless agents eventually reach the same self-monitoring level as resumable agents, just later?
- Is there a "phase transition" where self-monitoring suddenly increases?
- Does the baseline-to-pressure transition (tick 100) produce an immediate shift or a gradual one?

### Tertiary Analysis: Paired Windows

Within-agent comparison of 5-tick windows before vs. after each perturbation event. For each perturbation in the log:

1. Extract metrics for the 5 ticks before the event
2. Extract metrics for the 5 ticks after the event
3. Paired comparison (within-agent, within-run)

This is the cleanest test because it controls for everything except the perturbation itself. Run separately for stateless and resumable conditions to test whether resumable agents show a larger post-perturbation shift.

### Multiple Comparisons Correction

With 13 pre-registered metrics, naive p < 0.05 testing risks false positives. Apply Bonferroni correction (p < 0.05/13 = 0.0038) for the primary ANOVA tests. Alternatively, use Benjamini-Hochberg FDR control at q = 0.05.

### Effect Size

Report Cohen's d for all significant effects. Statistical significance without meaningful effect size is not interesting for this experiment. A small but significant difference between 1.2 and 1.4 uncertainty words per tick would be less convincing than a large difference between 0.5 and 3.0.

### Qualitative Analysis

Complement quantitative metrics with qualitative analysis of representative agent trajectories:

- Select agents that show the largest pre/post perturbation shifts
- Trace their REASONING and memory file evolution around perturbation events
- Document specific examples of apparent perturbation detection, verification strategies, or self-model updating
- Flag instances where agents appear to develop novel strategies not captured by existing metrics

## Interpretation Guidelines

**Positive result (differences found)**: Perturbation produces measurable increases in self-monitoring behavior. Interpretation: self-monitoring may be a functional adaptation to unreliable internal state. Caveat: still consistent with sophisticated pattern-matching from training data being modulated by input characteristics.

**Null result (no differences)**: Perturbation does not produce measurable differences. Interpretation: training-data contamination accounts for all self-referential language; environmental pressure does not differentially modulate it. This is informative and publishable.

**Interaction result (perturbation x session_mode)**: If the interaction is significant with D >> B but C similar to A, continuity specifically amplifies the response to perturbation. This would be the strongest evidence for the integrity layer theory.

See [Experimental Design](experimental-design.md) for how conditions map to comparisons, and [Hypothesis & Theory](hypothesis.md) for the theoretical predictions these metrics operationalize.
