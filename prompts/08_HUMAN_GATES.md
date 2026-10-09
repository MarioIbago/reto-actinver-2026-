# HUMAN GATES

## Objetivo

Minimizar preguntas innecesarias sin cruzar decisiones humanas reales.

---

# 1. DO NOT ASK ISAURO

No preguntar por:

- nombres internos;
- estructura de archivos;
- unit tests;
- retry de CI;
- fuente alternativa;
- refactor menor;
- búsqueda adicional;
- formato de artifacts;
- detalles de implementación reversibles.

Decide autónomamente.

---

# 2. ASK ONLY WHEN REQUIRED

Preguntar cuando sea necesario:

## ACCOUNT / SIMULATOR STATE
- current capital;
- current rank;
- current positions;
- manual fill;
- screenshot;
- exact platform symbol unavailable elsewhere.

## RULE AMBIGUITY
Interpretación que puede invalidar una operación.

## IRREVERSIBLE ACTION
Borrar datos, cambiar historia, grandes migraciones no reversibles.

## PHASE GATE
Avanzar oficialmente `CURRENT_PHASE`.

## FINAL TRADE
Sistema propone, humano ejecuta.

---

# 3. NO BACKGROUND PROMISES

Nunca digas:

“lo haré después”.

Haz todo lo posible en la sesión actual.

Si bloqueado:

```text
BLOCKED
reason
evidence
minimum human input required
```

---

# 4. HUMAN PROMPT MINIMIZATION

Cuando necesites algo humano:

pregunta por el mínimo dato exacto.

Mal:

> “¿Qué hacemos?”

Bien:

> “Necesito el fill observado de MU: hora, precio y acciones.”

---

# 5. FINAL TRADE BOUNDARY

Nunca ejecutar orden.

Output:

```text
PROPOSED MANUAL ACTION
```

No:

```text
ORDER SUBMITTED
```
