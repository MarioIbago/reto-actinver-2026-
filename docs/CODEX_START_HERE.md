# Codex — Start Here

## Your role

Estás construyendo el laboratorio científico del Reto Actinver 2026, no inventando picks.

## Read in this order

1. `README.md`
2. `MASTER_PLAN.md`
3. `AGENTS.md`
4. `docs/architecture.md`
5. `docs/research_standard.md`
6. `docs/codex_best_practices.md`
7. `prompts/00_GLOBAL_SYSTEM_PROMPT.md`
8. `prompts/CURRENT_PHASE.md`
9. prompt completo de la fase activa

Para reglas/universo, consulta además `research/source_material/`, pero no normalices ese material fuera de M1.

## Execution sequence

For M0, follow `docs/M0_RUNBOOK.md` one step at a time. Do not collapse audit, implementation, remote verification and closing audit into one opaque task.

## Current mission

La fase activa es M0.

Prueba el loop mínimo:

```text
repo code
   ↓
GitHub Actions
   ↓
deterministic Python smoke experiment
   ↓
machine-readable JSON result
   ↓
artifact
   ↓
PASS/FAIL evidence
```

## Foundation target

Una implementación mínima puede incluir:
```text
pyproject.toml
src/actinver/
tests/
scripts/ or equivalent CLI
.github/workflows/test.yml or foundation workflow
docs/phase_reports/
```

No copies ciegamente la estructura del repo viejo. Usa la estructura actual y el mínimo necesario.

## Smoke experiment

Debe:
- no tener significado financiero;
- ser deterministic;
- registrar seed;
- escribir JSON estable;
- incluir experiment_id/status;
- poder rastrearse al commit/config;
- tener tests.

Ejemplo conceptual:
```json
{
  "experiment_id": "HARNESS_SMOKE_001",
  "status": "PASS",
  "seed": 42,
  "metrics": {
    "deterministic_check": 1.0
  }
}
```

## Workflow requirements

El workflow M0 debe:
1. soportar `workflow_dispatch`;
2. checkout;
3. setup Python estable;
4. instalar paquete/test deps;
5. correr tests;
6. correr smoke experiment;
7. validar output;
8. subir artifact;
9. usar permisos mínimos;
10. no usar secrets.

## Explicitly do NOT do in M0

- market APIs;
- tickers;
- data ingestion real;
- backtesting financiero;
- ML;
- NLP/news ingestion;
- portfolio optimization;
- Tournament Brain;
- frontend;
- agent framework;
- automatic Actinver order submission;
- heavy dependencies sin necesidad.

## Definition of done

M0 solo pasa si:
- package instala limpio;
- tests pasan;
- smoke output es deterministic;
- workflow real en GitHub pasa;
- artifact se puede inspeccionar;
- resultado es machine-readable;
- docs explican trigger/inspection;
- no hubo scope creep.

Si algo no puede verificarse, reporta FAIL/BLOCKED, no asumas PASS.

No avances automáticamente a M1.
