# Codex — Start Here

## Your role

Estás construyendo el laboratorio científico del Reto Actinver 2026, no inventando picks.

## Read in this order

1. `README.md`
2. `MASTER_PLAN.md`
3. `AGENTS.md`
4. `docs/architecture.md`
5. `docs/research_standard.md`
6. `docs/codex_best_practices.md`
7. `prompts/00_GLOBAL_SYSTEM_PROMPT.md`
8. `prompts/CURRENT_PHASE.md`
9. prompt completo de la fase activa

Para reglas/universo, consulta además `research/source_material/`, pero no normalices ese material fuera de M1.

## Execution sequence

For M0, follow `docs/M0_RUNBOOK.md` one step at a time. Do not collapse audit, implementation, remote verification and closing audit into one opaque task.

## Current mission

La fase activa es M0.

Prueba el loop mínimo:

```text
repo code
   ↓
GitHub Actions
   ↓
deterministic Python smoke experiment
   ↓
machine-readable JSON result
   ↓
artifact
   ↓
PASS/FAIL evidence
```

## Foundation target

Una implementación mínima puede incluir:
```text
pyproject.toml
src/actinver/
tests/
scripts/ or equivalent CLI
.github/workflows/test.yml or foundation workflow
docs/phase_reports/
```

No copies ciegamente la estructura del repo viejo. Usa la estructura actual y el mínimo necesario.

## Smoke experiment

Debe:
- no tener significado financiero;
- ser deterministic;
- registrar seed;
- escribir JSON estable;
- incluir experiment_id/status;
- poder rastrearse al commit/config;
- tener tests.

Ejemplo conceptual:
```json
{
  "experiment_id": "HARNESS_SMOKE_001",
  "status": "PASS",
  "seed": 42,
  "metrics": {
    "deterministic_check": 1.0
  }
}
```

## Workflow requirements

El workflow M0 debe:
1. soportar `workflow_dispatch`;
2. checkout;
3. setup Python estable;
4. instalar paquete/test deps;
5. correr tests;
6. correr smoke experiment;
7. validar output;
8. subir artifact;
9. usar permisos mínimos;
10. no usar secrets.

## Explicitly do NOT do in M0

- market APIs;
- tickers;
- data ingestion real;
- backtesting financiero;
- ML;
- NLP/news ingestion;
- portfolio optimization;
- Tournament Brain;
- frontend;
- agent framework;
- automatic Actinver order submission;
- heavy dependencies sin necesidad.

## Definition of done

M0 solo pasa si:
- package instala limpio;
- tests pasan;
- smoke output es deterministic;
- workflow real en GitHub pasa;
- artifact se puede inspeccionar;
- resultado es machine-readable;
- docs explican trigger/inspection;
- no hubo scope creep.

Si algo no puede verificarse, reporta FAIL/BLOCKED, no asumas PASS.

No avances automáticamente a M1.

## M0 Step 2 — Local Python scaffold

The local scaffold and Foundation workflow are implemented. Actual GitHub
execution/artifact inspection and the M0 closure report remain Steps 4 and 5.

