# CURRENT PHASE

**M8 — TOURNAMENT BRAIN**

Codex debe leer:
1. `prompts/00_GLOBAL_SYSTEM_PROMPT.md`
2. `prompts/phases/M8_TOURNAMENT_BRAIN.md`

M0–M7 pasaron sus gates de software dentro del alcance de cada informe. M2 se cerró con el dataset de calendario BMV `actinver-pit-v1-347fa83b3804ea2bff4ac9d125686df5b05cfc3f3d84ba72e663d06883c952bd`, reconstruido por tiempo de fuente/sistema y registrado en `docs/phase_reports/M2_REPORT.md`. M3 quedó integrado en el merge `47edadac78ad0bb9b731054e1be06a6693e21c7a`; M4 en `9d12e52d72bb74251a7eb1e5d0a47b295b13f8ce`; M5 en `533958e11258a2d4603166fc0f731d58fb2e3a58`; M6 en `e3c0887160013f6ff21ee7c7fd7ffd5eefda2b35`; y M7 en `1cc66f9082e3f38e9b00ec80ce9f5c92d22af14c`. Los informes contienen la evidencia por fase.

**M6 y M7 tienen gate de software PASS y gate empírico `NEEDS_MORE_EVIDENCE`.** No hay corpus noticioso histórico autorizado, OHLCV/trades históricos autorizados, fills reales de práctica ni mapeo autenticado de símbolos. M7 no tiene señales PROMOTE financieras ni artefactos de forecast por instrumento; su registro de producción está vacío. M8 queda activa por instrucción explícita del usuario, sin convertir los gates pendientes en aprobación científica. Usa escenarios sintéticos solo para verificar cálculos y software; no emitas recomendaciones de cartera respaldadas por entradas sintéticas o vacías.

M8 debe maximizar conceptualmente `P(final_rank = 1)` con un simulador reproducible de escenarios, restricciones Actinver y comparaciones contra baselines de retorno esperado y Sharpe. No uses datos futuros del leaderboard, no optimices un único path y separa retorno esperado, riesgo de ruina y probabilidad de primer lugar. La instrucción del usuario de continuar fases autoriza el trabajo sin pausas de aprobación, pero no reemplaza evidencia ni autoriza automatizar órdenes.
