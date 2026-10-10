# Reto Actinver 2026 — Quant Research & Tournament System

Repositorio maestro para construir un sistema cuantitativo reproducible orientado al **Reto Actinver 2026**.

> Estado: M0–M9 pasaron sus gates de software dentro del alcance documentado. El trabajo por fases está cerrado; los gates empíricos de M6, M7 y M8 siguen `NEEDS_MORE_EVIDENCE`. M1 conserva sin resolver el mapeo a símbolos/series del simulador y ambigüedades oficiales. M2 verifica PIT con el calendario oficial BMV; aún no hay OHLCV ni noticias históricas autorizadas. No hay evidencia de alpha ni backtests financieros con datos reales.

## Operación diaria a las 07:00 CDMX

El [plan operativo diario](docs/daily_0700_operations.md) incorpora tres
subagentes nativos de Codex: investigador de resultados/noticias (con la sesión
disponible de Perplexity), contador de evidencia manual del concurso y analista
FOMO de consumidor/inversionista. Una sola corrida diaria a las **07:00
America/Mexico_City**, hasta el 13 de noviembre de 2026, reemplaza la vigilancia
horaria del 5–6 de octubre. El heartbeat vive en Codex; no hay un segundo
programador de Perplexity/Actions. La cuenta requiere evidencia manual y la
entrada de órdenes sigue siendo manual conforme a las bases oficiales. El
estado operativo actual conserva `NO_TRADE`.

## Objetivo

No buscamos un portafolio tradicional ni un bot de picks.

El objetivo final es construir evidencia suficiente para alimentar un Tournament Brain que estudie:

```text
maximize P(final_rank = 1)
```

bajo reglas reales, costos, ejecución, liquidez, ranking y tiempo restante.

## Idea central

```text
RESEARCH / RULES / MARKET DATA / NEWS
                ↓
        falsifiable hypotheses
                ↓
              CODEX
                ↓
             GITHUB
                ↓
         GITHUB ACTIONS
                ↓
      PYTHON / STATS / ML / MC
                ↓
          VALIDATION
        ↙             ↘
     REJECT         PROMOTE
                       ↓
                 ALPHA ENGINE
                       ↓
                RISK/CONSTRAINTS
                       ↓
                TOURNAMENT BRAIN
                       ↓
                   TRADE SHEET
                       ↓
                     HUMAN
                       ↓
                    ACTINVER
```

## Read first

Owner:
1. `docs/START_HERE.md`
2. `MASTER_PLAN.md`

Codex:
1. `README.md`
2. `MASTER_PLAN.md`
3. `AGENTS.md`
4. `docs/CODEX_START_HERE.md`
5. `docs/architecture.md`
6. `docs/research_standard.md`
7. `prompts/00_GLOBAL_SYSTEM_PROMPT.md`
8. `prompts/CURRENT_PHASE.md`
9. active phase prompt

## Roadmap

M0 → Foundation & Research Infrastructure  
M1 → Rules & Eligible Universe  
M2 → Point-in-Time Data Engine  
M3 → Actinver Execution Simulator  
M4 → Baselines & Validation Engine  
M5 → Research Factory  
M6 → News/Event Engine + Intelligence  
M7 → Alpha Ensemble  
M8 → Tournament Brain  
M9 → Trade Sheet & Human Execution Interface

No avanzar por intuición. Cada fase tiene gate.

## Source material

Raw evidence stays in:
`research/source_material/`

Actualmente incluye:
- participant-guide snapshot;
- raw 207-instrument universe list;
- official Grupo BMV 2026 holiday-calendar capture.

M1 normalizó/verificó reglas y el anexo de instrumentos sin afirmar que las etiquetas de la guía sean símbolos ejecutables del simulador. No usar raw material como configuración ejecutable.

## Scientific rule

Una estrategia no se promueve porque el backtest se vea bien.

Debe sobrevivir, según corresponda:
- point-in-time checks;
- leakage controls;
- time-aware OOS/walk-forward;
- costs/execution;
- liquidity;
- robustness;
- multiple-testing accounting;
- comparison with simple baselines.

Los resultados negativos se preservan.

