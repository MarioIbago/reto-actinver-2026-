import json
from pathlib import Path
import re
import unittest
from zoneinfo import ZoneInfo

import yaml


ROOT = Path(__file__).resolve().parents[1]


class NewsContractTests(unittest.TestCase):
    def test_json_contracts_are_strict_versioned_schemas(self):
        for name in (
            "news_document.schema.json",
            "news_extraction.schema.json",
            "news_event_snapshot.schema.json",
            "news_forward_return_label.schema.json",
            "news_evaluation_case.schema.json",
            "news_evaluation_result.schema.json",
        ):
            with self.subTest(schema=name):
                schema = json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
                self.assertEqual(schema["type"], "object")
                self.assertFalse(schema["additionalProperties"])
                self.assertTrue(schema["required"])

    def test_schedule_spec_has_explicit_timezone_and_disabled_tasks(self):
        schedule = yaml.safe_load((ROOT / "config" / "news_schedules.yaml").read_text(encoding="utf-8"))
        self.assertEqual(schedule["schema_version"], 1)
        self.assertFalse(schedule["scheduler_enabled"])
        ZoneInfo(schedule["timezone"])
        required_tasks = {
            "overnight_news", "macro_fx_commodities", "issuer_earnings_guidance",
            "issuer_communications", "morning_digest", "overnight_digest", "material_event_alerts",
        }
        tasks = {task["task_id"]: task for task in schedule["tasks"]}
        self.assertEqual(set(tasks), required_tasks)
        self.assertTrue(all(task["enabled"] is False for task in tasks.values()))
        for task in tasks.values():
            cadence = task["schedule"]
            if "local_time" in cadence:
                self.assertRegex(cadence["local_time"], re.compile(r"^\d{2}:\d{2}$"))
            else:
                self.assertEqual(cadence["frequency"], "interval")
                self.assertGreater(cadence["interval_minutes"], 0)


if __name__ == "__main__":
    unittest.main()
