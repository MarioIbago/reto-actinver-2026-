# Codex Best Practices — Reto Actinver 2026

## Principio
Codex trabaja como ingeniero de un laboratorio científico, no como generador libre de código.

## Reglas

1. Una tarea concreta por turno.
2. Antes de cambios grandes: inspección y plan.
3. Leer siempre `AGENTS.md` y la fase activa.
4. No adelantar fases.
5. Commits pequeños y auditables.
6. Los tests forman parte de la tarea.
7. No borrar resultados negativos.
8. No dejar secretos ni archivos temporales.
9. No añadir dependencias sin justificar problema, licencia y mantenimiento.
10. Preferir interfaces pequeñas y desacopladas.
11. No iterar usando el test final.
12. Cada tarea debe tener criterios de aceptación verificables.
13. Al cerrar: diff, tests, limitaciones, deuda técnica y siguiente paso.

OpenAI documenta `AGENTS.md` como mecanismo de instrucciones de proyecto para Codex:
- https://openai.com/index/introducing-codex/
- https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan

## Prompt recomendado

```text
Lee AGENTS.md y el prompt de la fase activa.

Inspecciona antes de modificar.

Objetivo:
<UNA tarea concreta>

Restricciones:
- no adelantar fases;
- no introducir dependencias innecesarias;
- mantener contratos existentes;
- escribir/actualizar tests;
- ejecutar tests relevantes.

Antes de implementar responde:
1. estado actual;
2. plan;
3. archivos a tocar;
4. riesgos;
5. criterios de aceptación.

Después implementa.

Al terminar responde:
1. resumen del diff;
2. tests ejecutados y resultado;
3. limitaciones;
4. deuda técnica;
5. siguiente paso recomendado.

Detente.
```
