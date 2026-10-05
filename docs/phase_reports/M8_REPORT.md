# M8 — Tournament Brain Report

## Objective and implementation

M8 adds a deterministic, point-in-time scenario comparison for the contest
objective `P(final_rank = 1)`. It validates a timestamped leaderboard and M1
portfolio state, binds the exact M7 result bytes and scenario-model digests,
checks long-only candidate weights through the M1 constraint engine, and
compares rank-aware, expected-return, and scenario-Sharpe choices. Seeded
common-random-number draws estimate holdout metrics and report leaderboard-model
sensitivity. The command never emits a trade instruction.

The rank-aware policy reports `DEFEND`, `NEUTRAL`, or `CATCH_UP` from the
point-in-time gap and remaining competition fraction. It uses only the base
selection split to select candidates; locked holdout outcomes are used for
evaluation. The test fixture demonstrates the requested distinction: in a
two-outcome synthetic contest, a portfolio can have higher P1 while its
expected return is lower than the expected-return baseline.

## Files changed

- `src/actinver/tournament.py` — strict case validation, M1 feasibility,
  seeded candidate generation, rank/return/risk calculations, holdout and
  leaderboard sensitivity.
- `src/actinver/tournament_cli.py` and `pyproject.toml` — installed
  `actinver-tournament evaluate` command with exact-byte M7 hash binding and
  verified M1 source snapshots.
- `schemas/tournament_case.schema.json` and
  `schemas/tournament_result.schema.json` — versioned input and result
  contracts; result `decision` is always null.
- `tests/test_tournament.py` — behavior, point-in-time, digest, determinism,
  M1-constraint, CLI, policy-mode, holdout, and fail-closed coverage.
- `docs/actinver_tournament.md` and `docs/m8_reference_research.md` — input
  contract, formulas, cost and evidence limitations, and license/activity
  review of the required references.

## Verification

Local verification on the implementation commit `225672a22838795c955b2d771a17fb3ebdc779ed`:

- `python -m unittest discover -s tests -v` — PASS, 149 tests.
- `python -m pip install -e .` — PASS; installed editable package and command.
- `python -m pip check` — PASS.
- `python -m compileall -q src tests` — PASS.
- `actinver-tournament --help` and `actinver-tournament evaluate --help` — PASS.
- `git diff --check` — PASS (only Git's configured LF-to-CRLF notices).

PR #24 was merged to `main` on 2026-10-05 as merge commit
`21ad31deb9a637e09e30d0cfc86e4295bb314fe1`. GitHub exposed no Actions workflow
run or commit status for either the PR head or merge commit. The report records
that limitation rather than treating a missing run as a CI pass. The local
full-suite and installed-CLI checks above are the available software-gate
evidence.

## Gate status

**M8 software gate: PASS; merged to `main`.** The verified package can parse
and compare joint scenarios, enforce the conservative M1 constraints, compare
the required baselines, and explain a higher-P1/lower-expected-return case. It
rejects future source cutoffs, unlocked holdouts, incomplete leaderboards,
mismatched M7 bytes, missing forecasts, invalid portfolio states, and excessive
configured work. GitHub did not expose an Actions run for this merge; local
verification is the recorded evidence.

**M8 empirical gate: NEEDS_MORE_EVIDENCE.** The M5 promotion ledger and M7
signal registry have no financially promoted instrument forecasts. No
authorized historical joint competitor/portfolio scenario bank or complete
point-in-time leaderboard history was supplied. Synthetic tests establish
software behavior only.

## Assumptions, risks, and blockers

- Scenario probabilities, joint stock/competitor dependence, and alternative
  leaderboard models are supplied assumptions, not estimated from contest
  history.
- Scenario returns declare `net_of_costs` and bind a transaction-cost-model
  digest. M8 avoids deducting these costs twice but does not recalculate
  candidate-specific transition commissions or slippage. Those costs must be
  included in the scenario inputs before any empirical or tradable claim.
- Current M1 source ambiguities leave official award eligibility
  indeterminate; exact simulator symbols and SIC series remain unverified;
  M3 fills do not certify platform fills.
- Candidate generation is finite and heuristic; it does not certify a global
  optimum. The engine bounds configured scenario work to keep runs
  deterministic and practical.
- Synthetic scenario output is always `SIMULATION_ONLY`; all output keeps
  `decision: null` and `empirical_gate: NEEDS_MORE_EVIDENCE`.

## Artifacts and next step

No financial experiment was run or promoted. The synthetic comparison fixture
is generated in `tests/test_tournament.py`; it is not recorded as market
evidence. M9 is now active by the user's explicit all-phases instruction. Build
the human-readable, audit-traced trade sheet and responsive NO-TRADE cockpit;
Actinver order entry remains manual.
