# Codex — Start Here

## Operating order

Before changing production code, read `README.md`, `MASTER_PLAN.md`, `AGENTS.md`, `docs/CODEX_START_HERE.md`, `docs/architecture.md`, `docs/research_standard.md`, `prompts/00_GLOBAL_SYSTEM_PROMPT.md`, `prompts/CURRENT_PHASE.md`, and the complete active-phase prompt. Inspect the actual Git and repository state before editing.

Raw evidence under `research/source_material/` must remain unchanged. M1 owns its normalization into versioned data under `data/metadata/`.

## Current phase: M1 — Rules & Eligible Universe

Follow `prompts/phases/M1_RULES_UNIVERSE.md`. Verify current official sources, record checked times and differences, and keep the constraints machine-readable. Do not backtest strategies or build future-phase modules.

Current outputs:

- `config/actinver_rules.yaml` — dated official-source rules and explicit ambiguities.
- `data/metadata/actinver_universe_2026_v1.json` — guide-annex instruments with stable repository IDs and source hashes.
- `src/actinver/m1.py` and `src/actinver/m1_cli.py` — date queries, rule screens and snapshot diffs.
- `docs/actinver_rules.md` — source interpretation, limits and commands.
- `docs/phase_reports/M1_REPORT.md` — evidence, blockers and M1 status.

The guide's 207 symbols have not been mapped to exact authenticated simulator search symbols/series. Preserve them as guide labels and report platform operability as unverified. Source wording also conflicts on the minimum qualifying assets, 50% concentration measurement and FIBRA eligibility. Return `INDETERMINATE` when the supplied evidence cannot resolve a rule.

Useful commands:

```powershell
python -m unittest discover -s tests -v
actinver-m1 audit
actinver-m1 eligible --as-of 2026-10-05
```

## Completed M0 reference

M0 was merged to `main` in commit `fcff0242c781661f6518e14b3d6978887d12f7f8`. Its runbook and evidence remain in `docs/M0_RUNBOOK.md` and `docs/phase_reports/M0_REPORT.md`. The following is retained as M0 history, not as the current mission.

- The deterministic smoke experiment has no financial meaning.
- The foundation workflow supports `workflow_dispatch`, tests, a smoke JSON artifact, and artifact verification.
- M0 used no real market data, models, strategies, backtests, news APIs, or order automation.

## Security and execution

Do not store secrets or automate Actinver login, clicks or order entry. Final orders remain manual. Research agents may read, structure, critique and synthesize evidence; production implementation and calculations stay in deterministic code.
