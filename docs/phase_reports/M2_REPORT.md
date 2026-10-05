# M2 Phase Report — Point-in-Time Data Engine

## Scope and outcome

M2 implements a provider-agnostic point-in-time ingestion, provenance, query,
and stale-price validation layer. No investment signals, execution model, or
later-phase modules were added. The synthetic rows used in tests are clearly
identified as fixtures and make no claim about market performance.

## Files changed

- `.gitignore` — keep raw/interim/processed market rows local by default.
- `pyproject.toml` — expose the `actinver-data` command.
- `src/actinver/data_engine.py` — record normalization, immutable snapshots,
  manifests, integrity verification, point-in-time queries, and price freshness
  checks.
- `src/actinver/data_cli.py` — `ingest`, `verify`, and `query` commands.
- `schemas/pit_data_record.schema.json` — normalized record contract.
- `tests/test_data_engine.py` — temporal, integrity, schema, deduplication,
  coverage, and CLI regression tests using synthetic data.
- `data/README.md`, `docs/data_engine.md` — usage, data-rights, and contract
  documentation.

## Evidence and verification

The targeted M2 suite passed after a red-team review found and fixed a stale
price check that had considered every historical bar instead of each
instrument's newest bar:

- `python -m unittest tests.test_data_engine -v` — PASS; 18 tests.
- Cases include missing required fields, unknown fields, timezone rejection,
  exact decimal handling, duplicate and conflicting revisions, monotone
  normalized output ordering, source/system as-of differences, future and
  unpublished information, latest-bar freshness, expected-instrument coverage,
  raw-byte preservation, immutable artifacts, manifest path containment,
  SHA-256 tampering, raw-to-processed reconciliation, duplicate-count
  verification, and CLI ingest/verify/query round trips.
- `python -m unittest discover -s tests -v` — PASS; 61 tests across M0/M1/M2.
- `python -m compileall -q src scripts tests` — PASS.
- `python -m pip install -e .` — PASS; editable package installation exposes
  `actinver-data`.
- `actinver-data --help` and `actinver-data query --help` — PASS.
- `python -m pip check` — PASS.
- `actinver-m1 audit` — PASS; all 207 guide records and source fingerprints.
- `git diff --check` — PASS (only Git's Windows LF/CRLF conversion notices).

Remote CI remains to be run on the implementation PR.

## Data rights and evidence gap

The [official BMV database catalog](https://www.bmv.com.mx/es/Grupo_BMV/Bases_de_datos)
lists daily closing-price products for the local market, SIC, and funds and
directs requests for historical/custom data to sales. BMV's [2026 price
list](https://www.bmv.com.mx/work/models/Grupo_BMV/Resource/1192/10/images/LISTA%20DE%20PRECIOS%20BASES%20DE%20DATOS%202026.pdf)
lists annual charges for those products. Its [distribution
policy](https://www.bmv.com.mx/work/models/Grupo_BMV/Resource/1999/31/images/Politicas_de_Distribucion_de_Informacion_2025.pdf)
describes licensing for internal/external data-feed use and paid end-of-day
information. This task did not purchase or subscribe to a dataset. No external
provider rows were scraped or added.

## Limitations

- There is no real historical OHLCV or trade dataset in the repository, so
  software fixtures cannot establish real-data coverage, actual source
  availability times, or absence of all data leakage.
- No provider-specific adapter is included; field mappings and rights must be
  verified for the chosen export.
- Freshness thresholds are caller-supplied and must be versioned with later
  research configs. The helper checks newest-bar age and can require coverage
  for an expected instrument set; it does not infer the official platform
  symbols that remain unresolved in M1.
- Prices remain unadjusted; corporate actions are preserved separately.
- The repository does not contain an authorized BMV/SIC/fund historical export.

## Gate status

**OPEN — BLOCKERS REMAIN.** The M2 engine's software contracts pass targeted
tests, but the written exit criterion requires a historical dataset that can
be reconstructed by version and timestamp. No licensed/authorized market
history was available to ingest, so that criterion is not yet demonstrated.
`prompts/CURRENT_PHASE.md` remains M2.

## Exact next step

Ingest a licensed BMV/SIC/fund historical export or an otherwise authorized
provider dataset, preserving its source file locally. Run `actinver-data
verify`, query an explicit historical cutoff in both `source` and `system`
modes, select and version a freshness threshold based on the provider cadence
and intended session, check expected instrument coverage, then record the
dataset ID and evidence here. Do not commit its raw or derived rows unless the
data rights permit it.
