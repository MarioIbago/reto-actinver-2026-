# Dossier 001 — Tournament / Rank Optimization Science

**Status:** research dossier, not implementation  
**Date:** 2026-09-28  
**Purpose:** define what the project should optimize when the real objective is finishing #1 in a short investment contest.

## 1. Research question

How should portfolio construction change when the objective is not long-run expected utility, Sharpe ratio, or benchmark-relative return, but instead:

```text
maximize P(final_rank = 1)
```

under:
- a finite horizon;
- a leaderboard;
- many competing portfolios;
- official position constraints;
- uncertain rival behavior;
- no short selling in Actinver;
- human execution.

## 2. Why this matters

A conventional portfolio can be objectively good for wealth management and still be suboptimal for a contest.

The central distinction is:

```text
high expected return != high probability of finishing first
```

Contest optimization introduces:
- rank dependence;
- relative performance;
- opponent behavior;
- state-dependent risk taking;
- value of differentiation;
- positive-skew / right-tail demand;
- time remaining;
- leader gap.

This must remain separate from Alpha Engine research.

## 3. Core evidence

### 3.1 Staněk — M6 rank optimization

Source:
- Filip Staněk, *A Note on the M6 Forecasting Competition: Rank Optimization* (2023)
- SSRN: https://ssrn.com/abstract=4527154
- replication/code reference: https://github.com/stanek-fi/rank_optimization

Main finding relevant to Actinver:
the strategy that maximizes probability of reaching a top rank can differ materially from a strategy that maximizes expected return.

The paper formulates a finite-horizon rank-optimization problem and shows that a portfolio may improve its chance of winning while having poor expected performance.

**Project implication:** M8 must optimize tournament rank explicitly rather than pretending Sharpe/expected return is an adequate proxy.

### 3.2 Staněk — role of luck and strategic considerations in M6

Source:
- Filip Staněk, *M6 investment challenge: The role of luck and strategic considerations*
- International Journal of Forecasting, 2025
- https://doi.org/10.1016/j.ijforecast.2025.03.005

Relevant findings:
- extreme realized performance in a large competition can arise from chance;
- apparent outperformance should not automatically be interpreted as skill;
- differentiation from competitors can matter for ranking;
- the optimal contest objective is not the same as ordinary expected-return optimization.

In M6, greater use of short positions was associated with differentiation and higher top-rank incidence. This exact mechanism does **not** transfer directly to Actinver because short selling is prohibited.

**Transferable idea:** differentiation / low correlation with competitors may have tournament value.

**Non-transferable implementation:** shorting as the mechanism.

### 3.3 Portfolio Selection in Contests — Lu & Tse

Source:
- Yumin Lu, Alex S. L. Tse, *Portfolio Selection in Contests*
- SIAM Journal on Financial Mathematics, 2026
- UCL open version: https://discovery.ucl.ac.uk/id/eprint/10214043/
- DOI: https://doi.org/10.1137/24M1686358

The paper studies dynamic portfolio selection when rewards depend on terminal ranking.

Relevant theoretical result:
top-heavy reward structures can induce return distributions with greater positive skew and a high probability of poor outcomes. In winner-takes-all settings, greater competitive intensity can increase risky-asset exposure.

**Project implication:** under a first-place objective, right-tail shape can matter independently of mean return.

This does NOT imply:
- "always maximize volatility";
- "always concentrate";
- "always choose lottery-like assets".

The result is conditional on contest structure, state, opponent behavior and feasible assets.

### 3.4 M6 main competition findings

Source:
- Makridakis et al., *The M6 forecasting competition: Bridging the gap between forecasting and investment decisions*
- International Journal of Forecasting, 2025
- https://doi.org/10.1016/j.ijforecast.2024.11.002

Important lessons:
- forecasting relative asset performance was difficult;
- consistently outperforming was difficult;
- the connection between submitted forecasts and investment decisions was limited;
- risk models can matter when translating predictions into decisions.

**Project implication:** even if Alpha Engine forecasting is good, portfolio conversion can destroy or improve value. Prediction and decision must be tested separately.

### 3.5 Avoiding overconfidence

Source:
- Makridakis, Spiliotis, Michailidis, *Avoiding overconfidence: Evidence from the M6 financial competition*
- International Journal of Forecasting, 2025
- https://doi.org/10.1016/j.ijforecast.2024.10.001

Relevant result:
less than one quarter of M6 teams beat a simple probabilistic benchmark in forecast accuracy, and forecast performance was unstable.

The paper identifies overconfidence as a major failure mode.

