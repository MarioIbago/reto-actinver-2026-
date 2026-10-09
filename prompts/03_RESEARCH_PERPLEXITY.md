# PERPLEXITY DEEP RESEARCH + DUAL DISCOVERY

## Objetivo

Usar Perplexity Deep Research como radar y research scout.

Nunca como trader autónomo.

---

# 1. ACCESS

El usuario abre Perplexity y hace login manualmente.

Con agent-browser:

```text
open
↓
wait networkidle
↓
snapshot
↓
select Deep Research
↓
re-snapshot
↓
submit research query
↓
wait
↓
extract answer/citations
↓
open sources
↓
verify
```

Nunca:

- escribir contraseña;
- exportar cookies;
- guardar browser auth state;
- cambiar billing.

---

# 2. MODE

Usar explícitamente:

`Deep Research / Research`

según el nombre visible.

Registrar:

```text
mode_display_name
timestamp
query_hash
```

Si no está disponible:

`DEEP_RESEARCH_UNAVAILABLE`

---

# 3. SKILL A — FOMO-FIRST

Pipeline:

```text
verified universe
↓
Perplexity Deep Research broad scan
↓
max 5 candidates
↓
second-pass research per candidate
↓
contradiction search
↓
quant validation
↓
execution/cost check
↓
Tournament Brain
```

---

# 4. BROAD QUERY

Pedir:

- todas las noticias recientes relevantes;
- primary sources;
- earnings;
- guidance;
- revisions;
- regulatory;
- contracts;
- M&A;
- product events;
- macro/commodity exposure;
- unusual attention;
- sector/peer effects.

Solicitar máximo 5 instrumentos que merecen validación.

NO pedir simplemente:

> “¿Qué compro?”

Pregunta correcta:

> “¿Qué instrumentos merecen investigación inmediata y por qué?”

---

# 5. SECOND PASS

Cada candidato vuelve a Deep Research.

Prompt mental:

```text
Try to DISPROVE this thesis.
Find contradictory evidence.
Find stale/recycled news.
Determine what is already priced in.
Find the first publication timestamp.
Find primary sources.
Find next catalysts.
Find reasons for reversal.
```

---

# 6. THIRD PASS

Si quedan 2–3 finalistas:

comparación homogénea:

- novelty;
- materiality;
- surprise;
- freshness;
- prior move;
- liquidity;
- contradictions;
- peer confirmation;
- downside narrative.

---

# 7. FOMO STATUS

- RESEARCH_STRONG
- RESEARCH_MIXED
- RESEARCH_WEAK
- RESEARCH_REJECT

Esto mide research, no alpha.

---

# 8. QUANT VALIDATION

Para shortlist FOMO:

- PIT;
- stale-price check;
- momentum;
- abnormal volume;
- volatility;
- sector-relative move;
- event analogues;
- costs;
- liquidity;
- expected distribution.

No busques indicadores hasta encontrar uno que confirme la narrativa.

---

# 9. SKILL B — QUANT-FIRST

Pipeline:

```text
full universe
↓
quant scanner
↓
top unusual instruments
↓
Perplexity Deep Research
↓
catalyst/contradiction classification
↓
validation
```

Possible outcomes:

- CATALYST_FOUND
- NO_CLEAR_CATALYST
- CONTRADICTORY_CATALYST
- STALE_INFORMATION
- DATA_ISSUE_SUSPECTED

---

# 10. DUAL DISCOVERY MATRIX

| Quant | Research | Interpretation |
|---|---|---|
| strong | strong | VALIDATED_CANDIDATE |
| strong | mixed | QUANT_LED |
| mixed | strong | RESEARCH_LED |
| weak | strong | NARRATIVE_RISK |
| strong | reject | CONTRADICTED |
| weak | weak | REJECT |

Esto NO es una regla automática de BUY.

---

# 11. DUPLICATE NEWS

Agrupa:

```text
root_event_id
primary_source
first_public_time
```

40 copias de una misma nota ≠ 40 eventos.

Distingue:

- novelty;
- attention;
- syndication.

---

# 12. SOURCE PRIORITY

1. company IR / filing;
2. regulator / exchange;
3. government;
4. official earnings release;
5. reputable wire;
6. major financial press;
7. analyst secondary source;
8. social/community.

Reddit puede medir atención.

No establece por sí solo un hecho corporativo.

---

# 13. ARTIFACTS

Guardar sin secretos:

```text
query.md
answer.md
sources.csv
verified_sources.csv
candidate_set.json
contradictions.md
handoff.json
```

---

# 14. RESEARCH RUN REGISTER

```text
run_id
started_at
mode
query_hash
universe_version
candidate_count
source_count
primary_sources_verified
finalists
handoff_status
```

---

# 15. FINAL HANDOFF

Perplexity solo entrega:

```text
candidate
claim
sources
contradictions
event timestamp
research confidence
data requirements
```

Después Python / validation decide.

Nunca:

```text
Perplexity → BUY
```
