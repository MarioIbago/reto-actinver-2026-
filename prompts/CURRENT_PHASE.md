# CURRENT PHASE

**M9 — TRADE SHEET & HUMAN EXECUTION INTERFACE**

Codex debe leer:
1. `prompts/00_GLOBAL_SYSTEM_PROMPT.md`
2. `prompts/phases/M9_TRADE_SHEET.md`

M0–M8 pasaron sus gates de software dentro del alcance documentado. M2 se cerró con el dataset de calendario BMV `actinver-pit-v1-347fa83b3804ea2bff4ac9d125686df5b05cfc3f3d84ba72e663d06883c952bd`, reconstruido por tiempo de fuente/sistema y registrado en `docs/phase_reports/M2_REPORT.md`. M3 quedó integrado en el merge `47edadac78ad0bb9b731054e1be06a6693e21c7a`; M4 en `9d12e52d72bb74251a7eb1e5d0a47b295b13f8ce`; M5 en `533958e11258a2d4603166fc0f731d58fb2e3a58`; M6 en `e3c0887160013f6ff21ee7c7fd7ffd5eefda2b35`; M7 en `1cc66f9082e3f38e9b00ec80ce9f5c92d22af14c`; y M8 en `21ad31deb9a637e09e30d0cfc86e4295bb314fe1`. Los informes contienen la evidencia y limitaciones por fase.

**M6, M7 y M8 conservan gate empírico `NEEDS_MORE_EVIDENCE`.** No hay corpus noticioso histórico autorizado, OHLCV/trades históricos autorizados, fills reales de práctica ni mapeo autenticado de símbolos. M7 no tiene señales PROMOTE financieras ni artefactos de forecast por instrumento; su registro de producción está vacío. M8 está implementada para simulación y siempre emite `decision: null`; su reporte documenta que GitHub no expuso un run de Actions para el merge y contiene los controles locales. No conviertas estos estados en aprobación científica. No emitas recomendaciones respaldadas por entradas sintéticas o vacías.

M9 debe generar morning report, event update, evening review, trade sheet versionada, audit trail, post-trade attribution y cockpit responsive. Cuando M7/M8 no estén validados, muestra `NO TRADE` y datos incompletos/stale con claridad. La instrucción del usuario de completar todas las fases autoriza el trabajo sin pausas de aprobación, pero no reemplaza evidencia ni autoriza automatizar órdenes.
