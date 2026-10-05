import json
import re
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from html import unescape
from pathlib import Path

from actinver.m1 import (
    M1DataError,
    bmv_trading_day_status,
    diff_rules,
    diff_universes,
    eligible_instruments,
    load_rules,
    load_universe,
    validate_order,
    validate_portfolio,
    verify_source_material,
    verify_rule_source_material,
)


ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "config/actinver_rules.yaml"
UNIVERSE = ROOT / "data/metadata/actinver_universe_2026_v1.json"


class M1SnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = load_rules(RULES)
        cls.universe = load_universe(UNIVERSE)
        cls.by_symbol = {item["guide_symbol"]: item for item in cls.universe["instruments"]}

    def test_raw_material_fingerprints_and_reproducible_generator(self):
        verify_source_material(self.universe, ROOT)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "universe.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/build_universe_snapshot.py"),
                    "--verified-at-utc",
                    self.universe["observed_at_utc"],
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), self.universe)

    def test_official_annex_counts_and_pit_window(self):
        self.assertEqual(
            self.universe["observed_counts"],
            {
                "national_equity": 40,
                "sic_equity": 100,
                "fund": 23,
                "etf": 40,
                "fibra": 4,
                "total": 207,
            },
        )
        self.assertEqual(len(eligible_instruments(self.universe, "2026-10-05")), 207)
        self.assertEqual(eligible_instruments(self.universe, "2026-10-04"), [])
        self.assertEqual(eligible_instruments(self.universe, "2026-11-14"), [])

    def test_unresolved_platform_symbols_and_fibra_conflict_are_explicit(self):
        self.assertTrue(all(item["platform_symbol"] is None for item in self.universe["instruments"]))
        fib_records = [item for item in self.universe["instruments"] if item["category"] == "fibra"]
        self.assertEqual(len(fib_records), 4)
        self.assertTrue(all(item["eligibility"]["rulebook_category_conflict"] for item in fib_records))

    def test_cost_rate_and_sources_are_validated(self):
        self.assertEqual(self.rules["rules"]["costs"]["effective_rate"], 0.00116)
        broken = dict(self.rules)
        broken["rules"] = dict(self.rules["rules"])
        broken["rules"]["costs"] = dict(self.rules["rules"]["costs"])
        broken["rules"]["costs"]["effective_rate"] = 0.001
        with self.assertRaises(M1DataError):
            from actinver.m1 import validate_rules

            validate_rules(broken)

    def test_rule_source_capture_fingerprint_is_verified(self):
        verify_rule_source_material(self.rules, ROOT)
        source_index = next(
            index
            for index, source in enumerate(self.rules["sources"])
            if source.get("repository_snapshot_path")
        )
        with tempfile.TemporaryDirectory() as directory:
            changed_file = Path(directory) / "changed.html"
            changed_file.write_text("altered source", encoding="utf-8")
            altered = dict(self.rules)
            altered["sources"] = [dict(item) for item in self.rules["sources"]]
            altered["sources"][source_index]["repository_snapshot_path"] = str(changed_file)
            with self.assertRaises(M1DataError):
                verify_rule_source_material(altered, ROOT)

    def test_bmv_holiday_weekend_coverage_and_session_status(self):
        self.assertEqual(len(self.rules["rules"]["market_calendar"]["holidays"]), 11)
        source_path = ROOT / "research/source_material/bmv_2026_holidays_official.html"
        source_text = source_path.read_text(encoding="utf-8", errors="replace")
        visible_text = " ".join(
            unescape(re.sub(r"<[^>]+>", " ", source_text)).split()
        ).casefold()
        month_names = (
            "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre"
        ).split()
        for holiday_row in self.rules["rules"]["market_calendar"]["holidays"]:
            holiday_date = date.fromisoformat(holiday_row["date"])
            expected = (
                re.escape(holiday_row["name"].casefold())
                + rf"\s+0?{holiday_date.day}\s+de\s+{month_names[holiday_date.month - 1]}"
            )
            self.assertRegex(visible_text, expected)

        holiday = bmv_trading_day_status("2026-11-02", self.rules)
        self.assertEqual(holiday["status"], "CLOSED")
        self.assertEqual(holiday["reason"], "BMV holiday: Día de muertos.")

        weekend = bmv_trading_day_status("2026-10-31", self.rules)
        self.assertEqual(weekend["status"], "CLOSED")

        regular = bmv_trading_day_status("2026-11-03", self.rules)
        self.assertEqual(regular["status"], "SCHEDULED_SESSION")
        self.assertTrue(regular["is_bmv_trading_day"])

        later_holiday = bmv_trading_day_status("2026-11-16", self.rules)
        self.assertEqual(later_holiday["status"], "CLOSED")

        uncovered = bmv_trading_day_status("2027-01-04", self.rules)
        self.assertEqual(uncovered["status"], "UNKNOWN")
        self.assertIsNone(uncovered["is_bmv_trading_day"])

    def test_snapshot_diff_detects_added_removed_and_modified_records(self):
        before = {"snapshot_id": "before", "instruments": self.universe["instruments"][:2]}
        after = {
            "snapshot_id": "after",
            "instruments": [dict(self.universe["instruments"][0]), {"instrument_id": "added"}],
        }
        after["instruments"][0]["issuer_or_name"] = "Changed name"
        result = diff_universes(before, after)
        self.assertEqual(result["added"], ["added"])
        self.assertEqual(result["removed"], [self.universe["instruments"][1]["instrument_id"]])
        self.assertEqual(len(result["modified"]), 1)

    def test_rules_diff_reports_changed_path(self):
        after = dict(self.rules)
        after["rules"] = dict(self.rules["rules"])
        after["rules"]["starting_capital_actipesos"] = 900000
        result = diff_rules(self.rules, after)
        self.assertIn("rules.starting_capital_actipesos", {item["path"] for item in result["changes"]})


