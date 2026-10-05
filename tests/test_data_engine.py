import contextlib
import csv
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from actinver.data_cli import main as data_cli_main
from actinver.data_engine import (
    DataEngineError,
    build_dataset,
    normalize_record,
    normalize_records,
    query_as_of,
    read_dataset,
    require_fresh_price_bars,
    verify_manifest,
)


BASE_TIME = "2026-10-05T15:00:00Z"
COMMIT_SHA = "a" * 40
ROOT = Path(__file__).resolve().parents[1]


def price_bar(
    *,
    record_id="bar-1",
    event_time=BASE_TIME,
    available_time="2026-10-05T15:01:00Z",
    ingestion_time="2026-10-05T15:02:00Z",
    close="100.25",
):
    return {
        "record_id": record_id,
        "instrument_id": "MX-TEST-1",
        "record_type": "price_bar",
        "event_time": event_time,
        "available_time": available_time,
        "ingestion_time": ingestion_time,
        "source_id": "fixture",
        "source_revision": "1",
        "payload": {
            "open": "99.00",
            "high": "101.00",
            "low": "98.50",
            "close": close,
            "volume": 1000,
        },
    }


def source_row():
    return price_bar()


class DataEngineNormalizationTests(unittest.TestCase):
    def test_canonical_record_shape_matches_the_checked_in_schema(self):
        schema = json.loads(
            (ROOT / "schemas/pit_data_record.schema.json").read_text(encoding="utf-8")
        )
        normalized = normalize_record(source_row())
        self.assertTrue(set(schema["required"]).issubset(normalized))
        self.assertFalse(set(normalized) - set(schema["properties"]))
        self.assertEqual(schema["additionalProperties"], False)
        self.assertEqual(
            normalized["schema_version"],
            schema["properties"]["schema_version"]["const"],
        )

    def test_normalizes_zoned_timestamps_to_utc_and_preserves_exact_prices(self):
        row = source_row()
        row["event_time"] = "2026-10-05T10:00:00-05:00"
        row["available_time"] = "2026-10-05T10:01:00-05:00"
        row["ingestion_time"] = "2026-10-05T10:02:00-05:00"
        normalized = normalize_record(row)
        self.assertEqual(normalized["event_time"], "2026-10-05T15:00:00Z")
        self.assertEqual(normalized["payload"]["close"], "100.25")
        self.assertEqual(normalized["payload"]["volume"], 1000)

    def test_rejects_missing_fields_unknown_fields_and_non_string_keys(self):
        row = source_row()
        del row["available_time"]
        with self.assertRaisesRegex(DataEngineError, "Missing required"):
            normalize_record(row)
        row = source_row()
        row["unexpected"] = "value"
        with self.assertRaisesRegex(DataEngineError, "Unknown record fields"):
            normalize_record(row)
        row = source_row()
        row[1] = "bad-key"
        with self.assertRaisesRegex(DataEngineError, "field names must be strings"):
            normalize_record(row)

    def test_rejects_naive_time_binary_float_and_boolean_schema_version(self):
        row = source_row()
        row["event_time"] = "2026-10-05T10:00:00"
        with self.assertRaisesRegex(DataEngineError, "include a UTC offset"):
            normalize_record(row)
        row = source_row()
        row["payload"]["close"] = 100.25
        with self.assertRaisesRegex(DataEngineError, "binary float"):
            normalize_record(row)
        row = source_row()
        row["schema_version"] = True
        with self.assertRaisesRegex(DataEngineError, "schema_version"):
            normalize_record(row)

    def test_rejects_invalid_ohlcv_and_impossible_availability(self):
        row = source_row()
        row["payload"]["high"] = "97"
        with self.assertRaisesRegex(DataEngineError, "high must be at least"):
            normalize_record(row)
        row = source_row()
        row["available_time"] = "2026-10-05T14:59:00Z"
        with self.assertRaisesRegex(DataEngineError, "cannot precede bar event_time"):
            normalize_record(row)
        trade = {
            "record_id": "trade-1",
            "instrument_id": "MX-TEST-1",
            "record_type": "market_trade",
            "event_time": "2026-10-05T15:00:00Z",
            "available_time": "2026-10-05T14:59:59Z",
            "source_revision": "1",
            "payload": {"price": "100", "quantity": "1"},
        }
        with self.assertRaisesRegex(DataEngineError, "cannot precede trade event_time"):
            normalize_record(
                trade,
                default_source_id="fixture",
                default_ingestion_time="2026-10-05T15:01:00Z",
            )

    def test_deduplicates_identical_rows_and_rejects_conflicting_duplicates(self):
        first = source_row()
        duplicate = dict(first, ingestion_time="2026-10-05T15:03:00Z")
        rows, duplicate_count = normalize_records([first, duplicate])
        self.assertEqual(len(rows), 1)
        self.assertEqual(duplicate_count, 1)
        self.assertEqual(rows[0]["ingestion_time"], "2026-10-05T15:02:00Z")

        conflicting = price_bar(close="100.50")
        with self.assertRaisesRegex(DataEngineError, "Conflicting values share"):
            normalize_records([first, conflicting])

    def test_sorts_out_of_order_rows_monotonically_per_series(self):
        earlier = price_bar(
            record_id="bar-0",
            event_time="2026-10-05T14:00:00Z",
            available_time="2026-10-05T14:01:00Z",
            ingestion_time="2026-10-05T14:02:00Z",
        )
        normalized, _ = normalize_records([source_row(), earlier])
        self.assertEqual(
            [row["event_time"] for row in normalized],
            ["2026-10-05T14:00:00Z", "2026-10-05T15:00:00Z"],
        )