**Project implication:** Tournament Brain must consume uncertainty / believability, not just point estimates.

### 3.6 Consistency, luck and extreme periods

Source:
- Kaltsounis et al., *Unraveling the effect of engagement and consistency in the results of the M6 forecasting competition*
- International Journal of Forecasting, 2025
- https://doi.org/10.1016/j.ijforecast.2025.04.002

Relevant finding:
performance can be strongly influenced by extreme periods and luck, while consistency also matters.

**Project implication:** post-hoc evaluation of our tournament outcome must separate:
- model quality;
- decision quality;
- execution;
- luck / realized path.

A winning result alone is not proof that the model was good.

## 4. Actinver-specific transferability

Actinver differs from M6 in important ways.

### 4.1 Horizon

Actinver is approximately six weeks, much shorter than the M6 investment challenge.

Consequences:
- terminal-rank objective dominates sooner;
- path dependence / regime dependence is stronger;
- a small number of events can dominate realized ranking;
- there is less time for weak expected edges to compound;
- state-dependent aggression may become important earlier.

### 4.2 Long-only constraint

Actinver prohibits direct short selling.

Therefore:
- M6 short-position findings cannot be copied;
- differentiation must come from asset selection, concentration, sector/macro exposure, cash, inverse instruments if genuinely eligible/operational, and timing.

Any inverse ETF treatment must be verified under M1/M3 before operational use.

### 4.3 Position constraint

Actinver has a maximum concentration rule per issuer/instrument that must be represented by M1/M3.

Tournament optimization must search only feasible portfolios.

### 4.4 Mixed universe

The eligible universe contains:
- Mexican equities;
- SIC equities;
- ETFs;
- funds;
- FIBRAs.

This is useful because the Tournament Brain can potentially create differentiated macro/sector exposures without direct short selling.

### 4.5 Human execution

M8/M9 decisions ultimately become manually entered orders.

Therefore the optimizer must penalize portfolios whose theoretical advantage depends on:
- unrealistic fills;
- impossible speed;
- excessive turnover;
- fragile intraday timing.

## 5. Proposed Tournament State

M8 should eventually consume something close to:

```text
TournamentState:
    timestamp
    capital
    cash
    holdings
    current_return
    current_rank
    leader_return_or_capital
    gap_to_leader
    sessions_remaining
    official_constraints
    candidate_return_distributions
    covariance_or_scenario_dependence
    liquidity
    execution_uncertainty
    leaderboard_uncertainty
    opponent_model_version
```

## 6. Objective candidates

The core objective should be directly rank-aware.

### Primary

```text
maximize estimated P(final_rank = 1)
```

### Diagnostics

Also report:
- expected terminal return;
- median terminal return;
- downside quantiles;
- probability of finishing top 3 / top 10;
- probability of catastrophic loss;
- terminal-return skew;
- expected rank;
- concentration;
- turnover;
- correlation with modeled opponent portfolios.

Do not replace the primary objective with one of these.

## 7. Opponent modeling

We do not know competitor portfolios.

Therefore M8 should not optimize against one imagined rival.

Recommended layers:

### Baseline opponent model
Simulate opponents from:
- broad-market-like portfolios;
- common high-beta portfolios;
- diversified long-only portfolios;
- random feasible portfolios.

### Leader-conditioned model
When leaderboard data exists, condition scenarios on:
- leader return;
- distribution of top-ranked returns;
- time remaining.

### Uncertainty
Run multiple rival models and measure policy sensitivity.

A decision that only works under one fragile opponent assumption should receive low believability.

## 8. Dynamic aggression hypothesis

A central research hypothesis:

```text
required risk-taking is state dependent
```

Expected direction to test, not assume:

