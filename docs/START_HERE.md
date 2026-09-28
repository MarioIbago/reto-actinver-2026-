# START HERE — Cómo empezar

Este documento es para el dueño del proyecto.

## Método de trabajo

1. ChatGPT Research investiga y produce dossiers.
2. Codex implementa una sola fase.
3. Codex ejecuta tests y deja reporte.
4. ChatGPT revisa.
5. Solo entonces avanzamos.

## Qué haces ahora

### 1. Abre el repo con Codex
Repositorio:
`MarioIbago/reto-actinver-2026-`

Primer mensaje recomendado:

```text
Lee completos y en este orden:
1. AGENTS.md
2. prompts/00_GLOBAL_SYSTEM_PROMPT.md
3. prompts/CURRENT_PHASE.md
4. el prompt de la fase activa

Después inspecciona el repositorio.

Trabaja únicamente en la fase activa.
Antes de modificar archivos, explícame:
- estado actual;
- plan;
- archivos que propones tocar;
- tests que ejecutarás;
- criterios de salida.

No avances a otra fase.
```

### 2. La fase activa es M0
M0 solo debe construir infraestructura científica: packaging, schemas, ExperimentSpec/ExperimentResult, logging, tests, CI, ledger y reproducibilidad.

No pedir todavía:
- estrategias;
- picks;
- noticias en vivo;
- ML;
- UI;
- Tournament Brain.

### 3. Cuando Codex termine
Comparte con ChatGPT:
- reporte de fase;
- commit o PR;
- salida de tests;
- dudas/riesgos.

### 4. Tu lista de instrumentos Actinver es muy valiosa
Cuando lleguemos a M1, esa lista será uno de los inputs principales.

No la limpies manualmente antes de guardarla.

Preferencia de formato:
1. CSV/XLSX oficial;
2. PDF/documento oficial;
3. lista copiada del simulador;
4. capturas si no existe otra opción.

La versión normalizada terminará en:
`data/metadata/actinver_universe.csv`

## Cómo usamos Research

Research sirve para:
- papers;
- señales 1–30 días;
- microestructura BMV;
- M6/rank optimization;
- fuentes de datos;
- noticias/NLP;
- validación;
- UI/referencias técnicas.

Research produce dossiers; Codex los convierte en código y experimentos.

## Orden correcto

```text
RESEARCH
  ↓
DOSSIER
  ↓
CODEX
  ↓
IMPLEMENTATION
  ↓
TESTS / ACTIONS
  ↓
EXPERIMENT
  ↓
VALIDATION
  ↓
PROMOTE / REJECT
```
