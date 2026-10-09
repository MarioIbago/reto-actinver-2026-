# DAILY MARKET LOOP

## Objetivo

Que el sistema opere como research/decision workflow diario sin pedir instrucciones constantes.

---

# MORNING

1. sync repo/state;
2. check CI;
3. update market calendar;
4. refresh allowed data;
5. run data-quality checks;
6. stale-price firewall;
7. update capital/rank/positions if available;
8. run Perplexity FOMO-first scan when useful;
9. run quant scanner;
10. union candidates;
11. deep research finalists;
12. validate events/timestamps;
13. run active strategy registry;
14. estimate return distributions;
15. execution feasibility;
16. risk;
17. Tournament Brain;
18. produce CLI + Excel + Trade Sheet.

---

# INTRADAY

No recalcular todo sin motivo.

Triggers:

- material price move;
- material news;
- event;
- fill manually recorded;
- data correction;
- rule issue;
- ranking update;
- invalidation.

Evita churn.

---

# EVENING

1. reconcile manual fills;
2. reconcile positions/cash;
3. P&L;
4. compare decision vs outcome;
5. update calibration;
6. update decision log;
7. record research failures;
8. record bugs;
9. prepare next-day watchlist.

---

# CANDIDATE FUNNEL

```text
207 universe
↓
eligible
↓
data quality
↓
quant/news candidates
↓
deep dive
↓
validation
↓
execution
↓
risk
↓
Tournament Brain
↓
Trade Sheet
```

---

# NO-TRADE

Todos los candidatos pueden ser rechazados.

Salida válida:

```text
NO_TRADE
reason: insufficient edge after validation/costs
```

---

# DATA FRESHNESS

Mostrar siempre:

```text
market_data_as_of
news_as_of
rank_as_of
positions_as_of
```

Nunca ocultar state stale.

---

# FAILURE BEHAVIOR

Si falla un upstream crítico:

```text
DATA BLOCKED → NO TRADE
RULES BLOCKED → NO TRADE
EXECUTION BLOCKED → MANUAL REVIEW
```

No producir decisión verde con pipeline roto.
