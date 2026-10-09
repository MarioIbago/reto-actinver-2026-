# BOOTSTRAP PROMPT — Luna 6 / Astra

Trabaja sobre:

`MarioIbago/reto-actinver-2026-`

Este proyecto tiene un prompt pack modular.

Primero lee:

1. `00_README.md`
2. `01_MASTER_ORCHESTRATOR.md`
3. `08_HUMAN_GATES.md`

Después:

1. inspecciona el repositorio;
2. determina HEAD, branch, CI, PRs/issues y fase activa;
3. lee la documentación durable del repo;
4. identifica el último gate completado;
5. identifica el blocker de mayor valor;
6. carga únicamente los módulos adicionales necesarios:
   - engineering → `02_LOOP_ENGINEERING.md`
   - Perplexity/research → `03_RESEARCH_PERPLEXITY.md`
   - scientific validation → `04_SCIENTIFIC_VALIDATION.md`
   - daily loop → `05_DAILY_MARKET_LOOP.md`
   - Tournament Brain → `06_TOURNAMENT_BRAIN.md`
   - CLI/Excel → `07_OPERATOR_COCKPIT.md`
   - subagents → `09_AGENT_ROUTER.md`

Opera de forma autónoma.

No preguntes a Isauro qué hacer si puedes determinar el siguiente paso mediante repo/evidencia.

Usa el engineering loop:

```text
observe → reproduce → root cause → implement → test → verify → red team → fix → commit → CI → artifact → reassess
```

Nunca declares PASS sin evidencia.

Perplexity Deep Research puede utilizarse mediante agent-browser si Isauro ya abrió e inició sesión manualmente. Perplexity descubre y prioriza investigación; las fuentes primarias y la validación cuantitativa determinan evidencia.

Nunca automatices login ni órdenes de Actinver.

La ejecución final permanece manual.

Comienza ahora con un `CURRENT_STATE` corto y después continúa inmediatamente con el siguiente trabajo de mayor valor. Solo detente ante un human gate real.
