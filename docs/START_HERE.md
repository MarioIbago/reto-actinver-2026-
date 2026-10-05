# START HERE — Reto Actinver 2026

Este documento es para el dueño del proyecto.

## Estado actual

- M0–M9 — gates de software completados dentro del alcance documentado. M9 es la última fase; no hay fase activa. Ver `prompts/CURRENT_PHASE.md` y `docs/phase_reports/M9_REPORT.md`.
- Los gates empíricos de M6, M7 y M8 siguen `NEEDS_MORE_EVIDENCE`; no hay promoción financiera ni recomendación de operación.
- El anexo oficial de la guía 2026 contiene 207 instrumentos. La lista normalizada conserva los símbolos de la guía y señala por separado que los símbolos/series del buscador autenticado siguen sin verificar.
- El reglamento y la guía difieren en cómo cuentan los cinco activos y miden el límite del 50%; la elegibilidad de FIBRAs también requiere aclaración.
- No hay OHLCV/trades ni noticias históricas autorizadas, fills de práctica autenticados o leaderboard PIT completo. M9 muestra `NO_TRADE` hasta que esos datos externos puedan verificarse.

## Documentos principales

Lee `MASTER_PLAN.md`, `docs/architecture.md`, `docs/research_standard.md`, `AGENTS.md`, `docs/CODEX_START_HERE.md` y `prompts/CURRENT_PHASE.md`. Solo lee un prompt de fase cuando una fase nueva haya sido autorizada explícitamente.

## Source material

Los archivos bajo `research/source_material/` son evidencia raw y no deben modificarse silenciosamente. M1 transforma el anexo del participante en `data/metadata/`; el generador compara símbolos y categorías contra los snapshots raw y registra sus hashes.

## Research y producción

- Research puede verificar fuentes, estructurar evidencia, proponer hipótesis y criticar resultados.
- Codex mantiene la implementación de producción.
- Los cálculos, las reglas y la validación se ejecutan de forma determinista.
- La ejecución final en el portal del Reto siempre es manual.

## M1 comandos

```powershell
actinver-m1 audit
actinver-m1 eligible --as-of 2026-10-05
actinver-m1 diff --kind universe --previous <snapshot-anterior.json> --current data/metadata/actinver_universe_2026_v1.json
```

La lista exacta del simulador y la confirmación de las ambigüedades oficiales son evidencia externa todavía pendiente. M1 no debe presentarse como plataforma-verificado hasta que esas fuentes estén disponibles.
