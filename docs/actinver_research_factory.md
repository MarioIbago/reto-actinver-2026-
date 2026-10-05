# M5 — Research Factory

## Scope

`actinver-research` manages a pre-registered batch of M4 validation cases. A
separate hypothesis JSON records the falsifiable statement, rationale, source
references, and the required attempt to falsify it. Each batch also contains
an explicit `ExperimentSpec` that pins the strategy family, features, target,
horizon, dataset/universe, train/validation/test periods, parameter variants,
transaction and execution models, benchmark, seed, validation protocol, and
promotion criteria. The runner checks these fields against the M4 validation
case before evaluating it.

The lightweight factory uses no external tracking service. It records a
canonical plan fingerprint, exact hypothesis/case file fingerprints, Git
commit, relevant code/config fingerprint, runtime, full M4 results, falsifier
diagnostics, and every run failure in `research/factory_ledger.jsonl`. The
preregistration event copies the hypothesis and a sanitized M4 experiment-spec
snapshot, including parameter values and fingerprints, but excludes return and
turnover series. Ledger verification cross-checks each specification and result
against the preregistered plan. The completion event stores aggregate M4 results and
falsification diagnostics. The ledger is append-only, hash-chained, and
single-writer. Its hash chain is tamper-evident, not an authenticated
signature. The prior M0
`research/ledger.jsonl` is preserved unchanged.

## Lifecycle

1. Write a hypothesis under `research/hypotheses/` using
   `schemas/research_hypothesis.schema.json`.
2. Create an M4 validation case with preregistered splits, candidates,
   benchmarks, costs, attempted-trial count, and promotion criteria.
3. Create a batch plan using `schemas/research_plan.schema.json`; include the
   SHA-256 of the exact hypothesis and case file bytes.
4. Register the plan. Registration verifies both files and records their
   immutable identity before evaluation begins.
5. Run the registered batch. Each M4 result, including `REJECT`,
   `NEEDS_MORE_EVIDENCE`, errors, and falsification gaps, is preserved.
6. Verify the hash chain and inspect hypothesis/decision counts.

The same batch can be registered idempotently, but a changed plan, input hash,
or code identity requires a new batch ID. A completed batch cannot be run again
or overwritten. Repeated attempts require new plan IDs and remain counted.

## Commands

```powershell
python -m pip install -e .
actinver-research --help
actinver-research register --plan experiments/plans/batch.json
actinver-research run-batch --plan experiments/plans/batch.json
actinver-research verify-ledger
actinver-research summary
```

Plans resolve relative file references from their own directory. The default
ledger is `research/factory_ledger.jsonl`; an alternate path can be passed
with `--ledger`. The case file's exact bytes are fingerprinted but not copied
into the ledger, so authorized/private market data can remain outside Git.
Keep the case file at its referenced immutable location for independent
reproduction.

## Falsification and decisions

The factory collects M4 leakage, cost, regime, parameter, sample-size, and
multiple-testing diagnostics. M5 also removes the single validation session
with the largest absolute net return across submitted trials and reruns
selection with that date excluded. It records the date and before/after winner;
a changed winner is `FAILED`. The final test is untouched. Instrument-level
liquidity remains `NOT_AVAILABLE` because M4 receives aggregate portfolio
returns and turnover, not instrument-level volume or bid/ask observations; this
blocks a new promotion.
`CHECKED` means the diagnostic was calculated; it does not mean the candidate
survived a preregistered threshold.

M4 remains the source of `REJECT` / `NEEDS_MORE_EVIDENCE` / `PROMOTE`. M5
withholds `PROMOTE` if evidence gaps, required falsification checks, or a dirty
execution-relevant worktree remain. Synthetic fixtures cannot become a
financial promotion. M5 does not execute arbitrary code from a plan; the only
runner is the in-process M4 evaluator.

## Current hypothesis backlog

`research/hypotheses/TORN-001_rank_vs_expected_return.json` captures one
testable idea from the tournament dossier. It remains planned for M8 and is
not evidence or an M5 portfolio implementation. No authorized historical
market returns, authenticated simulator identifiers, or real M3 returns are
currently available.
