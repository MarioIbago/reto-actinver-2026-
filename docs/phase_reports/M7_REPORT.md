# M7 — Alpha Ensemble Report

Date: 2026-10-05

## Scope and outcome

M7 adds a deterministic ensemble interface that admits only the latest
hash-verified M5 `PROMOTE` records and binds every registered signal to its
hypothesis, experiment, strategy family, feature list, dataset digest, M1
universe snapshot, instrument-level net-of-cost target, and horizon. The production signal
registry is empty; no forecast or trade decision is emitted in the current
repository state.

The software supports train-only empirical quantile-residual calibration and
isotonic positive-return probabilities per signal/instrument/horizon;
equal-family aggregation; an
equal-signal comparator; robust cross-sectional feature normalization;
train-only correlation/redundancy diagnostics; temporal holdout checks; OOS
forecast metrics; regime reports; and leave-one-family-out ablations. Synthetic
fixtures verify calculations and safeguards. They are not financial evidence.

## Gate status

**M7 software gate: PASS — READY FOR HUMAN REVIEW.** The interface rejects
unpromoted/stale signals, non-instrument targets, mismatched provenance,
look-ahead timestamps, overlapping label windows, and LLM-only alpha. The CLI
verifies instrument identifiers against the sourced M1 universe.

**M7 empirical gate: NEEDS_MORE_EVIDENCE.** `research/factory_ledger.jsonl`
does not exist; `research/signals/registry.json` has zero signals. The only
present ledger, `research/ledger.jsonl`, contains M0 arithmetic harness records.
M5's report records zero financially promoted hypotheses, and its current M4
validation output is portfolio-level rather than a per-instrument forecast
series. No authorized historical OHLCV/news corpus or authenticated Actinver
symbol mapping is available. Consequently there is no measured alpha claim.

The user's explicit instruction to continue through the remaining phases is
recorded as authorization to proceed to M8 after this software gate. It does
not change the empirical status or represent M7 alpha approval.

## Files changed

- `src/actinver/ensemble.py` — promotion-gated registry validation, PIT checks,
  train-only calibration, family-balanced ensemble, diagnostics, and scores.
- `src/actinver/ensemble_cli.py` and `pyproject.toml` — `actinver-ensemble`
  commands for verified promotions and evaluation against M1 universe IDs.
- `src/actinver/research_factory.py` — read-only index of the latest M5
  promotions per hypothesis; later decisions supersede older ones.
- `schemas/promoted_signal_registry.schema.json`,
  `schemas/alpha_ensemble_case.schema.json`, and
  `schemas/alpha_ensemble_result.schema.json` — versioned M7 contracts.
- `research/signals/registry.json` and `research/signals/README.md` — empty by
  design until eligible promoted instrument-level signals exist.
- `tests/test_ensemble.py` and `tests/test_research_factory.py` — synthetic
  calibration, OOS isolation, provenance, temporal integrity, CLI, and empty
  promotion index coverage.
- `docs/actinver_alpha_ensemble.md`, `README.md`, `docs/CODEX_START_HERE.md`,
  and this report — workflow and limits.

## Method decisions and risks

- Signal promotion is resolved from the M5 append-only ledger, not from
  registry claims. The ledger is tamper-evident but not signed/authenticated.
- M5 acceptance is necessary but not sufficient: an M5 result must carry an
  instrument forecast artifact descriptor, and the M7 case's canonical
  per-signal forecast digest must match it, along with the net-of-cost target,
  exact cost model, data, universe, and horizon.
- Quantile residual corrections and isotonic probability calibration use
  training observations only. At least 30 training examples per
  signal/instrument/horizon are required; fewer or single-class training
  samples produce no calibrated forecast for that instrument.
- Alpha Score reports the median return forecast. Believability is the minimum
  of five auditable evidence ratios, not a return estimate or probability of
  profit. It cannot trigger an order.
- Correlation and regime diagnostics are descriptive. The deterministic
  equal-family baseline does not fit weights or select signals on the test
  split.
- Current M5 validation produces portfolio-return metrics and no
  per-instrument forecast artifact. That interface gap and the unavailable
  authorized market data keep empirical performance unresolved.

## Verification

Local targeted checks run during implementation:

- `python -m unittest discover -s tests -p test_ensemble.py -v` — PASS; 10
  tests.
- `python -m unittest discover -s tests -p test_research_factory.py -v` — PASS;
  10 tests.
- `python -m unittest discover -s tests -v` — PASS; 137 tests.
- `python -m compileall -q src tests` — PASS.
- `python -m pip install -e .`, `actinver-ensemble --help`,
  `actinver-ensemble promotions --ledger research/factory_ledger.jsonl`,
  `python -m pip check`, and `actinver-m1 audit` — PASS; current M5 promotion
  count is zero and the M1 snapshot contains 207 source-verified guide IDs.

Full-suite, GitHub Actions, and artifact details will be recorded after the
implementation PR completes CI.

## Exact next step

After M7's implementation PR and CI artifact are verified, merge the M7
software-gate report and explicit M8 activation. M8 must use the M7 interface
without assuming any real forecast exists; it must preserve the empirical
blockers and produce no portfolio recommendation from empty or synthetic
inputs.
