# Reto Actinver 2026 — Quant Research & Tournament System

Repositorio maestro para construir un sistema cuantitativo reproducible orientado al **Reto Actinver 2026**.

> Estado: M0–M7 pasaron sus gates de software dentro del alcance documentado. Los gates empíricos de M6 y M7 permanecen `NEEDS_MORE_EVIDENCE`. M1 conserva sin resolver el mapeo a símbolos/series del simulador y ambigüedades oficiales. M2 verifica PIT con el calendario oficial BMV; aún no hay OHLCV ni noticias históricas autorizadas. No hay evidencia de alpha ni backtests financieros con datos reales.

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

## Current priority — M7

M3 now provides `actinver-exec simulate`: deterministic replay, auditable cash/position/fee ledger, versioned case/result schemas, and provenance. Its synthetic tests establish software mechanics only. No real practice fills, authorized OHLCV/trades, or authenticated simulator symbols are available.

M4 provides eight point-in-time baseline families and a time-aware validation engine. M5 adds pre-registered experiment batches, tamper-evident scientific memory, falsification tracking, and decision accounting; its software gate passed with synthetic cases only. M6 adds a point-in-time news/event software pipeline and PIT labeling/evaluation tools, but no authorized news corpus, price history, authenticated instrument mapping, or real M3 execution inputs are available. Its empirical gate remains `NEEDS_MORE_EVIDENCE`.

M7's software gate is complete: `actinver-ensemble` validates current M5 promotions, calibrates by signal/instrument/horizon using train-only data, combines equal-weight families, and reports OOS/correlation/regime/ablation diagnostics. `research/signals/registry.json` is empty and no M5 factory ledger exists; M7's empirical gate remains `NEEDS_MORE_EVIDENCE`. The M5 result format also needs an instrument-level forecast artifact before any promotion can enter M7. No financial claims may be made from synthetic data.

Check the current promotion index with `actinver-ensemble promotions --ledger research/factory_ledger.jsonl`; see `docs/actinver_alpha_ensemble.md` for the M7 registry and case contracts.

## Official sources

- https://www.retoactinver.com/
- https://www.retoactinver.com/bases-y-mecanica
- https://www.retoactinver.com/es-mx/general
- https://www.bmv.com.mx/es/Grupo_BMV/Calendario_de_dias_festivos/_rid/662/_mod/TAB_DIAS_FEST

M1 must re-verify/version current rules.
