# M0 Runbook — Execute Foundation in Small Steps

This runbook preserves the strongest operational pattern from the previous repository: do not ask Codex to complete M0 in one opaque jump.

Run one step at a time and review before continuing.

## Step 1 — Audit and plan only

```text
Read completely, in order:
1. README.md
2. MASTER_PLAN.md
3. AGENTS.md
4. docs/CODEX_START_HERE.md
5. docs/architecture.md
6. docs/research_standard.md
7. prompts/00_GLOBAL_SYSTEM_PROMPT.md
8. prompts/CURRENT_PHASE.md
9. prompts/phases/M0_FOUNDATION.md

Your task in this turn is ONLY to audit and plan M0. Do not implement yet.

Goal:
prove the minimal loop:
repo -> GitHub Actions -> deterministic Python -> structured JSON artifact -> verified PASS/FAIL.

Deliver:
- current repository audit;
- what already exists and must not be duplicated;
- minimum files to create/modify;
- tiny Python design;
- deterministic smoke experiment design;
- GitHub Actions design;
- acceptance checklist mapped one-to-one to M0 exit criteria;
- risks/unknowns;
- exact next implementation step.

Constraints:
- no real market data;
- no tickers;
- no strategies;
- no backtesting;
- no ML;
- no news APIs;
- no database unless demonstrably required (it should not be);
- no frontend;
- no agent framework;
- no Actinver order automation;
- no future-phase implementation.

Prefer boring, testable infrastructure.
```

Review before continuing:
- scope is truly M0;
- no heavy dependency was introduced;
- smoke output is machine-readable;
- workflow_dispatch is included;
- source material is untouched.

## Step 2 — Implement the minimal Python scaffold

```text
Implement only the approved minimal Python scaffold for M0.

Requirements:
- use pyproject.toml;
- use the existing src/actinver package namespace;
- implement the minimum ExperimentSpec / ExperimentResult contracts needed by M0;
- implement a deterministic harness smoke experiment with no financial meaning;
- serialize a stable JSON result;
- provide a small CLI/script or equivalent entrypoint;
- add fast unit tests for determinism and schema/basic content;
- implement only the minimum research-ledger/version identity needed by the M0 gate;
- do not implement GitHub Actions yet unless the approved plan explicitly grouped it into this step.

Keep dependencies minimal.

Run local tests and report:
- files changed;
- commands run;
- test results;
- assumptions;
- anything intentionally deferred.
```

## Step 3 — Implement the GitHub Actions Foundation path

```text
Implement the M0 GitHub Actions execution path.

The workflow must:
1. support workflow_dispatch;
2. checkout the repository;
3. set up a stable modern Python;
4. install the project and test dependencies;
5. run tests;
6. run the deterministic smoke experiment;
7. verify the JSON result exists and is valid;
8. upload the result as a clearly named artifact;
9. use minimal permissions;
10. use no secrets.

Do not add schedules, external APIs, market data or financial logic.

Update docs only as needed to explain how to trigger the workflow and inspect the artifact.

Validate the workflow and local commands where possible.
```

## Step 4 — Run and verify on GitHub

```text
Verify M0 on GitHub itself.

- trigger the Foundation workflow manually if GitHub access permits;
- inspect the workflow result;
- if it fails, diagnose logs and make only M0-scoped fixes;
- rerun until PASS or until a real platform/permission blocker is reached;
- inspect the uploaded artifact;
- verify the JSON contents and traceability fields.

Do not add product features.

Report:
- workflow result;
- tests result;
- artifact name;
- artifact content summary;
- fixes required;
- anything not verified.

If the workflow/artifact was not actually observed, do not claim PASS.
```

## Step 5 — Closing audit

```text
Perform a strict M0 closing audit. Do not add features.

Read prompts/phases/M0_FOUNDATION.md and map every exit criterion to evidence.

Look for:
- unnecessary dependencies;
- unnecessary abstractions;
- secrets;
- non-determinism;
- brittle paths;
- undocumented commands;
- excessive workflow permissions;
- missing artifact validation;
- accidental financial logic;
- modifications to source material;
- implementation belonging to future phases.

Fix only issues necessary to pass M0.

Create/update docs/phase_reports/M0_REPORT.md.

End with exactly one status:
- M0 PASS — READY FOR HUMAN REVIEW
or
- M0 OPEN — BLOCKERS REMAIN

Do not update CURRENT_PHASE.md.
```

## Gate

The human owner/ChatGPT review decides whether to advance to M1. Codex never advances the phase automatically.
