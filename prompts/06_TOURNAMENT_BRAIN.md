# TOURNAMENT BRAIN

## Objetivo

Separar alpha de estrategia de torneo.

Alpha Engine:

> What are the candidate return distributions?

Tournament Brain:

> Given contest state, which feasible portfolio maximizes our chance of finishing first?

---

# 1. STATE

```text
capital
cash
rank
leader_capital
leader_gap
days_remaining
positions
candidate_distributions
correlations
liquidity
rules
opponent_uncertainty
```

---

# 2. OBJECTIVE

Preferir simulación directa:

\[
\max_w P(R_{final}(w) > R_{rivals})
\]

cuando el rival model sea suficientemente definido.

---

# 3. FALSE PRECISION

No reportar:

```text
P(win)=37.4281%
```

sin:

- model assumptions;
- sensitivity;
- uncertainty;
- opponent model dependence.

---

# 4. OPPONENT MODELS

Probar sensibilidad a:

- random feasible;
- diversified;
- benchmark-like;
- high-beta;
- concentrated;
- momentum-following;
- retail-like;
- leader-conditioned.

---

# 5. DYNAMIC RISK HYPOTHESES

Investigar:

```text
early:
edge quality / avoid unnecessary ruin
```

```text
mid:
rank/gap/differentiation matters more
```

```text
late + leading:
possibly defend
```

```text
late + behind:
possibly seek positive skew / differentiation
```

No hardcodear hasta validar.

---

# 6. CONSTRAINTS

Nunca proponer:

- ineligible instrument;
- > allowed weight;
- short if prohibited;
- impossible cash;
- unsupported fill assumption.

---

# 7. OUTPUT

```text
mode
candidate_portfolio
expected_terminal_distribution
estimated_rank_distribution
main_assumptions
sensitivity
largest_risks
why_not_alternatives
```

---

# 8. FAIL SAFE

Si opponent uncertainty es demasiado alta:

reportar:

`TOURNAMENT_MODEL_LOW_CONFIDENCE`

y usar política más robusta, no falsa precisión.
