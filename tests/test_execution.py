import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from actinver.execution import ExecutionError, simulate_execution
from actinver.m1 import load_rules, load_universe


ROOT = Path(__file__).resolve().parents[1]
RULES = load_rules(ROOT / "config/actinver_rules.yaml")
UNIVERSE = load_universe(ROOT / "data/metadata/actinver_universe_2026_v1.json")
INSTRUMENT = "actinver:2026:national_equity:ac"


def order(
    order_id="O1",
    *,
    side="buy",
    order_type="market",
    quantity=10,
    submitted_at="2026-10-05T09:00:00-06:00",
    expires_at="2026-10-05T10:00:00-06:00",
    sequence=1,
    limit_price=None,
    reference_price="100.00",
    instrument_id=INSTRUMENT,
):
    item = {
        "order_id": order_id,
        "instrument_id": instrument_id,
        "side": side,
        "order_type": order_type,
        "quantity": quantity,
        "submitted_at": submitted_at,
        "expires_at": expires_at,
        "sequence": sequence,
    }
    if limit_price is not None:
        item["limit_price_actipesos"] = limit_price
    if reference_price is not None:
        item["buying_power_reference_price_actipesos"] = reference_price
    return item


def market_trade(
    trade_id,
    *,
    traded_at="2026-10-05T09:01:00-06:00",
    sequence=2,
    price="100.00",
    instrument_id=INSTRUMENT,
):
    return {
        "trade_id": trade_id,
        "instrument_id": instrument_id,
        "traded_at": traded_at,
        "price_actipesos": price,
        "sequence": sequence,
        "source_id": "synthetic_fixture",
        "source_revision": "fixture-v1",
    }


def case(**updates):
    value = {
        "schema_version": 1,
        "simulation_start": "2026-10-05T08:00:00-06:00",
        "simulation_as_of": "2026-10-05T09:10:00-06:00",
        "initial_cash_actipesos": "1000000.00",
        "initial_positions": [],
        "prior_purchase_notional_actipesos": {},
        "prior_traded_share_ids": [],
        "orders": [],
        "market_trades": [],
        "cancellations": [],
        "market_data_dataset_id": "synthetic-fixture-m3-v1",
        "order_expiration_basis": "explicit_timestamp",
    }
    value.update(updates)
    return value


def simulate(value):
    return simulate_execution(value, RULES, UNIVERSE)


