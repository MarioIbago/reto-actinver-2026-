import json
from pathlib import Path
import tempfile
import unittest

from scripts.validate_order_memo import (
    WATCHLIST,
    MemoValidationError,
    bundle_memo,
    validate_memo,
)


def memo_fixture(session_date="2026-10-06"):
    return {
        "schema_version": 1,
        "memo_id": f"ACTINVER-WATCHLIST-{session_date}",
        "for_session_date": session_date,
        "prepared_at_utc": "2026-10-05T21:30:00Z",
        "decision_status": "NO_TRADE",
        "execution_policy": "MANUAL_ONLY",
        "actinver_order_entry_enabled": False,
        "portfolio_state_verified": False,
        "orders": [],
        "sources": [{"title": "Primary source", "url": "https://issuer.example/ir"}],
        "watchlist": [
            {
                "ticker": ticker,
                "name": ticker,
                "status": "NO_TRADE",
                "actinver_identity_verified": False,
                "watch_condition": "Wait for verified data and a confirmed setup.",
                "source_urls": ["https://issuer.example/ir"],
                "quote": {
                    "price": 10.0,
                    "observed_at_local": "2026-10-05T15:00:00-06:00",
                    "source_url": "https://finance.example/quote",
                    "actionable": False,
                },
            }
            for ticker in sorted(WATCHLIST)
        ],
    }


class OrderMemoTests(unittest.TestCase):
    def test_valid_no_trade_memo_covers_the_fixed_watchlist(self):
        validated = validate_memo(memo_fixture(), expected_date="2026-10-06")
        self.assertEqual(validated["decision_status"], "NO_TRADE")
        self.assertEqual({item["ticker"] for item in validated["watchlist"]}, WATCHLIST)

    def test_rejects_any_order_or_non_no_trade_decision(self):
        with self.assertRaisesRegex(MemoValidationError, "orders must be an empty list"):
            validate_memo({**memo_fixture(), "orders": [{"ticker": "BA", "side": "BUY"}]})
        with self.assertRaisesRegex(MemoValidationError, "must remain NO_TRADE"):
            validate_memo({**memo_fixture(), "decision_status": "BUY"})

    def test_rejects_wrong_date_and_path_like_date(self):
        with self.assertRaisesRegex(MemoValidationError, "does not match requested date"):
            validate_memo(memo_fixture(), expected_date="2026-10-07")
        with self.assertRaisesRegex(MemoValidationError, "YYYY-MM-DD"):
            validate_memo({**memo_fixture(), "for_session_date": "../memo"})
        with self.assertRaisesRegex(MemoValidationError, "memo_id must match"):
            validate_memo({**memo_fixture(), "memo_id": "ACTINVER-WATCHLIST-2026-10-07"})

    def test_rejects_incomplete_universe_duplicate_ticker_or_unverified_quote_claim(self):
        memo = memo_fixture()
        with self.assertRaisesRegex(MemoValidationError, "exactly 16 instruments"):
            validate_memo({**memo, "watchlist": memo["watchlist"][:-1]})
        duplicate = memo_fixture()
        duplicate["watchlist"][-1]["ticker"] = duplicate["watchlist"][0]["ticker"]
        with self.assertRaisesRegex(MemoValidationError, "duplicate watchlist ticker"):
            validate_memo(duplicate)
        actionable = memo_fixture()
        actionable["watchlist"][0]["quote"]["actionable"] = True
        with self.assertRaisesRegex(MemoValidationError, "non-actionable"):
            validate_memo(actionable)

    def test_bundles_selected_memo_and_appends_github_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            memo_dir = root / "reports" / "order_memos" / "2026-10-06"
            memo_dir.mkdir(parents=True)
            report_relative = Path("reports/intraday/2026-10-05_review.md")
            research_report = root / report_relative
            research_report.parent.mkdir(parents=True)
            research_report.write_text("# Research report\n", encoding="utf-8")
            memo = memo_fixture()
            memo["research"] = {"comparison_report": report_relative.as_posix()}
            (memo_dir / "memo.json").write_text(json.dumps(memo), encoding="utf-8")
            (memo_dir / "memo.md").write_text(
                "# Manual memo\n\nNO_TRADE. Órdenes: 0.\n", encoding="utf-8"
            )
            output = root / "bundle"
            summary = root / "github-summary.md"

            result = bundle_memo(
                root / "reports" / "order_memos",
                None,
                output,
                summary,
                repository_root=root,
            )

            self.assertEqual(result["order_count"], 0)
            self.assertEqual(result["watchlist_count"], 16)
            self.assertTrue((output / "memo.json").is_file())
            self.assertTrue((output / "memo.md").is_file())
            self.assertTrue((output / report_relative).is_file())
            self.assertEqual(result["research_report"], report_relative.as_posix())
            self.assertIn(report_relative.as_posix(), (output / "summary.md").read_text(encoding="utf-8"))
            self.assertIn("Orders: **0**", (output / "summary.md").read_text(encoding="utf-8"))
            self.assertIn("MANUAL_ONLY", (output / "memo.json").read_text(encoding="utf-8"))
            self.assertTrue(summary.is_file())


if __name__ == "__main__":
    unittest.main()
