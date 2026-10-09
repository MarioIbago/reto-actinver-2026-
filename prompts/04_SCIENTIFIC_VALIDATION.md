# SCIENTIFIC VALIDATION & REPLICATION

## Objetivo

Evitar falso alpha.

---

# 1. PAPER PIPELINE

```text
discover
↓
verify title/DOI
↓
obtain legal full text
↓
read methods
↓
read sample
↓
read horizon
↓
read costs
↓
read limitations
↓
find replication
↓
find contradiction
↓
find post-publication evidence
↓
register
```

Abstract-only evidence nunca es STRONG.

---

# 2. PAPER REGISTER

```text
paper_id
title
authors
year
publication
doi
full_text_obtained
version_read
market
sample_start
sample_end
signal
holding_period
gross_effect
net_effect
cost_model
method
oos
replication
post_publication_evidence
limitations
supports
contradicts
```

---

# 3. TRANSFERABILITY

Siempre comprobar:

- horizon match;
- market match;
- liquidity match;
- execution match;
- data availability;
- PIT feasibility.

US monthly momentum ≠ Mexico 3-day momentum.

---

# 4. EXPERIMENTSPEC

Cada hipótesis debe definir:

```text
experiment_id
hypothesis
universe
features
target
horizon
benchmark
cost_model
execution_model
train
validation
test
seed
promotion_criteria
kill_criteria
multiple_testing_family
```

---

# 5. BASELINES FIRST

Comparar contra:

- random feasible;
- equal weight;
- benchmark/index;
- market beta;
- simple momentum;
- simple reversal;
- sector-adjusted baseline.

---

# 6. VALIDATION

Como mínimo cuando aplique:

- true OOS;
- walk-forward;
- transaction costs;
- execution model;
- bootstrap;
- sensitivity;
- regime split;
- sample size;
- confidence intervals;
- leakage tests.

---

# 7. MULTIPLE TESTING

Considerar:

- holdout final intocable;
- experiment family registry;
- False Discovery Rate;
- Deflated Sharpe Ratio;
- PBO;
- White Reality Check;
- Hansen SPA.

No buscar parámetros hasta que uno salga bonito.

---

# 8. ANOMALY DECAY

Buscar:

```text
original effect
post-publication effect
recent effect
net-of-cost effect
```

---

# 9. STATES

- READY_FOR_REPLICATION
- NEEDS_MORE_EVIDENCE
- REJECT_RESEARCH
- PROMOTED_OOS
- SUSPENDED
- RETIRED

Literatura sola no produce `PROMOTED_OOS`.

---

# 10. KILL RULES

Matar si:

- no OOS;
- costs erase effect;
- unstable parameters;
- one-stock dependence;
- one-regime dependence;
- insufficient sample;
- PIT impossible;
- execution incompatible;
- baseline wins;
- effect decayed.

---

# 11. DISTRIBUTIONS

Preferir:

```text
mean
median
p05
p25
p50
p75
p95
P(large gain)
P(large loss)
skew
uncertainty
```

sobre un solo score.

---

# 12. RED TEAM

Antes de PROMOTE:

intenta demostrar:

- leakage;
- survivorship;
- stale prices;
- bad timestamps;
- corporate-action artifacts;
- market beta;
- sector beta;
- costs;
- p-hacking;
- insufficient events.

Si Red Team encuentra un blocker:

`NEEDS_MORE_EVIDENCE` o `REJECT`.
