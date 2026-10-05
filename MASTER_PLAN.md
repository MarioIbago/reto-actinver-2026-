# Reto Actinver 2026 — Master Plan

**Estado:** vivo / sujeto a cambios  
**Fuente de verdad:** este repositorio  
**Objetivo final:** maximizar de forma científicamente defendible la probabilidad de terminar #1 en el Reto Actinver 2026.

## 1. Misión

Construir un laboratorio cuantitativo reproducible que:

1. convierta papers, datos, eventos y noticias en hipótesis falsables;
2. implemente experimentos versionados;
3. ejecute cálculo determinista con Python/estadística/ML;
4. use GitHub Actions para CI, research batch y artefactos reproducibles;
5. detecte leakage, sobreajuste, costos y fragilidad;
6. preserve también los experimentos negativos;
7. promueva solo señales que sobrevivan validación;
8. produzca distribuciones de retorno/riesgo, no solo scores;
9. mantenga separado el Alpha Engine del Tournament Brain;
10. termine en una Trade Sheet clara para ejecución humana.

No estamos construyendo un bot que "adivina acciones". Estamos construyendo una máquina científica para tomar mejores decisiones bajo un torneo corto.

## 2. Objetivo de decisión

El proyecto tiene dos problemas distintos.

### A. Alpha / oportunidad

Para cada instrumento y horizonte:

```text
P(return over horizon | features, event, regime, market state)
```

Horizontes prioritarios:
- intradía cuando sea pertinente;
- 1 día;
- 2–3 días;
- 5 días;
- 10 días;
- 20 días;
- máximo ~30 sesiones.

### B. Torneo / decisión

Dadas las distribuciones, reglas y estado del concurso:

```text
maximize P(final_rank == 1)
```

sujeto a:
- restricciones oficiales;
- capital/cash;
- posiciones;
- liquidez;
- correlaciones;
- ranking;
- gap contra el líder;
- días restantes;
- incertidumbre sobre rivales.

Una cartera puede tener menor retorno esperado y aun así mayor probabilidad de terminar #1.

## 3. Arquitectura mental

```text
PAPERS / OFFICIAL RULES / MARKET DATA / NEWS / EVENTS
                         ↓
                 RESEARCH LAYER
     ChatGPT Research / Perplexity / human inputs
                         ↓
              falsifiable hypotheses
                         ↓
                       CODEX
                code + experiment specs
                         ↓
                       GITHUB
             code + scientific memory
                         ↓
                  GITHUB ACTIONS
                         ↓
          PYTHON / STATS / ML / MONTE CARLO
                         ↓
            VALIDATION + ARTIFACTS + LOGS
                         ↓
          REJECT / NEEDS_MORE_EVIDENCE / PROMOTE
                         ↓
                    ALPHA ENGINE
                         ↓
                RISK / CONSTRAINTS
                         ↓
                 TOURNAMENT BRAIN
                         ↓
                    TRADE SHEET
                         ↓
                       HUMAN
                         ↓
                     ACTINVER
```

La ejecución final en el portal permanece manual.

## 4. Responsabilidades

### Research agents / LLMs
Sirven para:
- leer y resumir papers;
- investigar fuentes;
- traducir evidencia a hipótesis;
- estructurar noticias/eventos;
- hacer crítica bull/bear;
- descubrir variables omitidas;
- proponer experimentos.

No sustituyen cálculos reproducibles.

### Codex
Sirve para:
- implementar dentro del repo;
- escribir/revisar código;
- crear tests;
- construir pipelines;
- ejecutar y reparar workflows;
- convertir dossiers en ExperimentSpec;
- documentar decisiones técnicas.

Por defecto, Codex es el único escritor de producción.

### Código determinista
Debe calcular:
- returns/labels;
- regresiones/tests;
- backtests;
- bootstrap;
- walk-forward;
- Monte Carlo;
- costos;
- optimización;
- calibración;
- promotion gates.

## 5. Ciclo científico obligatorio

```text
idea / paper / event
        ↓
falsifiable hypothesis
        ↓
ExperimentSpec
        ↓
predefined baseline + validation plan
        ↓
implementation
        ↓
in-sample research
        ↓
validation / OOS / walk-forward
        ↓
costs + liquidity + execution
        ↓
robustness + sensitivity + multiple testing
        ↓
explicit falsification attempt
        ↓
REJECT / NEEDS_MORE_EVIDENCE / PROMOTE
        ↓
permanent research record
```

Un backtest espectacular no es evidencia suficiente.

## 6. Identidad reproducible

Todo resultado serio debe poder rastrearse a algo cercano a:

```text
(commit SHA,
 dataset version,
 universe version,
 config/parameters,
 dependency versions,
 random seed)
```

Si falta alguna pieza, la limitación debe quedar explícita.

## 7. Investigación prioritaria

Familias candidatas, no edges asumidos:

1. momentum / relative strength / 52-week-high;
2. abnormal volume + continuation;
3. earnings / PEAD / event drift;
4. gap continuation;
5. sector/industry spillovers;
6. volatility expansion;
7. conditioned reversal;
8. cross-sectional ML después de baselines;
9. news/event structured features;
10. ensemble probabilístico;
11. tournament-aware allocation.

