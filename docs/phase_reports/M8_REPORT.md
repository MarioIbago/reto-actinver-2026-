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

Local checks before CI:

- `python -m unittest discover -s tests -v` — PASS, 149 tests.
- `python -m pip install -e .` — PASS; installed editable package and command.
- `python -m pip check` — PASS.
- `python -m compileall -q src tests` — PASS.
- `actinver-tournament --help` and `actinver-tournament evaluate --help` — PASS.
- `git diff --check` — PASS (Git emitted only the configured LF-to-CRLF notice
  for `pyproject.toml`).

CI and merge evidence will be appended in the M8 closure report after the
implementation PR has passed its repository workflow.

## Gate status

**M8 software gate: PASS locally; repository CI pending.** The verified package
can parse and compare joint scenarios, enforce the conservative M1 constraints,
compare the required baselines, and explain a higher-P1/lower-expected-return
case. It rejects future source cutoffs, unlocked holdouts, incomplete
leaderboards, mismatched M7 bytes, missing forecasts, invalid portfolio states,
and excessive configured work.

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
evidence. After implementation CI passes and the PR is merged, append the CI
run/artifact details, activate M9, and build the human-readable, audit-traced
NO-TRADE cockpit and trade-sheet interface. Actinver order entry remains
manual.
