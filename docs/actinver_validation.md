# M4 — Baselines and validation

## Scope

M4 adds two software contracts:

- `build_baseline_weights` turns normalized M2 `price_bar` records into
  deterministic, long-only target weights at a caller-supplied point in time.
- `actinver-m4 evaluate` evaluates aligned portfolio-return trials using
  chronological splits, costs, walk-forward folds, bootstrap, CSCV/PBO, DSR,
  regime labels, sensitivity checks, and explicit promotion criteria.

Baseline weights are intentions only. They do not generate orders or assert
that a fill occurred. The validation engine receives gross portfolio returns
and turnover from an upstream M3 replay or a separately documented equivalent;
it does not reconstruct fills.

## Reference baselines

| Baseline | Deterministic definition |
| --- | --- |
| `random_control` | Seeded positive pseudo-random weights over instruments with visible bars. |
| `equal_weight` | Equal target weights over instruments with visible bars. |
| `benchmark` | 100% weight in the explicitly supplied benchmark instrument ID. |
| `momentum` | Normalize positive close-to-close return over the specified lookback. |
| `relative_strength` | Normalize positive lookback return in excess of the explicit benchmark return. |
| `abnormal_volume` | Normalize positive current-volume ratio over the median of preceding lookback volumes. |
| `reversal` | Normalize positive negative lookback return. |
| `breakout_volatility_expansion` | Require close above prior lookback highs and current true range above the mean prior range. |

Every baseline reads bars visible under `source` or `system` as-of semantics,
requires timezone-aware cutoffs, and filters future event or availability times.
The caller supplies the eligible instrument IDs and benchmark ID. Missing bars
produce no target weight; the function does not fill forward stale values.
An empty target is an explicit no-position output.

## Validation input and decisions

The strict input contract is
[`schemas/validation_case.schema.json`](../schemas/validation_case.schema.json).
Each trial supplies aligned date, gross portfolio return, total turnover, and
optional caller-defined regime labels. `gross_return` is before transaction
fees and `turnover` is total absolute buy-plus-sell notional divided by prior
portfolio value. Case inputs require exact decimal strings or integers; binary
floating-point inputs are rejected.

Train, validation, and final test ranges must be chronological and disjoint.
Candidates are selected by annualized net Sharpe on validation only; ties use
trial ID ordering. The result reports test metrics only for the selected trial,
plus the named benchmark for comparison. The final test does not affect
selection. Holdout locking itself is an explicit caller assertion; M5 must
preserve the experiment history so repeated test use cannot be hidden.

M1's 0.10% commission and 16% IVA on the commission are charged on each unit of
declared traded notional. Cost-sensitivity rows add the declared slippage basis
points per side. The caller must not include those same fees a second time in
`gross_return`.

The engine provides:

- train, validation, and single final-test metrics;
- expanding or rolling walk-forward selection/evaluation before the final
  test, with non-overlapping evaluation folds;
- a seeded circular moving-block bootstrap interval for mean test return;
- CSCV/PBO on train plus validation only;
- a Deflated Sharpe Ratio probability on validation, using attempted trial
  count and observed variation in trial Sharpe estimates;
- cost sensitivity without reselecting a candidate, caller-labeled regime
  splits, sample-size diagnostics, and descriptive validation-Sharpe summaries
  grouped by submitted parameter values.

Each trial includes a scalar-valued `parameters` object. Its fingerprint is
SHA-256 over compact, sorted, UTF-8 JSON with one trailing newline; the evaluator
recomputes and checks the fingerprint before calculating the sensitivity
summary. The summary describes submitted variants. When multiple parameter
values change together, it cannot attribute performance changes to one cause.

PBO follows the combinatorially symmetric cross-validation approach described
by [Bailey, Borwein, López de Prado, and Zhu](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253).
DSR follows [Bailey and López de Prado](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf).
The DSR expected-maximum approximation assumes a comparable distribution of
trial Sharpes; its `attempted_trial_count` is treated as the number of
independent trials. Strongly correlated or incompletely recorded trials make
that adjustment approximate. PBO and DSR are diagnostics, not proof of an
edge.

`status` describes whether the software evaluation ran. `status_decision` is
one of `REJECT`, `NEEDS_MORE_EVIDENCE`, or `PROMOTE`. Failing a preregistered
criterion rejects the candidate. Missing samples, diagnostics, or source
evidence produce `NEEDS_MORE_EVIDENCE`. Promotion additionally requires the
caller to provide verified point-in-time availability, instrument mapping,
M3 execution evidence, cost inputs, a locked holdout, and dataset/M3 result
fingerprints. Those flags and hashes are recorded but are not independently
verified by this M4 evaluator.

## Run

```powershell
python -m pip install -e .
actinver-m4 --help
actinver-m4 evaluate --input validation-case.json --output validation-result.json
```

Existing result files are not overwritten. The result identity includes the
input hash, code commit, M1 rules revision, universe snapshot, and dataset
version.

## Current evidence boundary

Tests use fabricated return streams and synthetic bars only to exercise code
paths, deterministic behavior, leakage guards, and overfit detection. They do
not establish financial performance. The repository still has no authorized
historical OHLCV/trade series, authenticated simulator symbol mapping, or
real M3-period portfolio return stream. Therefore M4 infrastructure can run,
but real strategy decisions remain `NEEDS_MORE_EVIDENCE` until those inputs
exist. No strategy is promoted from fixtures, and no Actinver orders are
submitted.
