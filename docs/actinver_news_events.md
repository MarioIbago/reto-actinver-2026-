# M6 — News and Event Engine

## Purpose and boundary

M6 turns a licensed, timestamped source revision into versioned event features, then labels and evaluates those features in separate deterministic steps. The repository does not fetch news or call an LLM. `actinver-news` accepts source records and separately supplied structured extractions, so a provider/model adapter can be added only after its license and provenance contract are known.

An extraction receives only the document metadata, title, body, and text fingerprint. The extraction schema rejects return/price fields. Event snapshots preserve source publication, revision, ingestion, extraction completion, feature availability, model, prompt hash, and source text hash. A normalized document or event snapshot is rejected if its content fingerprint is inconsistent.

The taxonomy and exact-match entity resolver are implemented in [`src/actinver/news_events.py`](../src/actinver/news_events.py). Unrecognized names remain `UNMAPPED`; issuer aliases that refer to several guide instruments remain issuer-level; ambiguous matches are never guessed. The M1 simulator mapping flag stays false until verified against the authenticated platform.

## Data and permissions

Raw articles are not copied into the repository. Store only permitted data in an approved external dataset location, retain its source license/terms and capture manifest, and record whether redistribution is permitted, restricted, or unknown. Do not send restricted article text to an extraction provider unless its contract permits that use.

The current repository has no authorized historical news corpus, OHLCV history, or verified Actinver symbol/series mapping. The committed tests use synthetic fixtures and demonstrate software behavior only. They do not establish event-extraction accuracy, incremental predictive value, or tradability.

## Contracts

- `schemas/news_document.schema.json`: one raw article revision with source/publication/ingestion timestamps.
- `schemas/news_extraction.schema.json`: strict model-output shape; future return/price fields are not allowed.
- `schemas/news_event_snapshot.schema.json`: structured events bound to one article content hash, extraction version, model, and prompt hash.
- `schemas/news_forward_return_label.schema.json`: explicit PIT label cutoff and entry/exit M2 record revisions.
- `schemas/news_evaluation_case.schema.json` and `schemas/news_evaluation_result.schema.json`: temporal OOS evaluation input and metrics.
- [`prompts/M6_EVENT_EXTRACTION_V1.md`](../prompts/M6_EVENT_EXTRACTION_V1.md): source-only extraction instructions and strict output shape.

All source, feature, price, and label cutoffs are timezone-aware. The event engine canonicalizes its own timestamps to fixed-width UTC strings and compares timestamps as instants. The M2 engine compares source-availability/ingestion timestamps as instants when selecting revisions, including sub-second boundaries.

## Local command workflow

Install the package in the active environment with `python -m pip install -e .`. Commands accept UTF-8 JSON and write JSON to stdout by default; pass `--output path.json` to save it.

1. Normalize raw revisions from an array or `{"documents": [...]}` file:

   ```powershell
   actinver-news normalize --input news_raw.json --output news_normalized.json
   ```

2. Reconstruct documents available at a source or system cutoff, then prepare article-only extraction payloads:

   ```powershell
   actinver-news documents-as-of --input news_normalized.json --as-of 2026-10-05T14:00:00Z --mode system
   actinver-news prepare-extraction --input news_normalized.json --as-of 2026-10-05T14:00:00Z --mode system --output extraction_queue.json
   ```

3. Run a separately approved extractor using the prompt and the extraction queue. Keep its outputs in a distinct file. Bind each output to its exact normalized source revision:

   ```powershell
   actinver-news create-snapshot --document article.json --extraction extraction.json --universe data/metadata/actinver_universe_2026_v1.json --extraction-version events-v1 --model provider/model-id --prompt-sha256 PROMPT_SHA256 --completed-at 2026-10-05T14:01:00Z --ingestion-time 2026-10-05T14:01:05Z --output event_snapshot.json
   ```

   Replace the model, timestamps, and prompt digest with recorded values. No model invocation or credential handling occurs in this command.

4. Query event snapshots, build a local-time digest, or poll a breaking-event cursor:

   ```powershell
   actinver-news events-as-of --input snapshots.json --as-of 2026-10-05T15:00:00Z --mode system
   actinver-news digest --input snapshots.json --window-start 2026-10-04T12:00:00Z --as-of 2026-10-05T15:00:00Z --timezone America/Mexico_City --mode system
   actinver-news watch --input snapshots.json --after-time 2026-10-05T14:00:00Z --as-of 2026-10-05T15:00:00Z --timezone America/Mexico_City --minimum-materiality 0.5 --mode system
   ```

   Digests and alerts are informational; they do not emit BUY/SELL instructions or operate the Actinver portal.

5. Label after-features close-to-close outcomes separately, using one explicit data revision cutoff:

   ```powershell
   actinver-news label-forward-returns --snapshots snapshots.json --prices data/processed/prices.json --price-dataset-id DATASET_ID_FROM_M2_MANIFEST --horizon-sessions 3 --label-as-of 2026-10-20T23:59:59Z --mode system --output event_labels.json
   ```

   `--label-as-of` controls which source/system price revisions the M2 point-in-time engine selects. `--price-dataset-id` binds labels to the M2 manifest version. The output includes a content-derived `label_id`, source and revision record IDs, cutoff, entry/exit closes, and label availability. It is a gross close-to-close outcome, not a simulated fill; costs, corporate actions, and Actinver execution are not modeled. Ambiguous multi-source or duplicate-session price coverage fails closed.

6. Evaluate externally generated out-of-sample probabilities using chronological train/validation/test periods:

   ```powershell
   actinver-news evaluate --input evaluation_case.json --output evaluation_result.json
   ```

   Every observation records feature and prediction availability, decision time, label availability, and `label_id`. Features or predictions after the decision, labels crossing a split boundary, overlapping event groups across splits, non-chronological periods, or a test-selection attestation fail validation. The unconditional reference probability is computed only from training labels and is held fixed for validation and test. Test results are still descriptive; input attestations do not prove that an analyst actually kept a holdout untouched.

## Scheduled intelligence specifications

[`config/news_schedules.yaml`](../config/news_schedules.yaml) specifies overnight news, macro/FX/commodities, earnings/guidance, issuer and official notices, morning and overnight digests, and material-event polling. Every task is disabled, and the schedule has `scheduler_enabled: false`, until licensed source connectors, provenance fields, and a runner are configured. Wall-clock times use the explicit `America/Mexico_City` IANA timezone, are configurable, and do not promise market-session alignment or low-latency monitoring. This file does not create app automations or run a collector.

## Validation and phase gate

Run the local suite with `python -m unittest discover -s tests -v`; run syntax compilation with `python -m compileall -q src tests`; inspect the change with `git diff --check`.

The software gate covers PIT source and event revisions, exact duplicate handling, URL and content-hash validation, entity ambiguity, extraction-field isolation, scheduled-task contracts, stable alert cursors, M2-based labels, training-only baselines, temporal split checks, and CLI read/write paths.

The scientific M6 gate remains unverified until authorized historical news and prices are available, point-in-time entity mappings are verified, extraction quality is evaluated against a human-labeled sample, and event probabilities are evaluated with preregistered OOS splits and realistic costs. The software status must not be represented as an alpha result or financial promotion.
