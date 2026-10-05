# M3 Closure Report — Actinver Execution Simulator

Date: 2026-10-05

## Scope and outcome

M3 adds a deterministic replay engine for registered market/limit orders,
versioned BMV trade prints, cancellations, and expiry. It produces an auditable
cash, holdings, fee, valuation, and eligibility ledger. Event sequence breaks
timestamp ties; timezone-aware inputs and exact decimal values are required.
Buying-power and share reservations, no-short behavior, session windows, and
the official contest cutoff are enforced. Partial-period inputs can carry
prior purchase notional and previously traded shares.

The simulator applies a documented full-order fill interpretation when a
qualifying trade print appears. This makes synthetic and future authorized
replays deterministic; it is not a claim about actual broker allocation,
queue priority, or fill size relative to exchange volume.

## Files changed

- `src/actinver/execution.py` — deterministic order/trade event replay and
  ledger.
- `src/actinver/execution_cli.py` — installed `actinver-exec simulate`
  command, source checks, immutable result writing, and provenance identity.
- `schemas/execution_case.schema.json` and
  `schemas/execution_result.schema.json` — versioned input/output contracts.
- `tests/test_execution.py` — deterministic lifecycle, accounting, boundary,
  schema, and CLI fixtures.
- `pyproject.toml` — CLI registration.
- `docs/actinver_execution.md` — behavior, assumptions, usage, and limits.

## Evidence and verification

Local verification on the merged source tree:

- `python -m pip install -e .` — PASS.
- `actinver-exec --help` — PASS.
- `python -m unittest tests.test_execution -v` — PASS; 15 tests.
- `python -m unittest discover -s tests -v` — PASS; 78 tests.
- `python -m compileall -q src scripts tests` — PASS.
- `python -m pip check` — PASS.
- `actinver-m1 audit` — PASS; all 207 guide records and source fingerprints.
- `git diff --check` — PASS (Git reported only its configured Windows
  LF/CRLF conversion notice).

GitHub Actions PR run [#124](https://github.com/MarioIbago/reto-actinver-2026-/actions/runs/37298952962)
on PR #14 completed successfully: package install, full test suite, M0 smoke,
result verification, and artifact upload all passed. Artifact ID
`11339264784`, SHA-256
`1312249d56cb6837eac5205cabc7238c83e209bf7070ab57c74942150c95740f`.
The PR merged as `47edadac78ad0bb9b731054e1be06a6693e21c7a`.

The first PR run, #123 (`37298738447`), exposed an installed-wheel path bug:
the command looked for configuration under `site-packages`. That failed run
was preserved; root discovery now searches the working directory and parents.
The follow-up PR run #124 passed from a clean Ubuntu runner with the package
installed as a wheel.

## Gate status

**M3: PASS — READY FOR HUMAN REVIEW**, scoped to deterministic software
behavior against explicitly supplied cases and versioned rules. The user has
waived approval stops and directed continuation through the remaining phases.

## Limitations and blockers

- No real Actinver practice fills were available for comparison or calibration.
- No authorized historical OHLCV or market-trade dataset is available.
- The M1 guide IDs are not authenticated simulator search symbols or series.
- Official sources leave expiry day basis, some eligibility wording, partial
  allocation, queue priority, and platform rounding unresolved.
- Synthetic fixtures establish code behavior only. M3 produces no financial
  performance evidence and does not automate Actinver login or order entry.
- The cumulative purchase weight is reported as a diagnostic using ending
  portfolio value; it is not official eligibility certification.

## Exact next step

Proceed to M4. Implement reproducible baseline and time-aware validation
contracts. Keep every financial strategy at `NEEDS_MORE_EVIDENCE` until
authorized point-in-time prices, usable instrument IDs, and execution inputs
are available; do not use synthetic fixtures to promote or rank a strategy.
