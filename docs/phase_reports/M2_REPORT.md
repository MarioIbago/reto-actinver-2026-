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
- Follow-up: `.gitignore`, `README.md`, `docs/CODEX_START_HERE.md`,
  `scripts/build_bmv_calendar_dataset.py`, and `tests/test_bmv_calendar_data.py`
  add a reproducible source-backed calendar-event dataset while keeping its
  generated rows and manifest local.

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
- GitHub Actions [run 37291455075](https://github.com/MarioIbago/reto-actinver-2026-/actions/runs/37291455075)
  on PR #10 / commit `1339febd03cf213dff85182b622aac2c3ac24c74` — PASS;
  package install, complete 61-test suite, deterministic M0 smoke, result
  verification, and artifact upload all succeeded.
- CI artifact `m0-foundation-37291455075-1`, ID `11336501576`, SHA-256
  `54720f76bda8902b0e66cefe0e788cb14e3c289e0b77a6ac13e70080a322c86b`.
- PR #10 merged to `main` as `a94aa8a2302f3ae8b270bf19989aa494ab549c16`.

The CI artifact confirms the software/runner path only; it does not contain
licensed market history and does not close the M2 data gate.

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

## Initial gate status before the calendar dataset

**OPEN — BLOCKERS REMAIN.** The M2 engine's software contracts pass targeted
tests, but the written exit criterion requires a historical dataset that can
be reconstructed by version and timestamp. No licensed/authorized market
history was available to ingest, so that criterion is not yet demonstrated.
`prompts/CURRENT_PHASE.md` remains M2.

## Initial next step before the calendar dataset

Ingest a licensed BMV/SIC/fund historical export or an otherwise authorized
provider dataset, preserving its source file locally. Run `actinver-data
verify`, query an explicit historical cutoff in both `source` and `system`
modes, select and version a freshness threshold based on the provider cadence
and intended session, check expected instrument coverage, then record the
dataset ID and evidence here. Do not commit its raw or derived rows unless the
data rights permit it.

## Supplemental reproducible BMV calendar dataset — 2026-10-05

The original official HTML capture is preserved at
`research/source_material/bmv_2026_holidays_official.html`; its canonical-LF
SHA-256 is `7702be0373cd46f46a3c273b5dcf02285e94206a44e073f9a8a7cf7ff8eee164`.
The M2 builder verifies that fingerprint and creates 11 date-precision
`calendar_event` records. Event time is local midnight in the versioned
`America/Mexico_City` timezone; this is an explicit representation convention
for date-only events, not an observed intraday event time. Source
`available_time` is the capture timestamp `2026-10-05T08:15:08Z`, the earliest
availability evidenced by the repository. The source's actual first-publication
time is unknown. System `ingestion_time` was `2026-10-05T10:14:04Z`.

The reproducible local build used:

```powershell
python scripts/build_bmv_calendar_dataset.py `
  --ingestion-time 2026-10-05T10:14:04Z `
  --code-commit-sha 00e1f1e10c0b1dea24e9b34918aa5a1c2f11c3b0
```

Dataset ID: `actinver-pit-v1-347fa83b3804ea2bff4ac9d125686df5b05cfc3f3d84ba72e663d06883c952bd`.
Raw normalized-input SHA-256:
`9bb466eef506424cbd9d9ef138b9133e39474aa79157b20a04895749edadfc55`.
The local manifest is at
`data/metadata/datasets/actinver-pit-v1-347fa83b3804ea2bff4ac9d125686df5b05cfc3f3d84ba72e663d06883c952bd.json`
and has SHA-256
`5527f7c7050fb046389b882f8aea6e2ce7274f154e31edf75113209a0ce734be`.
Data rows and manifests are gitignored because BMV redistribution rights are
not established; the manifest records `redistribution_status: unknown`.

PIT evidence from `actinver-data verify` and `actinver-data query`:

| Query | Count | Result |
|---|---:|---|
| `source` at `2026-10-05T08:15:07Z` | 0 | Nothing returned before the preserved capture. |
| `source` at `2026-10-05T08:15:08Z` | 11 | All captured calendar rows became source-visible. |
| `system` at `2026-10-05T10:14:03Z` | 0 | Nothing returned before system ingestion. |
| `system` at `2026-10-05T10:14:04Z` | 11 | All rows became system-visible at ingestion. |
| `system` at `2026-10-05T10:35:00-06:00` | 11 | The known future 2026-11-02 closure remains visible. |

The 2026-11-02 closure row has event date `2026-11-02`, local-midnight event
time normalized to `2026-11-02T06:00:00Z`, source availability
`2026-10-05T08:15:08Z`, and system ingestion
`2026-10-05T10:14:04Z`. Its date precision and unknown original publication
time are explicit in its payload.

Verification after merging PR #12:

- PR #12, `feat(m2): add reproducible BMV calendar PIT dataset`, merged as
  `00e1f1e10c0b1dea24e9b34918aa5a1c2f11c3b0`.
- PR CI run [#119](https://github.com/MarioIbago/reto-actinver-2026-/actions/runs/37294997301)
  — PASS. Artifact `11338146704` is the workflow's M0 smoke artifact; it does
  not contain the local BMV data.
- Main CI run [#120](https://github.com/MarioIbago/reto-actinver-2026-/actions/runs/37295133332)
  — PASS on the merge commit.
- `python -m unittest discover -s tests -v` — PASS; 63 tests.
- `python -m compileall -q src scripts tests` — PASS.
- `python -m pip check` — PASS.
- `actinver-m1 audit` — PASS; 207 guide records and source fingerprints.
- `actinver-data verify --manifest <local manifest>` — PASS; 11 records and
  snapshot reconciliation.
- PIT queries at the source, ingestion and competition cutoffs — PASS; counts
  and future-known calendar behavior match the table above.
- `git diff --check` — PASS.

## Final gate reassessment

The written M2 exit criterion is that a historical dataset be reconstructable
by version and timestamp without known leakage. The source-backed, versioned
2026 BMV calendar now meets that criterion: the original capture, revision,
availability cutoff, ingestion cutoff, immutable raw/interim/processed
snapshots, manifest, integrity verification, and source/system as-of queries
are linked by hashes and a full code commit.

**M2 status: PASS — READY FOR HUMAN REVIEW.** The scope of this pass is the
actual BMV calendar-event dataset and the generic M2 data-engine contracts. It
does not certify historical price, volume, trades, or corporate-action data.
No OHLCV has been ingested, and the exact simulator symbol mapping remains
unverified. M4 cannot make financial backtest claims until authorized price
history and usable instrument identifiers exist. Data rights remain unknown;
local derived rows and manifest are not included in Git.

The user explicitly directed continuation through all phases and waived human
approval stops. `prompts/CURRENT_PHASE.md` therefore advances to M3 only after
this report records the M2 gate evidence. M3 can validate deterministic
execution mechanics with synthetic cases; real-practice fill comparisons are
unavailable in the repository.

## Exact next step

Implement M3's deterministic order-to-ledger simulator using only versioned
Actinver rules and explicit unknowns. Keep real simulator behavior, market
trades, and price history unclaimed unless a source or practice export is
available. Preserve manual-only Actinver order entry.
