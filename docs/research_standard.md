# Research Standard — Reto Actinver 2026

## Purpose

Definir cómo una idea se convierte en evidencia. El objetivo no es maximizar la cantidad de estrategias probadas, sino la calidad de la evidencia que sobrevive.

## 1. Hypothesis first

Todo experimento serio empieza con una hipótesis falsable.

Malo:
> buscar una estrategia rentable.

Mejor:
> dadas ciertas condiciones observables y disponibles en tiempo real, la distribución de retorno a 3–5 días difiere de un baseline explícito después de costos.

Antes de correr:
- universe;
- decision timestamp;
- features;
- target/horizon;
- baseline;
- metrics;
- validation method;
- cost/execution assumptions;
- leakage risks;
- promotion/rejection criteria cuando sea práctico.

## 2. Point-in-time integrity

Una feature solo puede usar información disponible al timestamp simulado.

Riesgos:
- fundamentales revisados;
- corporate actions mal aplicados;
- membership futura;
- timestamps de noticias incorrectos;
- earnings dates conocidas retrospectivamente;
- survivorship bias;
- vendor fields restated;
- series/tickers actuales proyectados hacia atrás.

Si la validez point-in-time no puede demostrarse, marcar la evidencia como débil/no promovible.

## 3. Time-aware validation

Random train/test split no es el default para series financieras.

Preferir según el caso:
- expanding walk-forward;
- rolling walk-forward;
- temporal train/validation/OOS;
- purging/embargo si hay labels solapados.

El holdout final no se usa para iterar decisiones.

## 4. Baselines first

Todo método complejo debe compararse con algo más simple:
- unconditional probability;
- equal weight;
- benchmark ETF/index;
- naive momentum;
- relative strength;
- simple event rule;
- linear/logistic baseline;
- random/control.

Si la complejidad no supera el baseline neto de costos y OOS, no se justifica.

## 5. Execution and costs

Cuando el claim sea tradable, incorporar progresivamente:
- Actinver commissions/IVA;
- turnover;
- fill semantics;
- bid/ask/slippage cuando corresponda;
- liquidity;
- order expiration/no-fill;
- concentration;
- no-short;
- exact eligible universe.

No inventar reglas: M1/M3 las versionan.

## 6. Multiple testing

Registrar:
- number of hypotheses/variants;
- parameters explored;
- metrics used for selection;
- whether holdout influenced selection.

Herramientas cuando sean pertinentes:
- bootstrap;
- parameter sensitivity;
- PBO;
- Deflated Sharpe;
- false-discovery/multiple-testing adjustments;
- nested validation.

No todo experimento necesita todas las técnicas; el método debe ser proporcional al claim.

## 7. Robustness / try to kill it

Para cada candidato prometedor intentar destruirlo:
- subperiods;
- costs;
- one-name concentration;
- crisis dependence;
- nearby parameters;
- sector/market controls;
- illiquid names;
- frequency choice;
- intended horizon;
- regime dependence;
- sample size;
- outliers;
- stale data;
- leakage.

El investigador debe buscar evidencia contra la hipótesis, no solo a favor.

## 8. LLM/news protocol

Para features derivadas de LLM:
1. schema estructurado;
2. eval set cuando sea posible;
3. extraction accuracy;
4. confidence/calibration;
5. no future-return leakage;
6. prompt/model configuration versionada;
7. comparación with/without LLM features;
8. cost/latency;
9. incremental predictive value.

La pregunta no es "¿suena inteligente?" sino "¿mejora una tarea medible sin leakage?"

## 9. Research states

Estados operativos oficiales del proyecto:
- REJECT
- NEEDS_MORE_EVIDENCE
- PROMOTE

Si M5 necesita estados de workflow internos, puede añadir IDEA/PLANNED/RUNNING, pero el resultado científico final debe mapear a uno de los tres anteriores.

PROMOTE no significa automáticamente producción/tamaño grande. Significa que el candidato sobrevivió el gate definido para esa etapa.

## 10. Scientific memory

Nunca borrar un experimento por fallar.

Cada resultado debe preservar:
- experiment ID;
- hypothesis;
- commit;
- dataset/universe version;
- parameters;
- metrics;
- validation;
- costs;
- robustness;
- status;
- rejection/promotion reason;
- artifacts.

## 11. Tournament research

Tournament optimization es un problema distinto del alpha.

Preguntas válidas:
- ¿cómo cambia concentración con tiempo restante?
- ¿cómo cambia risk-taking con leader gap?
- ¿qué tan sensible es P(#1) a correlaciones?
- ¿cuándo defender una ventaja domina expected return?
- ¿qué ocurre bajo opponent uncertainty?

No optimizar torneo con señales cuya distribución no tenga evidencia suficiente.

## 12. Reproducibility

Cada experimento serio debe identificar:
- code commit;
- dataset version;
- universe version;
- config;
- dependencies;
- seed;
- artifact references.

## 13. Core questions

El harness siempre pregunta:

1. **¿Es probable que este edge sea real?**
2. **Si lo es, ¿esta forma de usarlo maximiza nuestro objetivo de torneo?**

No responder 2 antes de tener evidencia razonable para 1.
