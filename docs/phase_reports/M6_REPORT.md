# M6 Closure Report — News and Event Engine

Date: 2026-10-05

## Scope and outcome

M6 adds a deterministic point-in-time pipeline for timestamped news revisions,
source-only structured extraction, exact M1 entity mapping, event snapshots,
informational digests/alerts, M2 price labels, and chronological calibration /
incremental-prediction metrics. It never calls a news provider or LLM, never
passes prices/returns to extraction, and never submits Actinver orders.

The software path is implemented and tested on synthetic fixtures. **The
software gate passes. The empirical M6 exit gate remains `NEEDS_MORE_EVIDENCE`**:
there is no authorized historical news corpus, human-reviewed extraction set,
OHLCV history, or authenticated simulator mapping with which to measure
extraction quality, calibration, incremental out-of-sample value, and costs.
No financial result or alpha claim is made.

The user explicitly requested that work continue through all phases. The next
phase may therefore be implemented after this report, while this unverified
M6 evidence gate remains visible. Advancing the workflow pointer is not a
claim that the missing scientific evidence exists.

## Files changed

- `src/actinver/news_events.py` — document normalization, source/system
  point-in-time queries, exact entity mapping, extraction snapshots, digests,
  alerts, PIT labels, and train-only-baseline evaluation.
- `src/actinver/news_cli.py` and `pyproject.toml` — installed `actinver-news`
  commands for the pipeline.
- `src/actinver/data_engine.py` — compare publication and ingestion instants
  as datetimes when ordering/selecting M2 revisions, including fractional
  seconds.
- `schemas/news_*.schema.json` — source documents, extraction, snapshots,
  labels, and evaluation contracts.
- `config/news_schedules.yaml` — timezone-explicit disabled schedule specs.
- `prompts/M6_EVENT_EXTRACTION_V1.md` — versioned source-only extraction
  contract.
- `tests/test_news_*.py` and `tests/test_data_engine.py` — provenance,
  leakage, revision/cutoff, extraction isolation, labels, evaluation, schedule,
  and CLI coverage.
- `docs/actinver_news_events.md` and this report — commands, limitations,
  gate evidence, and blockers.

The user-provided prompt-pack files remain untouched and unstaged.

## Verification

Commands and outcomes on the local branch:

- `python -m pip install -e .` — PASS.
- `python -m unittest discover -s tests -v` — PASS; 126 tests.
- `python -m compileall -q src tests` — PASS.
- `python -m pip check` — PASS.
- `actinver-news --help` — PASS; all nine subcommands registered.
- `actinver-m1 audit` — PASS; 207 guide instruments and source fingerprints.
- JSON schema parse and schedule timezone/disabled-state checks — PASS.
- `git diff --cached --check` — PASS.
- GitHub Actions [run #137](https://github.com/MarioIbago/reto-actinver-2026-/actions/runs/37315359219) — PASS on commit `54d527db33ed93543b2e748b798ca165d9ad02d8`; install, dependency check, all 126 tests, deterministic smoke, checkout identity, and artifact verification succeeded.
- CI artifact ID `11347417420`, digest `sha256:2ef1b84d0d243d3b9e2543eece6b00e469a5824713b76dc76bc90bfa688d7ede`.
- Pull request [#20](https://github.com/MarioIbago/reto-actinver-2026-/pull/20) merged into `main` at `e3c0887160013f6ff21ee7c7fd7ffd5eefda2b35`. The final report-only update passed the complete Actions run [#138](https://github.com/MarioIbago/reto-actinver-2026-/actions/runs/37315565896), artifact `11348136997`, digest `sha256:5f8103cf49d21f068d0d10e337faff2ae5cf2fe2fdbf9a11e221a5f946fdbe10`.

An M2 regression test reproduced a timestamp-ordering defect where lexical
comparison could place an exact-second timestamp after a later fractional
second timestamp. M2 now compares instants directly, and its tests cover both
PIT revision selection and chronological bar sorting.

## Gate status

**M6 software gate: PASS.** The deterministic path validates article
provenance and deduplication; keeps extraction input separate from labels;
selects source revisions by publication and system-availability cutoffs;
preserves ambiguous entity mappings; binds extraction output to source,
prompt, model, and timing; deduplicates copied events; and labels post-feature
returns against explicit M2 data-revision cutoffs and dataset IDs. Evaluation
rejects unavailable features/predictions, split leakage, duplicate groups,
and holdout-selection attestations, and fits its unconditional baseline only
on training outcomes.

**M6 empirical research gate: NEEDS_MORE_EVIDENCE.** The evaluator can
calculate descriptive metrics once authorized records and predictions are
provided, but none are available to establish extraction accuracy, probability
calibration, or incremental value on genuine historical out-of-sample data.
The current successful metrics are software-fixture checks only.

## Assumptions, risks, and blockers

- All scheduled tasks in `config/news_schedules.yaml` are disabled until
  licensed source contracts, timestamp/revision metadata, and a runner exist.
- The labels are raw gross close-to-close returns from one M2 price source.
  They do not adjust for corporate actions, model fills, fees, slippage,
  liquidity, or platform execution.
- Guide universe IDs do not establish the simulator's exact symbol/series;
  platform operability remains unverified.
- Evaluation inputs attest to holdout controls; the tool cannot prove that an
  analyst did not inspect or tune on a holdout.
- The historical evidence gate requires external licensed news, prices,
  human-reviewed extraction labels, verified instrument identity, and an M3
  execution-cost/fill calibration.

## Exact next step

Proceed with M7 software under the user's explicit all-phases instruction;
keep the M6 empirical status unverified. To complete M6's empirical claim,
obtain authorized point-in-time news and price datasets, verify the M1-to-
Actinver instrument mapping, lock a human-reviewed extraction evaluation set,
and register a preregistered M5 out-of-sample comparison with costs and
falsification checks.