- far behind + little time remaining:
  higher right-tail exposure may increase P(#1);

- near/at lead + little time remaining:
  reducing unnecessary idiosyncratic risk may preserve P(#1);

- early competition:
  expected edge / evidence quality may matter more because there is time to recover;

- late competition:
  rank gap and tail probability may dominate average return.

This must be derived by simulation under Actinver constraints.

## 9. Falsifiable hypotheses for later experiments

### TORN-001 — Objective mismatch
A portfolio selected to maximize expected return does not maximize simulated P(#1) under realistic contest states.

Reject if:
rank-aware optimizer does not improve P(#1) across meaningful simulated states.

### TORN-002 — State-dependent aggression
Optimal portfolio variance/right-tail exposure increases as negative leader gap grows and sessions remaining decline.

Reject if:
relationship is unstable or dominated by modeling assumptions.

### TORN-003 — Defend mode
When already leading late in the contest, lower correlation-adjusted active risk can improve P(#1) relative to expected-return maximizing allocation.

Reject if:
defensive policies do not improve rank probability after realistic opponent simulation.

### TORN-004 — Differentiation value
Conditional on similar expected return distributions, portfolios less correlated with common opponent exposures can have higher P(#1).

Reject if:
benefit disappears across rival models or is offset by weaker alpha / execution.

### TORN-005 — Positive skew
For a participant materially behind, positive-skew candidate distributions may dominate symmetric distributions with similar expected return/variance for P(#1).

Reject if:
skew advantage is not robust to scenario generation and feasible constraints.

### TORN-006 — Forecast uncertainty penalty
Using calibrated uncertainty/believability reduces false aggressive bets and improves simulated contest performance relative to using alpha scores alone.

Reject if:
uncertainty adjustment adds no stable value.

## 10. Baselines M8 must beat

At minimum:

1. equal weight feasible universe subset;
2. market / broad ETF proxy;
3. maximum expected return;
4. maximum Sharpe / risk-adjusted proxy;
5. volatility-targeted portfolio;
6. static high-beta portfolio;
7. random feasible portfolio;
8. naive catch-up rule based only on gap;
9. rank-aware optimizer.

The rank-aware system must prove incremental value versus these controls.

## 11. Simulation design

Recommended starting architecture:

```text
current state
    ↓
sample correlated candidate returns
    ↓
sample opponent returns / portfolios
    ↓
apply Actinver constraints + execution costs
    ↓
simulate terminal wealth/rank
    ↓
estimate P(#1)
    ↓
repeat under alternative rival/distribution models
```

Potential methods:
- Monte Carlo;
- historical bootstrap;
- block/bootstrap for dependence;
- empirical residual simulation;
- scenario mixtures by regime;
- dynamic programming only where state space is tractable;
- stochastic optimization / search over feasible portfolios.

Start simple.

## 12. Critical risks

### Model risk
P(#1) can be highly sensitive to tail assumptions.

### Opponent-model risk
We do not observe rival positions.

### Estimation error
Expected returns and covariance are noisy.

### Alpha circularity
Tournament Brain must not manufacture alpha.

### Overfitting to simulated rivals
A strategy can overfit the opponent generator just like a trading strategy can overfit price history.

### False precision
A reported P(#1)=12.37% is not credible unless uncertainty is reported.

## 13. Recommended outputs

Tournament Brain should return:

```text
portfolio
estimated_P_first
uncertainty_interval_or_sensitivity
expected_return
tail_metrics
expected_rank
key_scenarios
gap_state
risk_mode
main_reason
failure_modes
constraints_check
model_versions
```

Potential risk modes:
- DEFEND
- NEUTRAL
- CATCH_UP

These are descriptive policy states, not hard-coded trading rules.

## 14. What Codex should eventually test

- rank objective vs expected-return objective;
- state-dependent policies;
- alternative opponent generators;
- tail-distribution misspecification;
- correlation sensitivity;
- leader-gap uncertainty;
- no-short constraint;
- 50% concentration constraint;
- costs/fills;
- different universe subsets;
- effect of inverse ETFs only if M1/M3 confirm operational eligibility;
- robustness across synthetic and historical contest paths.

## 15. What NOT to infer

Do not infer:
- that maximum volatility is optimal;
- that concentration is always optimal;
- that positive skew guarantees higher P(#1);
- that M6 shorting results apply directly to Actinver;
- that winning proves alpha;
- that a precise simulated probability is objectively true;
- that Tournament Brain can compensate for unvalidated alpha.

## 16. Implementation order

Do not implement this in M0.

Later order:

```text
M4 validation primitives
        ↓
M5/M6 validated signals
        ↓
M7 calibrated distributions
        ↓
M8 simple opponent simulator
        ↓
M8 baseline P(#1) estimator
        ↓
rank-aware feasible optimizer
        ↓
sensitivity / misspecification tests
        ↓
M9 explanation layer
```

## 17. Bottom line

The strongest evidence supports the project's central architectural choice:

**Alpha generation and contest decision optimization are separate problems.**

The Tournament Brain should not ask only:
> Which portfolio has the highest expected return?

It should ask:
> Given what we know, what feasible portfolio gives the best robust estimate of finishing first under current contest state and rival uncertainty?

That claim is strong enough to guide architecture.

The exact optimal policy is not yet known and must be learned through Actinver-specific simulation and validation.
