# Reto Actinver 2026 — Research & Tournament System

Repositorio maestro para construir, validar y operar un sistema cuantitativo orientado al **Reto Actinver 2026**.

> Estado actual: **solo arquitectura + system prompts por fase**. No se han implementado todavía modelos, backtests, feeds de noticias ni automatización operativa.

## Misión

Construir un sistema reproducible que transforme datos de mercado, eventos, noticias e investigación cuantitativa en decisiones de portafolio para el simulador del Reto Actinver, manteniendo la ejecución final dentro del portal como una acción manual del participante.

La función objetivo final no es simplemente maximizar Sharpe o retorno promedio. El sistema deberá, en su fase de torneo, estudiar cómo maximizar la probabilidad de terminar en el primer lugar dadas las reglas, el capital, el ranking, el tiempo restante y las distribuciones de retorno estimadas.

## Orden de construcción

M0 → Foundation & Research Infrastructure  
M1 → Rules & Eligible Universe  
M2 → Point-in-Time Data Engine  
M3 → Actinver Execution Simulator  
M4 → Baselines & Validation Engine  
M5 → Research Factory  
M6 → News/Event Engine + Scheduled Intelligence  
M7 → Alpha Ensemble  
M8 → Tournament Brain  
M9 → Trade Sheet & Human Execution Interface

Si eres el dueño del proyecto y vas a empezar, lee primero:
- `docs/START_HERE.md`
- `docs/codex_best_practices.md`

Codex debe leer:
- `AGENTS.md`
- `prompts/00_GLOBAL_SYSTEM_PROMPT.md`
- el prompt de la fase activa en `prompts/phases/`

No se debe avanzar a una fase posterior hasta satisfacer los criterios de salida de la fase activa.

## Estructura objetivo

```text
reto-actinver-2026/
│
├── README.md
├── AGENTS.md
├── pyproject.toml
├── .gitignore
├── .env.example
│
├── config/
│   ├── actinver_rules.yaml
│   ├── universe.yaml
│   └── research.yaml
│
├── docs/
│   ├── objective.md
│   ├── architecture.md
│   ├── research_standard.md
│   └── actinver_rules.md
│
├── prompts/
│   ├── 00_GLOBAL_SYSTEM_PROMPT.md
│   ├── CURRENT_PHASE.md
│   └── phases/
│       ├── M0_FOUNDATION.md
│       ├── M1_RULES_UNIVERSE.md
│       ├── M2_DATA_ENGINE.md
│       ├── M3_EXECUTION_SIMULATOR.md
│       ├── M4_BASELINES_VALIDATION.md
│       ├── M5_RESEARCH_FACTORY.md
│       ├── M6_NEWS_EVENTS.md
│       ├── M7_ALPHA_ENSEMBLE.md
│       ├── M8_TOURNAMENT_BRAIN.md
│       └── M9_TRADE_SHEET.md
│
├── data/
│   ├── raw/
│   ├── interim/
│   ├── processed/
│   └── metadata/
│
├── src/
│   └── actinver/
│       ├── data/
│       ├── execution/
│       ├── features/
│       ├── strategies/
│       ├── validation/
│       ├── portfolio/
│       ├── tournament/
│       ├── news/
│       └── reporting/
│
├── experiments/
│   ├── specs/
│   └── results/
│
├── research/
│   ├── papers/
│   ├── hypotheses/
│   ├── accepted/
│   └── rejected/
│
├── tests/
│
├── reports/
│   ├── morning/
│   ├── evening/
│   └── trade_sheets/
│
└── .github/
    └── workflows/
        ├── test.yml
        ├── research.yml
        ├── nightly.yml
        └── morning.yml
```

## Fuentes oficiales principales

- https://www.retoactinver.com/
- https://www.retoactinver.com/bases-y-mecanica
- https://www.retoactinver.com/es-mx/general

Las reglas pueden cambiar. M1 debe volver a verificar fuentes oficiales antes de congelar la configuración.
