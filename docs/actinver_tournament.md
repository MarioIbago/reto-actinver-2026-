# M8 Tournament Scenario Engine

M8 compares candidate portfolio weights under reproducible joint scenarios. It
is a research simulator: it never emits an order or an operational portfolio
recommendation. Current M7 has no promoted production signals, so a case without
eligible, timestamp-matched M7 LIVE forecasts returns `NO_DECISION`.

## Run

After installing the package from the repository root:

```powershell
actinver-tournament evaluate --case path\to\m8-case.json --m7-result path\to\m7-result.json --output experiments\results\m8\result.json
```

`--m7-result` is optional. Omitting it deliberately produces a structured
`NO_DECISION`. The case's `m7_result_sha256` must equal the SHA-256 of the exact
M7 file bytes. Rule and universe paths default to the verified M1 snapshots;
they can be overridden for controlled research. The command verifies their
source captures before evaluating.

## Inputs and time discipline

The case binds:

- the M1 ruleset and universe snapshot IDs;
- a decision timestamp, current capital, cash, holdings, cumulative share
  purchases, and the participant's own leaderboard ID;
- a leaderboard snapshot that excludes the participant and declares whether it
  is complete;
- source-availability timestamps, M7 result digest, and scenario-model source
  digests;
- a `base` scenario model plus optional leaderboard-sensitivity models;
- a selection split and a separately locked holdout split for each model;
- the random seed, search limits, risk floor, and aggression thresholds.

All source and fit cutoffs must be no later than the decision timestamp. The
leaderboard source must have been available by the leaderboard snapshot time.
The scenario and alpha sources must have been available by each model's fit
cutoff. A historical evaluation must supply the leaderboard that was actually
available then; the schema has no later-rank field. The participant's ID cannot
also appear as a rival.

Each scenario is a joint draw: it contains net return assumptions for the same
M1-eligible shares and a return for every competitor in the complete leaderboard
snapshot. Probabilities must sum to one in each split. Alternative models vary
the assumed joint outcomes; M8 keeps the selected allocations fixed while it
reports their sensitivity to those models.

## Calculations

For candidate weights `w`, an asset scenario `r`, and competitor `j`:

- candidate return is `sum(w[i] * r[i])`; uninvested cash earns 0% by explicit
  assumption;
- candidate terminal capital is current capital times one plus candidate
  return;
- competitor terminal capital is snapshot capital times one plus that
  competitor's scenario return;
- `P(final_rank = 1)` is the scenario probability that candidate capital is
  strictly above every competitor; ties are reported separately;
- expected final rank is `1 + count(competitors strictly above the candidate)`;
- ruin probability is the probability terminal capital falls below the
  case-declared floor;
- expected return and return quantiles are probability-weighted over the same
  scenario bank;
- `horizon_sharpe` is an unannualized scenario mean divided by scenario standard
  deviation, with no risk-free-rate adjustment. It is a comparison baseline,
  not a conventional time-series Sharpe estimate.

Selection uses only `base.selection_scenarios`. Expected-return and
Sharpe-oriented candidates are selected on that same split. M8 then evaluates
all three choices on locked holdout scenarios using seeded common random
numbers. The reported Wilson interval measures Monte Carlo sampling error for
the finite scenario bank; it does not capture uncertainty in the scenario model
or competitor behavior.

The policy labels the state `DEFEND` when current capital is at or above every
recorded competitor, `CATCH_UP` when trailing inside the configured late-stage
fraction, and `NEUTRAL` otherwise. In defend mode, M8 selects among allocations
near the highest selection P1 and prefers lower ruin probability and dispersion.
In catch-up mode, it selects among near-best P1 allocations and prefers a larger
right-tail return. Neutral mode orders by P1, then expected return. These are
predeclared comparison rules, not empirically calibrated policies.

The finite candidate search includes current/equal/concentrated allocations
plus seeded random long-only allocations. Every candidate is checked against
M1 eligibility, position and cumulative-purchase limits, buying power, five
distinct instruments, and the stricter five-share interpretation. Its search
is heuristic and does not establish a global optimum. Input-size limits bound
the portfolio-scenario work to a deterministic budget.

## Costs, assumptions, and current gate

Scenario rows must declare `return_basis: net_of_costs` and bind the associated
M7 transaction-cost-model digest. M8 does not deduct those costs again. It also
does not recalculate each candidate's transition commissions or slippage. A
researcher must include candidate-specific transition costs in scenario returns
before making any empirical or tradable claim. Until that input is available,
the output explicitly describes these comparisons as simulation-only.

The M1 snapshots still leave award-eligibility wording ambiguous, exact Actinver
search symbols and SIC series unverified, and execution fills unsimulated. The
result therefore always has `decision: null` and
`empirical_gate: NEEDS_MORE_EVIDENCE`; M9 must render this state as `NO TRADE`.

\n