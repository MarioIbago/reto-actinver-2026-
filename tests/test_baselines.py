from datetime import date, timedelta
from decimal import Decimal
import unittest

from actinver.baselines import BASELINE_NAMES, BaselineError, build_baseline_weights


def weekdays(start: date, count: int) -> list[date]:
    result = []
    current = start
    while len(result) < count:
        if current.weekday() < 5:
            result.append(current)
        current += timedelta(days=1)
    return result


def price_bar(instrument_id, event_day, close, *, volume="100", high=None, low=None, available=None, ingestion=None):
    close = Decimal(str(close))
    high = Decimal(str(high)) if high is not None else close + Decimal(1)
    low = Decimal(str(low)) if low is not None else close - Decimal(1)
    event = f"{event_day.isoformat()}T22:00:00Z"
    available = available or f"{event_day.isoformat()}T22:10:00Z"
    ingestion = ingestion or f"{event_day.isoformat()}T22:20:00Z"
    return {
        "record_id": f"{instrument_id}-{event_day.isoformat()}",
        "instrument_id": instrument_id,
        "record_type": "price_bar",
        "event_time": event,
        "available_time": available,
        "ingestion_time": ingestion,
        "payload": {
            "open": str(close),
            "high": str(high),
            "low": str(low),
            "close": str(close),
            "volume": volume,
        },
    }


class BaselineSignalTests(unittest.TestCase):
    def setUp(self):
        self.days = weekdays(date(2025, 1, 1), 25)
        self.records = []
        for index, event_day in enumerate(self.days):
            self.records.append(price_bar("A", event_day, 100 + 2 * index, volume="10000" if index == 24 else "100"))
            self.records.append(price_bar("B", event_day, 200 - index, volume="100"))
            self.records.append(price_bar("BMK", event_day, 100 + index // 4, volume="1000"))
        last = self.days[-1]
        self.records = [
            row for row in self.records
            if not (row["instrument_id"] == "A" and row["event_time"].startswith(last.isoformat()))
        ]
        self.records.append(
            price_bar("A", last, 150, volume="10000", high="160", low="120")
        )
        # C breaks the latest four highs but not the full five-session window.
        for offset, event_day in enumerate(self.days[-6:]):
            is_oldest = offset == 0
            is_current = offset == 5
            close = 100 if not is_current else 150
            self.records.append(
                price_bar(
                    "C",
                    event_day,
                    close,
                    high="300" if is_oldest else ("160" if is_current else "102"),
                    low="120" if is_current else "99",
                )
            )
        self.as_of = f"{last.isoformat()}T23:00:00Z"
        self.ids = ["A", "B", "BMK", "NO_DATA"]

    def build(self, name, **kwargs):
        return build_baseline_weights(
            name,
            self.records,
            as_of=self.as_of,
            universe_instrument_ids=self.ids,
            lookback_sessions=5,
            **kwargs,
        )

    def test_all_required_baseline_families_are_registered(self):
        self.assertEqual(
            set(BASELINE_NAMES),
            {
                "random_control", "equal_weight", "benchmark", "momentum",
                "relative_strength", "abnormal_volume", "reversal",
                "breakout_volatility_expansion",
            },
        )

    def test_equal_weight_random_and_benchmark_are_deterministic_and_normalized(self):
        equal = self.build("equal_weight")
        self.assertEqual(set(equal), {"A", "B", "BMK"})
        self.assertEqual(sum(equal.values()), Decimal(1))
        first = self.build("random_control", seed=73)
        second = self.build("random_control", seed=73)
        self.assertEqual(first, second)
        self.assertEqual(sum(first.values()), Decimal(1))
        next_cutoff_weights = build_baseline_weights(
            "random_control",
            self.records,
            as_of=f"{(self.days[-1] + timedelta(days=1)).isoformat()}T23:00:00Z",
            universe_instrument_ids=self.ids,
            lookback_sessions=5,
            seed=73,
        )
        self.assertNotEqual(first, next_cutoff_weights)
        self.assertEqual(self.build("benchmark", benchmark_instrument_id="BMK"), {"BMK": Decimal(1)})

    def test_momentum_relative_strength_and_reversal_use_prior_visible_bars(self):
        self.assertIn("A", self.build("momentum"))
        self.assertNotIn("B", self.build("momentum"))
        self.assertIn("A", self.build("relative_strength", benchmark_instrument_id="BMK"))
        reversal = self.build("reversal")
        self.assertIn("B", reversal)
        self.assertNotIn("A", reversal)

    def test_volume_and_breakout_baselines_detect_only_the_declared_cross_section(self):
        volume = self.build("abnormal_volume")
        self.assertEqual(set(volume), {"A"})
        breakout = self.build("breakout_volatility_expansion")
        self.assertEqual(set(breakout), {"A"})
        self.assertNotIn("C", breakout)

    def test_future_or_unpublished_bars_are_not_visible(self):
        future = price_bar(
            "B",
            self.days[-1] + timedelta(days=1),
            10000,
            available=f"{(self.days[-1] + timedelta(days=1)).isoformat()}T22:10:00Z",
            ingestion=f"{(self.days[-1] + timedelta(days=1)).isoformat()}T22:20:00Z",
        )
        weights_before = self.build("equal_weight")
        weights_after = build_baseline_weights(
            "equal_weight",
            self.records + [future],
            as_of=self.as_of,
            universe_instrument_ids=self.ids,
        )
        self.assertEqual(weights_before, weights_after)

    def test_source_and_system_as_of_modes_use_their_own_availability_times(self):
        day = self.days[0]
        row = price_bar(
            "LATE",
            day,
            10,
            available=f"{day.isoformat()}T22:10:00Z",
            ingestion=f"{day.isoformat()}T23:10:00Z",
        )
        kwargs = {
            "as_of": f"{day.isoformat()}T22:30:00Z",
            "universe_instrument_ids": ["LATE"],
        }
        self.assertEqual(build_baseline_weights("equal_weight", [row], as_of_mode="source", **kwargs), {"LATE": Decimal(1)})
        self.assertEqual(build_baseline_weights("equal_weight", [row], as_of_mode="system", **kwargs), {})

    def test_rejects_unknown_baseline_bad_inputs_and_naive_cutoff(self):
        with self.assertRaisesRegex(BaselineError, "Unknown baseline"):
            self.build("sentiment")
        with self.assertRaisesRegex(BaselineError, "UTC offset"):
            build_baseline_weights("equal_weight", [], as_of="2025-01-01T00:00:00", universe_instrument_ids=["A"])
        broken = dict(self.records[0])
        broken["payload"] = dict(broken["payload"], close=100.0)
        with self.assertRaisesRegex(BaselineError, "exact decimal"):
            build_baseline_weights("equal_weight", [broken], as_of=self.as_of, universe_instrument_ids=["A"])
        impossible_availability = dict(self.records[0], available_time="2024-12-31T00:00:00Z")
        with self.assertRaisesRegex(BaselineError, "precedes the bar event"):
            build_baseline_weights(
                "equal_weight", [impossible_availability], as_of=self.as_of, universe_instrument_ids=["A"]
            )
        with self.assertRaisesRegex(BaselineError, "benchmark_instrument_id is required"):
            self.build("benchmark")


if __name__ == "__main__":
    unittest.main()
