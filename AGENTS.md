# AGENTS.md — Operating Contract for Codex

## Mission

This repository is the source of truth for the Reto Actinver 2026 quantitative research system.

The goal is not to build a generic trading bot. The goal is to construct a scientifically defensible decision system whose final tournament objective is to study how to maximize `P(final_rank = 1)`.

## Mandatory read order

Before modifying code/configuration:
1. `README.md`
2. `MASTER_PLAN.md`
3. `docs/CODEX_START_HERE.md`
4. `docs/architecture.md`
5. `docs/research_standard.md`
6. `prompts/00_GLOBAL_SYSTEM_PROMPT.md`
7. `prompts/CURRENT_PHASE.md`
8. complete prompt for the active phase
9. inspect the actual repository state

When architecture/backtesting/optimization/NLP/UI is relevant, also read `docs/reference_projects.md`.

## Phase discipline

Only implement the active phase.

Do not pre-build future modules "just in case". If a useful future idea appears:
- document it;
- create a backlog/issue if needed;
- do not implement it unless required by the active phase.

A phase completes only when its exit gate is verified.

## Separation of responsibilities

### Research agents / LLMs
May:
- read papers/sources;
- structure news/events;
- propose hypotheses;
- critique;
- synthesize evidence.

### Codex
Owns production-code changes by default.

### Deterministic code
Must perform:
- calculations;
- labels/returns;
- backtests;
- regressions/tests;
- bootstrap;
- Monte Carlo;
- validation;
- portfolio math;
- cost/execution modeling.

Never substitute an LLM estimate for a reproducible calculation.

## Scientific rules — non-negotiable

1. No look-ahead bias.
2. No data leakage.
3. No survivorship bias.
4. Preserve point-in-time availability.
5. Time-aware validation by default.
6. Protect final holdout.
7. Compare complexity against simple baselines.
8. Include realistic costs/execution when claims are tradable.
9. Track multiple testing / variants attempted.
10. Preserve failed experiments.
11. Trace results to code/data/config/seed.
12. Try to falsify promising results.

Read `docs/research_standard.md` for the full protocol.

## Experiment lifecycle

```text
hypothesis
→ ExperimentSpec
→ baseline + validation plan
→ implementation
→ research
→ OOS / walk-forward
→ costs / execution
→ robustness / multiple testing
→ falsification attempt
→ REJECT / NEEDS_MORE_EVIDENCE / PROMOTE
→ permanent record
```

Promotion must be explicit.

## Compute policy

Local:
- lint;
- unit tests;
- schema/config checks;
- tiny deterministic samples.

GitHub Actions / remote runner:
- broad backtests;
- universe-wide research;
- bootstrap/Monte Carlo;
- ML;
- batch ingestion;
- expensive experiments.

Scheduled Actions are batch infrastructure, not guaranteed low-latency intraday trading infrastructure.

## External reference policy

Before reusing an external project:
- verify license;
- verify activity;
- document fit;
- list incompatible assumptions;
- classify as BUILD CUSTOM / ADAPT / STUDY ONLY / IGNORE.

Never copy a project because it is popular.

## Agent coordination

Research roles may parallelize independent questions.

Do not let multiple agents edit the same production module/config/dataset concurrently unless an explicit coordination mechanism exists.

See:
- `docs/AGENT_ROLES.md`
- `docs/manual_agent_workflow.md`

## Source material

Raw evidence in `research/source_material/` must not be silently rewritten.

M1 owns normalization of rules/universe.

## Security and execution

- no secrets/tokens in repo;
- least-privilege workflows;
- respect data/code licenses;
- no automated clicks/orders in Actinver;
- final order entry is manual.

## Engineering rules

- `pyproject.toml` for Python project config;
- dependencies minimal and justified;
- tests with new behavior;
- typed/structured outputs preferred;
- machine-readable experiment results;
- record seeds and dependency versions when relevant;
- keep changes reviewable and reversible.

## End-of-task report

Always report:
1. files changed;
2. commands/tests/workflows run;
3. PASS/FAIL;
4. assumptions/risks;
5. artifacts/experiment IDs;
6. blockers;
7. exact next step.

## Stop rule

When the active phase gate is complete, stop.

Do not advance `prompts/CURRENT_PHASE.md` unless explicitly instructed.
