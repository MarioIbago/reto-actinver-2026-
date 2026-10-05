from contextlib import redirect_stdout
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from actinver.trade_sheet import (
    TradeSheetError,
    append_audit_event,
    build_post_trade_attribution,
    build_trade_sheet,
    canonical_sha256,
    create_trade_sheet,
    verify_audit_log,
)
from actinver.trade_sheet_cli import main as cockpit_main
from actinver.news_events import build_entity_catalog, create_event_snapshot, normalize_news_documents


def context_fixture():
    return {
        "schema_version": 1,
        "context_id": "operator-cut-1",
        "as_of_utc": "2026-10-05T14:00:00Z",
        "competition": {
            "capital_actipesos": 100000,
            "rank": 20,
            "gap_to_first_actipesos": 50000,
            "sessions_remaining": 14,
        },
        "portfolio": {"positions": [{"instrument_id": "internal-id-1", "market_value_actipesos": 25000}]},
        "data_sources": [{
            "source_id": "operator_statement",
            "observed_at_utc": "2026-10-05T13:30:00Z",
            "max_age_minutes": 60,
        }],
    }


def m7_fixture():
    return {
        "schema_version": 1,
        "software_status": "PASS",
        "forecast_status": "NO_PROMOTED_SIGNALS",
        "empirical_gate": "NEEDS_MORE_EVIDENCE",
        "signal_count": 0,
        "predictions": [],
    }


def event_snapshot_fixture():
    document = {
        "schema_version": 1,
        "document_id": "m9-fixture-release",
        "revision_id": "r1",
        "source_id": "fixture_issuer",
        "publisher": "Fixture issuer",
        "first_public_time": "2026-10-05T09:00:00-06:00",
        "revision_public_time": "2026-10-05T09:00:00-06:00",
        "ingestion_time": "2026-10-05T15:00:05Z",
        "event_time": "2026-10-05T08:30:00-06:00",
        "source_url": "https://issuer.example/releases/fixture",
        "source_type": "issuer_release",
        "redistribution_status": "restricted",
        "source_quality": "primary_issuer",
        "title": "Fixture guidance",
        "body": "Synthetic test-only event fixture.",
    }
    docs, _duplicates = normalize_news_documents([document])
    catalog = build_entity_catalog({"instruments": [{
        "instrument_id": "internal-fixture-id",
        "issuer_key": "issuer:fixture",
        "guide_symbol": "FIXTURE",
        "issuer_or_name": "Fixture issuer",
        "sector": None,
        "platform_symbol": None,
        "series": None,
        "eligibility": {"platform_search_symbol_verified": False},
    }]})
    extraction = {"events": [{
        "event_type": "earnings_guidance",
        "event_time": "2026-10-05T08:30:00-06:00",
        "entity_mentions": ["FIXTURE"],
        "novelty": "0.8",
        "direction": "positive",
        "surprise_magnitude": "0.4",
        "guidance_direction": "positive",
        "materiality": "0.7",
        "confidence": "0.9",
        "affected_sectors": [],
        "links": [],
    }]}
    return create_event_snapshot(
        docs[0], extraction, entity_catalog=catalog,
        extraction_version="m9-fixture-extractor-v1",
        extraction_model="synthetic-test-only",
        prompt_sha256="f" * 64,
        extraction_completed_at="2026-10-05T15:01:00Z",
        ingestion_time="2026-10-05T15:01:05Z",
    )


