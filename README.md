# Reto Actinver 2026 — Quant Research & Tournament System

Repositorio maestro para construir un sistema cuantitativo reproducible orientado al **Reto Actinver 2026**.

> Estado: arquitectura + prompts + source material. M0 es la fase activa; el código financiero todavía no debe existir.

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
- raw 207-instrument universe list.

M1 normalizará/verificará símbolos y reglas. No usar raw material como configuración ejecutable.

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
- Human: phase approval + final Actinver execution.

Research can parallelize; production code is single-writer by default.

## External references

See `docs/reference_projects.md`.

References are not automatic dependencies.

## Current priority — M0

El primer éxito debe ser:

```text
workflow_dispatch
→ clean runner
→ tests
→ deterministic Python smoke
→ JSON result
→ uploaded artifact
→ verified PASS/FAIL
```

No real data, models, signals or UI yet.

## Official sources

- https://www.retoactinver.com/
- https://www.retoactinver.com/bases-y-mecanica
- https://www.retoactinver.com/es-mx/general

M1 must re-verify/version current rules.
