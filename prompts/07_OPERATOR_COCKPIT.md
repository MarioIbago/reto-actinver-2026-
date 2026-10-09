# OPERATOR COCKPIT — CLI + EXCEL

## Objetivo

Isauro debe poder entender la decisión sin tocar infraestructura.

---

# 1. CLI

Comandos conceptuales:

```bash
actinver status
actinver cockpit
actinver candidates
actinver decision
actinver research fomo-scan
actinver research quant-scan
actinver research deep-dive TICKER
actinver reconcile
```

---

# 2. MAIN VIEW

```text
ACTINVER 2026

CAPITAL
RANK
LEADER GAP
DAYS LEFT

DATA        PASS/WARN/BLOCKED
EXECUTION   PASS/WARN/BLOCKED
CI          PASS/FAIL
RESEARCH    CURRENT/STALE

TOP CANDIDATES
1.
2.
3.

BEST DECISION
ACTION
TICKER
SIZE
HORIZON
WHY
RISK
INVALIDATION

ISAURO ACTION:
...
```

---

# 3. EXCEL CONTROL TOWER

Archivo:

`reports/ACTINVER_CONTROL_TOWER.xlsx`

Derivado del repo y resultados.

Sheets:

- OVERVIEW
- UNIVERSE
- STOCKS
- RULES
- DATA_QUALITY
- SOURCES
- HYPOTHESES
- EXPERIMENTS
- STRATEGIES
- FOMO_SCOUT
- DEEP_RESEARCH_RUNS
- CANDIDATE_FUNNEL
- TODAY_SIGNALS
- POSITIONS
- MANUAL_ORDERS
- TOURNAMENT
- RISK
- BUGS
- CI
- DECISION_LOG
- DAILY_REVIEW

---

# 4. EXCEL RULE

Excel es output operativo.

Nunca source of truth.

Actualización por código reproducible.

---

# 5. DECISION RECORD

```text
decision_id
timestamp
repo_sha
dataset_version
rules_version
ticker
action
current_position
proposed_position
horizon
why_now
strategies
distribution
risk
invalidation
execution
tournament_reason
evidence_status
uncertainty
manual_action_required
```

---

# 6. REJECTED IDEAS

Mostrar también 1–3 ideas llamativas rechazadas.

Ejemplo:

```text
TSLA — REJECTED
Reason: headline strong, quant support weak, move already extended.
```

Esto evita que Isauro piense que el sistema “ignoró” una narrativa popular.

---

# 7. STALE WARNINGS

Mostrar:

```text
positions stale
rank stale
news stale
market data stale
```

No esconderlo.
