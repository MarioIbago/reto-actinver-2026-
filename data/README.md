# Data layers (M2)

The data engine keeps source bytes and derived records separate:

- `data/raw/` stores content-addressed source files exactly as received.
- `data/interim/` stores normalized, deduplicated, revision-preserving JSONL.
- `data/processed/` stores deterministic query-ready ordering of those records.
- `data/metadata/datasets/` stores manifests with source/license provenance, hashes, schema and code version.

The first three directories are ignored by Git because market data may be licensed,
private, or non-redistributable. The manifest is safe to retain only when the
source terms allow its provenance metadata to be shared. Never commit provider
data or derived rows unless the applicable license permits it.

Each record distinguishes:

- `event_time`: when the market event or observation occurred;
- `available_time`: when the source made this value public;
- `ingestion_time`: when this project captured the value.

`actinver-data query --mode source` reconstructs source-public knowledge.
`--mode system` additionally requires the project to have ingested the record by
the cutoff. Known future calendar/news events may be returned if already public;
future price bars are always excluded. Price bars remain unadjusted. Corporate
actions are separate records and no price adjustment is applied implicitly.

Inputs must be normalized JSONL or CSV using the schema in
`schemas/pit_data_record.schema.json`. Vendor-specific adapters must be added
only after the provider format and data rights are verified. BMV historical
market data is not bundled in this repository.

For a price-aware query, pass `--max-price-age-seconds` to make the CLI fail
closed if the newest bar for any returned instrument is stale. Repeat
`--expected-instrument <instrument_id>` for every required instrument to fail on
missing price coverage. Choose and version the age threshold for the intended
market/session; the engine does not guess it. The age check uses each
instrument's newest event time, not every historical bar in the dataset.

Example with a licensed, locally held normalized file:

```powershell
actinver-data ingest `
  --input C:\licensed-data\provider.jsonl `
  --source-id vendor_daily `
  --publisher "Provider name" `
  --license-id "contract-reference" `
  --redistribution-status restricted `
  --ingestion-time 2026-10-05T22:00:00Z `
  --code-commit-sha <full-git-sha>

actinver-data verify --manifest data/metadata/datasets/<dataset-id>.json
actinver-data query `
  --manifest data/metadata/datasets/<dataset-id>.json `
  --as-of 2026-10-05T21:35:00Z `
  --mode system `
  --max-price-age-seconds 86400 `
  --expected-instrument MX:AC
```

The filename under `data/raw/` is its byte-level SHA-256. Do not place tokens,
credentials, signed URLs, or secrets in source metadata. Query strings are
rejected from provenance URLs. `redistribution_status` is descriptive metadata,
not a license grant; the user's agreement remains authoritative.
