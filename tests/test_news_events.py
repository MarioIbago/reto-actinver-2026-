from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from actinver.news_events import (
    NewsEventError,
    build_entity_catalog,
    build_extraction_payload,
    build_intelligence_digest,
    create_event_snapshot,
    evaluate_event_predictions,
    label_forward_returns,
    normalize_news_documents,
    query_event_snapshots_as_of,
    query_news_documents_as_of,
    watch_breaking_events,
)


def article(*, revision="r1", first_public="2026-10-05T09:00:00-06:00", revision_public=None, ingested=None, body="Issuer reports quarterly results."):
    revision_public = revision_public or first_public
    ingested = ingested or (datetime.fromisoformat(revision_public).astimezone(timezone.utc) + timedelta(seconds=5)).isoformat()
    return {
        "schema_version": 1,
        "document_id": "issuer-release-1",
        "revision_id": revision,
        "source_id": "issuer_site",
        "publisher": "Alpha issuer",
        "first_public_time": first_public,
        "revision_public_time": revision_public,
        "ingestion_time": ingested,
        "event_time": "2026-10-05T08:30:00-06:00",
        "source_url": "https://issuer.example/releases/1",
        "source_type": "issuer_release",
        "redistribution_status": "restricted",
        "source_quality": "primary_issuer",
        "title": "Quarterly results",
        "body": body,
    }


def universe_fixture():
    def instrument(instrument_id, issuer_key, symbol, name):
        return {
            "instrument_id": instrument_id,
            "issuer_key": issuer_key,
            "guide_symbol": symbol,
            "issuer_or_name": name,
            "sector": None,
            "platform_symbol": None,
            "series": None,
            "eligibility": {"platform_search_symbol_verified": False},
        }

    return {
        "instruments": [
            instrument("actinver:2026:national_equity:alpha_a", "issuer:alpha", "ALPHA-A", "Alpha Holdings"),
            instrument("actinver:2026:national_equity:alpha_b", "issuer:alpha", "ALPHA-B", "Alpha Holdings"),
            instrument("actinver:2026:national_equity:beta", "issuer:beta", "BETA", "Beta Industries"),
        ]
    }


def extraction():
    return {
        "events": [
            {
                "event_type": "earnings_guidance",
                "event_time": "2026-10-05T08:30:00-06:00",
                "entity_mentions": ["ALPHA-A"],
                "novelty": "0.8",
                "direction": "positive",
                "surprise_magnitude": "0.4",
                "guidance_direction": "positive",
                "materiality": "0.7",
                "confidence": "0.9",
                "affected_sectors": [],
                "links": [],
            }
        ]
    }


def make_snapshot():
    documents, _duplicates = normalize_news_documents([article()])
    return create_event_snapshot(
        documents[0],
        extraction(),
        entity_catalog=build_entity_catalog(universe_fixture()),
        extraction_version="fixture-extractor-v1",
        extraction_model="synthetic-test-only",
        prompt_sha256="a" * 64,
        extraction_completed_at="2026-10-05T15:01:00Z",
        ingestion_time="2026-10-05T15:01:05Z",
    )


