# LOOP ENGINEERING

## Objetivo

Resolver ingeniería, bugs y reliability sin depender de intervención constante del usuario.

---

# 1. ISSUE LOOP

Para cada problema crea mentalmente o en GitHub:

```text
PROBLEM
EXPECTED BEHAVIOR
OBSERVED BEHAVIOR
REPRODUCTION
ROOT CAUSE HYPOTHESES
ACCEPTANCE CRITERIA
TEST PLAN
```

---

# 2. BUG CLASSES

- P0 — integrity / leakage / money / fills / corrupted state.
- P1 — scientific invalidity.
- P2 — decision logic.
- P3 — pipeline / reliability / performance.
- P4 — operator UX.
- P5 — cosmetic.

Siempre resuelve mayor severidad primero.

---

# 3. ROOT-CAUSE LOOP

```text
reproduce
↓
instrument/log
↓
reduce scope
↓
identify invariant violated
↓
write failing test
↓
minimal fix
↓
targeted test
↓
full relevant suite
↓
integration test
↓
CI
```

Si después de 3 intentos estás cambiando cosas sin nueva evidencia:

DETENTE.

No sigas parchando.

Haz:

```text
ROOT_CAUSE_REASSESSMENT
```

y reconsidera arquitectura/assumptions.

---

# 4. REGRESSION RULE

Bug significativo => regression test.

Especialmente:

- leakage;
- timezone;
- stale prices;
- corporate actions;
- commission;
- cash;
- constraints;
- fills;
- ranking;
- strategy routing.

---

# 5. OBSERVABILITY-FIRST DEBUGGING

Antes de cambios grandes, añade cuando convenga:

- structured logs;
- counters;
- assertions;
- invariant checks;
- reproducible fixtures;
- artifact snapshots.

La observabilidad debe reducir incertidumbre.

---

# 6. GIT UNIT OF WORK

Ideal:

```text
one issue
one branch
one coherent change
one regression test
one PR
```

Evita mega-commits.

---

# 7. COMMIT RULE

Antes de commit:

```text
git status
git diff
git diff --check
tests
no secrets
scope check
```

Mensaje:

```text
type(phase): concise change
```

---

# 8. PR RULE

PR describe:

- problem;
- solution;
- tests;
- risks;
- evidence;
- what is intentionally not included.

---

# 9. CI FAILURE

Si CI falla:

1. inspect exact failing job;
2. reproduce locally if possible;
3. classify infra vs code;
4. fix only root cause;
5. rerun;
6. preserve failed run;
7. do not rewrite history to hide it.

---

# 10. DONE

Una tarea termina cuando:

- acceptance criteria pass;
- tests pass;
- CI passes when required;
- artifact inspected when required;
- docs updated;
- no hidden blocker.

No porque “se ve bien”.
