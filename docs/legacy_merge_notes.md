# Legacy Architecture Merge Notes

## Source

Repositorio previo revisado completo:
`MarioIbago/RetoActinverIGLx0`

Repositorio destino:
`MarioIbago/reto-actinver-2026-`

## Decision

El repo nuevo permanece como única fuente de verdad.

No se copiaron fases antiguas literalmente. Se fusionaron los conceptos superiores del repo viejo dentro de la estructura M0–M9 actual.

## What was inherited

### From old AGENTS.md
- separation LLM vs deterministic math;
- compute policy;
- experiment lifecycle;
- research memory;
- stricter scientific rules;
- GitHub Actions/artifact discipline;
- final human execution boundary.

Merged into:
- `AGENTS.md`
- `MASTER_PLAN.md`
- `docs/architecture.md`
- `docs/research_standard.md`

### From old MASTER_PLAN.md
- scientific harness loop;
- Alpha vs Tournament separation;
- structured news features;
- adversarial research;
- reproducibility identity;
- priority principles;
- explicit Foundation proof loop.

Merged into:
- `MASTER_PLAN.md`
- `docs/architecture.md`

### From old ARCHITECTURE.md
- layer model;
- data contracts;
- GitHub Actions contract;
- security/realtime boundaries.

Merged into:
- `docs/architecture.md`

### From old RESEARCH_PROTOCOL.md
- falsifiable hypothesis standard;
- point-in-time integrity;
- time-aware validation;
- baselines;
- multiple testing;
- robustness;
- LLM eval protocol.

Merged into:
- `docs/research_standard.md`

### From old CODEX_START_HERE + Phase 1
- deterministic smoke experiment;
- workflow_dispatch;
- JSON artifact;
- PASS/FAIL Foundation gate;
- five-step M0 execution sequence: audit → scaffold → Actions → remote verification → closing audit.

Merged into:
- `docs/CODEX_START_HERE.md`
- `prompts/phases/M0_FOUNDATION.md`
- `docs/M0_RUNBOOK.md`

## Phase mapping

```text
OLD Harness Foundation                → NEW M0
OLD Paper Research / registry         → NEW M0 + M5
OLD Data + Company Intelligence       → NEW M1 + M2 + research agents
OLD Quant Engine                      → NEW M4 + M5
OLD News/NLP                          → NEW M6
OLD Validation + Risk                 → NEW M4 + M7
OLD Signal Ranking                    → NEW M7 + M9
OLD Tournament Brain                  → NEW M8
OLD Chat Product                      → NEW M9
OLD Demo/Hardening/Practice/Live Ops  → operational modes after/around M9
```

## What was intentionally NOT copied

- stale future-phase placeholders;
- alternate package name `actinver_quant`;
- old phase numbering;
- assumptions that predate the verified 2026 universe/rules;
- any architecture that would conflict with current source material, Perplexity prompts or M0–M9 governance.

## Result

The merged architecture keeps:
- the old repo's rigor;
- the new repo's 2026-specific context;
- current universe/source material;
- current agent roles;
- current reference-project catalog;
- current M0–M9 prompts.
