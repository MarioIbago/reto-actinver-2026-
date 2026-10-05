# M4 Closure Report — Baselines & Validation Engine

Date: 2026-10-05

## Scope and outcome

M4 adds eight deterministic, long-only baseline signal families over normalized
M2 `price_bar` records. The baseline builder applies source/system availability
cutoffs, event-time checks, exact decimal inputs, and explicit empty-target
semantics. Weights are target allocations; the builder does not calculate
returns or claim fills.

The `actinver-m4 evaluate` command evaluates precomputed aligned portfolio
returns and turnover using chronological train/validation/test periods. It
selects only on validation and reports selected-trial holdout metrics,
transaction-cost and slippage sensitivity, expanding/rolling walk-forward,
moving-block bootstrap, CSCV/PBO, DSR, regime splits, parameter sensitivity,
sample-size diagnostics, multiple-testing context, and structured
`REJECT` / `NEEDS_MORE_EVIDENCE` / `PROMOTE` decisions. Inputs and outputs have
versioned schemas, parameter fingerprints, immutable output files, and run
provenance.

## Files changed

- `src/actinver/baselines.py` — eight point-in-time deterministic baselines.
- `src/actinver/validation.py` — time-aware validation and evidence gates.
- `src/actinver/validation_cli.py` — installed CLI and provenance.
- `schemas/validation_case.schema.json` and
  `schemas/validation_result.schema.json` — versioned contracts.
- `tests/test_baselines.py` and `tests/test_validation.py` — deterministic,
  leakage, holdout, cost, statistical, CLI, and schema checks.
- `pyproject.toml` — `actinver-m4` console script.
- `docs/actinver_validation.md` — usage, method assumptions, and evidence
  boundary.
- `docs/phase_reports/M4_REPORT.md` — this closure record.
- `README.md`, `docs/CODEX_START_HERE.md`, and `prompts/CURRENT_PHASE.md` —
  phase status and handoff to M5.

## Evidence and verification

Local verification:

- `python -m pip install -e .` — PASS.
- `python -m unittest discover -s tests -v` — PASS; 96 tests.
- `python -m compileall -q src tests` — PASS.
- `python -m pip check` — PASS.
- `actinver-m1 audit` — PASS; 207 universe records and source fingerprints.
- JSON schema parsing, `actinver-m4 --help`, and `git diff --check` — PASS.

GitHub Actions run [#128](https://github.com/MarioIbago/reto-actinver-2026-/actions/runs/37302113555)
completed successfully on PR [#16](https://github.com/MarioIbago/reto-actinver-2026-/pull/16).
Package installation, installed dependencies, the full test suite, M0 smoke,
and artifact verification all passed. Artifact ID `11341894255`, SHA-256
`451be7a77d7c667c49c058c2743a900706a2d50dc547215ddf654408839c3777`.
PR #16 merged to `main` as `9d12e52d72bb74251a7eb1e5d0a47b295b13f8ce`.

An adversarial breakout fixture found an off-by-one lookback window during
review. The baseline now checks the full declared prior window, and the fixture
confirms an older high cannot be silently excluded.

## Gate status

**M4: PASS — software gate only.** The reproducible baseline and validation
pipeline runs end-to-end, detects the synthetic overfit candidate, and keeps a
synthetic winner at `NEEDS_MORE_EVIDENCE`. This is not evidence of tradable
performance and does not promote a strategy.

## Assumptions, limitations, and blockers

- Baseline weights express intended allocations only; they are not portfolio
  replay, execution evidence, or proof that an asset was operable in Actinver.
- Validation consumes caller-supplied portfolio returns and turnover. It does
  not independently reconstruct M3 fills or authenticate supplied evidence
  flags and dataset/result fingerprints.
- PBO and DSR are approximate diagnostics; DSR treats attempted trials as
  independent for the expected-maximum adjustment.
- Fixtures use synthetic bars and returns. There is still no authorized
  historical OHLCV/trade series, authenticated Actinver symbol mapping,
  calibrated practice-fill record, or real M3-period return stream.
- Financial decisions therefore remain `NEEDS_MORE_EVIDENCE`; no alpha claim
  is supported.

## Exact next step

Proceed to M5. Build a reproducible research factory that records hypotheses,
pre-registered ExperimentSpecs, attempts, validation decisions, falsification
notes, and permanent positive/negative scientific memory. Start from synthetic
or metadata-only examples until authorized market and execution inputs exist.