class PointInTimeQueryTests(unittest.TestCase):
    def test_fractional_publication_cutoffs_are_compared_as_instants(self):
        original = price_bar(
            event_time="2026-10-05T10:00:00Z",
            available_time="2026-10-05T10:00:00Z",
            ingestion_time="2026-10-05T10:00:00Z",
            close="100",
        )
        revised = price_bar(
            event_time="2026-10-05T10:00:00Z",
            available_time="2026-10-05T10:00:00.100000Z",
            ingestion_time="2026-10-05T10:00:00.200000Z",
            close="101",
        )
        revised["source_revision"] = "2"
        source_view = query_as_of([original, revised], "2026-10-05T10:00:00.150000Z", mode="source")
        system_view = query_as_of([original, revised], "2026-10-05T10:00:00.150000Z", mode="system")
        self.assertEqual(source_view[0]["payload"]["close"], "101")
        self.assertEqual(system_view[0]["payload"]["close"], "100")

    def test_fractional_price_bars_sort_by_timestamp_not_timestamp_text(self):
        later = price_bar(
            record_id="bar-later",
            event_time="2026-10-05T10:00:00.100000Z",
            available_time="2026-10-05T10:00:01.100000Z",
            ingestion_time="2026-10-05T10:00:02.100000Z",
        )
        earlier = price_bar(
            record_id="bar-earlier",
            event_time="2026-10-05T10:00:00Z",
            available_time="2026-10-05T10:00:01Z",
            ingestion_time="2026-10-05T10:00:02Z",
        )
        normalized, _ = normalize_records([later, earlier])
        self.assertEqual([row["record_id"] for row in normalized], ["bar-earlier", "bar-later"])

    def test_source_and_system_as_of_views_respect_publication_and_ingestion(self):
        original = price_bar(
            event_time="2026-10-05T10:00:00Z",
            available_time="2026-10-05T10:05:00Z",
            ingestion_time="2026-10-05T10:06:00Z",
            close="100",
        )
        revised = price_bar(
            event_time="2026-10-05T10:00:00Z",
            available_time="2026-10-05T10:30:00Z",
            ingestion_time="2026-10-05T10:40:00Z",
            close="101",
        )
        revised["source_revision"] = "2"
        calendar = {
            "record_id": "event-1",
            "instrument_id": "MX-TEST-1",
            "record_type": "calendar_event",
            "event_time": "2026-10-05T13:00:00Z",
            "available_time": "2026-10-05T09:00:00Z",
            "ingestion_time": "2026-10-05T09:01:00Z",
            "source_id": "fixture",
            "source_revision": "1",
            "payload": {"event": "known future event"},
        }
        cutoff = "2026-10-05T10:35:00Z"
        source_view = query_as_of([revised, calendar, original], cutoff, mode="source")
        system_view = query_as_of([revised, calendar, original], cutoff, mode="system")
        source_bar = next(row for row in source_view if row["record_type"] == "price_bar")
        system_bar = next(row for row in system_view if row["record_type"] == "price_bar")
        self.assertEqual(source_bar["payload"]["close"], "101")
        self.assertEqual(system_bar["payload"]["close"], "100")
        self.assertTrue(any(row["record_type"] == "calendar_event" for row in source_view))

    def test_does_not_return_prices_before_their_publication_or_future_event_time(self):
        unpublished = price_bar(
            event_time="2026-10-05T10:00:00Z",
            available_time="2026-10-05T10:31:00Z",
            ingestion_time="2026-10-05T10:32:00Z",
        )
        self.assertEqual(query_as_of([unpublished], "2026-10-05T10:30:00Z"), [])

    def test_stale_price_firewall_fails_closed(self):
        recent = price_bar(
            event_time="2026-10-05T10:00:00Z",
            available_time="2026-10-05T10:00:01Z",
            ingestion_time="2026-10-05T10:00:02Z",
        )
        cutoff = "2026-10-05T10:05:00Z"
        result = require_fresh_price_bars([recent], cutoff, max_age_seconds=300)
        self.assertEqual(result["status"], "PASS")
        with self.assertRaisesRegex(DataEngineError, "Stale price_bar"):
            require_fresh_price_bars([recent], cutoff, max_age_seconds=299)
        with self.assertRaisesRegex(DataEngineError, "No price_bar"):
            require_fresh_price_bars([], cutoff, max_age_seconds=300)
        with self.assertRaisesRegex(DataEngineError, "non-negative integer"):
            require_fresh_price_bars([recent], cutoff, max_age_seconds=True)

    def test_freshness_checks_latest_bar_per_instrument_and_can_require_coverage(self):
        older = price_bar(
            record_id="bar-old",
            event_time="2026-10-05T09:00:00Z",
            available_time="2026-10-05T09:00:01Z",
            ingestion_time="2026-10-05T09:00:02Z",
        )
        recent = price_bar(
            record_id="bar-new",
            event_time="2026-10-05T10:00:00Z",
            available_time="2026-10-05T10:00:01Z",
            ingestion_time="2026-10-05T10:00:02Z",
        )
        result = require_fresh_price_bars(
            [older, recent],
            "2026-10-05T10:05:00Z",
            max_age_seconds=300,
            expected_instrument_ids=["MX-TEST-1"],
        )
        self.assertEqual(result["checked_instruments"], 1)
        self.assertEqual(result["historical_price_bars_considered"], 2)
        self.assertEqual(result["coverage_status"], "CHECKED")
        with self.assertRaisesRegex(DataEngineError, "Missing price_bar coverage"):
            require_fresh_price_bars(
                [recent],
                "2026-10-05T10:05:00Z",
                max_age_seconds=300,
                expected_instrument_ids=["MX-TEST-1", "MX-TEST-2"],
            )

    def test_freshness_rejects_records_outside_the_requested_as_of_view(self):
        not_yet_public = price_bar(
            event_time="2026-10-05T10:00:00Z",
            available_time="2026-10-05T10:05:01Z",
            ingestion_time="2026-10-05T10:05:02Z",
        )
        with self.assertRaisesRegex(DataEngineError, "Unpublished price_bar"):
            require_fresh_price_bars(
                [not_yet_public], "2026-10-05T10:05:00Z", max_age_seconds=60
            )
        not_yet_ingested = price_bar(
            event_time="2026-10-05T10:00:00Z",
            available_time="2026-10-05T10:01:00Z",
            ingestion_time="2026-10-05T10:06:00Z",
        )
        with self.assertRaisesRegex(DataEngineError, "Not-yet-ingested"):
            require_fresh_price_bars(
                [not_yet_ingested],
                "2026-10-05T10:05:00Z",
                max_age_seconds=600,
                mode="system",
            )