Cada familia debe sobrevivir al protocolo científico del repo.

## 8. News + LLM

Objetivo:

```text
raw text
   ↓
structured event features
   ↓
features + market state
   ↓
historical/statistical validation
   ↓
conditional distribution + uncertainty
```

Ejemplos de fields:
- event_type;
- event_time;
- first_public_time;
- source_quality;
- novelty;
- surprise;
- guidance_direction;
- materiality;
- confidence.

Nunca asumir:
```text
positive text == positive alpha
```

## 9. Tournament Brain

Inputs conceptuales:
- capital;
- holdings;
- cash;
- candidate return distributions;
- correlations;
- liquidity;
- official constraints;
- rank;
- leader gap;
- days remaining;
- opponent scenarios.

Debe comparar sus decisiones contra baselines tradicionales como expected-return / Sharpe-oriented allocation.

## 10. Compute policy

Local:
- lint;
- unit tests;
- schema/config checks;
- small deterministic samples;
- smoke tests.

GitHub Actions / runner remoto:
- broad backtests;
- universe-wide analysis;
- bootstrap / Monte Carlo;
- ML training;
- parameter sweeps;
- batch ingestion;
- report generation.

GitHub Actions no es un motor garantizado para reacción intradía de baja latencia.

## 11. Roadmap oficial

El roadmap oficial conserva la numeración actual M0–M9.

### M0 — Foundation & Research Infrastructure
Package Python, ExperimentSpec/Result, logging, seeds, ledger, CI y primer ciclo reproducible.

### M1 — Rules & Eligible Universe
Reglas 2026 y universo real versionados/consultables.

### M2 — Point-in-Time Data Engine
Precios/eventos/metadatos con available_time y provenance.

### M3 — Actinver Execution Simulator
Órdenes, fills, no-fills, costos, cash/positions y restricciones reales.

### M4 — Baselines & Validation Engine
Controles simples + OOS/walk-forward/robustness/multiple testing.

### M5 — Research Factory
Papers → hipótesis → ExperimentSpec → experimentos → falsificación → memoria.

### M6 — News/Event Engine
Texto → eventos estructurados → evals → valor incremental histórico.

### M7 — Alpha Ensemble
Solo señales PROMOTE → distribuciones/probabilidades calibradas.

### M8 — Tournament Brain
Simulación de escenarios y optimización de P(#1).

### M9 — Trade Sheet & Human Execution Interface
Decision cockpit / reportes / audit trail / post-trade attribution.

## 12. Modos operativos — no son nuevas fases de desarrollo

### Practice Week
La semana de práctica sirve para medir el simulador real:
- fills;
- timestamps;
- expiración;
- comisiones;
- símbolos;
- restricciones;
- comportamiento de instrumentos ilíquidos;
- actualización del leaderboard.

Sus observaciones alimentan M1/M3.

### Live Tournament
Cuando empiece la competencia:
- componentes críticos congelados o con cambios controlados;
- auditoría diaria;
- provenance de cada señal;
- postmortem;
- ejecución manual.

## 13. Reglas anti-autoengaño

- no look-ahead;
- no leakage;
- no survivorship bias;
- point-in-time correctness;
- splits temporales;
- holdout final protegido;
- costos realistas;
- fills realistas;
- multiple-testing accounting;
- sensitivity/regime checks;
- comparación contra baselines;
- preservar resultados negativos;
- no promover complejidad sin mejora OOS.

## 14. Política de complejidad

Antes de una dependencia o framework:
- problema concreto;
- alternativa simple;
- licencia;
- mantenimiento;
- supuestos;
- beneficio esperado.

Clasificar referencias externas como:
- BUILD CUSTOM;
- ADAPT;
- STUDY ONLY;
- IGNORE.

## 15. Qué NO optimizar

No optimizar por:
- cantidad de indicadores;
- cantidad de modelos;
- visuales bonitos demasiado pronto;
- backtests impresionantes;
- autonomía del portal;
- complejidad arquitectónica.

Optimizar por:
- correctness;
- reproducibility;
- point-in-time integrity;
- falsifiability;
- fast research iteration;
- useful tournament decisions.

## 16. Prioridad inmediata

M0–M8 pasaron sus gates de software dentro del alcance documentado. M8 se integró en `21ad31deb9a637e09e30d0cfc86e4295bb314fe1`; su suite local completa pasó, aunque GitHub no expuso un workflow/status de Actions para ese merge. Los gates empíricos de M6, M7 y M8 siguen `NEEDS_MORE_EVIDENCE`; el registro M7 está vacío. M8 no convierte escenarios sintéticos en evidencia financiera ni usa información futura del leaderboard.

La fase activa es M9: producir reportes morning/event/evening, trade sheet, audit trail, post-trade attribution y cockpit responsive. Cuando falten entradas validadas o frescas, el resultado debe ser `NO TRADE`. La ejecución de órdenes en Actinver permanece manual.
