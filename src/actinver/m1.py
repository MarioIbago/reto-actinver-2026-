"""M1 rules and universe queries from versioned official-source snapshots."""

from __future__ import annotations

import json
import hashlib
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

import yaml


class M1DataError(ValueError):
    """Raised when a rules or universe snapshot is malformed or inconsistent."""


def _decimal(value: Any, field: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise M1DataError(f"{field} must be a finite non-negative number")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise M1DataError(f"{field} must be a finite non-negative number") from exc
    if not parsed.is_finite() or parsed < 0:
        raise M1DataError(f"{field} must be a finite non-negative number")
    return parsed


def _as_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise M1DataError(f"Invalid ISO date: {value!r}") from exc


def _combined_status(checks: list[dict[str, str]]) -> str:
    statuses = {item["status"] for item in checks}
    if "FAIL" in statuses:
        return "NON_COMPLIANT"
    if "UNKNOWN" in statuses:
        return "INDETERMINATE"
    return "COMPLIANT"


def load_rules(path: str | Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise M1DataError(f"Could not read YAML rules at {path}: {exc}") from exc
    validate_rules(value)
    return value


def validate_rules(rules: Any) -> None:
    if not isinstance(rules, dict) or rules.get("schema_version") != 1:
        raise M1DataError("Rules must be a schema_version 1 mapping")
    required = {"ruleset_id", "status", "verified_at_utc", "sources", "rules", "ambiguities"}
    missing = sorted(required - rules.keys())
    if missing:
        raise M1DataError(f"Rules missing required fields: {', '.join(missing)}")
    if not isinstance(rules["sources"], list) or not rules["sources"]:
        raise M1DataError("Rules must include at least one dated source")
    for source in rules["sources"]:
        if not isinstance(source, dict) or not all(
            source.get(field) for field in ("source_id", "url", "checked_at_utc")
        ):
            raise M1DataError("Each rules source needs source_id, url and checked_at_utc")
    values = rules["rules"]
    required_rules = {
        "starting_capital_actipesos",
        "short_selling_allowed",
        "allowed_order_sides",
        "allowed_order_types",
        "costs",
        "portfolio_constraints",
        "instrument_eligibility",
    }
    missing_rules = sorted(required_rules - values.keys())
    if missing_rules:
        raise M1DataError(f"Rules missing required constraints: {', '.join(missing_rules)}")
    if type(values["starting_capital_actipesos"]) is not int or values[
        "starting_capital_actipesos"
    ] <= 0:
        raise M1DataError("starting_capital_actipesos must be a positive integer")
    if values["short_selling_allowed"] is not False:
        raise M1DataError("The 2026 rules snapshot must disallow short selling")
    costs = values["costs"]
    commission = _decimal(costs.get("commission_rate"), "commission_rate")
    iva = _decimal(costs.get("iva_rate_on_commission"), "iva_rate_on_commission")
    effective = _decimal(costs.get("effective_rate"), "effective_rate")
    if commission * (Decimal(1) + iva) != effective:
        raise M1DataError("effective_rate must equal commission_rate * (1 + IVA)")
    constraints = values["portfolio_constraints"]
    for field in (
        "minimum_distinct_guide_instruments",
        "minimum_distinct_traded_shares",
    ):
        if type(constraints.get(field)) is not int or constraints[field] < 1:
            raise M1DataError(f"{field} must be a positive integer")
    cap = _decimal(constraints.get("maximum_single_instrument_weight"), "concentration cap")
    if cap > 1:
        raise M1DataError("maximum_single_instrument_weight cannot exceed 1")


def load_universe(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise M1DataError(f"Could not read universe JSON at {path}: {exc}") from exc
    validate_universe(value)
    return value


def validate_universe(universe: Any) -> None:
    if not isinstance(universe, dict) or universe.get("schema_version") != 1:
        raise M1DataError("Universe must be a schema_version 1 object")
    records = universe.get("instruments")
    if not isinstance(records, list):
        raise M1DataError("Universe instruments must be an array")
    expected = universe.get("expected_counts")
    observed = universe.get("observed_counts")
    if not isinstance(expected, dict) or not isinstance(observed, dict):
        raise M1DataError("Universe must include expected_counts and observed_counts")
    if len(records) != expected.get("total") or len(records) != observed.get("total"):
        raise M1DataError("Universe record count does not match snapshot counts")
    ids = [record.get("instrument_id") for record in records]
    if any(not isinstance(identifier, str) or not identifier for identifier in ids):
        raise M1DataError("Every universe record needs a non-empty instrument_id")
    if len(ids) != len(set(ids)):
        raise M1DataError("Universe instrument_id values must be unique")
    category_counts: dict[str, int] = {}
    for record in records:
        required = ("category", "guide_symbol", "issuer_or_name", "eligibility")
        if any(not record.get(field) for field in required):
            raise M1DataError("Every universe record needs category, guide_symbol, issuer and eligibility")
        category_counts[record["category"]] = category_counts.get(record["category"], 0) + 1
        if record["eligibility"].get("listed_in_official_2026_guide_annex") is not True:
            raise M1DataError(f"Record {record['instrument_id']} is not marked as guide-listed")
    for category, expected_count in expected.items():
        if category == "total":
            continue
        if category_counts.get(category, 0) != expected_count:
            raise M1DataError(f"Unexpected {category} count in universe snapshot")
        if observed.get(category) != category_counts[category]:
            raise M1DataError(f"Observed {category} count does not match records")


def eligible_instruments(universe: Mapping[str, Any], as_of: str | date) -> list[dict[str, Any]]:
    """Return records listed in the official guide annex and date-valid in the snapshot."""
    point = _as_date(as_of)
    eligible = []
    snapshot_start = _as_date(universe["effective_from"])
    snapshot_end = _as_date(universe["effective_to"]) if universe.get("effective_to") else None
    for instrument in universe["instruments"]:
        if _listed_on(instrument, point) and point >= snapshot_start and (
            snapshot_end is None or point <= snapshot_end
        ):
            eligible.append(instrument)
    return sorted(eligible, key=lambda item: item["instrument_id"])


def _listed_on(instrument: Mapping[str, Any], point: date) -> bool:
    window = instrument["eligibility"]
    start = _as_date(window["valid_from"])
    end = _as_date(window["valid_to"]) if window.get("valid_to") else None
    return bool(
        window.get("listed_in_official_2026_guide_annex")
        and start <= point
        and (end is None or point <= end)
    )


def verify_source_material(universe: Mapping[str, Any], repository_root: str | Path) -> None:
    """Check the normalized snapshot still fingerprints the untouched raw inputs."""
    root = Path(repository_root)
    source = universe.get("source", {})
    for path_field, digest_field in (
        ("repository_guide_snapshot", "repository_guide_snapshot_sha256"),
        ("repository_symbol_list_snapshot", "repository_symbol_list_sha256"),
    ):
        path = root / source.get(path_field, "")
        try:
            canonical_bytes = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            observed = hashlib.sha256(canonical_bytes).hexdigest()
        except OSError as exc:
            raise M1DataError(f"Could not verify source material {path}: {exc}") from exc
        if observed != source.get(digest_field):
            raise M1DataError(f"Source material changed since snapshot build: {path}")


def diff_universes(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    """Detect additions, removals and changed record fields between snapshots."""
    left = {record["instrument_id"]: record for record in before["instruments"]}
    right = {record["instrument_id"]: record for record in after["instruments"]}
    added = sorted(right.keys() - left.keys())
    removed = sorted(left.keys() - right.keys())
    modified = []
    for instrument_id in sorted(left.keys() & right.keys()):
        if left[instrument_id] != right[instrument_id]:
            modified.append(
                {
                    "instrument_id": instrument_id,
                    "before": left[instrument_id],
                    "after": right[instrument_id],
                }
            )
    return {
        "before_snapshot_id": before.get("snapshot_id"),
        "after_snapshot_id": after.get("snapshot_id"),
        "added": added,
        "removed": removed,
        "modified": modified,
    }


def diff_rules(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    """Return leaf-path changes between two rulesets, including rule provenance."""
    changes = []

    def walk(path: str, left: Any, right: Any) -> None:
        if isinstance(left, dict) and isinstance(right, dict):
            for key in sorted(left.keys() | right.keys()):
                child = f"{path}.{key}" if path else key
                if key not in left:
                    changes.append({"path": child, "before": None, "after": right[key]})
                elif key not in right:
                    changes.append({"path": child, "before": left[key], "after": None})
                else:
                    walk(child, left[key], right[key])
        elif left != right:
            changes.append({"path": path, "before": left, "after": right})

    walk("", dict(before), dict(after))
    return {
        "before_ruleset_id": before.get("ruleset_id"),
        "after_ruleset_id": after.get("ruleset_id"),
        "changes": changes,
    }


def validate_order(
    order: Mapping[str, Any],
    portfolio: Mapping[str, Any],
    ruleset: Mapping[str, Any],
    universe: Mapping[str, Any],
    as_of: str | date,
) -> dict[str, Any]:
    """Check source-listed eligibility and deterministic pre-trade constraints.

    This is a rules screen, not an order router or fill simulator. It does not
    claim that an annex symbol is the exact authenticated simulator symbol.
    """
    point = _as_date(as_of)
    checks: list[dict[str, str]] = []

    def add(check_id: str, status: str, detail: str) -> None:
        checks.append({"check_id": check_id, "status": status, "detail": detail})

    records = {item["instrument_id"]: item for item in universe["instruments"]}
    period = ruleset.get("effective_period", {})
    if period.get("start") and period.get("end"):
        in_competition = _as_date(period["start"]) <= point <= _as_date(period["end"])
        add(
            "competition_period",
            "PASS" if in_competition else "FAIL",
            f"as_of={point.isoformat()}",
        )
    instrument_id = order.get("instrument_id")
    instrument = records.get(instrument_id)
    if instrument is None:
        add("annex_eligibility", "FAIL", "instrument_id is absent from the versioned guide annex")
        return _order_result(checks, instrument, ruleset)

    snapshot_start = _as_date(universe["effective_from"])
    snapshot_end = _as_date(universe["effective_to"]) if universe.get("effective_to") else None
    snapshot_current = point >= snapshot_start and (snapshot_end is None or point <= snapshot_end)
    if _listed_on(instrument, point) and snapshot_current:
        add("annex_eligibility", "PASS", "listed in the 2026 official guide annex for this date")
    else:
        add("annex_eligibility", "FAIL", "not listed or outside the snapshot's validity window")
    if instrument["eligibility"].get("rulebook_category_conflict"):
        add("rulebook_category", "UNKNOWN", "guide-listed FIBRA category is omitted from the rules body")

    side = order.get("side")
    allowed_sides = ruleset["rules"]["allowed_order_sides"]
    add("order_side", "PASS" if side in allowed_sides else "FAIL", f"side={side!r}")
    order_type = order.get("order_type")
    allowed_types = ruleset["rules"]["allowed_order_types"]
    add("order_type", "PASS" if order_type in allowed_types else "FAIL", f"order_type={order_type!r}")

    quantity = order.get("quantity")
    quantity_valid = type(quantity) is int and quantity > 0
    add("positive_integer_quantity", "PASS" if quantity_valid else "FAIL", f"quantity={quantity!r}")
    price_key = "limit_price_actipesos" if order_type == "limit" else "reference_price_actipesos"
    raw_price = order.get(price_key)
    try:
        price = _decimal(raw_price, price_key) if raw_price is not None else None
    except M1DataError:
        price = None
    if order_type == "limit":
        price_ok = price is not None and price > 0
        add("limit_price", "PASS" if price_ok else "FAIL", "limit orders require a positive limit price")
    elif order_type == "market":
        price_ok = price is not None and price > 0
        add(
            "market_order_estimate",
            "PASS" if price_ok else "UNKNOWN",
            "a positive reference price is required only to estimate buying power",
        )
    else:
        price_ok = False

    holdings = portfolio.get("holdings", [])
    held_quantity = 0
    held_market_value = Decimal(0)
    if isinstance(holdings, list):
        for holding in holdings:
            if holding.get("instrument_id") == instrument_id:
                hq = holding.get("quantity", 0)
                if type(hq) is int and hq >= 0:
                    held_quantity += hq
                if holding.get("market_value_actipesos") is not None:
                    held_market_value += _decimal(
                        holding["market_value_actipesos"], "holding market_value_actipesos"
                    )

    amount = price * quantity if price is not None and quantity_valid else None
    costs = ruleset["rules"]["costs"]
    fee_rate = _decimal(costs["effective_rate"], "effective_rate")
    fee = amount * fee_rate if amount is not None else None
    if side == "buy" and amount is not None and fee is not None:
        available = portfolio.get("available_buying_power_actipesos")
        if available is None:
            add("buying_power", "UNKNOWN", "available buying power was not supplied")
        else:
            available_amount = _decimal(available, "available_buying_power_actipesos")
            add(
                "buying_power",
                "PASS" if amount + fee <= available_amount else "FAIL",
                f"estimated debit {amount + fee} actipesos vs available {available_amount}",
            )
    elif side == "buy" and (not quantity_valid or not price_ok):
        add("buying_power", "UNKNOWN", "cannot estimate debit without quantity and price")

    if side == "sell" and quantity_valid:
        add(
            "no_short_sale",
            "PASS" if quantity <= held_quantity else "FAIL",
            f"sell quantity {quantity}; held quantity {held_quantity}",
        )

    if side == "buy" and amount is not None:
        portfolio_value = portfolio.get("portfolio_value_actipesos")
        if portfolio_value is None:
            add("single_instrument_concentration", "UNKNOWN", "portfolio value was not supplied")
        else:
            value = _decimal(portfolio_value, "portfolio_value_actipesos")
            if value <= 0:
                add("single_instrument_concentration", "UNKNOWN", "portfolio value must be positive")
            else:
                cap = _decimal(
                    ruleset["rules"]["portfolio_constraints"]["maximum_single_instrument_weight"],
                    "maximum_single_instrument_weight",
                )
                projected_weight = (held_market_value + amount) / value
                add(
                    "single_instrument_concentration",
                    "PASS" if projected_weight <= cap else "FAIL",
                    f"projected holding weight {projected_weight}; cap {cap}; guide interpretation",
                )

    return _order_result(checks, instrument, ruleset, amount=amount, fee=fee)


def _order_result(
    checks: list[dict[str, str]],
    instrument: Mapping[str, Any] | None,
    ruleset: Mapping[str, Any],
    amount: Decimal | None = None,
    fee: Decimal | None = None,
) -> dict[str, Any]:
    return {
        "constraint_status": _combined_status(checks),
        "operability_status": (
            "UNVERIFIED"
            if instrument is None or instrument.get("platform_symbol") is None
            else "VERIFIED"
        ),
        "official_award_eligibility_status": "INDETERMINATE",
        "ruleset_id": ruleset.get("ruleset_id"),
        "instrument_id": instrument.get("instrument_id") if instrument else None,
        "guide_symbol": instrument.get("guide_symbol") if instrument else None,
        "estimated_gross_actipesos": str(amount) if amount is not None else None,
        "estimated_fee_actipesos": str(fee) if fee is not None else None,
        "checks": checks,
        "limitations": [
            "The guide symbol and series are not confirmed against the authenticated simulator search.",
            "Published sources disagree on concentration measurement and minimum-asset wording; see config/actinver_rules.yaml.",
            "This screen does not model fills, BMV holiday calendars, or platform-specific buying-power calculations.",
        ],
    }


def validate_portfolio(
    portfolio: Mapping[str, Any],
    ruleset: Mapping[str, Any],
    universe: Mapping[str, Any],
    as_of: str | date,
) -> dict[str, Any]:
    """Evaluate published minimum-asset and concentration checks with explicit unknowns."""
    point = _as_date(as_of)
    records = {item["instrument_id"]: item for item in universe["instruments"]}
    constraints = ruleset["rules"]["portfolio_constraints"]
    checks: list[dict[str, str]] = []

    def add(check_id: str, status: str, detail: str) -> None:
        checks.append({"check_id": check_id, "status": status, "detail": detail})

    period = ruleset.get("effective_period", {})
    if period.get("start") and period.get("end"):
        in_competition = _as_date(period["start"]) <= point <= _as_date(period["end"])
        add("competition_period", "PASS" if in_competition else "FAIL", f"as_of={point.isoformat()}")

    holdings = portfolio.get("holdings")
    if not isinstance(holdings, list):
        holdings = []
        add("holdings_data", "UNKNOWN", "holdings array was not supplied")
    held_ids: set[str] = set()
    invalid_ids: list[str] = []
    invalid_dates: list[str] = []
    for holding in holdings:
        instrument_id = holding.get("instrument_id")
        quantity = holding.get("quantity", 0)
        if instrument_id not in records:
            invalid_ids.append(str(instrument_id))
            continue
        if type(quantity) is not int or quantity < 0:
            add("holding_quantity", "FAIL", f"invalid quantity for {instrument_id}")
            continue
        if quantity > 0:
            held_ids.add(instrument_id)
            if not _listed_on(records[instrument_id], point):
                invalid_dates.append(instrument_id)
    add(
        "held_instruments_eligible",
        "FAIL" if invalid_ids else "PASS",
        "unknown IDs: " + ", ".join(invalid_ids) if invalid_ids else "all holdings map to the snapshot",
    )
    add(
        "held_instruments_date_valid",
        "FAIL" if invalid_dates else "PASS",
        "outside snapshot validity: " + ", ".join(invalid_dates) if invalid_dates else "all held instruments are date-valid",
    )

    traded_ids_value = portfolio.get("traded_instrument_ids")
    if traded_ids_value is None:
        traded_ids: set[str] = set()
        traded_available = False
    elif isinstance(traded_ids_value, list):
        traded_ids = set(traded_ids_value)
        traded_available = True
    else:
        traded_ids = set()
        traded_available = False
        add("trade_history", "UNKNOWN", "traded_instrument_ids must be an array")
    valid_traded = {identifier for identifier in traded_ids if identifier in records}
    invalid_traded = traded_ids - valid_traded
    if invalid_traded:
        add("traded_instruments_eligible", "FAIL", f"unknown trade IDs: {sorted(invalid_traded)}")
    all_distinct = held_ids | valid_traded
    conflicting_ids = sorted(
        identifier
        for identifier in held_ids | valid_traded
        if records[identifier]["eligibility"].get("rulebook_category_conflict")
    )
    add(
        "rulebook_category_eligibility",
        "UNKNOWN" if conflicting_ids else "PASS",
        "source-conflicted categories present: " + ", ".join(conflicting_ids)
        if conflicting_ids
        else "all held or traded categories are named consistently in the source set",
    )
    min_any = constraints["minimum_distinct_guide_instruments"]
    add(
        "minimum_guide_instruments",
        "PASS" if len(all_distinct) >= min_any else "FAIL",
        f"{len(all_distinct)} distinct held or traded guide instruments; minimum {min_any}",
    )
    if traded_available:
        traded_shares = {
            identifier
            for identifier in valid_traded
            if records[identifier]["category"] in {"national_equity", "sic_equity"}
        }
        min_shares = constraints["minimum_distinct_traded_shares"]
        add(
            "minimum_distinct_traded_shares",
            "PASS" if len(traded_shares) >= min_shares else "FAIL",
            f"{len(traded_shares)} distinct share IDs traded; minimum {min_shares}",
        )
    else:
        add(
            "minimum_distinct_traded_shares",
            "UNKNOWN",
            "trade history is required by the stricter rules-page wording",
        )

    portfolio_value_raw = portfolio.get("portfolio_value_actipesos")
    if portfolio_value_raw is None:
        portfolio_value = None
        add("portfolio_value", "UNKNOWN", "portfolio value was not supplied")
    else:
        portfolio_value = _decimal(portfolio_value_raw, "portfolio_value_actipesos")
        if portfolio_value <= 0:
            add("portfolio_value", "UNKNOWN", "portfolio value must be positive")
            portfolio_value = None

    if portfolio_value is not None and isinstance(portfolio.get("holdings"), list):
        cap = _decimal(constraints["maximum_single_instrument_weight"], "concentration cap")
        position_checks = []
        for holding in holdings:
            identifier = holding.get("instrument_id")
            if identifier not in records or not holding.get("quantity", 0):
                continue
            market_value = _decimal(
                holding.get("market_value_actipesos"), f"holding market value for {identifier}"
            )
            weight = market_value / portfolio_value
            position_checks.append((identifier, weight))
        max_position = max((weight for _identifier, weight in position_checks), default=Decimal(0))
        add(
            "maximum_current_single_instrument_weight",
            "PASS" if max_position <= cap else "FAIL",
            f"maximum current holding weight {max_position}; cap {cap}; guide interpretation",
        )
    else:
        add(
            "maximum_current_single_instrument_weight",
            "UNKNOWN",
            "position values and positive portfolio value are required",
        )

    cumulative = portfolio.get("cumulative_purchase_value_actipesos_by_instrument")
    if portfolio_value is None:
        add("maximum_period_single_share_purchases", "UNKNOWN", "portfolio value is required")
    elif not isinstance(cumulative, dict):
        add(
            "maximum_period_single_share_purchases",
            "UNKNOWN",
            "cumulative purchases by share are needed under the rules-page wording",
        )
    else:
        cap = _decimal(
            constraints["maximum_single_share_purchase_to_portfolio_value"],
            "share purchase cap",
        )
        unknown_purchase_ids = sorted(set(cumulative) - records.keys())
        if unknown_purchase_ids:
            add(
                "maximum_period_single_share_purchases",
                "FAIL",
                f"purchase history has unknown IDs: {unknown_purchase_ids}",
            )
        else:
            share_purchases = []
            for identifier, raw_amount in cumulative.items():
                if records[identifier]["category"] in {"national_equity", "sic_equity"}:
                    share_purchases.append(
                        (identifier, _decimal(raw_amount, f"cumulative purchases for {identifier}"))
                    )
            maximum = max((amount for _identifier, amount in share_purchases), default=Decimal(0))
            add(
                "maximum_period_single_share_purchases",
                "PASS" if maximum <= portfolio_value * cap else "FAIL",
                f"largest cumulative share purchases {maximum}; threshold {portfolio_value * cap}; rules-page interpretation",
            )

    status = _combined_status(checks)
    source_ambiguities = [item["ambiguity_id"] for item in ruleset.get("ambiguities", [])]
    return {
        "constraint_status": status,
        "official_award_eligibility_status": (
            "INDETERMINATE" if source_ambiguities or status == "INDETERMINATE" else status
        ),
        "ruleset_id": ruleset.get("ruleset_id"),
        "universe_snapshot_id": universe.get("snapshot_id"),
        "as_of": point.isoformat(),
        "checks": checks,
        "source_ambiguities": source_ambiguities,
        "limitations": [
            "A portfolio can only be certified against guide symbols after their simulator search symbols are verified.",
            "Both published minimum-count and concentration interpretations are checked; the sources do not resolve which measurement Actinver applies.",
        ],
    }
