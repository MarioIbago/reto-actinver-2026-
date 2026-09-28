# START HERE — Cómo empezar

Este documento es para el dueño del proyecto.

## 1. Método

```text
Research
   ↓
dossier / evidence
   ↓
Codex
   ↓
implementation
   ↓
tests / GitHub Actions
   ↓
experiment
   ↓
validation
   ↓
REJECT / PROMOTE
```

No construir todo a la vez.

## 2. Documentos principales

Lee:
1. `MASTER_PLAN.md`
2. `docs/architecture.md`
3. `docs/research_standard.md`

Codex usa además:
- `AGENTS.md`
- `docs/CODEX_START_HERE.md`
- `prompts/CURRENT_PHASE.md`
- prompt de fase.

## 3. Fase activa

M0 — Foundation & Research Infrastructure.

Todavía NO:
- estrategias;
- picks;
- noticias en producción;
- ML;
- backtests financieros;
- Tournament Brain;
- UI.

M0 solo prueba que el laboratorio funciona.

## 4. Primer prompt a Codex

Pídele:
- leer los docs obligatorios;
- inspeccionar repo;
- planificar M0;
- no implementar hasta revisar el plan.

Después autoriza implementación por pasos pequeños.

## 5. Source material

Siempre disponible:
- `research/source_material/reto-actinver-2026-guia.md`
- `research/source_material/actinver_universe_symbols_raw.md`

Ese universo raw tiene 207 instrumentos.

No normalizar/editar fuera de M1.

## 6. Research paralelo

Mientras Codex trabaja en M0:
- ChatGPT Research puede preparar dossiers;
- Perplexity puede verificar universe/news/sources;
- manual research roles can critique/synthesize.

Research no modifica producción.

## 7. Simulated agents

Antes de construir multi-agent infrastructure:
- `docs/manual_agent_workflow.md`
- `prompts/manual_agents/00_MANAGER.md`

Codex sigue siendo single production-code writer.

## 8. Cuando M0 termine

Trae:
- `docs/phase_reports/M0_REPORT.md`;
- commit/PR;
- test output;
- GitHub workflow run;
- artifact.

Solo después decidimos M1.