class NewsDocumentTests(unittest.TestCase):
    def test_normalization_fingerprints_and_deduplicates_exact_reingestion(self):
        raw = article()
        duplicate = dict(raw, ingestion_time="2026-10-05T15:00:10Z")
        documents, duplicates = normalize_news_documents([raw, duplicate])
        self.assertEqual(duplicates, 1)
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0]["revision_public_time"], "2026-10-05T15:00:00.000000Z")
        self.assertEqual(documents[0]["duplicate_group_id"], documents[0]["content_sha256"])
        self.assertEqual(documents[0]["ingestion_time"], "2026-10-05T15:00:05.000000Z")

    def test_fractional_timestamps_keep_chronological_as_of_order(self):
        first = article(
            revision="r1",
            first_public="2026-10-05T09:00:00Z",
            revision_public="2026-10-05T10:00:00Z",
            ingested="2026-10-05T10:00:01Z",
        )
        second = article(
            revision="r2",
            first_public="2026-10-05T09:00:00Z",
            revision_public="2026-10-05T10:00:00.100000Z",
            ingested="2026-10-05T10:00:01.100000Z",
            body="A correction published one tenth of a second later.",
        )
        documents, _ = normalize_news_documents([first, second])
        before_second = query_news_documents_as_of(documents, "2026-10-05T10:00:00.050000Z")
        self.assertEqual([row["revision_id"] for row in before_second], ["r1"])

    def test_conflicting_reingestion_and_unsafe_urls_are_rejected(self):
        first = article()
        changed = dict(first, body="A different article under the same revision.")
        with self.assertRaisesRegex(NewsEventError, "conflicting values"):
            normalize_news_documents([first, changed])
        with self.assertRaisesRegex(NewsEventError, "query strings"):
            normalize_news_documents([dict(article(), source_url="https://issuer.example/news?id=private")])
        with self.assertRaisesRegex(NewsEventError, "valid HTTP"):
            normalize_news_documents([dict(article(), source_url="https://[invalid-host")])

    def test_point_in_time_document_revision_and_system_ingestion(self):
        first = article(revision="r1", first_public="2026-10-05T09:00:00Z")
        second = article(
            revision="r2",
            first_public="2026-10-05T09:00:00Z",
            revision_public="2026-10-05T10:00:00Z",
            ingested="2026-10-05T10:05:00Z",
            body="Issuer corrects quarterly guidance.",
        )
        documents, _ = normalize_news_documents([first, second])
        before_correction = query_news_documents_as_of(documents, "2026-10-05T09:30:00Z", mode="source")
        after_correction = query_news_documents_as_of(documents, "2026-10-05T10:02:00Z", mode="source")
        before_system_ingest = query_news_documents_as_of(documents, "2026-10-05T10:02:00Z", mode="system")
        self.assertEqual([item["revision_id"] for item in before_correction], ["r1"])
        self.assertEqual([item["revision_id"] for item in after_correction], ["r2"])
        self.assertEqual([item["revision_id"] for item in before_system_ingest], ["r1"])

    def test_extraction_payload_is_limited_to_source_document(self):
        documents, _ = normalize_news_documents([article()])
        payload = build_extraction_payload(documents[0])
        self.assertIn("body", payload)
        self.assertNotIn("returns", payload)
        self.assertNotIn("price_bars", payload)
        self.assertNotIn("forward_return", payload)
        corrupted = dict(documents[0], content_sha256="0" * 64)
        with self.assertRaisesRegex(NewsEventError, "fingerprints"):
            build_extraction_payload(corrupted)


