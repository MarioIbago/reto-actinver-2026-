import json
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO

from actinver.news_cli import main
from actinver.news_events import normalize_news_documents
from test_news_events import article, extraction, universe_fixture


class NewsCliTests(unittest.TestCase):
    def test_normalize_then_prepare_extraction_through_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_path = root / "raw.json"
            normalized_path = root / "normalized.json"
            prepared_path = root / "prepared.json"
            raw_path.write_text(json.dumps([article()]), encoding="utf-8")

            self.assertEqual(main(["normalize", "--input", str(raw_path), "--output", str(normalized_path)]), 0)
            normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
            self.assertEqual(normalized["duplicate_count"], 0)

            self.assertEqual(main([
                "prepare-extraction",
                "--input", str(normalized_path),
                "--as-of", "2026-10-05T15:01:00Z",
                "--mode", "system",
                "--output", str(prepared_path),
            ]), 0)
            prepared = json.loads(prepared_path.read_text(encoding="utf-8"))
            self.assertEqual(len(prepared), 1)
            self.assertIn("body", prepared[0])
            self.assertNotIn("forward_return", prepared[0])

    def test_cli_reports_malformed_input_without_traceback(self):
        stderr = StringIO()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text("{broken", encoding="utf-8")
            with redirect_stderr(stderr):
                result = main(["normalize", "--input", str(path)])
        self.assertEqual(result, 2)
        self.assertIn("actinver-news:", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_cli_creates_snapshot_digest_watch_and_reproducible_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document_path = root / "document.json"
            extraction_path = root / "extraction.json"
            universe_path = root / "universe.json"
            snapshot_path = root / "snapshots.json"
            events_path = root / "events.json"
            documents_path = root / "documents.json"
            documents_as_of_path = root / "documents_as_of.json"
            digest_path = root / "digest.json"
            watch_path = root / "watch.json"
            prices_path = root / "prices.json"
            labels_path = root / "labels.json"
            evaluation_path = root / "evaluation.json"
            evaluation_result_path = root / "evaluation_result.json"

            documents_path.write_text(json.dumps([article()]), encoding="utf-8")
            self.assertEqual(main([
                "documents-as-of", "--input", str(documents_path), "--as-of", "2026-10-05T15:01:00Z",
                "--mode", "system", "--output", str(documents_as_of_path),
            ]), 0)
            self.assertEqual(len(json.loads(documents_as_of_path.read_text(encoding="utf-8"))), 1)

            normalized, _ = normalize_news_documents([article()])
            document_path.write_text(json.dumps(normalized[0]), encoding="utf-8")
            extraction_path.write_text(json.dumps(extraction()), encoding="utf-8")
            universe_path.write_text(json.dumps(universe_fixture()), encoding="utf-8")
            self.assertEqual(main([
                "create-snapshot", "--document", str(document_path),
                "--extraction", str(extraction_path), "--universe", str(universe_path),
                "--extraction-version", "fixture-extractor-v1", "--model", "synthetic-test-only",
                "--prompt-sha256", "a" * 64, "--completed-at", "2026-10-05T15:01:00Z",
                "--ingestion-time", "2026-10-05T15:01:05Z", "--output", str(snapshot_path),
            ]), 0)
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            snapshot_path.write_text(json.dumps([snapshot]), encoding="utf-8")

            self.assertEqual(main([
                "events-as-of", "--input", str(snapshot_path), "--as-of", "2026-10-05T16:00:00Z",
                "--mode", "system", "--output", str(events_path),
            ]), 0)
            self.assertEqual(len(json.loads(events_path.read_text(encoding="utf-8"))), 1)
            self.assertEqual(main([
                "digest", "--input", str(snapshot_path), "--window-start", "2026-10-05T14:00:00Z",
                "--as-of", "2026-10-05T16:00:00Z", "--timezone", "America/Mexico_City",
                "--mode", "system", "--output", str(digest_path),
            ]), 0)
            self.assertEqual(json.loads(digest_path.read_text(encoding="utf-8"))["event_count"], 1)
            self.assertEqual(main([
                "watch", "--input", str(snapshot_path), "--after-time", "2026-10-05T15:00:00Z",
                "--as-of", "2026-10-05T16:00:00Z", "--timezone", "America/Mexico_City",
                "--mode", "system", "--output", str(watch_path),
            ]), 0)
            self.assertEqual(len(json.loads(watch_path.read_text(encoding="utf-8"))["events"]), 1)

            prices = []
            for day, close in ((5, "100"), (6, "102")):
                timestamp = f"2026-10-{day:02d}T21:00:00Z"
                prices.append({
                    "record_id": f"bar-{day}",
                    "instrument_id": "actinver:2026:national_equity:alpha_a",
                    "record_type": "price_bar",
                    "event_time": timestamp,
                    "available_time": f"2026-10-{day:02d}T21:01:00Z",
                    "ingestion_time": f"2026-10-{day:02d}T21:02:00Z",
                    "source_id": "synthetic_prices",
                    "source_revision": "v1",
                    "payload": {"open": close, "high": close, "low": close, "close": close, "volume": "1000"},
                })
            prices_path.write_text(json.dumps(prices), encoding="utf-8")
            self.assertEqual(main([
                "label-forward-returns", "--snapshots", str(snapshot_path), "--prices", str(prices_path),
                "--horizon-sessions", "1", "--label-as-of", "2026-10-06T22:00:00Z",
                "--price-dataset-id", "fixture-prices-v1", "--mode", "system", "--output", str(labels_path),
            ]), 0)
            labels = json.loads(labels_path.read_text(encoding="utf-8"))
            self.assertEqual(len(labels), 1)
            self.assertEqual(labels[0]["price_dataset_id"], "fixture-prices-v1")

            periods = {
                "train": ("2026-01-01T00:00:00Z", "2026-01-31T23:59:59Z"),
                "validation": ("2026-02-01T00:00:00Z", "2026-02-28T23:59:59Z"),
                "test": ("2026-03-01T00:00:00Z", "2026-03-31T23:59:59Z"),
            }
            observations = []
            for split, (start, _end) in periods.items():
                decision = start
                observations.append({
                    "event_id": f"event-{split}",
                    "event_group_id": f"group-{split}",
                    "instrument_id": "instrument-fixture",
                    "feature_available_time": decision,
                    "prediction_available_time": decision,
                    "decision_time": decision,
                    "label_available_time": (datetime.fromisoformat(decision.replace("Z", "+00:00")) + timedelta(days=1)).isoformat().replace("+00:00", "Z"),
                    "label_id": f"label-{split}",
                    "split": split,
                    "forward_return": "0.01",
                    "event_probability": "0.6",
                })
            evaluation = {
                "schema_version": 1,
                "evaluation_id": "cli-fixture-eval",
                "target_definition": "gross_forward_return_gt_zero",
                "horizon_sessions": 1,
                "baseline_description": "training-sample positive rate",
                "train_period": {"start": periods["train"][0], "end": periods["train"][1]},
                "validation_period": {"start": periods["validation"][0], "end": periods["validation"][1]},
                "test_period": {"start": periods["test"][0], "end": periods["test"][1]},
                "final_holdout_locked": True,
                "test_used_for_selection": False,
                "evidence": {
                    "data_status": "synthetic_fixture",
                    "source_availability_verified": False,
                    "instrument_mapping_verified": False,
                    "prices_authorized": False,
                    "execution_costs_verified": False,
                },
                "observations": observations,
            }
            evaluation_path.write_text(json.dumps(evaluation), encoding="utf-8")
            self.assertEqual(main([
                "evaluate", "--input", str(evaluation_path), "--output", str(evaluation_result_path),
            ]), 0)
            result = json.loads(evaluation_result_path.read_text(encoding="utf-8"))
            self.assertEqual(result["baseline_fit_split"], "train")


if __name__ == "__main__":
    unittest.main()
