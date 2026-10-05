# Codex — Start Here

## Operating order

Before changing production code, read `README.md`, `MASTER_PLAN.md`, `AGENTS.md`, `docs/CODEX_START_HERE.md`, `docs/architecture.md`, `docs/research_standard.md`, `prompts/00_GLOBAL_SYSTEM_PROMPT.md`, `prompts/CURRENT_PHASE.md`, and the complete active-phase prompt. Inspect the actual Git and repository state before editing.

Raw evidence under `research/source_material/` must remain unchanged. M1 owns normalization of rules and the guide universe; M2 owns PIT market-data ingestion and manifests.

## Current phase: M6 — News/Event Engine

Follow `prompts/phases/M6_NEWS_EVENTS.md`. Build point-in-time event ingestion, deduplication, structured extraction contracts, and evaluation tooling that keeps extraction separate from future-return labeling. No LLM output may directly decide BUY/SELL. No authorized historical news corpus, OHLCV history, or authenticated Actinver ticker mapping is currently available; preserve those evidence gaps and do not claim financial performance from fixtures. M5's completed research factory is available through `actinver-research`; see `docs/actinver_research_factory.md` and `docs/phase_reports/M5_REPORT.md`.

M6's software path is available through `actinver-news` for source revision normalization, as-of queries, extraction payloads/snapshots, digests, alerts, separately cut PIT labels, and chronological evaluation. See `docs/actinver_news_events.md` and `docs/phase_reports/M6_REPORT.md`. All schedule specs are disabled until licensed source connectors and a runner exist. The software gate passes; M6 empirical predictive value remains `NEEDS_MORE_EVIDENCE`.

Completed M1 outputs:

- `config/actinver_rules.yaml` — dated rules, explicit ambiguities and the sourced 2026 BMV calendar queried by `actinver-m1 market-day`.
- `data/metadata/actinver_universe_2026_v1.json` — guide-annex instruments with stable repository IDs and source hashes.
- `src/actinver/m1.py` and `src/actinver/m1_cli.py` — date queries, rule screens and snapshot diffs.
- `docs/actinver_rules.md` — source interpretation, limits and commands.
- `docs/phase_reports/M1_REPORT.md` — evidence, blockers and M1 status.

The guide's 207 symbols have not been mapped to exact authenticated simulator search symbols/series. Preserve them as guide labels and report platform operability as unverified. Source wording also conflicts on the minimum qualifying assets, 50% concentration measurement and FIBRA eligibility. Return `INDETERMINATE` when the supplied evidence cannot resolve a rule. Scheduled 2026 holidays are captured from the official BMV page; exceptional closures and shortened sessions are not represented.

M2 provides `src/actinver/data_engine.py`, `actinver-data`, and `scripts/build_bmv_calendar_dataset.py`. Its gate passes for the source-backed BMV calendar-event dataset. That calendar is the only real dataset currently available; no authorized historical OHLCV has been ingested. The calendar data and manifest remain local while redistribution rights are unknown. Do not make financial backtest claims from calendar records or synthetic fixtures.

M3 provides `src/actinver/execution.py`, `src/actinver/execution_cli.py`, versioned execution schemas, and `docs/actinver_execution.md`. It passed deterministic synthetic replay and the complete CI workflow. The gate does not certify broker behavior: partial fills/queue priority, platform rounding, practice fills, market trades, and exact Actinver symbols remain unavailable or unspecified.

Useful commands:

```powershell
python -m unittest discover -s tests -v
actinver-m1 audit
actinver-m1 eligible --as-of 2026-10-05
actinver-m1 market-day --as-of 2026-11-02
actinver-exec --help
$ingestionTime = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$codeCommitSha = (git rev-parse HEAD).Trim()
python scripts/build_bmv_calendar_dataset.py --ingestion-time $ingestionTime --code-commit-sha $codeCommitSha
```

Keep the timestamp and commit SHA emitted in the phase report when repeating an exact dataset build.

M4 and M5's software gates passed with synthetic fixtures only. All financial results must remain `NEEDS_MORE_EVIDENCE` until authorized point-in-time news and price data, instrument identity, and M3 execution inputs are available. M6's technical outputs do not establish incremental predictive value without a historical out-of-sample evaluation.

## Completed M0 reference

M0 was merged to `main` in commit `fcff0242c781661f6518e14b3d6978887d12f7f8`. Its runbook and evidence remain in `docs/M0_RUNBOOK.md` and `docs/phase_reports/M0_REPORT.md`. The following is retained as M0 history, not as the current mission.

- The deterministic smoke experiment has no financial meaning.
- The foundation workflow supports `workflow_dispatch`, tests, a smoke JSON artifact, and artifact verification.
- M0 used no real market data, models, strategies, backtests, news APIs, or order automation.

## Security and execution

Do not store secrets or automate Actinver login, clicks or order entry. Final orders remain manual. Research agents may read, structure, critique and synthesize evidence; production implementation and calculations stay in deterministic code.