## Agent roles

- ChatGPT Research: deep research / methodology.
- Perplexity Pro: current web/news/source verification.
- Codex: production repo implementation.
- Human: final manual execution in Actinver; order entry is never automated.

Research can parallelize; production code is single-writer by default.

## External references

See `docs/reference_projects.md`.

References are not automatic dependencies.

## M9 completed — Trade Sheet & Human Execution Interface

M3 now provides `actinver-exec simulate`: deterministic replay, auditable cash/position/fee ledger, versioned case/result schemas, and provenance. Its synthetic tests establish software mechanics only. No real practice fills, authorized OHLCV/trades, or authenticated simulator symbols are available.

M4 provides eight point-in-time baseline families and a time-aware validation engine. M5 adds pre-registered experiment batches, tamper-evident scientific memory, falsification tracking, and decision accounting; its software gate passed with synthetic cases only. M6 adds a point-in-time news/event software pipeline and PIT labeling/evaluation tools, but no authorized news corpus, price history, authenticated instrument mapping, or real M3 execution inputs are available. Its empirical gate remains `NEEDS_MORE_EVIDENCE`.

M7's software gate is complete and merged at `1cc66f9082e3f38e9b00ec80ce9f5c92d22af14c`: `actinver-ensemble` validates current M5 promotions, calibrates by signal/instrument/horizon using train-only data, combines equal-weight families, and reports OOS/correlation/regime/ablation diagnostics. `research/signals/registry.json` is empty and no M5 factory ledger exists; M7's empirical gate remains `NEEDS_MORE_EVIDENCE`. The M5 result format also needs an instrument-level forecast artifact before any promotion can enter M7. No financial claims may be made from synthetic data.

M8 is implemented and merged at `21ad31deb9a637e09e30d0cfc86e4295bb314fe1`. Its `actinver-tournament evaluate` command compares rank-aware, expected-return, and Sharpe allocations under joint scenarios and the strict M1 constraints. It always emits `decision: null`; M8's empirical gate stays `NEEDS_MORE_EVIDENCE`. The merge had no Actions run/status exposed by GitHub, so its software evidence is the 149-test local suite, editable install, dependency check, compileall, and CLI smoke documented in `docs/phase_reports/M8_REPORT.md`.

M9 provides `actinver-cockpit` for morning/event/evening reports, a versioned trade sheet, a hash-linked append-only audit trail, descriptive post-activity attribution, and a responsive local cockpit. It rejects future/stale inputs and remains `NO TRADE` because M7/M8 empirical gates are not passed and the authenticated platform symbol map is unavailable. See `docs/actinver_trade_sheet.md`, `docs/m9_reference_research.md`, and `docs/phase_reports/M9_REPORT.md`. No automated order controls are present; Actinver entry remains manual.

The 21-sheet [`reports/ACTINVER_CONTROL_TOWER.xlsx`](reports/ACTINVER_CONTROL_TOWER.xlsx)
captures the repository's current evidence, software gates, missing inputs and
manual-review state. It is a versioned snapshot, not a live market or account
feed; unsupplied values remain `UNKNOWN`.

Quick local workflow:

```powershell
python -m pip install -e .
actinver-cockpit report --type morning --context examples/m9_empty_context.template.json
actinver-cockpit verify-audit
cd frontend
npm ci
npm run dev
```

The checked-in context is an intentionally empty template; it contains no contest metrics or market data. Fill only with authorized, timestamped source records before using a report operationally. M9 is the last roadmap phase; do not add a new phase without an explicit request.

Check the current promotion index with `actinver-ensemble promotions --ledger research/factory_ledger.jsonl`; see `docs/actinver_alpha_ensemble.md` for the M7 registry and case contracts. See `docs/actinver_tournament.md` for M8 input and scenario contracts.

## Official sources

- https://www.retoactinver.com/
- https://www.retoactinver.com/bases-y-mecanica
- https://www.retoactinver.com/es-mx/general
- https://www.bmv.com.mx/es/Grupo_BMV/Calendario_de_dias_festivos/_rid/662/_mod/TAB_DIAS_FEST

M1 must re-verify/version current rules.
