"""Deterministic Actinver order-to-ledger simulator (M3)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .m1 import M1DataError, bmv_trading_day_status


class ExecutionError(ValueError):
    """Raised when a simulation case cannot be replayed deterministically."""


_UTC = timezone.utc
_CASE_FIELDS = {
    "schema_version",
    "simulation_start",
    "simulation_as_of",
    "initial_cash_actipesos",
    "initial_positions",
    "prior_purchase_notional_actipesos",
    "prior_traded_share_ids",
    "orders",
    "market_trades",
    "cancellations",
    "market_data_dataset_id",
    "order_expiration_basis",
}
_ORDER_REQUIRED = {
    "order_id",
    "instrument_id",
    "side",
    "order_type",
    "quantity",
    "submitted_at",
    "expires_at",
    "sequence",
}
_ORDER_OPTIONAL = {"limit_price_actipesos", "buying_power_reference_price_actipesos"}
_TRADE_FIELDS = {
    "trade_id",
    "instrument_id",
    "traded_at",
    "price_actipesos",
    "sequence",
    "source_id",
    "source_revision",
}
_CANCELLATION_FIELDS = {"order_id", "cancelled_at", "sequence"}
_POSITION_FIELDS = {"instrument_id", "quantity", "mark_price_actipesos", "marked_at"}


@dataclass
class _OrderState:
    order_id: str
    instrument_id: str
    side: str
    order_type: str
    quantity: int
    submitted_at: datetime
    submission_sequence: int
    expires_at: datetime
    limit_price: Decimal | None
    reservation_price: Decimal | None
    reserved_buying_power: Decimal
    status: str = "PENDING"
    filled_quantity: int = 0
    fill_trade_id: str | None = None
    fill_price: Decimal | None = None
    rejection_reason: str | None = None


def _time(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ExecutionError(f"{field} must be an ISO-8601 timestamp with timezone")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExecutionError(f"{field} is not a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ExecutionError(f"{field} must include a UTC offset")
    return parsed.astimezone(_UTC)


def _time_text(value: datetime) -> str:
    return value.astimezone(_UTC).isoformat().replace("+00:00", "Z")


def _decimal(value: Any, field: str, *, positive: bool = False) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ExecutionError(f"{field} must be an exact decimal string or integer")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ExecutionError(f"{field} must be a valid decimal") from exc
    if not parsed.is_finite() or parsed < 0 or (positive and parsed == 0):
        requirement = "positive" if positive else "non-negative"
        raise ExecutionError(f"{field} must be finite and {requirement}")
    return parsed


def _config_decimal(value: Any, field: str) -> Decimal:
    """Read YAML numeric rates through their decimal text representation."""
    if isinstance(value, float):
        value = str(value)
    return _decimal(value, field)


def _decimal_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def _object(value: Any, field: str, required: set[str], optional: set[str] | None = None) -> dict:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ExecutionError(f"{field} must be a JSON object")
    optional_fields = optional or set()
    missing = sorted(required - value.keys())
    unknown = sorted(value.keys() - required - optional_fields)
    if missing:
        raise ExecutionError(f"{field} is missing fields: {', '.join(missing)}")
    if unknown:
        raise ExecutionError(f"{field} has unknown fields: {', '.join(unknown)}")
    return value


def _sequence(value: Any, field: str) -> int:
    if type(value) is not int or value < 0:
        raise ExecutionError(f"{field} must be a non-negative integer")
    return value


def _identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExecutionError(f"{field} must be a non-empty string")
    return value.strip()


def _check_competition_timestamp(
    timestamp: datetime,
    ruleset: Mapping[str, Any],
    timezone_name: str,
    field: str,
) -> None:
    period = ruleset["effective_period"]
    local = timestamp.astimezone(ZoneInfo(timezone_name))
    start_date = date.fromisoformat(period["start"])
    end_date = date.fromisoformat(period["end"])
    end_time = time.fromisoformat(period["end_time_local"])
    if local.date() < start_date or local.date() > end_date:
        raise ExecutionError(f"{field} is outside the official competition dates")
    if local.date() == end_date and local.timetz().replace(tzinfo=None) > end_time:
        raise ExecutionError(f"{field} is after the official competition cutoff")


def _validate_market_trade_time(
    timestamp: datetime,
    ruleset: Mapping[str, Any],
    timezone_name: str,
) -> None:
    local = timestamp.astimezone(ZoneInfo(timezone_name))
    day_status = bmv_trading_day_status(local.date(), ruleset)
    if day_status["status"] != "SCHEDULED_SESSION":
        raise ExecutionError(
            f"Market trade {local.isoformat()} falls on a non-session or uncovered date"
        )
    windows = ruleset["rules"]["market_execution_windows"]["windows"]
    window = next(
        (
            item
            for item in windows
            if date.fromisoformat(item["start_date"]) <= local.date()
            and (item.get("end_date") is None or local.date() <= date.fromisoformat(item["end_date"]))
        ),
        None,
    )
    if window is None:
        raise ExecutionError(f"No market-hours rule covers {local.date().isoformat()}")
    market_open = time.fromisoformat(window["open"])
    market_close = time.fromisoformat(window["close"])
    local_time = local.timetz().replace(tzinfo=None)
    if local_time < market_open or local_time > market_close:
        raise ExecutionError(
            f"Market trade {local.isoformat()} falls outside the configured session"
        )


def _fee_breakdown(gross: Decimal, ruleset: Mapping[str, Any]) -> tuple[Decimal, Decimal, Decimal]:
    costs = ruleset["rules"]["costs"]
    commission = gross * _config_decimal(costs["commission_rate"], "commission_rate")
    iva = commission * _config_decimal(costs["iva_rate_on_commission"], "iva_rate_on_commission")
    return commission, iva, commission + iva


def _position_value(
    instrument_id: str,
    quantity: int,
    mark_prices: Mapping[str, Decimal],
) -> Decimal:
    if quantity == 0:
        return Decimal(0)
    if instrument_id not in mark_prices:
        raise ExecutionError(f"A current mark is required for held instrument {instrument_id}")
    return mark_prices[instrument_id] * quantity


def simulate_execution(
    case: Mapping[str, Any],
    ruleset: Mapping[str, Any],
    universe: Mapping[str, Any],
) -> dict[str, Any]:
    """Replay registered orders and market trades into a deterministic ledger.

    Full-order fills at the published triggering trade are an explicit simulator
    interpretation. Partial allocations and exchange queue priority are not
    specified by the public contest rules and are not inferred here.
    """
    input_case = _object(case, "case", _CASE_FIELDS)
    if type(input_case["schema_version"]) is not int or input_case["schema_version"] != 1:
        raise ExecutionError("case schema_version must equal 1")
    if input_case["order_expiration_basis"] != "explicit_timestamp":
        raise ExecutionError(
            "order_expiration_basis must be explicit_timestamp; the source does not define calendar vs business day"
        )
    dataset_id = _identifier(input_case["market_data_dataset_id"], "market_data_dataset_id")
    simulation_start = _time(input_case["simulation_start"], "simulation_start")
    simulation_as_of = _time(input_case["simulation_as_of"], "simulation_as_of")
    if simulation_as_of < simulation_start:
        raise ExecutionError("simulation_as_of cannot precede simulation_start")

    rules = ruleset["rules"]
    timezone_name = rules["market_execution_windows"]["source_timezone"]
    try:
        market_timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ExecutionError(f"Unknown configured timezone {timezone_name!r}") from exc
    _check_competition_timestamp(simulation_start, ruleset, timezone_name, "simulation_start")
    _check_competition_timestamp(simulation_as_of, ruleset, timezone_name, "simulation_as_of")
    cash = _decimal(input_case["initial_cash_actipesos"], "initial_cash_actipesos")
    initial_cash = cash

    universe_records = {
        item["instrument_id"]: item for item in universe.get("instruments", [])
    }
    if not universe_records:
        raise ExecutionError("The versioned instrument universe is empty")

    positions: dict[str, int] = {}
    mark_prices: dict[str, Decimal] = {}
    mark_times: dict[str, datetime] = {}
    initial_positions = input_case["initial_positions"]
    if not isinstance(initial_positions, list):
        raise ExecutionError("initial_positions must be an array")
    for index, raw_position in enumerate(initial_positions):
        position = _object(raw_position, f"initial_positions[{index}]", _POSITION_FIELDS)
        instrument_id = _identifier(position["instrument_id"], "instrument_id")
        if instrument_id not in universe_records:
            raise ExecutionError(f"Unknown guide instrument {instrument_id}")
        if instrument_id in positions:
            raise ExecutionError(f"Duplicate initial position for {instrument_id}")
        quantity = position["quantity"]
        if type(quantity) is not int or quantity < 0:
            raise ExecutionError("Initial position quantity must be a non-negative integer")
        marked_at = _time(position["marked_at"], "initial_positions.marked_at")
        if marked_at > simulation_start:
            raise ExecutionError("Initial position marks cannot use information after simulation_start")
        positions[instrument_id] = quantity
        if quantity > 0:
            mark_prices[instrument_id] = _decimal(
                position["mark_price_actipesos"], "initial_positions.mark_price_actipesos", positive=True
            )
            mark_times[instrument_id] = marked_at
        elif position["mark_price_actipesos"] is not None:
            mark_prices[instrument_id] = _decimal(
                position["mark_price_actipesos"], "initial_positions.mark_price_actipesos", positive=True
            )
            mark_times[instrument_id] = marked_at

    prior_purchases = input_case["prior_purchase_notional_actipesos"]
    if not isinstance(prior_purchases, dict):
        raise ExecutionError("prior_purchase_notional_actipesos must be an object")
    purchases_by_instrument: dict[str, Decimal] = {}
    for instrument_id, notional in prior_purchases.items():
        if instrument_id not in universe_records:
            raise ExecutionError(f"Unknown guide instrument in prior purchases: {instrument_id}")
        purchases_by_instrument[instrument_id] = _decimal(
            notional, f"prior_purchase_notional_actipesos.{instrument_id}"
        )

    prior_trades = input_case["prior_traded_share_ids"]
    if not isinstance(prior_trades, list):
        raise ExecutionError("prior_traded_share_ids must be an array")
    prior_traded_share_ids: set[str] = set()
    for instrument_id in prior_trades:
        instrument_id = _identifier(instrument_id, "prior_traded_share_ids item")
        if instrument_id in prior_traded_share_ids:
            raise ExecutionError(f"Duplicate prior traded share: {instrument_id}")
        if instrument_id not in universe_records:
            raise ExecutionError(f"Unknown guide instrument in prior trades: {instrument_id}")
        if universe_records[instrument_id].get("category") not in {"national_equity", "sic_equity"}:
            raise ExecutionError(f"Prior traded instrument is not a share: {instrument_id}")
        prior_traded_share_ids.add(instrument_id)

    raw_orders = input_case["orders"]
    raw_trades = input_case["market_trades"]
    raw_cancellations = input_case["cancellations"]
    if not isinstance(raw_orders, list) or not isinstance(raw_trades, list) or not isinstance(raw_cancellations, list):
        raise ExecutionError("orders, market_trades, and cancellations must be arrays")

    events: list[tuple[datetime, int, str, dict[str, Any]]] = []
    sequences: set[int] = set()
    order_ids: set[str] = set()
    trade_ids: set[str] = set()
    parsed_orders: dict[str, dict[str, Any]] = {}
    parsed_trades: dict[str, dict[str, Any]] = {}
    parsed_cancellations: list[dict[str, Any]] = []

    for index, raw_order in enumerate(raw_orders):
        order = _object(raw_order, f"orders[{index}]", _ORDER_REQUIRED, _ORDER_OPTIONAL)
        order_id = _identifier(order["order_id"], "order_id")
        instrument_id = _identifier(order["instrument_id"], "instrument_id")
        if order_id in order_ids:
            raise ExecutionError(f"Duplicate order_id {order_id}")
        if instrument_id not in universe_records:
            raise ExecutionError(f"Unknown guide instrument {instrument_id}")
        order_ids.add(order_id)
        submitted_at = _time(order["submitted_at"], f"orders[{index}].submitted_at")
        expires_at = _time(order["expires_at"], f"orders[{index}].expires_at")
        if not simulation_start <= submitted_at <= simulation_as_of:
            raise ExecutionError(f"Order {order_id} timestamp falls outside the simulation window")
        if expires_at <= submitted_at:
            raise ExecutionError(f"Order {order_id} expiry must follow its registration")
        _check_competition_timestamp(submitted_at, ruleset, timezone_name, f"Order {order_id}")
        sequence = _sequence(order["sequence"], f"orders[{index}].sequence")
        if sequence in sequences:
            raise ExecutionError(f"Duplicate event sequence {sequence}")
        sequences.add(sequence)
        side = order["side"]
        order_type = order["order_type"]
        if side not in rules["allowed_order_sides"]:
            raise ExecutionError(f"Order {order_id} has unsupported side {side!r}")
        if order_type not in rules["allowed_order_types"]:
            raise ExecutionError(f"Order {order_id} has unsupported type {order_type!r}")
        quantity = order["quantity"]
        if type(quantity) is not int or quantity <= 0:
            raise ExecutionError(f"Order {order_id} quantity must be a positive integer")
        limit_price = None
        if order_type == "limit":
            limit_price = _decimal(
                order.get("limit_price_actipesos"),
                f"orders[{index}].limit_price_actipesos",
                positive=True,
            )
        elif order.get("limit_price_actipesos") is not None:
            raise ExecutionError(f"Market order {order_id} must not include a limit price")
        reservation_price = None
        if side == "buy":
            reference = order.get("buying_power_reference_price_actipesos")
            if order_type == "market" and reference is None:
                raise ExecutionError(
                    f"Market buy order {order_id} requires a buying-power reference price"
                )
            reservation_price = _decimal(
                reference if reference is not None else limit_price,
                f"orders[{index}].buying_power_reference_price_actipesos",
                positive=True,
            )
            if limit_price is not None and reservation_price < limit_price:
                raise ExecutionError(
                    f"Buy order {order_id} reservation price cannot be below its limit price"
                )
        parsed = dict(order)
        parsed.update(
            {
                "order_id": order_id,
                "instrument_id": instrument_id,
                "submitted_at_utc": submitted_at,
                "expires_at_utc": expires_at,
                "sequence_value": sequence,
                "limit_price_value": limit_price,
                "reservation_price_value": reservation_price,
            }
        )
        parsed_orders[order_id] = parsed
        events.append((submitted_at, sequence, "order", parsed))

    for index, raw_trade in enumerate(raw_trades):
        trade = _object(raw_trade, f"market_trades[{index}]", _TRADE_FIELDS)
        trade_id = _identifier(trade["trade_id"], "trade_id")
        instrument_id = _identifier(trade["instrument_id"], "instrument_id")
        if trade_id in trade_ids:
            raise ExecutionError(f"Duplicate trade_id {trade_id}")
        if instrument_id not in universe_records:
            raise ExecutionError(f"Unknown guide instrument in market trade: {instrument_id}")
        trade_ids.add(trade_id)
        traded_at = _time(trade["traded_at"], f"market_trades[{index}].traded_at")
        if not simulation_start <= traded_at <= simulation_as_of:
            raise ExecutionError(f"Market trade {trade_id} falls outside the simulation window")
        _check_competition_timestamp(traded_at, ruleset, timezone_name, f"Market trade {trade_id}")
        _validate_market_trade_time(traded_at, ruleset, timezone_name)
        sequence = _sequence(trade["sequence"], f"market_trades[{index}].sequence")
        if sequence in sequences:
            raise ExecutionError(f"Duplicate event sequence {sequence}")
        sequences.add(sequence)
        parsed = dict(trade)
        parsed.update(
            {
                "trade_id": trade_id,
                "instrument_id": instrument_id,
                "traded_at_utc": traded_at,
                "sequence_value": sequence,
                "price_value": _decimal(
                    trade["price_actipesos"],
                    f"market_trades[{index}].price_actipesos",
                    positive=True,
                ),
                "source_id_value": _identifier(trade["source_id"], "source_id"),
                "source_revision_value": _identifier(trade["source_revision"], "source_revision"),
            }
        )
        parsed_trades[trade_id] = parsed
        events.append((traded_at, sequence, "trade", parsed))

    for index, raw_cancel in enumerate(raw_cancellations):
        cancellation = _object(raw_cancel, f"cancellations[{index}]", _CANCELLATION_FIELDS)
        order_id = _identifier(cancellation["order_id"], "cancellations.order_id")
        cancelled_at = _time(cancellation["cancelled_at"], f"cancellations[{index}].cancelled_at")
        if not simulation_start <= cancelled_at <= simulation_as_of:
            raise ExecutionError(f"Cancellation for {order_id} falls outside the simulation window")
        _check_competition_timestamp(cancelled_at, ruleset, timezone_name, f"Cancellation for {order_id}")
        sequence = _sequence(cancellation["sequence"], f"cancellations[{index}].sequence")
        if sequence in sequences:
            raise ExecutionError(f"Duplicate event sequence {sequence}")
        sequences.add(sequence)
        parsed = {
            "order_id": order_id,
            "cancelled_at_utc": cancelled_at,
            "sequence_value": sequence,
        }
        parsed_cancellations.append(parsed)
        events.append((cancelled_at, sequence, "cancel", parsed))

    fee_rate = _config_decimal(rules["costs"]["effective_rate"], "effective_rate")
    fee_components = (
        _config_decimal(rules["costs"]["commission_rate"], "commission_rate"),
        _config_decimal(rules["costs"]["iva_rate_on_commission"], "iva_rate_on_commission"),
    )
    weight_limit = _config_decimal(
        rules["portfolio_constraints"]["maximum_single_instrument_weight"],
        "maximum_single_instrument_weight",
    )
    purchase_limit = _config_decimal(
        rules["portfolio_constraints"]["maximum_single_share_purchase_to_portfolio_value"],
        "maximum_single_share_purchase_to_portfolio_value",
    )
    order_states: dict[str, _OrderState] = {}
    ledger: list[dict[str, Any]] = []
    total_commission = Decimal(0)
    total_iva = Decimal(0)
    traded_share_ids = prior_traded_share_ids.copy()

    def append_ledger(entry: dict[str, Any]) -> None:
        entry["ledger_sequence"] = len(ledger) + 1
        ledger.append(entry)

    def pending_buy_reserve(exclude_order_id: str | None = None) -> Decimal:
        return sum(
            (
                state.reserved_buying_power
                for order_id, state in order_states.items()
                if order_id != exclude_order_id
                and state.status == "PENDING"
                and state.side == "buy"
            ),
            Decimal(0),
        )

    def pending_sell_quantity(instrument_id: str, exclude_order_id: str | None = None) -> int:
        return sum(
            state.quantity
            for order_id, state in order_states.items()
            if order_id != exclude_order_id
            and state.status == "PENDING"
            and state.side == "sell"
            and state.instrument_id == instrument_id
        )

    def portfolio_value() -> Decimal:
        value = cash
        for instrument_id, quantity in positions.items():
            value += _position_value(instrument_id, quantity, mark_prices)
        return value

    def expire_orders(at_time: datetime, *, inclusive: bool) -> None:
        for state in sorted(order_states.values(), key=lambda item: (item.submitted_at, item.submission_sequence, item.order_id)):
            expired = state.expires_at <= at_time if inclusive else state.expires_at < at_time
            if state.status == "PENDING" and expired:
                state.status = "EXPIRED"
                append_ledger(
                    {
                        "event_time": _time_text(state.expires_at),
                        "event_sequence": None,
                        "event_type": "order_expired",
                        "order_id": state.order_id,
                        "instrument_id": state.instrument_id,
                        "reason": "explicit expires_at cutoff reached",
                        "cash_balance_actipesos": _decimal_text(cash),
                    }
                )

    def mark_and_fill(trade: Mapping[str, Any]) -> None:
        nonlocal cash, total_commission, total_iva
        instrument_id = trade["instrument_id"]
        traded_at = trade["traded_at_utc"]
        trade_sequence = trade["sequence_value"]
        price = trade["price_value"]
        mark_prices[instrument_id] = price
        mark_times[instrument_id] = traded_at
        positions.setdefault(instrument_id, 0)
        append_ledger(
            {
                "event_time": _time_text(traded_at),
                "event_sequence": trade_sequence,
                "event_type": "market_mark",
                "trade_id": trade["trade_id"],
                "instrument_id": instrument_id,
                "price_actipesos": _decimal_text(price),
                "source_id": trade["source_id_value"],
                "source_revision": trade["source_revision_value"],
                "cash_balance_actipesos": _decimal_text(cash),
            }
        )
        eligible_orders = sorted(
            (
                state
                for state in order_states.values()
                if state.status == "PENDING"
                and state.instrument_id == instrument_id
                and (traded_at, trade_sequence)
                > (state.submitted_at, state.submission_sequence)
                and traded_at < state.expires_at
            ),
            key=lambda item: (item.submitted_at, item.submission_sequence, item.order_id),
        )
        for state in eligible_orders:
            if state.order_type == "limit" and price != state.limit_price:
                continue
            gross = price * state.quantity
            commission, iva, total_fee = _fee_breakdown(gross, ruleset)
            if state.side == "buy":
                free_after_other_reservations = cash - pending_buy_reserve(state.order_id)
                if gross + total_fee > free_after_other_reservations:
                    state.status = "REJECTED_AT_FILL_INSUFFICIENT_BUYING_POWER"
                    state.rejection_reason = "actual fill debit exceeds free buying power"
                    append_ledger(
                        {
                            "event_time": _time_text(traded_at),
                            "event_sequence": trade_sequence,
                            "event_type": "order_rejected_at_fill",
                            "order_id": state.order_id,
                            "instrument_id": instrument_id,
                            "trade_id": trade["trade_id"],
                            "reason": state.rejection_reason,
                            "cash_balance_actipesos": _decimal_text(cash),
                        }
                    )
                    continue
                cash -= gross + total_fee
                positions[instrument_id] = positions.get(instrument_id, 0) + state.quantity
                purchases_by_instrument[instrument_id] = (
                    purchases_by_instrument.get(instrument_id, Decimal(0)) + gross
                )
            else:
                available_quantity = positions.get(instrument_id, 0) - pending_sell_quantity(
                    instrument_id, state.order_id
                )
                if state.quantity > available_quantity:
                    state.status = "REJECTED_AT_FILL_INSUFFICIENT_HOLDINGS"
                    state.rejection_reason = "held quantity changed before fill"
                    append_ledger(
                        {
                            "event_time": _time_text(traded_at),
                            "event_sequence": trade_sequence,
                            "event_type": "order_rejected_at_fill",
                            "order_id": state.order_id,
                            "instrument_id": instrument_id,
                            "trade_id": trade["trade_id"],
                            "reason": state.rejection_reason,
                            "cash_balance_actipesos": _decimal_text(cash),
                        }
                    )
                    continue
                cash += gross - total_fee
                positions[instrument_id] = positions.get(instrument_id, 0) - state.quantity

            total_commission += commission
            total_iva += iva
            state.status = "FILLED"
            state.filled_quantity = state.quantity
            state.fill_trade_id = trade["trade_id"]
            state.fill_price = price
            category = universe_records[instrument_id].get("category")
            if category in {"national_equity", "sic_equity"}:
                traded_share_ids.add(instrument_id)
            append_ledger(
                {
                    "event_time": _time_text(traded_at),
                    "event_sequence": trade_sequence,
                    "event_type": "fill",
                    "order_id": state.order_id,
                    "instrument_id": instrument_id,
                    "side": state.side,
                    "trade_id": trade["trade_id"],
                    "source_id": trade["source_id_value"],
                    "source_revision": trade["source_revision_value"],
                    "quantity": state.quantity,
                    "price_actipesos": _decimal_text(price),
                    "gross_actipesos": _decimal_text(gross),
                    "commission_actipesos": _decimal_text(commission),
                    "iva_actipesos": _decimal_text(iva),
                    "total_fee_actipesos": _decimal_text(total_fee),
                    "cash_delta_actipesos": _decimal_text(
                        -(gross + total_fee) if state.side == "buy" else gross - total_fee
                    ),
                    "cash_balance_actipesos": _decimal_text(cash),
                    "position_quantity_after": positions[instrument_id],
                }
            )

    events.sort(key=lambda item: (item[0], item[1]))
    for event_time, sequence, event_type, payload in events:
        expire_orders(event_time, inclusive=True)
        if event_type == "order":
            order_id = payload["order_id"]
            instrument_id = payload["instrument_id"]
            side = payload["side"]
            order_type = payload["order_type"]
            quantity = payload["quantity"]
            limit_price = payload["limit_price_value"]
            reservation_price = payload["reservation_price_value"]
            reserved_amount = Decimal(0)
            if side == "buy":
                assert reservation_price is not None
                estimate = reservation_price * quantity
                _, _, estimated_fee = _fee_breakdown(estimate, ruleset)
                reserved_amount = estimate + estimated_fee
                if reserved_amount > cash - pending_buy_reserve():
                    state = _OrderState(
                        order_id,
                        instrument_id,
                        side,
                        order_type,
                        quantity,
                        event_time,
                        sequence,
                        payload["expires_at_utc"],
                        limit_price,
                        reservation_price,
                        reserved_amount,
                        status="REJECTED_INSUFFICIENT_BUYING_POWER",
                        rejection_reason="reserved amount exceeds available cash after pending buy intentions",
                    )
                    order_states[order_id] = state
                    append_ledger(
                        {
                            "event_time": _time_text(event_time),
                            "event_sequence": sequence,
                            "event_type": "order_rejected",
                            "order_id": order_id,
                            "instrument_id": instrument_id,
                            "reason": state.rejection_reason,
                            "reserved_buying_power_actipesos": _decimal_text(reserved_amount),
                            "available_buying_power_actipesos": _decimal_text(
                                max(Decimal(0), cash - pending_buy_reserve())
                            ),
                        }
                    )
                    continue
            else:
                held = positions.get(instrument_id, 0)
                available = held - pending_sell_quantity(instrument_id)
                if quantity > available:
                    state = _OrderState(
                        order_id,
                        instrument_id,
                        side,
                        order_type,
                        quantity,
                        event_time,
                        sequence,
                        payload["expires_at_utc"],
                        limit_price,
                        None,
                        Decimal(0),
                        status="REJECTED_INSUFFICIENT_HOLDINGS",
                        rejection_reason="sell quantity exceeds unreserved held quantity",
                    )
                    order_states[order_id] = state
                    append_ledger(
                        {
                            "event_time": _time_text(event_time),
                            "event_sequence": sequence,
                            "event_type": "order_rejected",
                            "order_id": order_id,
                            "instrument_id": instrument_id,
                            "reason": state.rejection_reason,
                            "held_quantity": held,
                            "available_quantity": available,
                        }
                    )
                    continue

            state = _OrderState(
                order_id,
                instrument_id,
                side,
                order_type,
                quantity,
                event_time,
                sequence,
                payload["expires_at_utc"],
                limit_price,
                reservation_price,
                reserved_amount,
            )
            order_states[order_id] = state
            append_ledger(
                {
                    "event_time": _time_text(event_time),
                    "event_sequence": sequence,
                    "event_type": "order_accepted",
                    "order_id": order_id,
                    "instrument_id": instrument_id,
                    "side": side,
                    "order_type": order_type,
                    "quantity": quantity,
                    "expires_at": _time_text(state.expires_at),
                    "reserved_buying_power_actipesos": _decimal_text(reserved_amount),
                    "available_buying_power_actipesos": _decimal_text(
                        max(Decimal(0), cash - pending_buy_reserve())
                    ),
                }
            )
        elif event_type == "trade":
            mark_and_fill(payload)
        else:
            order_id = payload["order_id"]
            state = order_states.get(order_id)
            if state is None:
                status = "CANCEL_REJECTED_UNKNOWN_ORDER"
                reason = "no registered order with this order_id"
            elif state.status == "FILLED":
                status = "CANCEL_REJECTED_FILLED_ORDER"
                reason = "filled orders cannot be cancelled"
            elif state.status != "PENDING":
                status = "CANCEL_REJECTED_NOT_PENDING"
                reason = f"order is already {state.status.lower()}"
            elif (event_time, sequence) <= (state.submitted_at, state.submission_sequence):
                status = "CANCEL_REJECTED_BEFORE_REGISTRATION"
                reason = "cancellation event does not follow order registration"
            else:
                state.status = "CANCELLED"
                status = "CANCELLED"
                reason = "pending order cancelled"
            append_ledger(
                {
                    "event_time": _time_text(event_time),
                    "event_sequence": sequence,
                    "event_type": "order_cancellation",
                    "order_id": order_id,
                    "status": status,
                    "reason": reason,
                    "cash_balance_actipesos": _decimal_text(cash),
                }
            )

    expire_orders(simulation_as_of, inclusive=True)

    position_rows = []
    for instrument_id in sorted(positions):
        quantity = positions[instrument_id]
        mark = mark_prices.get(instrument_id)
        mark_time = mark_times.get(instrument_id)
        position_rows.append(
            {
                "instrument_id": instrument_id,
                "quantity": quantity,
                "mark_price_actipesos": _decimal_text(mark),
                "marked_at": _time_text(mark_time) if mark_time else None,
                "market_value_actipesos": _decimal_text(mark * quantity if mark is not None else None),
            }
        )

    current_portfolio_value = portfolio_value()
    current_weights = {}
    for instrument_id, quantity in positions.items():
        if quantity <= 0:
            continue
        value = _position_value(instrument_id, quantity, mark_prices)
        current_weights[instrument_id] = value / current_portfolio_value if current_portfolio_value > 0 else Decimal(0)
    max_current_weight = max(current_weights.values(), default=Decimal(0))
    max_purchase_weight = max(
        (
            notional / current_portfolio_value if current_portfolio_value > 0 else Decimal(0)
            for instrument_id, notional in purchases_by_instrument.items()
            if universe_records[instrument_id].get("category")
            in {"national_equity", "sic_equity"}
        ),
        default=Decimal(0),
    )
    constraints = rules["portfolio_constraints"]
    distinct_share_count = len(traded_share_ids)
    min_share_requirement = constraints["minimum_distinct_traded_shares"]
    if distinct_share_count < min_share_requirement:
        minimum_share_status = "NOT_MET"
    else:
        minimum_share_status = "POTENTIALLY_MET"
    eligibility_fail = (
        max_current_weight > weight_limit or max_purchase_weight > purchase_limit
    ) or minimum_share_status == "NOT_MET"
    eligibility_status = "NON_COMPLIANT" if eligibility_fail else "INDETERMINATE"

    orders_output = []
    for state in sorted(order_states.values(), key=lambda item: (item.submitted_at, item.submission_sequence, item.order_id)):
        orders_output.append(
            {
                "order_id": state.order_id,
                "instrument_id": state.instrument_id,
                "side": state.side,
                "order_type": state.order_type,
                "quantity": state.quantity,
                "status": state.status,
                "filled_quantity": state.filled_quantity,
                "fill_trade_id": state.fill_trade_id,
                "fill_price_actipesos": _decimal_text(state.fill_price),
                "rejection_reason": state.rejection_reason,
                "instrument_mapping_status": "UNVERIFIED",
            }
        )

    return {
        "schema_version": 1,
        "status": "PASS",
        "ruleset_id": ruleset["ruleset_id"],
        "universe_snapshot_id": universe["snapshot_id"],
        "market_data_dataset_id": dataset_id,
        "simulation_start": _time_text(simulation_start),
        "simulation_as_of": _time_text(simulation_as_of),
        "order_expiration_basis": "explicit_timestamp_from_case",
        "fill_policy": "full_order_on_first_eligible_trade",
        "orders": orders_output,
        "ledger": ledger,
        "positions": position_rows,
        "balances": {
            "initial_cash_actipesos": _decimal_text(initial_cash),
            "ending_cash_actipesos": _decimal_text(cash),
            "reserved_buying_power_actipesos": _decimal_text(pending_buy_reserve()),
            "available_buying_power_actipesos": _decimal_text(
                max(Decimal(0), cash - pending_buy_reserve())
            ),
            "portfolio_value_actipesos": _decimal_text(current_portfolio_value),
        },
        "fees": {
            "commission_rate": _decimal_text(fee_components[0]),
            "iva_rate_on_commission": _decimal_text(fee_components[1]),
            "combined_rate": _decimal_text(fee_rate),
            "total_commission_actipesos": _decimal_text(total_commission),
            "total_iva_actipesos": _decimal_text(total_iva),
            "rounding_applied": False,
        },
        "eligibility_checks": {
            "distinct_traded_share_count": distinct_share_count,
            "minimum_distinct_share_requirement": minimum_share_status,
            "maximum_current_instrument_weight": _decimal_text(max_current_weight),
            "current_instrument_weight_cap": _decimal_text(weight_limit),
            "maximum_cumulative_single_share_purchase_weight": _decimal_text(max_purchase_weight),
            "cumulative_single_share_purchase_cap": _decimal_text(purchase_limit),
            "status": eligibility_status,
            "limitation": "Eligibility wording and guide-to-simulator instrument mapping remain unresolved under M1.",
        },
        "limitations": [
            "Guide-instrument IDs are not authenticated simulator symbols or series.",
            "Order expiry uses the explicit expires_at timestamp because the official one-day rule does not specify calendar versus business day.",
            "Limit and market fills use the published triggering trade; partial allocation and queue priority are not specified or modeled.",
            "Fees use exact decimal arithmetic without rounding because the published rounding rule is unspecified.",
            "Portfolio values use initial marks and the latest supplied market trades; stale-price screening remains an M2 caller responsibility.",
            "No real Actinver practice fills were available for calibration; this result validates deterministic mechanics only.",
        ],
    }


__all__ = ["ExecutionError", "simulate_execution"]
