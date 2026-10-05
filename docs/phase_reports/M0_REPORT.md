# M0 Closure Report — Foundation & Research Infrastructure

Date: 2026-10-05

Active phase: M0

Phase file remains unchanged: `prompts/CURRENT_PHASE.md`

## Scope completed

M0 now has a minimal installable Python package, validated experiment contracts, a deterministic non-financial smoke experiment, a CLI verifier, an append-only research ledger, fast unit tests, and a least-privilege GitHub Actions workflow that preserves machine-readable results and diagnostic logs as an artifact.

The workflow supports `workflow_dispatch`, `push` to `main`, and pull requests to `main`. Its Python source fingerprint now normalizes line endings to LF before hashing, so a Windows checkout with `core.autocrlf=true` verifies the same package code as the Linux CI runner.

No market data, tickers, strategy, financial backtest, ML, news ingestion, portfolio logic, frontend, or Actinver automation was added. Raw source material and `prompts/CURRENT_PHASE.md` were not changed. The permanent ledger was not extended with routine verification runs.

## Exit criteria and evidence

| M0 criterion | Evidence | Status |
| --- | --- | --- |
| Clean package installation | Fresh Python 3.12.10 virtual environment; `pip install .` succeeded from a detached clean checkout of commit `0cc4895ac966401fe23b2258ea438860b9f4decd`; `pip check` reported no broken requirements. | PASS |
| Tests pass | Full `unittest` suite passed 25/25 locally and in GitHub Actions run #100. | PASS |
| Deterministic smoke | `HARNESS_SMOKE_001`, seed 42, expected values `[43, 46, 51, 58, 67, 78, 91, 5]`, integer sum 439; local smoke and verifier passed with `working_tree_dirty=false`. | PASS |
| Machine-readable result | CI artifact contains canonical `payload.json`, `result.json`, resolved spec, and JSONL execution ledger. Result status is `PASS`; config and code SHA-256 identities are present. | PASS |
| Real GitHub workflow execution | Main run #99 completed successfully on commit `42b9311434106c2c4fa5e339fc18946adf604933`; PR run #100 completed successfully for PR #5. Every foundation job step passed on run #100. | PASS |
| Artifact inspection | Main artifact #11212471954 and PR artifact #11331400193 were downloaded and inspected. The PR artifact was independently verified on the Windows checkout against its recorded checkout SHA. | PASS |
| Commit/config/seed traceability | Main artifact identifies commit `42b9311434106c2c4fa5e339fc18946adf604933`, config SHA `b592a36672eae81109eafb5f99bc71bf565689843c1c922ecd36d268d12cfccf`, and seed 42. PR artifact identifies checkout `3195fd46f09f3518ebf1c01f7480ea1ebcc8d75e`, the same config SHA and seed, and code SHA `dd57d4704a7c9bc72538920a45699081ac742a4bf04e58c35396aff6a44de1e5`. | PASS |
| Documentation and scope | `docs/CODEX_START_HERE.md` documents install, smoke, verification, ledger, workflow, and fingerprint behavior. No future-phase implementation or source-material edits were introduced. | PASS |

### Remote artifacts

- Main run #99: `m0-foundation-36973696561-1`, artifact ID `11212471954`, SHA-256 `be4c3de3e2d04def945f8309ef1f8c5d5d710275e6faa1eb9aa07087cec595ca`. It contains the expected four bundle files and six diagnostic logs. Result: `PASS`; clean checkout; Python 3.12.14.
- PR run #100: `m0-foundation-37277709500-1`, artifact ID `11331400193`, SHA-256 `0d0b84a7a6ba1147911b26d9148029251933e82437bc406babbc1284a366422b`. Result and verifier: `PASS`; clean checkout; Python 3.12.14; 25 tests passed. The downloaded bundle also verified locally from Windows against checkout SHA `3195fd46f09f3518ebf1c01f7480ea1ebcc8d75e`.

## Reliability issue found and fixed

The first Windows verification of the main artifact failed because `code_sha256` hashed raw `.py` bytes: Git's `core.autocrlf=true` made the Windows installed package CRLF while the Linux runner used LF. The exact source tree and config matched, but their byte hashes differed. The fix normalizes CRLF and CR to LF before hashing and adds a regression test. On the fixed clean checkout, the local code SHA matches the Linux PR artifact (`dd57d470…`), and the artifact verifier passes. The failure was reproducible and led to the scoped code/test/documentation changes in PR #5.

## Files changed

M0 foundation files on `main` include `.github/workflows/test.yml`, `.gitignore`, `pyproject.toml`, `docs/CODEX_START_HERE.md`, `experiments/specs/HARNESS_SMOKE_001.json`, `research/ledger.jsonl`, the five `src/actinver` package modules, and the three test modules. The placeholder `morning.yml`, `nightly.yml`, and `research.yml` workflows were renamed to `.yml.disabled` and documented as inactive.

The focused follow-up in [PR #5](https://github.com/MarioIbago/reto-actinver-2026-/pull/5) changes `src/actinver/smoke.py`, `tests/test_smoke.py`, and `docs/CODEX_START_HERE.md`. This report is the M0 phase report.

## Commands and workflows run

- Fresh Python 3.12 environment: `pip install .`, `pip check`, targeted smoke tests, and full `python -m unittest discover -s tests -v` (25 tests).
- Deterministic smoke, then `actinver-m0 verify` with the exact committed SHA and `working_tree_dirty=false`.
- GitHub Actions main run #99 and PR run #100; both foundation jobs passed.
- Downloaded both artifacts, checked result/spec/checkout identity and artifact contents, then independently verified the PR artifact from the Windows checkout.
- `git diff --check` passed before the fix commit.

The explicit `workflow_dispatch` event was not triggered. The GitHub browser session was signed out, `gh` is not installed, and the available GitHub connector has no workflow-dispatch operation. The workflow declares `workflow_dispatch`; the same job has run successfully on `main` push and PR events, including artifact inspection. The runbook permits a manual trigger when access is available.

## Risks, blockers, and next step

There are no remaining technical blockers to the M0 harness gate. PR #5 is open and awaits human review before its portability fix is merged. GitHub still has an older draft PR #1 and the Step 1 issue #3 open; both are stale and do not block this M0 evidence. Manual dispatch itself remains unverified as described above.

Next step: review and merge PR #5, then conduct the human M0 phase review. Keep M0 active until that review; do not advance `prompts/CURRENT_PHASE.md` automatically.

M0 PASS — READY FOR HUMAN REVIEW