class DatasetManifestTests(unittest.TestCase):
    def _build(self, root: Path, *, source_url=None):
        input_path = root.parent / f"{root.name}-source.jsonl"
        input_path.write_text(json.dumps(source_row()) + "\n", encoding="utf-8")
        manifest = build_dataset(
            input_path,
            root,
            source_id="fixture",
            publisher="Synthetic test fixture",
            source_url=source_url,
            license_id="synthetic-test-data",
            redistribution_status="permitted",
            ingestion_time="2026-10-05T15:03:00Z",
            code_commit_sha=COMMIT_SHA,
        )
        return input_path, manifest

    def test_builds_immutable_layers_manifest_and_reads_back(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            input_path, manifest = self._build(root)
            manifest_path = root / "data/metadata/datasets" / f"{manifest['dataset_id']}.json"
            raw_snapshot = root / manifest["raw_snapshot"]["path"]
            self.assertEqual(raw_snapshot.read_bytes(), input_path.read_bytes())
            self.assertEqual(verify_manifest(manifest_path, root)["status"], "PASS")
            loaded_manifest, rows = read_dataset(manifest_path, root)
            self.assertEqual(loaded_manifest["dataset_id"], manifest["dataset_id"])
            self.assertEqual(len(rows), 1)
            repeated = build_dataset(
                input_path,
                root,
                source_id="fixture",
                publisher="Synthetic test fixture",
                license_id="synthetic-test-data",
                redistribution_status="permitted",
                ingestion_time="2026-10-05T15:03:00Z",
                code_commit_sha=COMMIT_SHA,
            )
            self.assertEqual(repeated["dataset_id"], manifest["dataset_id"])
            raw_snapshot.write_bytes(b"tampered")
            with self.assertRaisesRegex(DataEngineError, "Refusing to overwrite immutable"):
                build_dataset(
                    input_path,
                    root,
                    source_id="fixture",
                    publisher="Synthetic test fixture",
                    license_id="synthetic-test-data",
                    redistribution_status="permitted",
                    ingestion_time="2026-10-05T15:03:00Z",
                    code_commit_sha=COMMIT_SHA,
                )

    def test_verifier_detects_raw_tampering_and_path_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            _, manifest = self._build(root)
            manifest_path = root / "data/metadata/datasets" / f"{manifest['dataset_id']}.json"
            raw_path = root / manifest["raw_snapshot"]["path"]
            raw_path.write_bytes(raw_path.read_bytes() + b"tampered")
            with self.assertRaisesRegex(DataEngineError, "SHA-256 mismatch"):
                verify_manifest(manifest_path, root)

            processed_path = root / "data/processed" / f"{manifest['dataset_id']}.jsonl"
            raw_path.write_bytes(processed_path.read_bytes())
            altered = json.loads(manifest_path.read_text(encoding="utf-8"))
            altered["raw_snapshot"]["path"] = "../../outside.json"
            manifest_path.write_text(json.dumps(altered), encoding="utf-8")
            with self.assertRaisesRegex(DataEngineError, "inside the project root"):
                verify_manifest(manifest_path, root)

    def test_verifier_reconciles_raw_interim_processed_and_duplicate_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            input_path = root.parent / "duplicate-source.jsonl"
            first = source_row()
            duplicate = dict(first, ingestion_time="2026-10-05T15:03:00Z")
            input_path.write_text(
                json.dumps(first) + "\n" + json.dumps(duplicate) + "\n", encoding="utf-8"
            )
            manifest = build_dataset(
                input_path,
                root,
                source_id="fixture",
                publisher="Synthetic test fixture",
                license_id="synthetic-test-data",
                redistribution_status="permitted",
                ingestion_time="2026-10-05T15:04:00Z",
                code_commit_sha=COMMIT_SHA,
            )
            manifest_path = root / "data/metadata/datasets" / f"{manifest['dataset_id']}.json"
            self.assertEqual(manifest["records"]["duplicates_removed"], 1)
            self.assertEqual(verify_manifest(manifest_path, root)["status"], "PASS")

            processed_path = root / manifest["processed_snapshot"]["path"]
            altered_row = json.loads(processed_path.read_text(encoding="utf-8"))
            altered_row["payload"]["close"] = "100.50"
            altered_json = json.dumps(altered_row, sort_keys=True, separators=(",", ":"))
            altered_bytes = (altered_json + "\n").encode()
            processed_path.write_bytes(altered_bytes)
            changed_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            changed_manifest["processed_snapshot"]["sha256"] = hashlib.sha256(
                altered_bytes
            ).hexdigest()
            manifest_path.write_text(json.dumps(changed_manifest), encoding="utf-8")
            with self.assertRaisesRegex(DataEngineError, "records do not agree"):
                verify_manifest(manifest_path, root)

    def test_rejects_unsafe_urls_bad_git_sha_and_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            input_path = root.parent / "fixture-source.jsonl"
            input_path.write_text(json.dumps(source_row()) + "\n", encoding="utf-8")
            args = dict(
                source_id="fixture",
                publisher="Synthetic test fixture",
                license_id="synthetic-test-data",
                redistribution_status="permitted",
                ingestion_time="2026-10-05T15:03:00Z",
                code_commit_sha="short",
            )
            with self.assertRaisesRegex(DataEngineError, "full 40- or 64-character Git SHA"):
                build_dataset(input_path, root, **args)
            args["code_commit_sha"] = COMMIT_SHA
            with self.assertRaisesRegex(DataEngineError, "query parameters"):
                build_dataset(
                    input_path,
                    root,
                    source_url="https://example.com/data?token=x",
                    **args,
                )

            input_path.write_text('{"x":1,"x":2}\n', encoding="utf-8")
            with self.assertRaisesRegex(DataEngineError, "Duplicate JSON object key"):
                build_dataset(input_path, root, **args)

    def test_csv_contract_ingests_valid_rows_and_rejects_missing_cells(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            valid_path = root.parent / "fixture.csv"
            columns = [
                "record_id",
                "instrument_id",
                "record_type",
                "event_time",
                "available_time",
                "ingestion_time",
                "source_revision",
                "provider_symbol",
                "payload_json",
            ]
            row = source_row()
            with valid_path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(columns)
                writer.writerow(
                    [
                        row["record_id"],
                        row["instrument_id"],
                        row["record_type"],
                        row["event_time"],
                        row["available_time"],
                        row["ingestion_time"],
                        row["source_revision"],
                        "MXTEST",
                        json.dumps(row["payload"]),
                    ]
                )
            manifest = build_dataset(
                valid_path,
                root,
                source_id="fixture",
                publisher="Synthetic test fixture",
                license_id="synthetic-test-data",
                redistribution_status="permitted",
                ingestion_time="2026-10-05T15:03:00Z",
                code_commit_sha=COMMIT_SHA,
            )
            manifest_path = root / "data/metadata/datasets" / f"{manifest['dataset_id']}.json"
            _, normalized = read_dataset(manifest_path, root)
            self.assertEqual(normalized[0]["provider_symbol"], "MXTEST")

            invalid_path = root.parent / "invalid.csv"
            with invalid_path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(columns)
                writer.writerow(["bar-1", "MX-TEST-1"])
            with self.assertRaisesRegex(DataEngineError, "missing cells"):
                build_dataset(
                    invalid_path,
                    root,
                    source_id="fixture",
                    publisher="Synthetic test fixture",
                    license_id="synthetic-test-data",
                    redistribution_status="permitted",
                    ingestion_time="2026-10-05T15:03:00Z",
                    code_commit_sha=COMMIT_SHA,
                )

    def test_cli_ingest_verify_and_as_of_query_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            input_path = root.parent / "fixture-cli.jsonl"
            input_path.write_text(json.dumps(source_row()) + "\n", encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                status = data_cli_main(
                    [
                        "ingest",
                        "--input",
                        str(input_path),
                        "--source-id",
                        "fixture",
                        "--publisher",
                        "Synthetic fixture",
                        "--license-id",
                        "synthetic-test-data",
                        "--redistribution-status",
                        "permitted",
                        "--ingestion-time",
                        "2026-10-05T15:03:00Z",
                        "--code-commit-sha",
                        COMMIT_SHA,
                        "--project-root",
                        str(root),
                    ]
                )
            self.assertEqual(status, 0)
            ingest_result = json.loads(stdout.getvalue())
            manifest_path = root / ingest_result["manifest_path"]

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                status = data_cli_main(
                    ["verify", "--manifest", str(manifest_path), "--project-root", str(root)]
                )
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(stdout.getvalue())["status"], "PASS")

            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                status = data_cli_main(
                    [
                        "query",
                        "--manifest",
                        str(manifest_path),
                        "--as-of",
                        "2026-10-05T15:05:00Z",
                        "--expected-instrument",
                        "MX-TEST-1",
                        "--project-root",
                        str(root),
                    ]
                )
            self.assertEqual(status, 2)
            self.assertIn("requires --max-price-age-seconds", stderr.getvalue())

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                status = data_cli_main(
                    [
                        "query",
                        "--manifest",
                        str(manifest_path),
                        "--as-of",
                        "2026-10-05T15:05:00Z",
                        "--max-price-age-seconds",
                        "300",
                        "--expected-instrument",
                        "MX-TEST-1",
                        "--project-root",
                        str(root),
                    ]
                )
            self.assertEqual(status, 0)
            query = json.loads(stdout.getvalue())
            self.assertEqual(query["count"], 1)
            self.assertEqual(query["price_freshness"]["status"], "PASS")
            self.assertEqual(query["price_freshness"]["coverage_status"], "CHECKED")


if __name__ == "__main__":
    unittest.main()
