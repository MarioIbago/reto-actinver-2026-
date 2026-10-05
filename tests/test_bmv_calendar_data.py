import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from actinver.data_engine import query_as_of, read_dataset, verify_manifest


ROOT = Path(__file__).resolve().parents[1]
INGESTION_TIME = "2026-10-05T09:56:08Z"
CODE_COMMIT_SHA = "a" * 40
CAPTURE_TIME = "2026-10-05T08:15:08Z"


def build_calendar(output_root: Path) -> dict:
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/build_bmv_calendar_dataset.py"),
            "--ingestion-time",
            INGESTION_TIME,
            "--code-commit-sha",
            CODE_COMMIT_SHA,
            "--output-root",
            str(output_root),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr)
    return json.loads(completed.stdout)


class BMVCalendarDatasetTests(unittest.TestCase):
    def test_real_calendar_dataset_has_pit_provenance_and_future_event_semantics(self):
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)
            result = build_calendar(output_root)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["record_count"], 11)
            self.assertEqual(result["redistribution_status"], "unknown")

            manifest_path = output_root / result["manifest_path"]
            verification = verify_manifest(manifest_path, output_root)
            self.assertEqual(verification["status"], "PASS")
            self.assertEqual(verification["records"], 11)
            manifest, records = read_dataset(manifest_path, output_root)
            self.assertEqual(manifest["source"]["license_id"], "unknown-public-web-terms")
            self.assertEqual(
                manifest["records"]["counts_by_type"], {"calendar_event": 11}
            )

            before_capture = query_as_of(
                records, "2026-10-05T08:15:07Z", mode="source"
            )
            at_capture = query_as_of(records, CAPTURE_TIME, mode="source")
            before_ingestion = query_as_of(
                records, "2026-10-05T09:56:07Z", mode="system"
            )
            at_ingestion = query_as_of(
                records, INGESTION_TIME, mode="system"
            )
            at_competition_cutoff = datetime.fromisoformat(
                "2026-10-05T10:35:00-06:00"
            )
            at_competition_cutoff_records = query_as_of(
                records, at_competition_cutoff.isoformat(), mode="system"
            )

            self.assertEqual(len(before_capture), 0)
            self.assertEqual(len(at_capture), 11)
            self.assertEqual(len(before_ingestion), 0)
            self.assertEqual(len(at_ingestion), 11)
            self.assertEqual(len(at_competition_cutoff_records), 11)

            future_holiday = next(
                record
                for record in at_competition_cutoff_records
                if record["payload"]["event_date"] == "2026-11-02"
            )
            self.assertEqual(future_holiday["payload"]["event_name"], "Día de muertos")
            self.assertEqual(future_holiday["event_time"], "2026-11-02T06:00:00Z")
            self.assertEqual(future_holiday["available_time"], CAPTURE_TIME)
            self.assertEqual(future_holiday["ingestion_time"], INGESTION_TIME)
            self.assertIsNone(
                future_holiday["payload"]["original_first_publication_time"]
            )

    def test_same_capture_and_build_inputs_reproduce_identical_dataset_ids(self):
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = build_calendar(Path(first_dir))
            second = build_calendar(Path(second_dir))
        self.assertEqual(first["dataset_id"], second["dataset_id"])
        self.assertEqual(first["raw_sha256"], second["raw_sha256"])


if __name__ == "__main__":
    unittest.main()
