# M5 Closure Report — Research Factory

Date: 2026-10-05

## Scope and outcome

M5 adds `actinver-research` for registering, running, verifying, and summarizing
pre-registered M4 experiment batches. Each plan binds a falsifiable hypothesis,
an explicit `ExperimentSpec`, and an exact M4 validation-case fingerprint.
The specification records the strategy family, data/universe versions,
features, target, horizon, parameter variants and hashes, temporal splits,
transaction-cost and execution models, benchmark, criteria, seed, validation
protocol, and evidence state.

Registration captures the hypothesis and sanitized experiment specification,
plus the Git commit, relevant code/config fingerprint, runtime, and dependency
versions. Results preserve M4 metrics, scientific decisions, required
falsification checks, and run errors. Ledger verification checks canonical
JSON, a sequential hash chain, plan/specification consistency, and result
identity links. The ledger is append-only and single-writer; its hash chain is
tamper-evident but is not a signed or authenticated record.

The factory covers leakage, regime, outliers, parameter sensitivity, liquidity,
costs, sample size, and multiple testing. The outlier diagnostic removes the
largest-absolute-net-return validation session across variants and reruns M4
selection while leaving final-test observations untouched. Instrument-level
liquidity remains unavailable from aggregate return/turnover cases and blocks
promotion.

## Files changed

- `src/actinver/research_factory.py` — plan/spec validation, provenance,
  preregistration, M4 execution, falsification, append-only ledger, and summary.
- `src/actinver/research_cli.py` and `pyproject.toml` — installed CLI.
- `schemas/research_hypothesis.schema.json`,
  `schemas/research_experiment_spec.schema.json`,
  `schemas/research_plan.schema.json`, and
  `schemas/research_ledger_record.schema.json` — versioned contracts.
- `tests/test_research_factory.py` — end-to-end synthetic batch, tampering,
  stale inputs, invalid periods, and CLI checks.
- `research/hypotheses/README.md` and
  `research/hypotheses/TORN-001_rank_vs_expected_return.json` — hypothesis
  backlog and a planned M8 question; TORN-001 has not been tested.
- `docs/actinver_research_factory.md` — workflow, commands, and limitations.
- `README.md` and `docs/CODEX_START_HERE.md` — phase status, M5 usage, and
  handoff to M6.
- `docs/phase_reports/M5_REPORT.md` and `prompts/CURRENT_PHASE.md` — closure
  evidence and handoff to M6.

## Verification

Local checks on the merged M5 code:

- `python -m pip install -e .` — PASS.
- `python -m unittest discover -s tests -v` — PASS; 105 tests.
- `python -m unittest discover -s tests -p test_research_factory.py -v` — PASS;
  9 M5 tests.
- `python -m compileall -q src tests` — PASS.
- `python -m pip check` — PASS.
- `actinver-m1 audit` — PASS; 207 universe records and source fingerprints.
- `actinver-research --help`, parsing of four M5 JSON schemas, and
  `git diff --check` — PASS.

GitHub Actions run [#133](https://github.com/MarioIbago/reto-actinver-2026-/actions/runs/37308259351)
passed on commit `b7bf22894a1bde26797631205849099b12707ee6`, including package
installation, all 105 tests, deterministic smoke, checkout identity, and
artifact verification. Artifact ID `11344099678`; digest
`sha256:c7bb2208f0be435dd65dc2cccab2fe7fc642a94c861c5c8aebac0301a782faab`.
PR [#18](https://github.com/MarioIbago/reto-actinver-2026-/pull/18) merged to
`main` as `533958e11258a2d4603166fc0f731d58fb2e3a58`.

The first CI attempt found the CLI ending in the two-character backslash-n text
instead of a line ending. Commit `b7bf228` corrected it; the complete CI rerun
then passed. The user-provided prompt pack remained untracked and was not used
as an instruction source for M5 implementation.

## Gate status

**M5: PASS — software/research-process gate only.** Synthetic cases completed
the pre-registration-to-ledger workflow, preserved a rejected overfit case,
withheld promotion for a synthetic winner, and verified that changes to the
ledger chain or its internal plan/result links are detected.

This does not demonstrate financial performance. The hypothesis `TORN-001` is
backlog only. No OHLCV/trade history, authenticated Actinver symbol mapping,
practice-fill calibration, or real M3-period return stream is available.
Therefore no financial hypothesis was promoted and no research batch with
authorized real market inputs is recorded.

## Assumptions, risks, and blockers

- The hash chain detects accidental edits and semantic inconsistencies; it is
  not cryptographic authentication against an actor able to rewrite the full
  ledger.
- M4 receives aggregate returns and turnover, so instrument liquidity cannot
  yet be verified.
- CI and local cases use synthetic fixtures. Promotion requires authorized
  point-in-time data, usable instrument identity, verified costs/execution,
  and complete falsification evidence.
- TORN-001 references tournament-rank research as a question for later phases;
  the transfer to Actinver and its financial validity remain untested.

## Exact next step

Proceed to M6. Read `prompts/phases/M6_NEWS_EVENTS.md`; build point-in-time
news/event ingestion, deduplication and structured event contracts, while
keeping extraction separate from future-return labeling. The historical
predictive-value gate remains unverified until authorized news and price data
are available for a temporal out-of-sample evaluation.