class M1ConstraintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = load_rules(RULES)
        cls.universe = load_universe(UNIVERSE)
        cls.by_symbol = {item["guide_symbol"]: item for item in cls.universe["instruments"]}

    def test_limit_buy_checks_eligibility_fees_cash_and_concentration(self):
        record = self.by_symbol["AC"]
        result = validate_order(
            {
                "instrument_id": record["instrument_id"],
                "side": "buy",
                "quantity": 10,
                "order_type": "limit",
                "limit_price_actipesos": 100,
            },
            {
                "portfolio_value_actipesos": 1000000,
                "available_buying_power_actipesos": 250000,
                "holdings": [],
            },
            self.rules,
            self.universe,
            "2026-10-05",
        )
        self.assertEqual(result["constraint_status"], "COMPLIANT")
        self.assertEqual(result["operability_status"], "UNVERIFIED")
        self.assertEqual(result["official_award_eligibility_status"], "INDETERMINATE")
        self.assertEqual(result["estimated_gross_actipesos"], "1000")
        self.assertEqual(result["estimated_fee_actipesos"], "1.16000")

    def test_buy_above_available_buying_power_fails(self):
        record = self.by_symbol["AC"]
        result = validate_order(
            {
                "instrument_id": record["instrument_id"],
                "side": "buy",
                "quantity": 1000,
                "order_type": "limit",
                "limit_price_actipesos": 100,
            },
            {
                "portfolio_value_actipesos": 1000000,
                "available_buying_power_actipesos": 100000,
                "holdings": [],
            },
            self.rules,
            self.universe,
            "2026-10-05",
        )
        self.assertEqual(result["constraint_status"], "NON_COMPLIANT")
        self.assertEqual(
            next(item["status"] for item in result["checks"] if item["check_id"] == "buying_power"),
            "FAIL",
        )

    def test_sell_cannot_exceed_current_quantity(self):
        record = self.by_symbol["AC"]
        result = validate_order(
            {
                "instrument_id": record["instrument_id"],
                "side": "sell",
                "quantity": 4,
                "order_type": "market",
                "reference_price_actipesos": 100,
            },
            {
                "portfolio_value_actipesos": 1000000,
                "holdings": [
                    {"instrument_id": record["instrument_id"], "quantity": 3, "market_value_actipesos": 300}
                ],
            },
            self.rules,
            self.universe,
            "2026-10-05",
        )
        self.assertEqual(result["constraint_status"], "NON_COMPLIANT")
        self.assertIn("no_short_sale", {item["check_id"] for item in result["checks"]})

    def test_unknown_market_price_is_indeterminate(self):
        record = self.by_symbol["AC"]
        result = validate_order(
            {
                "instrument_id": record["instrument_id"],
                "side": "buy",
                "quantity": 1,
                "order_type": "market",
            },
            {"available_buying_power_actipesos": 1000, "portfolio_value_actipesos": 1000, "holdings": []},
            self.rules,
            self.universe,
            "2026-10-05",
        )
        self.assertEqual(result["constraint_status"], "INDETERMINATE")

    def test_fibra_is_guide_listed_but_rulebook_status_is_indeterminate(self):
        record = self.by_symbol["FUNO"]
        result = validate_order(
            {
                "instrument_id": record["instrument_id"],
                "side": "buy",
                "quantity": 1,
                "order_type": "limit",
                "limit_price_actipesos": 100,
            },
            {"available_buying_power_actipesos": 1000, "portfolio_value_actipesos": 1000, "holdings": []},
            self.rules,
            self.universe,
            "2026-10-05",
        )
        self.assertEqual(result["constraint_status"], "INDETERMINATE")
        self.assertEqual(result["operability_status"], "UNVERIFIED")

    def test_outside_competition_window_fails(self):
        record = self.by_symbol["AC"]
        result = validate_order(
            {"instrument_id": record["instrument_id"], "side": "buy", "quantity": 1, "order_type": "limit", "limit_price_actipesos": 1},
            {"available_buying_power_actipesos": 1000, "portfolio_value_actipesos": 1000, "holdings": []},
            self.rules,
            self.universe,
            "2026-11-14",
        )
        self.assertEqual(result["constraint_status"], "NON_COMPLIANT")

    def _valid_portfolio(self):
        records = [self.by_symbol[symbol] for symbol in ("AC", "ACTINVR", "ALFA", "ALPEK", "ALSEA")]
        ids = [record["instrument_id"] for record in records]
        return {
            "portfolio_value_actipesos": 1000000,
            "holdings": [
                {"instrument_id": instrument_id, "quantity": 1, "market_value_actipesos": 100000}
                for instrument_id in ids
            ],
            "traded_instrument_ids": ids,
            "cumulative_purchase_value_actipesos_by_instrument": {
                instrument_id: 100000 for instrument_id in ids
            },
        }

    def test_portfolio_satisfying_both_conservative_interpretations(self):
        result = validate_portfolio(self._valid_portfolio(), self.rules, self.universe, "2026-10-05")
        self.assertEqual(result["constraint_status"], "COMPLIANT")
        self.assertEqual(result["official_award_eligibility_status"], "INDETERMINATE")

    def test_portfolio_fails_if_only_four_shares_were_traded(self):
        portfolio = self._valid_portfolio()
        portfolio["traded_instrument_ids"] = portfolio["traded_instrument_ids"][:4]
        result = validate_portfolio(portfolio, self.rules, self.universe, "2026-10-05")
        self.assertEqual(result["constraint_status"], "NON_COMPLIANT")
        minimum = next(item for item in result["checks"] if item["check_id"] == "minimum_distinct_traded_shares")
        self.assertEqual(minimum["status"], "FAIL")

    def test_portfolio_over_concentration_cap_fails(self):
        portfolio = self._valid_portfolio()
        portfolio["holdings"][0]["market_value_actipesos"] = 600000
        portfolio["cumulative_purchase_value_actipesos_by_instrument"][portfolio["holdings"][0]["instrument_id"]] = 600000
        result = validate_portfolio(portfolio, self.rules, self.universe, "2026-10-05")
        self.assertEqual(result["constraint_status"], "NON_COMPLIANT")

    def test_missing_trade_history_is_indeterminate(self):
        ids = [
            self.by_symbol[symbol]["instrument_id"]
            for symbol in ("AC", "ACTINVR", "ALFA", "ALPEK", "ALSEA")
        ]
        result = validate_portfolio(
            {
                "portfolio_value_actipesos": 1000000,
                "holdings": [
                    {"instrument_id": instrument_id, "quantity": 1, "market_value_actipesos": 100000}
                    for instrument_id in ids
                ],
            },
            self.rules,
            self.universe,
            "2026-10-05",
        )
        self.assertEqual(result["constraint_status"], "INDETERMINATE")
        minimum = next(item for item in result["checks"] if item["check_id"] == "minimum_distinct_traded_shares")
        self.assertEqual(minimum["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
