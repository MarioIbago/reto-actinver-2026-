# M2 — Point-in-Time Data Engine

## Contract

The engine ingests normalized JSONL or CSV observations while preserving the
source bytes. The canonical field contract is defined in
`schemas/pit_data_record.schema.json`; timestamps must include a timezone and
are written in UTC. Prices and quantities are exact decimal strings or
integers. Binary floating-point input is rejected.

CSV input must use this exact header order:

```text
record_id,instrument_id,record_type,event_time,available_time,ingestion_time,source_revision,provider_symbol,payload_json
```

`payload_json` contains one JSON object. The `source_id` is provided once to
`actinver-data ingest` and applied to rows that omit it. Empty CSV
`ingestion_time` cells use the explicit ingestion timestamp supplied to the
command; source event and availability times are never inferred.

Required provenance fields:

- `event_time`: when the market event or observation happened;
- `available_time`: when the source first made that version available;
- `ingestion_time`: when this system captured it;
- `source_id` and `source_revision`;
- stable `record_id` and canonical `instrument_id`;
- a typed `payload`.

`provider_symbol` is retained separately from `instrument_id`; it must not be
treated as an Actinver simulator symbol. The exact simulator mapping remains
unverified under M1.

## Repeatable processing

`actinver-data ingest` stores the original file under `data/raw/` by content
hash, normalizes and deduplicates rows into `data/interim/`, writes a stable
processed ordering under `data/processed/`, and records source/license
metadata, file hashes, record counts, timestamp ranges, and the full Git SHA
in a dataset manifest. A previously written artifact cannot be silently
replaced. Raw and derived rows are ignored by Git by default because provider
terms may prohibit redistribution.

Manifest verification checks the hashes and sizes, rebuilds normalized rows
from the preserved raw source, compares them with both derived snapshots, and
reconciles the dataset ID and record summary with build provenance.

Deduplication is scoped to `(source_id, record_id, source_revision,
available_time)`. Identical duplicates keep the earliest ingestion time;
conflicting values are rejected. Two materially different revisions with the
same source-availability timestamp are also rejected because the engine could
not reconstruct their publication order.

Price bars are unadjusted. Corporate actions are preserved as separate
records, and the engine does not silently back-adjust a price series. OHLCV
records require positive prices, non-negative volume, consistent high/low
bounds, and an availability time no earlier than the bar event. Trades also
cannot be available before their event. Calendar and other event records may
describe the future if the source had already published them.

## As-of queries and stale prices

`actinver-data query --mode source` answers from the source's publication
history. `--mode system` additionally requires that ingestion had occurred by
the cutoff. Both modes exclude future price bars and retain future known
calendar or event observations. Query revision selection uses source
availability time, never file order or a guessed revision number.

An ordinary as-of query returns all known observations. For trading inputs,
also pass `--max-price-age-seconds`; the CLI then fails closed if an
instrument's latest bar is stale. Repeat `--expected-instrument` to require
price coverage for a known instrument set. This check applies to the most
recent bar per instrument, not every older bar. The caller must select an
age threshold that matches the market, bar interval, session, and strategy;
there is no universal safe default.

## Data rights and current evidence

No historical OHLCV or trade rows are bundled. The official BMV holiday calendar is captured and normalized by `scripts/build_bmv_calendar_dataset.py`; this produces 11 date-precision `calendar_event` records from the M1 ruleset and preserves the source capture SHA in each record. The source capture timestamp is used as the earliest evidenced availability time; it is not asserted to be the calendar's original publication time. The dataset builder records redistribution terms as unknown and writes outputs under ignored local data paths. Rebuild with a fixed `--ingestion-time` and the same code commit to reproduce the dataset ID. For example:

```powershell
$ingestionTime = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$codeCommitSha = (git rev-parse HEAD).Trim()
python scripts/build_bmv_calendar_dataset.py --ingestion-time $ingestionTime --code-commit-sha $codeCommitSha
```

The first command records an actual ingestion timestamp. For an exact rebuild, pass the original timestamp and code SHA stored in the phase report.

The 2026-11-02 closure should be visible in a 2026-10-05 10:35 Mexico City query because the source capture precedes that cutoff. A query before the capture time must return no calendar rows, and `system` mode must also wait until the explicit ingestion time. This validates calendar-event availability only; it is not a price feed or backtest dataset.

The [BMV database catalog](https://www.bmv.com.mx/es/Grupo_BMV/Bases_de_datos)
lists closing-price products for the local market, SIC, and investment funds,
and says historical/custom data must be requested from sales. The BMV's
[2026 market-data price list](https://www.bmv.com.mx/work/models/Grupo_BMV/Resource/1192/10/images/LISTA%20DE%20PRECIOS%20BASES%20DE%20DATOS%202026.pdf)
lists annual fees for daily closing-price products. Its [information
distribution policy](https://www.bmv.com.mx/work/models/Grupo_BMV/Resource/1999/31/images/Politicas_de_Distribucion_de_Informacion_2025.pdf)
describes licensing and fees for internal/external use of its data feed,
including end-of-day information. No subscription or data purchase was made.

Do not infer that a publicly viewable page grants a right to scrape, store,
backtest, or redistribute the underlying rows. [Yahoo Finance's own help
page](https://uk.help.yahoo.com/kb/exchanges-data-providers-yahoo-finance-sln2310.html)
states that its information must not be redistributed; it is therefore not
used as a substitute source here. The engine can record restricted or unknown
rights for local provenance, but that field does not create a license.

## Phase status

The ingestion, manifest, as-of query, and freshness contracts are implemented
and covered with explicitly synthetic test fixtures. The official BMV holiday
calendar also has a reproducible point-in-time dataset. Neither source provides
historical OHLCV for contest instruments. No price backtest or financial
validation is supported until authorized price history and the unresolved M1
platform-symbol mapping are supplied.