From the repository root, using Python 3.12 (the CI version):

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install .
python -m pip check
python -m unittest discover -s tests -v
actinver-m0 smoke --spec experiments/specs/HARNESS_SMOKE_001.json --output-dir experiments/results/m0/local-001 --run-id development-only-local-001
actinver-m0 verify --spec experiments/specs/HARNESS_SMOKE_001.json --output-dir experiments/results/m0/local-001 --commit-sha "$(git rev-parse HEAD)"
actinver-m0 record --output-dir experiments/results/m0/local-001 --ledger experiments/results/m0/local-ledger.jsonl
```

Use a new output directory for each execution. Existing bundles are never
overwritten. The installation is non-editable: reinstall after source changes.
Runtime and test dependencies are empty; `setuptools>=61` is build-only tooling
for PEP 621 metadata. No pip or exact build-tool version is pinned; CI selects
Python 3.12.

### Contracts and reproducibility

`ExperimentSpec` retains the architecture field names. Its active M0 fields are
schema version, ID, hypothesis, synthetic dataset version, parameters, benchmark,
seed and optional full commit SHA. Financial fields are null/empty and may not be
populated by M0. The versioned input has a null commit; the resolved spec records
the observed or explicitly supplied commit. Unknown fields and invalid types,
including booleans in integer fields, are rejected.

For `i = 0..sample_count-1`, the smoke computes:

```text
value[i] = (seed + (i + 1)^2) modulo modulus
seed=42, sample_count=8, modulus=101
values=[43,46,51,58,67,78,91,5]; sum=439
```

The benchmark vector is preregistered in the versioned spec. No RNG is used.
A reference mismatch is a technical FAIL. Scientific state fields remain null;
this smoke neither promotes nor rejects financial research.

Each bundle contains:

- `resolved_spec.json`: validated spec including commit identity when available.
- `payload.json`: canonical, deterministic `ExperimentResult` payload.
- `result.json`: an envelope containing `payload` and separate `execution` metadata.
- `ledger.jsonl`: a complete record of this execution, including technical FAILs.

Canonical JSON is UTF-8, uses sorted string keys and compact separators, and
ends with exactly one newline. NaN, Infinity, overflowing float literals and
duplicate object keys are rejected. The deterministic payload excludes commit,
Python/package versions, timestamp, run ID and working-tree state.

`config_sha256` hashes the complete, default-resolved canonical spec excluding
only `commit_sha`; key order and formatting do not affect it. `code_sha256`
hashes the canonical map of SHA-256 digests for the five installed package source
files. This identifies code even before a local commit is created. With identical
code/config/seed, `payload.json` is byte-for-byte identical across executions;
the complete envelope is not expected to be identical.

The verifier compares the bundle with a trusted input spec, checks identities,
recomputes the deterministic payload using the installed code, and requires PASS.
Use `--commit-sha <full-sha>` to check an independently known expected commit.
When running smoke outside a Git checkout, use that same option to supply commit
provenance; otherwise the commit may be null. Explicitly supplied commits are
declarations, not independently authenticated Git provenance. Automatic Git
discovery records whether the working tree is dirty; it does not claim that
uncommitted source is contained in the recorded base commit.

Exit codes: smoke PASS = 0; smoke reference/determinism FAIL = 1; invalid input or
verification error = 2. A valid FAIL still produces a bundle and local ledger.
The `record` command appends either PASS or FAIL and returns zero when the append
succeeds; it never changes the experiment's status. Invalid input does not
fabricate an experiment result.

### Ledger boundary

The JSONL ledger stores full spec/result snapshots and a payload digest. Appends
preserve prior bytes and refuse a truncated last line. Each execution writes its
own local ledger; `record` explicitly adds reviewed bundles to the permanent
`research/ledger.jsonl`. No database, synchronization, deduplication or automatic
Git write is implemented. Use one writer per ledger; repeated recording appends
another observation. Artifacts are not required for this local Step 2 proof.

For the Step 2 clean-commit checkpoint, distinguish record purpose from technical
PASS/FAIL. The permanent ledger's first record is the retained development-only
PASS baseline (`working_tree_dirty=true`); its second is controlled negative
validation (`run_id=step2-controlled-reference-mismatch`). Keep both snapshots
unchanged, including the negative evidence. Do not append routine development
runs to the permanent ledger.

Canonical harness executions use `canonical-harness-*` run IDs and require an
observed clean committed checkout. Let smoke discover Git HEAD and working-tree
state together, then pass the independently collected full SHA to `verify`.
Their per-execution ledgers live in ignored result bundles; they are not
automatically copied to the permanent ledger. This keeps the source checkout
clean while preserving canonical evidence separately from development history.

## M0 Step 3 — GitHub Actions Foundation path

`.github/workflows/test.yml` defines **M0 Foundation**. It supports manual
`workflow_dispatch`, pushes to `main` and pull requests targeting `main`.
One job uses Ubuntu 24.04, Python 3.12 and only `contents: read`; no configured
secrets are needed. The three external Actions are pinned to verified full
commit SHAs, with their release versions beside each reference.

The job checks out `github.sha`, checks that it equals `git rev-parse HEAD`,
installs with `python -m pip install .`, runs `pip check` and the complete
`unittest` suite, then runs smoke and verify. Smoke discovers the actual Git
HEAD and working-tree state; verify independently checks that HEAD. Its
`canonical-harness-<run_id>-<run_attempt>` execution ID stays outside the
deterministic payload. CI writes only the execution's local ledger and does
not append to the permanent research ledger.

### Manual execution and artifact inspection (Step 4)

The approved workflow must first be published to the default branch, `main`,
for GitHub's manual **Run workflow** control to be available. Step 3 does not
merge the implementation or trigger a remote run.

When that prerequisite is met:

1. Open the repository on GitHub, then **Actions → M0 Foundation**.
2. Choose **Run workflow**, select `main`, then confirm the run.
3. Open the run and inspect the `foundation` job and its step logs.
4. In the run's **Artifacts** section, download
   `m0-foundation-<run_id>-<run_attempt>` (retention: 30 days).

For a successful run, the downloaded archive contains exactly:

```text
bundle/
  resolved_spec.json
  payload.json
  result.json
  ledger.jsonl
logs/
  checkout-sha.log
  install.log
  pip-check.log
  tests.log
  smoke.log
  verifier.log
```

The upload step uses `always()`. A failing command fails the job even when its
logs or result bundle can be uploaded; Bash `pipefail` prevents `tee` from
hiding command failures. Subsequent execution steps are skipped after a
failure. If failure occurs before smoke, the artifact contains the available
diagnostic logs without a fabricated experiment result. Checkout/platform
failures may prevent any artifact from being produced. If no artifact files
are available, the upload step fails.

**PASS** requires a successful job, smoke payload `status=PASS`, a successful
verifier and an uploaded artifact. Smoke PASS alone does not establish workflow
PASS. Inspect the result's commit against `checkout-sha.log`, its seed/config
and the separate execution metadata; a clean runner should record
`working_tree_dirty=false`. To verify a downloaded bundle with the matching
commit installed, use:

```sh
actinver-m0 verify --spec experiments/specs/HARNESS_SMOKE_001.json --output-dir /path/to/download/bundle --commit-sha <full-checkout-sha>
```

**FAIL** means the execution path or technical harness check failed; preserve
its available logs and PASS/FAIL result snapshots for diagnosis. It is not a
scientific promotion/rejection decision. A cancelled or incomplete run does
not establish PASS. A remote PASS has not been verified in Step 3.

`morning.yml.disabled`, `nightly.yml.disabled` and `research.yml.disabled`
retain their placeholder contents. GitHub ignores them because they no longer
end in `.yml`/`.yaml`; no scheduling or future functionality is implemented.
