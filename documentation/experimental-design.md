# Experimental Design

AI Savannah uses a factorial experimental design with pre-registered dependent variables, multiple replications, and randomization. This document describes the design, conditions, key comparisons, and replication strategy.

## Full Factorial: 2 x 2 x 2

The complete design crosses three independent variables, each with two levels:

| Axis | Level 0 (off) | Level 1 (on) | Config Key |
|------|--------------|--------------|------------|
| Perturbation | No memory corruption | 5% per-agent-per-tick corruption | `perturbation.enabled` |
| Social adversity | 0 deceptive agents | 3 deceptive agents | `social.deceptive_agents` |
| Session mode | Stateless (fresh context each tick) | Resumable (persistent context) | `llm.session_mode` |

This produces 2 x 2 x 2 = **8 conditions** in the full design.

## Phase 1 Design: 2 x 2

Phase 1 excludes social features (no signals, no observation, no deceptive agents). The design is 2 x 2 = **4 conditions**:

| Condition | Perturbation | Session Mode | What It Tests |
|-----------|-------------|--------------|---------------|
| **A** | off | stateless | Pure baseline. Floor for all metrics. No pressure, no continuity |
| **B** | on | stateless | **Core hypothesis.** Does perturbation drive self-monitoring with explicit memory only? |
| **C** | off | resumable | Context-only control. Does continuity alone produce more self-monitoring? |
| **D** | on | resumable | **Full condition.** Does continuity amplify perturbation-driven self-monitoring? |

## Key Comparisons

Each comparison isolates a specific effect:

### B vs A: Perturbation Effect (Stateless)

The primary hypothesis test. Both conditions use stateless sessions (no implicit memory). The only difference is whether memory is corrupted. If B shows more self-monitoring than A, perturbation drives self-referential behavior even without continuity.

### D vs C: Perturbation Effect (Resumable)

Does the perturbation effect replicate when agents have continuity? If D shows more self-monitoring than C, the result generalizes across session modes.

### C vs A: Continuity Effect (No Perturbation)

Does implicit memory alone change behavior? If C shows more self-monitoring than A without any perturbation, continuity itself produces self-referential patterns. This would be interesting but would weaken the perturbation-specific claim.

### D vs B: Continuity Effect (Under Perturbation)

Does continuity amplify self-monitoring under pressure? If D >> B but C is roughly equal to A, then continuity specifically amplifies the response to perturbation. This is the interaction effect and is the most theoretically interesting result.

### D vs A: Combined Effect

Maximum pressure (perturbation + continuity) vs. minimum pressure (no perturbation + stateless). The largest expected difference. Useful for establishing the overall range of effects.

### Interaction Term (ANOVA)

The two-way interaction between perturbation and session_mode in the ANOVA is the most informative single test. A significant interaction means the effect of perturbation depends on session mode (or vice versa), which directly tests whether continuity amplifies the integrity layer.

## Replications

Each condition must be run multiple times with different random seeds to establish that results are not artifacts of a single initialization.

- **Minimum replications**: 5 per condition
- **Recommended for publication**: 10+ per condition
- **Random seeds**: Each replication uses a different seed controlling:
  - Agent starting positions
  - Food source placement
  - Perturbation event timing (which ticks, which agents)
  - Name assignment (shuffled independently per replication)

Seeds are assigned sequentially from a base seed: replication 1 uses seed 42, replication 2 uses seed 43, etc.

### What Varies Between Replications

- Initial food source positions
- Initial agent positions
- Perturbation timing (same rate, different random draws)
- Agent names (shuffled from the same pool)

### What Is Held Constant

- Config parameters (tick count, energy costs, grid size, etc.)
- Prompt template
- LLM model and temperature
- Perturbation rate and type weights
- Analysis pipeline and metric definitions

## Baseline Phase

Every condition includes a baseline phase (ticks 0-99) where perturbation is disabled and no deceptive agents are active. This establishes:

1. **Contamination floor**: How much self-referential language agents produce with zero pressure
2. **Behavioral baseline**: Normal action patterns, energy trajectories, memory management rates
3. **Within-run control**: Pre-perturbation vs. post-perturbation comparison within the same agents

All metrics computed for the experimental phase are also computed for the baseline phase. Analysis compares post-baseline behavior relative to the baseline floor.

## Randomization Protocol

The design uses the following randomization:

1. **Condition assignment is not randomized** -- all conditions are defined by config, not by random assignment of agents to conditions. Every agent within a condition experiences the same treatment.
2. **Within-condition randomization** (via seed) controls spatial and temporal stochasticity.
3. **Name assignment** is random and not correlated with condition. Perturbed agents do not get names suggesting confusion, and control agents do not get names suggesting clarity.

## Statistical Analysis Plan

See [Metrics & Analysis](metrics.md) for the full metric set. The analysis plan:

- **Primary test (Phase 1)**: Two-way ANOVA per metric: perturbation (on/off) x session_mode (stateless/resumable). Main effects and interaction.
- **Primary test (Phase 2+)**: Three-way ANOVA adding social adversity.
- **Secondary**: Time-series analysis for change points and onset timing.
- **Tertiary**: Within-agent paired comparison of 5-tick windows before vs. after each perturbation event.
- **Multiple comparisons**: Bonferroni correction across the metric set.
- **Effect size**: Cohen's d for all significant effects.

## Running the Factorial

```bash
# Phase 1: 2x2 design, 5 replications
python savannah/run.py --factorial --axes perturbation,session_mode --replications 5

# Phase 2+: Full 2x2x2 design
python savannah/run.py --factorial --axes perturbation,session_mode,social --replications 5

# Quick validation (2 replications, 500 ticks)
python savannah/run.py --factorial --axes perturbation,session_mode --replications 2 --ticks 500
```

See [Hypothesis & Theory](hypothesis.md) for the theoretical predictions these comparisons test, [Metrics & Analysis](metrics.md) for the dependent variables, and [Configuration Guide](configuration.md) for how experiment configs map to conditions.
