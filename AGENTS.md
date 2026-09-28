# AGENTS.md — Operating Contract for Codex

## Regla 0
Antes de modificar código o configuración:
1. Lee `README.md`.
2. Lee `prompts/00_GLOBAL_SYSTEM_PROMPT.md`.
3. Lee `prompts/CURRENT_PHASE.md`.
4. Lee el prompt completo de la fase activa.
5. Consulta `docs/reference_projects.md` si la fase toca arquitectura, backtesting, optimización, NLP, experiment tracking o UI/UX.
6. Inspecciona el estado real del repositorio.
7. No asumas que una fase está terminada porque exista su carpeta.

## Política de referencias externas
Las referencias de `docs/reference_projects.md` existen para evitar reinventar componentes maduros y para estudiar patrones de arquitectura/UX. No son dependencias automáticas.

Antes de reutilizar cualquier proyecto:
- verifica licencia vigente;
- verifica mantenimiento;
- documenta por qué encaja;
- identifica supuestos incompatibles con Actinver;
- clasifica la decisión como BUILD CUSTOM / ADAPT / STUDY ONLY / IGNORE.

Nunca copies código o una arquitectura completa solo porque el proyecto sea popular.

## Disciplina por fases
Solo implementa la fase activa. No adelantes módulos de fases futuras salvo interfaces mínimas indispensables.

Cada fase debe terminar con:
- tests relevantes;
- documentación actualizada;
- artefactos reproducibles;
- reporte de cierre en `docs/phase_reports/`;
- riesgos/deuda técnica;
- evidencia de que los criterios de salida se cumplieron.

## Principios científicos
- point-in-time correctness;
- sin look-ahead bias;
- sin survivorship bias;
- sin data leakage;
- costos y ejecución realista;
- train/validation/test;
- walk-forward cuando aplique;
- registrar múltiples pruebas e hipótesis fallidas;
- no promover complejidad sin mejora fuera de muestra;
- preservar resultados negativos;
- todo experimento ligado a código, datos, parámetros y commit.

## Seguridad operativa
El sistema puede investigar, puntuar, simular y producir instrucciones. No debe automatizar clicks ni órdenes dentro del portal del Reto Actinver. La ejecución final corresponde al participante humano.

## Regla de parada
Cuando cumplas la misión de la fase activa, detente y espera actualización de `prompts/CURRENT_PHASE.md`.
