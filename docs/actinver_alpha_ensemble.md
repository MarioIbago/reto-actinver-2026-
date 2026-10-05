# M7 Alpha Ensemble

## Scope and admission gate

`actinver-ensemble` combines instrument-level forecasts only when the registry
row points to the latest hash-verified M5 `PROMOTE` result for that hypothesis.
It verifies the promotion record digest, experiment/hypothesis identity,
strategy family, feature list, dataset and manifest digest, universe, target,
and horizon. M5 provenance must state authorized point-in-time data and verified
availability, instrument mapping, execution, and costs. The target must be
`instrument_forward_return_net_of_costs`, and its cost-model digest must match
M5. A portfolio-level M5 experiment cannot be relabeled as an instrument
forecast. The M5 result must carry an instrument forecast artifact descriptor;
the M7 case recomputes its per-signal canonical content digest and requires an
exact match. The digest is SHA-256 of a compact sorted-key JSON array, sorted
by `observation_id`, containing `{observation_id, forecast}` rows and one final
newline. LLM-only signals are rejected.

The registry at `research/signals/registry.json` is intentionally empty. The M5
factory ledger `research/factory_ledger.jsonl` is also absent. The older
`research/ledger.jsonl` contains M0 arithmetic harness records, not M5 research
promotions. Therefore the live command returns `NO_PROMOTED_SIGNALS` and emits
no forecast. Synthetic promotion indexes in unit tests exercise the software
path only; the test dataset and mocked promotion/artifact descriptors are
explicitly synthetic, and Believability remains zero. The current production
M5 result format does not export instrument-level forecast artifacts.

## Time and calibration rules

Every forecast and regime label carries its availability timestamp and is
rejected if that timestamp is later than its decision. Observations identify
decision and target-end times, and split windows must be chronological with
each prior split label ending before the next split begins. The CLI verifies
instrument IDs against the versioned M1 universe and checks its raw-source
fingerprints.

Calibration fits only on the `train` split for each signal, instrument, and
horizon, and requires 30 observations in that group. It applies empirical
quantile-residual corrections to the five return quantiles and isotonic
calibration to `P(return > 0)`. A missing or single-class training sample
remains uncalibrated. Signal raw scores receive same-decision, cross-sectional
median/MAD normalization; they are used for correlation diagnostics, not as an
arbitrary score-summing weight.

The primary ensemble first averages signals inside each strategy family and
then gives each family equal weight. The reported comparator gives each signal
equal weight. No family weights are selected with validation or final-test
outcomes. Correlations are fit on train rows only; pairs with absolute
correlation at least 0.90 are reported but not dropped automatically.

Test diagnostics include median absolute error, quantile pinball loss, Brier
score, probability reliability bins, regime slices, and leave-one-family-out
ablations. The test split is reported, never used to fit calibration. Alpha
Score is the ensemble median-return forecast. Believability Score is the
minimum of explicit evidence ratios for promotion provenance, authorized PIT
inputs, calibration support, instrument/horizon OOS support, and two
independent families. It is a conservative evidence score, not a probability
of profit and not a trade instruction.

## Commands

Install the package, then inspect eligible decisions:

```powershell
python -m pip install -e .
actinver-ensemble promotions --ledger research/factory_ledger.jsonl
```

Evaluate a registered set of signals against a versioned observation case:

```powershell
actinver-ensemble evaluate --registry research/signals/registry.json --case ensemble_case.json --ledger research/factory_ledger.jsonl --universe data/metadata/actinver_universe_2026_v1.json --output ensemble_result.json
```

The case and output contracts are `schemas/alpha_ensemble_case.schema.json`
and `schemas/alpha_ensemble_result.schema.json`; registry rows follow
`schemas/promoted_signal_registry.schema.json`. Store permitted source data
outside the repository and record its manifest digest. A successful software
run is not financial alpha evidence and cannot create an Actinver order.

## Current limits

No M5 signal with a current `PROMOTE` decision, instrument-level prediction
artifact, or authorized price/news history is recorded. M5's current
validation result is a portfolio-return evaluation and does not export
per-instrument forecast series. The M7 registry therefore fails closed until
an instrument-level experiment and its PIT forecasts are independently
registered and promoted. The guide's M1 IDs are not authenticated Actinver
search symbols; that mapping remains unverified.
