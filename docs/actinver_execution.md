# M3 — Deterministic execution replay

## Scope

`actinver-exec` replays a declared sequence of registered orders, BMV trade
prints, and cancellations into an auditable cash and positions ledger. It reads
the versioned M1 rules, universe, holiday calendar, and market-session windows.
The case's `sequence` is the tie-breaker when two events share a timestamp;
sequence values must be unique across the case.

The case contract is
[`schemas/execution_case.schema.json`](../schemas/execution_case.schema.json).
The result contract is
[`schemas/execution_result.schema.json`](../schemas/execution_result.schema.json).
For partial-period replays, carry in `prior_purchase_notional_actipesos` and
`prior_traded_share_ids`; otherwise the eligibility diagnostics cover only the
records in this case. A full-competition replay should include the complete
order/trade history and use empty prior-state fields.

## Execution rules

- A market order fills in full at the first later trade for the same guide
  instrument. A limit order fills in full at the first later trade whose price
  exactly equals the requested limit. A better price is not substituted.
- The event tuple `(timestamp, sequence)` must be later than the order's tuple.
  This makes same-timestamp order/trade cases deterministic without treating a
  preceding trade as a fill.
- Trade prints are rejected if their timestamp falls outside the versioned
  BMV weekday, holiday, or market-hours calendar. Orders may be registered
  outside market hours during the competition and remain pending for a later
  trade until cancelled or expired.
- The simulation window itself must stay within the configured contest period
  and published end cutoff. Events outside that window are rejected.
- `expires_at` is an explicit absolute timestamp. The official rule says
  “one day” but does not define calendar versus business day, so the engine
  does not choose one. An order is eligible on `[submitted_at, expires_at)`.
- Buy orders reserve estimated notional plus the commission and IVA from
  available buying power. If the eventual market fill exceeds unreserved cash,
  the order is rejected at fill. Sell quantity is reserved against current
  holdings; inventory cannot go short.
- Fees are calculated with exact decimal arithmetic as 0.10% commission plus
  16% IVA on that commission, on both sides. The public rules do not specify a
  rounding convention, so the ledger does not round.
- Current instrument weight, cumulative purchases by share, and distinct
  traded-share count are reported as eligibility checks. Concentration is not
  silently treated as an order-entry rule because its award-eligibility wording
  differs between the guide and rules. A reported violation remains visible.
- The cumulative-purchase ratio uses ending portfolio value because historical
  point-in-time portfolio values are not part of the M3 case contract. Treat it
  as a diagnostic, not official eligibility certification.
- Portfolio valuation uses the last supplied mark for each holding. M2's
  freshness firewall remains a separate caller responsibility.

Full-order assignment after a qualifying print follows the wording in the
official [Reto Actinver mechanics](https://www.retoactinver.com/bases-y-mecanica).
The rules do not define partial allocations, queue priority, or a fill-size
relationship to BMV print volume. Those behaviors are not inferred. This model
does not represent actual broker execution or authenticated platform
symbol/series mapping.

## Run a simulation

Install the project, prepare a case JSON conforming to the schema, and run:

```powershell
python -m pip install -e .
actinver-exec simulate --input execution-case.json --output execution-result.json
```

The result includes the full event ledger, fee breakdown, order states,
positions, buying-power reservations, portfolio valuation, M1 eligibility
checks, source revision IDs, and a deterministic execution ID tied to the input
hash, ruleset, universe snapshot, and full code commit. Existing result files
are not overwritten.

## Limits

- Synthetic test cases establish deterministic software behavior only; no
  real practice fills are present for calibration.
- M1 guide IDs are not authenticated Actinver search symbols or series. Result
  records keep `instrument_mapping_status: UNVERIFIED`.
- No OHLCV or market-trade dataset is available. A synthetic or placeholder
  dataset ID must not be presented as evidence of financial performance.
- Corporate actions, partial fills, exchange queue priority, suspensions not
  represented by missing trades, and platform-specific rounding are not
  reconstructed.
- The CLI does not log in, interact with the Actinver portal, or submit orders.
