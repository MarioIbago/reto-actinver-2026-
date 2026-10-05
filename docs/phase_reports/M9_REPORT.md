# M9 — Trade Sheet & Human Execution Interface

## Objective and status

M9 closes the M0–M9 software roadmap with versioned operator reports, strict
`NO_TRADE` behavior under the current evidence state, hash-linked audit records,
descriptive post-activity accounting, and a responsive local cockpit.

**M9 software gate: PASS.** The M0–M9 software roadmap is complete; there is no
active development phase. M6, M7 and M8 empirical gates remain
`NEEDS_MORE_EVIDENCE`. M9 has not run a financial experiment, promoted a signal,
or generated an order recommendation. The browser UI has no broker connection
or order-entry controls. Actinver entry remains manual.

## Implementation

- `src/actinver/trade_sheet.py` validates operator cuts, computes freshness,
  rejects post-cutoff source/event data, creates versioned reports, serializes
  concurrent audit writers, verifies append-only hash links, and calculates
  descriptive post-activity balances with decimal arithmetic.
- `src/actinver/trade_sheet_cli.py` installs `actinver-cockpit report`,
  `verify-audit` and `attribute` commands. M8's exact M7 input digest is
  compared with the exact bytes of the M7 file supplied to M9.
- `schemas/m9_context.schema.json`, `trade_sheet.schema.json`,
  `m9_audit_event.schema.json`, `post_trade_activity.schema.json`, and
  `post_trade_attribution.schema.json` version the input, output and audit
  contracts.
- `examples/m9_empty_context.template.json` is an intentionally blank,
  all-unknown operator template. It contains no contest metrics or market data.
- `frontend/` contains a React/Vite cockpit with overview, reports, evidence and
  audit views. Report and JSONL imports are processed locally in the browser;
  it verifies SHA-256 links and rejects reports containing a non-`NO_TRADE`
  action or non-null order fields.
- `docs/design/m9_operator_cockpit_concept.png` is the accepted visual concept.
  `docs/m9_reference_research.md` records license/activity review of the six
  required references. No reference code or dependency was reused.
- `reports/ACTINVER_CONTROL_TOWER.xlsx` is a versioned snapshot with 21 sheets
  covering the universe, rules, source/data quality, hypotheses, experiments,
  signals, account/tournament state, risk, CI and review. Missing current
  account/market evidence is explicit; this is not a live data connection.
- `tests/test_trade_sheet.py` covers unknown/stale input, exact cutoff and M7/M8
  binding, report output, audit tampering, CLI workflows, event visibility,
  descriptive attribution and money arithmetic.

## Design fidelity review

| Reference element | Rendered implementation | Result |
|---|---|---|
| Actinver 2026 brand and left navigation | Brand and four labeled destinations; mobile collapses to a labeled compact bar. | Match |
| Competition header and four summary cards | Capital, position, gap and sessions; unknowns are rendered as unavailable. | Match |
| Action queue | Prominent `NO TRADE` state, explanatory reason and manual-only label. | Match |
| Candidate radar | Empty state explains that no promoted M7 financial forecasts exist. | Match |
| Portfolio/tournament panel | Shows supplied positions or clearly states that positions were not supplied. | Match |
| Evidence drawer and material events | M1/M7/M8/freshness status plus a source-linked M6 event timeline. | Match |
| Review/audit strip | Chain status, imported event count, report-to-audit byte-hash match. | Match |

The only deliberate variation is that report metadata and audit verification
appear in the lower review strip once files are imported; the reference concept
shows an empty audit state. Mobile keeps all navigation labels visible and
stacks the evidence panels to avoid a desktop-width layout.

## Verification

- `python -m unittest discover -s tests -v` — PASS, 163 tests.
- `python -m pip install -e .` — PASS; `actinver-cockpit` installed.
- `python -m pip check` — PASS.
- `python -m compileall -q src tests` — PASS.
- All 28 checked-in schema/example JSON files parsed successfully.
- `npm ci` in `frontend/` — PASS; no npm audit vulnerabilities reported during dependency installation.
- `npm run build` in `frontend/` — PASS.
- `actinver-cockpit --help` — PASS; report, audit and attribution commands are present.
- Empty-context report/audit CLI smoke — PASS; report `86a079ba-70bb-4e96-9b95-5b2a9707f274`
  emitted `NO_TRADE` and its exact bytes passed audit-chain verification.
- Control Tower XLSX — PASS; 21 sheets exported and reopened, formulas return
  207 universe instruments, 140 stocks and zero promoted signals, with no
  formula errors. All 21 rendered sheets were visually reviewed.
- Browser QA at `http://127.0.0.1:5173/`: page identity/title and meaningful DOM
  verified; no framework overlay; console had no warning/error entries. Tested
  local M9 JSON import, JSONL chain verification and report/audit SHA match.
  A modified test report with `decision.action = BUY` was rejected while the
  valid report remained loaded. Desktop viewport was 1440×1000; mobile viewport
  was 390×844 with no horizontal overflow and visible navigation labels.
- Screenshots from the QA run are stored outside the repository; concept and
  rendered states were visually inspected at both sizes.

GitHub Actions may not expose a workflow run/status for this PR. The software
gate is based on the local evidence above; a missing Actions result is not
reported as a CI pass.

## Scientific and operational boundaries

- M7 has zero financially promoted instrument signals; its empirical gate is
  `NEEDS_MORE_EVIDENCE`.
- M8 result contracts keep `decision: null` and empirical gate
  `NEEDS_MORE_EVIDENCE`; simulation is labeled as simulation.
- M1 platform-symbol/series mapping and contest rule ambiguities remain
  unresolved. The report never changes these into verified status.
- The event timeline accepts only validated M6 snapshots visible by both
  feature-available and system-ingestion times at the report cutoff. Conflicting
  duplicate extractions fail closed.
- A report hash proves byte integrity against the audit event, not source
  authenticity. Manual activity captures are operator-entered and not broker
  authenticated.
- Post-activity attribution calculates portfolio change net of reported
  external flows and summarizes reported fill notional/fees. It cannot estimate
  causal strategy contribution or `P(final_rank=1)` without a no-trade
  counterfactual and authorized point-in-time leaderboard data.
- All current M9 trade-plan fields remain `null`, and the report generator
  emits `NO_TRADE` even if a caller supplies an M7/M8 artifact. The current
  upstream schemas do not produce an empirical order decision.

## Experiments, blockers, and next step

No financial experiment or promotion was created. The local UI import used an
empty-context report and a test-only modified copy solely to verify the safety
block; the files remained outside the repository.

External blockers are authorized PIT OHLCV/trades and news, verified platform
symbol mapping, real practice fills, and complete point-in-time leaderboard
history. The next step is to capture and version those data under their source
permissions, then rerun the existing M1/M6/M7/M8 empirical gates. Keep M9 at
`NO_TRADE` until those gates pass. No phase beyond M9 is opened.