class NewsEventTests(unittest.TestCase):
    def test_exact_entity_mapping_and_ambiguity_are_explicit(self):
        catalog = build_entity_catalog(universe_fixture())
        snapshot = create_event_snapshot(
            normalize_news_documents([article()])[0][0],
            {"events": [dict(extraction()["events"][0], entity_mentions=["ALPHA-A", "Alpha Holdings", "NOT-LISTED"]) ]},
            entity_catalog=catalog,
            extraction_version="fixture-extractor-v1",
            extraction_model="synthetic-test-only",
            prompt_sha256="a" * 64,
            extraction_completed_at="2026-10-05T15:01:00Z",
            ingestion_time="2026-10-05T15:01:05Z",
        )
        entities = snapshot["events"][0]["entities"]
        self.assertEqual(entities[0]["match_status"], "MATCHED")
        self.assertFalse(entities[0]["platform_mapping_verified"])
        self.assertEqual(entities[1]["match_status"], "MATCHED")
        self.assertEqual(len(entities[1]["instrument_ids"]), 2)
        self.assertEqual(entities[2]["match_status"], "UNMAPPED")

    def test_extraction_cannot_smuggle_forward_returns_or_change_source_times(self):
        documents, _ = normalize_news_documents([article()])
        raw = extraction()
        raw["events"][0]["forward_return"] = "0.25"
        with self.assertRaisesRegex(NewsEventError, "unknown fields"):
            create_event_snapshot(
                documents[0], raw,
                entity_catalog=build_entity_catalog(universe_fixture()),
                extraction_version="fixture-extractor-v1",
                extraction_model="synthetic-test-only",
                prompt_sha256="a" * 64,
                extraction_completed_at="2026-10-05T15:01:00Z",
                ingestion_time="2026-10-05T15:01:05Z",
            )
        with self.assertRaisesRegex(NewsEventError, "cannot precede source revision"):
            create_event_snapshot(
                documents[0], extraction(),
                entity_catalog=build_entity_catalog(universe_fixture()),
                extraction_version="fixture-extractor-v1",
                extraction_model="synthetic-test-only",
                prompt_sha256="a" * 64,
                extraction_completed_at="2026-10-05T14:59:00Z",
                ingestion_time="2026-10-05T15:01:05Z",
            )

    def test_event_snapshots_respect_feature_availability_and_revisions(self):
        earlier = make_snapshot()
        later_document = normalize_news_documents([
            article(
                revision="r2",
                first_public="2026-10-05T15:00:00Z",
                revision_public="2026-10-05T16:00:00Z",
                ingested="2026-10-05T16:00:05Z",
                body="Issuer corrects quarterly guidance.",
            )
        ])[0][0]
        later = create_event_snapshot(
            later_document,
            extraction(),
            entity_catalog=build_entity_catalog(universe_fixture()),
            extraction_version="fixture-extractor-v1",
            extraction_model="synthetic-test-only",
            prompt_sha256="a" * 64,
            extraction_completed_at="2026-10-05T16:01:00Z",
            ingestion_time="2026-10-05T16:01:05Z",
        )
        old_revision_document = normalize_news_documents([article()])[0][0]
        stale_reextraction = create_event_snapshot(
            old_revision_document,
            extraction(),
            entity_catalog=build_entity_catalog(universe_fixture()),
            extraction_version="fixture-extractor-v1",
            extraction_model="synthetic-test-only",
            prompt_sha256="a" * 64,
            extraction_completed_at="2026-10-05T16:02:00Z",
            ingestion_time="2026-10-05T16:02:05Z",
        )
        before = query_event_snapshots_as_of([earlier, later], "2026-10-05T15:30:00Z", mode="source")
        latest = query_event_snapshots_as_of([earlier, later], "2026-10-05T16:02:00Z", mode="source")
        despite_stale_reextraction = query_event_snapshots_as_of(
            [earlier, later, stale_reextraction], "2026-10-05T16:03:00Z", mode="source"
        )
        system = query_event_snapshots_as_of([earlier, later], "2026-10-05T16:01:02Z", mode="system")
        self.assertEqual([item["revision_id"] for item in before], ["r1"])
        self.assertEqual([item["revision_id"] for item in latest], ["r2"])
        self.assertEqual([item["revision_id"] for item in despite_stale_reextraction], ["r2"])
        self.assertEqual([item["revision_id"] for item in system], ["r1"])

    def test_digest_and_breaking_watch_use_explicit_timezone_and_watermark(self):
        snapshot = make_snapshot()
        with self.assertRaisesRegex(NewsEventError, "timezone"):
            build_intelligence_digest([snapshot], window_start="2026-10-05T14:00:00Z", as_of="2026-10-05T16:00:00Z", timezone_name="")
        digest = build_intelligence_digest(
            [snapshot],
            window_start="2026-10-05T14:00:00Z",
            as_of="2026-10-05T16:00:00Z",
            timezone_name="America/Mexico_City",
            minimum_materiality="0.5",
            mode="system",
        )
        self.assertEqual(digest["timezone"], "America/Mexico_City")
        self.assertEqual(len(digest["events"]), 1)
        self.assertEqual(digest["events"][0]["local_feature_time"], "2026-10-05T09:01:00-06:00")
        correction_digest = build_intelligence_digest(
            [make_snapshot(), create_event_snapshot(
                normalize_news_documents([article(
                    revision="r2",
                    first_public="2026-10-05T15:00:00Z",
                    revision_public="2026-10-05T16:00:00Z",
                    ingested="2026-10-05T16:00:05Z",
                    body="Issuer corrects quarterly guidance.",
                )])[0][0],
                extraction(),
                entity_catalog=build_entity_catalog(universe_fixture()),
                extraction_version="fixture-extractor-v1",
                extraction_model="synthetic-test-only",
                prompt_sha256="a" * 64,
                extraction_completed_at="2026-10-05T16:01:00Z",
                ingestion_time="2026-10-05T16:01:05Z",
            )],
            window_start="2026-10-05T15:30:00Z",
            as_of="2026-10-05T16:02:00Z",
            timezone_name="America/Mexico_City",
            mode="system",
        )
        self.assertEqual(correction_digest["event_count"], 1)
        self.assertEqual(correction_digest["events"][0]["local_revision_public_time"], "2026-10-05T10:00:00-06:00")
        watch = watch_breaking_events(
            [snapshot],
            after_time="2026-10-05T15:00:00Z",
            after_event_id=None,
            as_of="2026-10-05T16:00:00Z",
            timezone_name="America/Mexico_City",
            minimum_materiality="0.5",
            mode="system",
        )
        self.assertEqual(len(watch["events"]), 1)

    def test_forward_return_labels_use_only_post_feature_price_bars(self):
        snapshot = make_snapshot()
        prices = []
        for index, (day, close) in enumerate(((5, "100"), (6, "102"), (7, "105"), (8, "107"))):
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
        labels = label_forward_returns(
            [snapshot], prices, horizon_sessions=2,
            label_as_of="2026-10-08T22:00:00Z", price_dataset_id="fixture-prices-v1", mode="system"
        )
        self.assertEqual(len(labels), 1)
        self.assertEqual(labels[0]["entry_bar_time"], "2026-10-05T21:00:00Z")
        self.assertEqual(labels[0]["exit_bar_time"], "2026-10-07T21:00:00Z")
        self.assertEqual(Decimal(labels[0]["forward_return"]), Decimal("0.05"))
        with self.assertRaisesRegex(NewsEventError, "insufficient post-event price bars"):
            label_forward_returns(
                [snapshot], prices[:1], horizon_sessions=2,
                label_as_of="2026-10-08T22:00:00Z", price_dataset_id="fixture-prices-v1", mode="system"
            )

    def test_labels_use_declared_pit_cutoff_and_deduplicate_copied_articles(self):
        snapshot = make_snapshot()
        duplicate_document, _ = normalize_news_documents([
            dict(article(), source_id="secondary_wire", document_id="wire-copy", source_quality="secondary_reputable")
        ])
        duplicate_snapshot = create_event_snapshot(
            duplicate_document[0],
            extraction(),
            entity_catalog=build_entity_catalog(universe_fixture()),
            extraction_version="fixture-extractor-v1",
            extraction_model="synthetic-test-only",
            prompt_sha256="a" * 64,
            extraction_completed_at="2026-10-05T15:02:00Z",
            ingestion_time="2026-10-05T15:02:05Z",
        )
        prices = []
        for day, close in ((5, "100"), (6, "102"), (7, "105"), (8, "107")):
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
        revision = dict(prices[2])
        revision["source_revision"] = "v2"
        revision["available_time"] = "2026-10-07T21:10:00Z"
        revision["ingestion_time"] = "2026-10-07T21:11:00Z"
        revision["payload"] = {"open": "110", "high": "110", "low": "110", "close": "110", "volume": "1000"}
        prices.append(revision)

        before_revision = label_forward_returns(
            [snapshot, duplicate_snapshot], prices, horizon_sessions=2,
            label_as_of="2026-10-07T21:05:00Z", price_dataset_id="fixture-prices-v1", mode="system"
        )
        after_revision = label_forward_returns(
            [snapshot, duplicate_snapshot], prices, horizon_sessions=2,
            label_as_of="2026-10-07T21:12:00Z", price_dataset_id="fixture-prices-v1", mode="system"
        )
        self.assertEqual(len(before_revision), 1)
        self.assertEqual(Decimal(before_revision[0]["forward_return"]), Decimal("0.05"))
        self.assertEqual(Decimal(after_revision[0]["forward_return"]), Decimal("0.1"))
        self.assertEqual(after_revision[0]["label_available_time"], "2026-10-07T21:11:00.000000Z")
        self.assertEqual(after_revision[0]["exit_record_id"], "bar-7")
        self.assertEqual(after_revision[0]["exit_source_revision"], "v2")
        self.assertEqual(len(after_revision[0]["label_id"]), 64)

    def test_oos_evaluation_reports_calibration_and_incremental_metrics(self):
        observations = []
        periods = {
            "train": ("2026-01-01T00:00:00Z", "2026-01-31T23:59:59Z"),
            "validation": ("2026-02-01T00:00:00Z", "2026-02-28T23:59:59Z"),
            "test": ("2026-03-01T00:00:00Z", "2026-03-31T23:59:59Z"),
        }
        for split, (start, _end) in periods.items():
            base_date = datetime.fromisoformat(start.replace("Z", "+00:00"))
            for index in range(10):
                decision = (base_date + timedelta(days=index)).isoformat().replace("+00:00", "Z")
                outcome = index % 2 == 0 if split != "test" else True
                observations.append({
                    "event_id": f"{split}-{index // 2}",
                    "event_group_id": f"group-{split}-{index // 2}",
                    "instrument_id": f"instrument-{index % 2}",
                    "decision_time": decision,
                    "label_available_time": (base_date + timedelta(days=index + 1)).isoformat().replace("+00:00", "Z"),
                    "split": split,
                    "forward_return": "0.02" if outcome else "-0.01",
                    "feature_available_time": (base_date + timedelta(days=index)).isoformat().replace("+00:00", "Z"),
                    "prediction_available_time": decision,
                    "label_id": f"label-{split}-{index}",
                    "event_probability": "0.8" if outcome or split == "test" else "0.2",
                })
        case = {
            "schema_version": 1,
            "evaluation_id": "M6_SYNTHETIC_EVAL",
            "target_definition": "gross_forward_return_gt_zero",
            "horizon_sessions": 1,
            "baseline_description": "training-sample unconditional event rate",
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
        result = evaluate_event_predictions(case)
        self.assertEqual(result["status_decision"], "NEEDS_MORE_EVIDENCE")
        self.assertEqual(result["test_metrics"]["event_count"], 10)
        self.assertEqual(result["training_baseline_probability"], "0.5")
        self.assertEqual(result["baseline_fit_split"], "train")
        self.assertEqual(result["test_metrics"]["positive_rate"], "1")
        self.assertLess(result["test_metrics"]["event_brier_score"], result["test_metrics"]["baseline_brier_score"])
        self.assertIn("expected_calibration_error", result["test_metrics"])

    def test_evaluator_rejects_features_unavailable_at_decision(self):
        observations = []
        periods = {
            "train": ("2026-01-01T00:00:00Z", "2026-01-31T23:59:59Z"),
            "validation": ("2026-02-01T00:00:00Z", "2026-02-28T23:59:59Z"),
            "test": ("2026-03-01T00:00:00Z", "2026-03-31T23:59:59Z"),
        }
        for split, (start, _end) in periods.items():
            base_date = datetime.fromisoformat(start.replace("Z", "+00:00"))
            for index in range(2):
                decision = base_date + timedelta(days=index)
                observations.append({
                    "event_id": f"{split}-{index}",
                    "event_group_id": f"group-{split}-{index}",
                    "instrument_id": f"instrument-{index % 2}",
                    "feature_available_time": (decision + timedelta(seconds=1)).isoformat().replace("+00:00", "Z"),
                    "prediction_available_time": decision,
                    "decision_time": decision.isoformat().replace("+00:00", "Z"),
                    "label_available_time": (decision + timedelta(days=1)).isoformat().replace("+00:00", "Z"),
                    "split": split,
                    "forward_return": "0.01",
                    "label_id": f"label-{split}-{index}",
                    "event_probability": "0.5",
                })
        case = {
            "schema_version": 1,
            "evaluation_id": "unavailable-feature",
            "target_definition": "gross_forward_return_gt_zero",
            "horizon_sessions": 1,
            "baseline_description": "train-only unconditional event rate",
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
        with self.assertRaisesRegex(NewsEventError, "not available at the decision time"):
            evaluate_event_predictions(case)
        for observation in observations:
            observation["feature_available_time"] = observation["decision_time"]
            decision = datetime.fromisoformat(observation["decision_time"].replace("Z", "+00:00"))
            observation["prediction_available_time"] = (decision + timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
        with self.assertRaisesRegex(NewsEventError, "predictions were not available at the decision time"):
            evaluate_event_predictions(case)

    def test_evaluator_rejects_test_selection_duplicate_groups_and_overlap(self):
        periods = {
            "train": ("2026-01-01T00:00:00Z", "2026-01-31T23:59:59Z"),
            "validation": ("2026-02-01T00:00:00Z", "2026-02-28T23:59:59Z"),
            "test": ("2026-03-01T00:00:00Z", "2026-03-31T23:59:59Z"),
        }
        case = {
            "schema_version": 1,
            "evaluation_id": "bad",
            "target_definition": "gross_forward_return_gt_zero",
            "horizon_sessions": 1,
            "baseline_description": "training only",
            "train_period": {"start": periods["train"][0], "end": periods["train"][1]},
            "validation_period": {"start": periods["validation"][0], "end": periods["validation"][1]},
            "test_period": {"start": periods["test"][0], "end": periods["test"][1]},
            "final_holdout_locked": True,
            "test_used_for_selection": True,
            "evidence": {
                "data_status": "synthetic_fixture",
                "source_availability_verified": False,
                "instrument_mapping_verified": False,
                "prices_authorized": False,
                "execution_costs_verified": False,
            },
            "observations": [
                {
                    "event_id": f"event-{split}",
                    "event_group_id": f"group-{split}",
                    "instrument_id": f"instrument-{split}",
                    "feature_available_time": start,
                    "prediction_available_time": start,
                    "decision_time": start,
                    "label_available_time": (datetime.fromisoformat(start.replace("Z", "+00:00")) + timedelta(days=1)).isoformat().replace("+00:00", "Z"),
                    "label_id": f"label-{split}",
                    "split": split,
                    "forward_return": "0.01",
                    "event_probability": "0.5",
                }
                for split, (start, _end) in periods.items()
            ],
        }
        with self.assertRaisesRegex(NewsEventError, "test holdout cannot be used for selection"):
            evaluate_event_predictions(case)
        case["test_used_for_selection"] = False
        case["validation_period"]["start"] = "2026-01-15T00:00:00Z"
        with self.assertRaisesRegex(NewsEventError, "chronological and non-overlapping"):
            evaluate_event_predictions(case)
        case["validation_period"]["start"] = periods["validation"][0]
        case["observations"][1]["event_group_id"] = case["observations"][0]["event_group_id"]
        with self.assertRaisesRegex(NewsEventError, "event groups cross train/validation"):
            evaluate_event_predictions(case)
        case["observations"][1]["event_group_id"] = "group-validation"
        case["observations"][1]["label_id"] = case["observations"][0]["label_id"]
        with self.assertRaisesRegex(NewsEventError, "duplicate label_id"):
            evaluate_event_predictions(case)


if __name__ == "__main__":
    unittest.main()
