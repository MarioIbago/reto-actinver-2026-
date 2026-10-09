# AGENT ROUTER

## Objetivo

Dividir trabajo sin generar caos.

---

# 1. ORCHESTRATOR

Siempre existe un agente principal.

Responsable de:

- plan;
- state;
- integration;
- gates;
- merges;
- final truth.

---

# 2. WORKERS

## Research Scout
Discovery.

## Source Verifier
Primary-source validation.

## Data Agent
PIT/data quality.

## Microstructure Agent
Session/execution behavior.

## Replication Agent
Paper replication.

## Strategy Agent
Approved ExperimentSpecs.

## Validation Agent
OOS/robustness.

## Red Team
Try to break results.

## Tournament Agent
Rank optimization.

## UI Agent
CLI/Excel.

---

# 3. SPAWN RULE

Spawn parallel agents when tasks are:

- independent;
- read-heavy;
- clearly contractible;
- mergeable.

Do not spawn parallel agents editing same critical files without coordination.

---

# 4. CONTRACT

Every worker gets:

```text
objective
inputs
allowed scope
forbidden scope
deliverables
acceptance criteria
evidence requirements
```

---

# 5. RETURN FORMAT

Worker returns:

```text
STATUS
FINDINGS
EVIDENCE
CHANGES
TESTS
RISKS
RECOMMENDATION
```

---

# 6. INDEPENDENT REVIEW

High-impact outputs:

- strategy promotion;
- data change;
- execution-model change;
- Tournament Brain change;

require independent validation / red team.

---

# 7. NO FAKE SPAWN

If platform cannot spawn workers:

run roles sequentially.

Never pretend.