class ExecutionSimulationTests(unittest.TestCase):
    def test_market_and_limit_orders_create_exact_auditable_ledger(self):
        value = case(
            orders=[
                order(),
                order(
                    "O2",
                    side="sell",
                    order_type="limit",
                    quantity=4,
                    submitted_at="2026-10-05T09:00:30-06:00",
                    sequence=3,
                    limit_price="105.00",
                    reference_price=None,
                ),
            ],
            market_trades=[
                market_trade("T1", traded_at="2026-10-05T09:00:00-06:00", sequence=2),
                market_trade("T2", traded_at="2026-10-05T09:01:00-06:00", sequence=4, price="104.99"),
                market_trade("T3", traded_at="2026-10-05T09:02:00-06:00", sequence=5, price="105.00"),
            ],
        )
        result = simulate(value)
        states = {item["order_id"]: item for item in result["orders"]}
        fills = [item for item in result["ledger"] if item["event_type"] == "fill"]

        self.assertEqual(states["O1"]["status"], "FILLED")
        self.assertEqual(states["O2"]["status"], "FILLED")
        self.assertEqual([item["trade_id"] for item in fills], ["T1", "T3"])
        self.assertEqual(fills[0]["commission_actipesos"], "1")
        self.assertEqual(fills[0]["iva_actipesos"], "0.16")
        self.assertEqual(fills[1]["commission_actipesos"], "0.42")
        self.assertEqual(fills[1]["iva_actipesos"], "0.0672")
        self.assertEqual(result["balances"]["ending_cash_actipesos"], "999418.3528")
        self.assertEqual(result["positions"][0]["quantity"], 6)
        self.assertEqual(result["fees"]["total_commission_actipesos"], "1.42")
        self.assertEqual(result["fees"]["total_iva_actipesos"], "0.2272")

    def test_order_never_fills_on_a_trade_before_its_registration_sequence(self):
        value = case(
            orders=[order(submitted_at="2026-10-05T09:00:00-06:00", sequence=2)],
            market_trades=[
                market_trade("T1", traded_at="2026-10-05T09:00:00-06:00", sequence=1)
            ],
        )
        result = simulate(value)
        self.assertEqual(result["orders"][0]["status"], "PENDING")
        self.assertEqual(result["orders"][0]["filled_quantity"], 0)

    def test_limit_order_requires_an_exact_post_registration_trade_price(self):
        value = case(
            orders=[order(order_type="limit", limit_price="100.00", reference_price=None)],
            market_trades=[
                market_trade("T1", sequence=2, price="99.99"),
                market_trade("T2", sequence=3, price="100.00", traded_at="2026-10-05T09:02:00-06:00"),
            ],
        )
        result = simulate(value)
        self.assertEqual(result["orders"][0]["fill_trade_id"], "T2")
        self.assertEqual(result["orders"][0]["fill_price_actipesos"], "100")

    def test_pending_buy_reservations_include_commission_and_iva(self):
        value = case(
            initial_cash_actipesos="10000",
            simulation_as_of="2026-10-05T09:02:00-06:00",
            orders=[
                order("O1", order_type="limit", quantity=8, limit_price="100", reference_price=None),
                order(
                    "O2",
                    order_type="limit",
                    quantity=92,
                    limit_price="100",
                    reference_price=None,
                    submitted_at="2026-10-05T09:01:00-06:00",
                    sequence=2,
                ),
            ],
        )
        result = simulate(value)
        states = {item["order_id"]: item for item in result["orders"]}
        self.assertEqual(states["O1"]["status"], "PENDING")
        self.assertEqual(states["O2"]["status"], "REJECTED_INSUFFICIENT_BUYING_POWER")
        self.assertEqual(result["balances"]["reserved_buying_power_actipesos"], "800.928")
        self.assertEqual(result["balances"]["available_buying_power_actipesos"], "9199.072")

    def test_cancel_releases_reservation_and_filled_order_cannot_be_cancelled(self):
        value = case(
            initial_cash_actipesos="20000",
            simulation_as_of="2026-10-05T09:04:00-06:00",
            orders=[
                order("O1", order_type="limit", quantity=100, limit_price="100", reference_price=None),
                order(
                    "O2",
                    quantity=95,
                    submitted_at="2026-10-05T09:02:00-06:00",
                    sequence=4,
                    expires_at="2026-10-05T09:10:00-06:00",
                ),
            ],
            cancellations=[
                {"order_id": "O1", "cancelled_at": "2026-10-05T09:01:00-06:00", "sequence": 2},
                {"order_id": "O2", "cancelled_at": "2026-10-05T09:04:00-06:00", "sequence": 6},
            ],
            market_trades=[
                market_trade("T1", traded_at="2026-10-05T09:03:00-06:00", sequence=5)
            ],
        )
        result = simulate(value)
        states = {item["order_id"]: item for item in result["orders"]}
        cancellations = [item for item in result["ledger"] if item["event_type"] == "order_cancellation"]
        self.assertEqual(states["O1"]["status"], "CANCELLED")
        self.assertEqual(states["O2"]["status"], "FILLED")
        self.assertEqual(cancellations[1]["status"], "CANCEL_REJECTED_FILLED_ORDER")
        self.assertEqual(result["balances"]["ending_cash_actipesos"], "10488.98")

    def test_expiry_precedes_later_market_trade_and_releases_reservation(self):
        value = case(
            simulation_as_of="2026-10-05T09:32:00-06:00",
            orders=[order(expires_at="2026-10-05T09:30:00-06:00")],
            market_trades=[market_trade("T1", traded_at="2026-10-05T09:31:00-06:00", sequence=2)],
        )
        result = simulate(value)
        self.assertEqual(result["orders"][0]["status"], "EXPIRED")
        self.assertEqual(result["orders"][0]["filled_quantity"], 0)
        self.assertEqual(result["balances"]["reserved_buying_power_actipesos"], "0")
        self.assertEqual(result["balances"]["available_buying_power_actipesos"], "1000000")

    def test_sales_cannot_exceed_unreserved_inventory_and_no_short_is_possible(self):
        value = case(
            initial_cash_actipesos="0",
            initial_positions=[
                {
                    "instrument_id": INSTRUMENT,
                    "quantity": 5,
                    "mark_price_actipesos": "100",
                    "marked_at": "2026-10-05T08:00:00-06:00",
                }
            ],
            orders=[
                order("O1", side="sell", quantity=6, sequence=1, reference_price=None),
                order("O2", side="sell", quantity=5, sequence=2, reference_price=None),
                order("O3", side="sell", quantity=1, sequence=3, reference_price=None),
            ],
            market_trades=[market_trade("T1", sequence=4)],
        )
        result = simulate(value)
        states = {item["order_id"]: item for item in result["orders"]}
        self.assertEqual(states["O1"]["status"], "REJECTED_INSUFFICIENT_HOLDINGS")
        self.assertEqual(states["O2"]["status"], "FILLED")
        self.assertEqual(states["O3"]["status"], "REJECTED_INSUFFICIENT_HOLDINGS")
        self.assertEqual(result["positions"][0]["quantity"], 0)
        self.assertEqual(result["balances"]["ending_cash_actipesos"], "499.42")

    def test_eligibility_concentration_is_reported_separately_from_order_execution(self):
        value = case(
            orders=[order(quantity=6000)],
            market_trades=[market_trade("T1", sequence=2)],
        )
        result = simulate(value)
        self.assertEqual(result["orders"][0]["status"], "FILLED")
        self.assertEqual(result["eligibility_checks"]["status"], "NON_COMPLIANT")
        self.assertGreater(float(result["eligibility_checks"]["maximum_current_instrument_weight"]), 0.5)

    def test_rejects_non_session_trades_and_post_competition_orders(self):
        holiday_case = case(
            simulation_start="2026-11-02T08:00:00-06:00",
            simulation_as_of="2026-11-02T10:00:00-06:00",
            market_trades=[
                market_trade("T1", traded_at="2026-11-02T09:00:00-06:00", sequence=1)
            ],
        )
        with self.assertRaisesRegex(ExecutionError, "non-session"):
            simulate(holiday_case)

        after_close = case(
            orders=[
                order(
                    submitted_at="2026-11-13T15:01:00-06:00",
                    expires_at="2026-11-13T15:02:00-06:00",
                )
            ],
            simulation_as_of="2026-11-13T15:02:00-06:00",
        )
        with self.assertRaisesRegex(ExecutionError, "competition cutoff"):
            simulate(after_close)

        outside_window = case(
            simulation_start="2026-10-04T08:00:00-06:00",
            simulation_as_of="2026-10-04T09:00:00-06:00",
        )
        with self.assertRaisesRegex(ExecutionError, "simulation_start.*competition dates"):
            simulate(outside_window)

        after_competition = case(
            simulation_as_of="2026-11-13T15:01:00-06:00",
        )
        with self.assertRaisesRegex(ExecutionError, "simulation_as_of.*competition cutoff"):
            simulate(after_competition)

    def test_prior_traded_shares_carry_forward_for_eligibility_count(self):
        share_ids = [
            item["instrument_id"]
            for item in UNIVERSE["instruments"]
            if item["category"] in {"national_equity", "sic_equity"}
        ][:5]
        result = simulate(case(prior_traded_share_ids=share_ids))
        self.assertEqual(result["eligibility_checks"]["distinct_traded_share_count"], 5)
        self.assertEqual(
            result["eligibility_checks"]["minimum_distinct_share_requirement"],
            "POTENTIALLY_MET",
        )

        non_share_id = next(
            item["instrument_id"]
            for item in UNIVERSE["instruments"]
            if item["category"] not in {"national_equity", "sic_equity"}
        )
        with self.assertRaisesRegex(ExecutionError, "is not a share"):
            simulate(case(prior_traded_share_ids=[non_share_id]))

    def test_requires_timezone_exact_decimal_inputs_and_explicit_expiry_basis(self):
        naive = case(orders=[order(submitted_at="2026-10-05T09:00:00")])
        with self.assertRaisesRegex(ExecutionError, "UTC offset"):
            simulate(naive)

        binary_float = case(market_trades=[market_trade("T1", price=100.0)])
        with self.assertRaisesRegex(ExecutionError, "exact decimal"):
            simulate(binary_float)

        ambiguous_expiry = case(order_expiration_basis="unspecified")
        with self.assertRaisesRegex(ExecutionError, "explicit_timestamp"):
            simulate(ambiguous_expiry)

    def test_simulation_is_deterministic_and_marks_platform_mapping_unverified(self):
        value = case(
            orders=[order()],
            market_trades=[market_trade("T1", sequence=2)],
        )
        first = simulate(value)
        second = simulate(copy.deepcopy(value))
        self.assertEqual(first, second)
        self.assertEqual(first["orders"][0]["instrument_mapping_status"], "UNVERIFIED")
        self.assertEqual(first["eligibility_checks"]["status"], "NON_COMPLIANT")

    def test_cli_writes_provenance_and_refuses_to_overwrite_a_result(self):
        value = case(
            orders=[order()],
            market_trades=[market_trade("T1", sequence=2)],
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "case.json"
            output_path = root / "result.json"
            input_path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
            command = [
                sys.executable,
                "-m",
                "actinver.execution_cli",
                "simulate",
                "--input",
                str(input_path),
                "--output",
                str(output_path),
                "--code-commit-sha",
                "a" * 40,
            ]
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(result["run_provenance"]["code_commit_sha"], "a" * 40)
            self.assertEqual(
                result["run_provenance"]["input_sha256"],
                hashlib.sha256(input_path.read_bytes()).hexdigest(),
            )
            repeated = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(repeated.returncode, 2)
            self.assertIn("Refusing to overwrite", repeated.stderr)

    def test_case_and_result_match_versioned_schema_contracts(self):
        case_schema = json.loads((ROOT / "schemas/execution_case.schema.json").read_text(encoding="utf-8"))
        result_schema = json.loads((ROOT / "schemas/execution_result.schema.json").read_text(encoding="utf-8"))
        sample = case()
        result = simulate(sample)
        self.assertTrue(set(case_schema["required"]).issubset(sample))
        self.assertTrue(set(result_schema["required"]).issubset(result))
        self.assertFalse(set(sample) - set(case_schema["properties"]))
        self.assertFalse(set(result) - set(result_schema["properties"]))


if __name__ == "__main__":
    unittest.main()