class TradeSheetTests(unittest.TestCase):
    def test_report_fails_closed_and_exposes_unknown_action_fields(self):
        report = build_trade_sheet(
            context_fixture(),
            report_type="morning",
            created_at=datetime(2026, 10, 5, 16, 1, tzinfo=timezone.utc),
        )
        self.assertEqual(report["decision_status"], "NO_TRADE")
        self.assertEqual(report["decision"]["action"], "NO_TRADE")
        self.assertIsNone(report["decision"]["target_size_actipesos"])
        self.assertEqual(report["evidence"]["m7"]["status"], "NOT_SUPPLIED")
        self.assertEqual(report["evidence"]["m8"]["status"], "NOT_SUPPLIED")
        self.assertEqual(report["evidence"]["freshness"][0]["status"], "CURRENT")
        self.assertIsNone(report["decision"]["estimated_contribution_to_p1"])

    def test_m7_m8_evidence_does_not_unlock_simulation_or_missing_gate(self):
        raw_m7 = json.dumps(m7_fixture(), separators=(",", ":")).encode()
        m7_sha = hashlib.sha256(raw_m7).hexdigest()
        m8 = {
            "software_status": "PASS",
            "decision_status": "SIMULATION_ONLY",
            "empirical_gate": "NEEDS_MORE_EVIDENCE",
            "decision": None,
            "input_trace": {"m7_result_sha256": m7_sha},
        }
        report = build_trade_sheet(
            context_fixture(),
            report_type="event_update",
            m7_result=m7_fixture(),
            m7_sha256=m7_sha,
            m8_result=m8,
            m8_sha256="b" * 64,
            created_at=datetime(2026, 10, 5, 16, 1, tzinfo=timezone.utc),
        )
        self.assertEqual(report["decision"]["action"], "NO_TRADE")
        self.assertEqual(report["evidence"]["m7"]["status"], "NO_PROMOTED_SIGNALS")
        self.assertEqual(report["evidence"]["m8"]["status"], "SIMULATION_ONLY")
        self.assertEqual(report["provenance"]["m7_result_sha256"], m7_sha)

    def test_m8_m7_digest_mismatch_is_visible_and_remains_no_trade(self):
        m8 = {
            "software_status": "PASS",
            "decision_status": "SIMULATION_ONLY",
            "empirical_gate": "NEEDS_MORE_EVIDENCE",
            "decision": None,
            "input_trace": {"m7_result_sha256": "c" * 64},
        }
        report = build_trade_sheet(
            context_fixture(), report_type="morning", m7_result=m7_fixture(),
            m7_sha256="d" * 64, m8_result=m8,
            created_at=datetime(2026, 10, 5, 16, 1, tzinfo=timezone.utc),
        )
        self.assertEqual(report["decision_status"], "NO_TRADE")
        self.assertEqual(report["evidence"]["m8"]["status"], "M7_HASH_MISMATCH")

    def test_stale_and_unknown_freshness_are_reported_and_no_trade(self):
        stale_context = context_fixture()
        stale_context["data_sources"][0]["observed_at_utc"] = "2026-10-05T12:59:00Z"
        stale_context["data_sources"].append({"source_id": "missing", "observed_at_utc": None, "max_age_minutes": None})
        report = build_trade_sheet(
            stale_context, report_type="evening_review",
            created_at=datetime(2026, 10, 5, 16, 1, tzinfo=timezone.utc),
        )
        self.assertEqual([row["status"] for row in report["evidence"]["freshness"]], ["STALE", "UNKNOWN"])
        self.assertEqual(report["decision"]["action"], "NO_TRADE")

    def test_context_rejects_source_observation_after_as_of(self):
        invalid = context_fixture()
        invalid["data_sources"][0]["observed_at_utc"] = "2026-10-05T16:00:01Z"
        with self.assertRaisesRegex(TradeSheetError, "after the report as-of"):
            build_trade_sheet(invalid, report_type="morning")

    def test_event_snapshot_requires_cutoff_and_rejects_future_information(self):
        snapshot = event_snapshot_fixture()
        with self.assertRaisesRegex(TradeSheetError, "as_of_utc is required"):
            build_trade_sheet(context_fixture() | {"as_of_utc": None}, report_type="event_update", event_snapshots=[snapshot])
        before_availability = context_fixture() | {"as_of_utc": "2026-10-05T15:01:04Z"}
        with self.assertRaisesRegex(TradeSheetError, "unavailable at the report cutoff"):
            build_trade_sheet(before_availability, report_type="event_update", event_snapshots=[snapshot])
        after_availability = context_fixture() | {"as_of_utc": "2026-10-05T15:02:00Z"}
        report = build_trade_sheet(
            after_availability, report_type="event_update", event_snapshots=[snapshot],
            created_at=datetime(2026, 10, 5, 15, 3, tzinfo=timezone.utc),
        )
        self.assertEqual(len(report["material_events"]), 1)
        self.assertEqual(report["material_events"][0]["source_quality"], "primary_issuer")

    def test_freshness_threshold_does_not_round_down_past_cutoff(self):
        context = context_fixture()
        context["data_sources"][0]["observed_at_utc"] = "2026-10-05T14:59:59Z"
        context["data_sources"][0]["max_age_minutes"] = 60
        context["as_of_utc"] = "2026-10-05T16:00:00Z"
        report = build_trade_sheet(context, report_type="morning", created_at=datetime(2026, 10, 5, 16, 1, tzinfo=timezone.utc))
        self.assertEqual(report["evidence"]["freshness"][0]["status"], "STALE")
        self.assertEqual(report["evidence"]["freshness"][0]["age_minutes_at_as_of"], 61)

    def test_append_only_audit_verifies_and_detects_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "m9.jsonl"
            created = append_audit_event(path, event_type="TRADE_SHEET_CREATED", object_id="report-1", object_sha256="a" * 64)
            appended = append_audit_event(path, event_type="POST_TRADE_ATTRIBUTION_CREATED", object_id="attribution-1", object_sha256="b" * 64)
            result = verify_audit_log(path)
            self.assertTrue(result["valid"])
            self.assertEqual(result["event_count"], 2)
            self.assertEqual(appended["previous_event_sha256"], created["event_sha256"])
            with self.assertRaisesRegex(TradeSheetError, "already contains"):
                append_audit_event(path, event_type="TRADE_SHEET_CREATED", object_id="report-1", object_sha256="a" * 64)
            path.write_text(path.read_text(encoding="utf-8").replace("report-1", "report-x"), encoding="utf-8")
            with self.assertRaisesRegex(TradeSheetError, "does not match its event hash"):
                verify_audit_log(path)

    def test_created_report_audit_binds_exact_saved_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report, path, event = create_trade_sheet(
                context_fixture(), report_type="morning", output_dir=root / "reports", audit_path=root / "audit" / "m9.jsonl",
            )
            exact_digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(event["object_sha256"], exact_digest)
            self.assertEqual(event["object_id"], report["report_id"])
            self.assertTrue(verify_audit_log(root / "audit" / "m9.jsonl")["valid"])

    def test_post_trade_attribution_is_descriptive_not_causal(self):
        report = build_trade_sheet(
            context_fixture(), report_type="evening_review",
            created_at=datetime(2026, 10, 5, 16, 1, tzinfo=timezone.utc),
        )
        activity = {
            "schema_version": 1,
            "activity_id": "operator-entry-1",
            "report_id": report["report_id"],
            "captured_at_utc": "2026-10-05T18:00:00Z",
            "starting_capital_actipesos": 100000,
            "ending_capital_actipesos": 101100,
            "net_external_flows_actipesos": 100,
            "manual_fills": [{
                "fill_id": "manual-fill-1",
                "instrument_id": "internal-id-1",
                "side": "BUY",
                "quantity": 2,
                "price_actipesos": 500,
                "fees_actipesos": 3,
                "executed_at_utc": "2026-10-05T17:00:00Z",
            }],
            "source_reference": "operator statement reference",
        }
        result = build_post_trade_attribution(
            activity, report, report_sha256="e" * 64,
            created_at=datetime(2026, 10, 5, 18, 1, tzinfo=timezone.utc),
        )
        self.assertEqual(result["net_portfolio_change_actipesos"], 1000)
        self.assertEqual(result["net_portfolio_return"], 0.01)
        self.assertEqual(result["manual_fill_count"], 1)
        self.assertEqual(result["manual_fill_notional_actipesos"], 1000)
        self.assertIsNone(result["causal_strategy_contribution_actipesos"])
        self.assertIsNone(result["p_final_rank_1_contribution"])
        self.assertEqual(result["attribution_status"], "DESCRIPTIVE_ONLY")

    def test_post_trade_money_uses_decimal_arithmetic(self):
        report = build_trade_sheet(context_fixture(), report_type="evening_review")
        activity = {
            "schema_version": 1, "activity_id": "decimal-entry", "report_id": report["report_id"],
            "captured_at_utc": "2026-10-05T18:00:00Z", "starting_capital_actipesos": 10.1,
            "ending_capital_actipesos": 10.5, "net_external_flows_actipesos": 0.1,
            "manual_fills": [], "source_reference": "operator statement reference",
        }
        result = build_post_trade_attribution(activity, report, created_at=datetime(2026, 10, 5, 18, 1, tzinfo=timezone.utc))
        self.assertEqual(result["net_portfolio_change_actipesos"], 0.3)

    def test_post_trade_attribution_requires_linked_report_and_valid_fill_period(self):
        report = build_trade_sheet(context_fixture(), report_type="evening_review")
        activity = {
            "schema_version": 1, "activity_id": "a", "report_id": "wrong",
            "captured_at_utc": "2026-10-05T18:00:00Z", "starting_capital_actipesos": 100,
            "ending_capital_actipesos": 100, "net_external_flows_actipesos": 0,
            "manual_fills": [], "source_reference": "statement",
        }
        with self.assertRaisesRegex(TradeSheetError, "does not match"):
            build_post_trade_attribution(activity, report)

    def test_cli_generates_report_and_verifies_audit_chain(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            context_path = root / "context.json"
            context_path.write_text(json.dumps(context_fixture()), encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                status = cockpit_main([
                    "report", "--type", "morning", "--context", str(context_path),
                    "--output-dir", str(root / "reports"), "--audit-file", str(root / "audit.jsonl"),
                ])
            self.assertEqual(status, 0)
            summary = json.loads(output.getvalue())
            self.assertEqual(summary["decision_status"], "NO_TRADE")
            report_path = Path(summary["report_path"])
            self.assertTrue(report_path.is_file())
            report = json.loads(report_path.read_text(encoding="utf-8"))
            activity = {
                "schema_version": 1,
                "activity_id": "cli-activity-fixture",
                "report_id": report["report_id"],
                "captured_at_utc": report["created_at_utc"],
                "starting_capital_actipesos": 1000,
                "ending_capital_actipesos": 1000,
                "net_external_flows_actipesos": 0,
                "manual_fills": [],
                "source_reference": "test-only fixture",
            }
            activity_path = root / "activity.json"
            activity_path.write_text(json.dumps(activity), encoding="utf-8")
            attribution_path = root / "attribution.json"
            with redirect_stdout(io.StringIO()) as attribute_output:
                status = cockpit_main([
                    "attribute", "--activity", str(activity_path), "--trade-sheet", str(report_path),
                    "--output", str(attribution_path), "--audit-file", str(root / "audit.jsonl"),
                ])
            self.assertEqual(status, 0)
            attribution_summary = json.loads(attribute_output.getvalue())
            self.assertEqual(attribution_summary["attribution_status"], "DESCRIPTIVE_ONLY")
            self.assertTrue(attribution_path.is_file())
            with redirect_stdout(io.StringIO()) as verify_output:
                status = cockpit_main(["verify-audit", "--audit-file", str(root / "audit.jsonl")])
            self.assertEqual(status, 0)
            verification = json.loads(verify_output.getvalue())
            self.assertTrue(verification["valid"])
            self.assertEqual(verification["event_count"], 2)

    def test_trade_sheet_contract_keys_match_checked_in_schemas(self):
        root = Path(__file__).resolve().parents[1]
        context = context_fixture()
        context_schema = json.loads((root / "schemas/m9_context.schema.json").read_text(encoding="utf-8"))
        report_schema = json.loads((root / "schemas/trade_sheet.schema.json").read_text(encoding="utf-8"))
        activity_schema = json.loads((root / "schemas/post_trade_activity.schema.json").read_text(encoding="utf-8"))
        attribution_schema = json.loads((root / "schemas/post_trade_attribution.schema.json").read_text(encoding="utf-8"))
        audit_schema = json.loads((root / "schemas/m9_audit_event.schema.json").read_text(encoding="utf-8"))
        report = build_trade_sheet(context, report_type="morning", created_at=datetime(2026, 10, 5, 15, 0, tzinfo=timezone.utc))
        self.assertEqual(set(context), set(context_schema["required"]))
        self.assertEqual(set(report), set(report_schema["required"]))
        self.assertEqual(set(activity_schema["required"]), {
            "schema_version", "activity_id", "report_id", "captured_at_utc", "starting_capital_actipesos",
            "ending_capital_actipesos", "net_external_flows_actipesos", "manual_fills", "source_reference",
        })
        result = build_post_trade_attribution({
            "schema_version": 1, "activity_id": "schema-fixture", "report_id": report["report_id"],
            "captured_at_utc": "2026-10-05T15:00:00Z", "starting_capital_actipesos": 10,
            "ending_capital_actipesos": 10, "net_external_flows_actipesos": 0, "manual_fills": [],
            "source_reference": "test-only fixture",
        }, report, created_at=datetime(2026, 10, 5, 15, 1, tzinfo=timezone.utc))
        self.assertEqual(set(result), set(attribution_schema["required"]))
        with tempfile.TemporaryDirectory() as directory:
            event = append_audit_event(Path(directory) / "audit.jsonl", event_type="TRADE_SHEET_CREATED", object_id=report["report_id"], object_sha256="a" * 64)
        self.assertEqual(set(event), set(audit_schema["required"]))


if __name__ == "__main__":
    unittest.main()
