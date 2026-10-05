# Actinver Rules & Eligible Universe (M1)

## Current version

- Rules: [`config/actinver_rules.yaml`](../config/actinver_rules.yaml), ruleset `actinver-2026-rules-v1`.
- Universe: [`data/metadata/actinver_universe_2026_v1.json`](../data/metadata/actinver_universe_2026_v1.json), snapshot `actinver-2026-guide-annex-v1`.
- Structural contracts: [`schemas/actinver_rules.schema.json`](../schemas/actinver_rules.schema.json) and [`schemas/actinver_universe.schema.json`](../schemas/actinver_universe.schema.json).
- Verification time is recorded in UTC in each snapshot. The snapshot is a record of published sources, not a live Actinver API.

The M1 library can list guide-annex instruments for a date, screen orders and portfolios against encoded constraints, and report changes between rules or universe snapshots. `constraint_status` is `COMPLIANT`, `NON_COMPLIANT` or `INDETERMINATE`; exact simulator operability and award eligibility are reported separately where evidence is missing.

```powershell
actinver-m1 audit
actinver-m1 eligible --as-of 2026-10-05
actinver-m1 diff --kind universe --previous <older-snapshot.json> --current data/metadata/actinver_universe_2026_v1.json
```

Order-screen input JSON has this shape:

```json
{
  "order": {
    "instrument_id": "actinver:2026:national_equity:ac",
    "side": "buy",
    "quantity": 10,
    "order_type": "limit",
    "limit_price_actipesos": 150.0
  },
  "portfolio": {
    "portfolio_value_actipesos": 1000000,
    "available_buying_power_actipesos": 250000,
    "holdings": []
  }
}
```

Run it with `actinver-m1 validate-order --input order.json --as-of 2026-10-05`. For portfolio checks, `traded_instrument_ids`, current holding values, and cumulative purchases by share are needed to evaluate both published interpretations of the eligibility constraints. Missing evidence produces `INDETERMINATE` rather than an assumed pass.

## Verified published rules

The official competition window is **2026-10-05 through 2026-11-13 at 15:00 America/Mexico_City**. Starting capital is **1,000,000 actipesos**. The award rule for performance uses **absolute portfolio gain** at the end of the six-week event.

The simulator accepts market and limit orders 24/7, subject to maintenance; execution follows BMV sessions on weekdays excluding holidays. The official [Grupo BMV 2026 holiday calendar](https://www.bmv.com.mx/es/Grupo_BMV/Calendario_de_dias_festivos/_rid/662/_mod/TAB_DIAS_FEST) is preserved in `research/source_material/bmv_2026_holidays_official.html`; the rules config stores its SHA-256 and normalized dates. Use `actinver-m1 market-day --as-of 2026-11-02` to check the Día de muertos closure. The published regular hours are 07:30–14:00 CDMX, changing on November 3 to 08:30–15:00. Orders received after market hours receive the next BMV business date. A market order uses the next BMV trade after registration; a limit order requires a later BMV trade at the requested price. A request does not guarantee a fill. Unfilled orders expire after one day and may be cancelled; filled orders cannot be cancelled and orders cannot be modified.

The simulator uses a 0.10% commission plus 16% IVA on the commission, charged on buys and sells. The combined modeled rate is 0.116%. Purchases are checked against buying power, including cash and realized sale proceeds less pending buy reservations; sales cannot exceed held quantities and short sales are prohibited.

Portfolio values are updated during market hours and reconciled after the session. Cash/stock dividends and subscriptions are not reproduced. Splits, reverse splits and name changes are reproduced according to BMV rules and Actinver notices.

## Universe snapshot

The official 2026 participant-guide annex lists **207 records**: 40 Mexican equities, 100 SIC equities, 23 funds, 40 ETFs and 4 FIBRAs. The snapshot was normalized from the preserved guide table and compared category-by-category with the preserved 207-symbol raw list. Its source fingerprints and category counts are checked by `actinver-m1 audit`. Text fingerprints canonicalize line endings to LF so Windows and Linux checkouts produce the same digest; the source files themselves are not rewritten.

Every row carries a stable repository instrument ID, its annex category, the guide symbol verbatim and the guide's issuer/name text. No external listing, currency, liquidity or sector facts have been invented: those fields remain `null` where the source does not provide them. The guide warns that its issuer symbol may not be the exact series in the simulator search, so `platform_symbol` and `series` also remain `null`. The data answers “listed in the official guide annex as of date X”; it does not certify that a source label is currently searchable or executable in the authenticated simulator.

The guide annex includes four FIBRAs, while the rules body lists shares, ETFs and investment funds and does not name FIBRAs. The guide explicitly says there are no leveraged ETFs but its ETF appendix includes `PSQ` (“ProShares Short QQQ”). That product's inclusion and the participant short-sale ban are preserved as separate source facts; the dataset does not infer an additional eligibility restriction.

## Source conflicts and conservative behavior

The current official [rules page](https://www.retoactinver.com/bases-y-mecanica) has a displayed title naming 2025 but its body says “Mecánica Reto Actinver 2026” and labels the regulation May–December 2026. The [2026 participant guide](https://www.retoactinver.com/documents/d/reto-actinver/guia-participante_reto-actinver-2026) has the correct edition in its title and includes the annex.

Two eligibility constraints are phrased differently across these sources:

| Topic | Rules body | Participant guide | Stored treatment |
| --- | --- | --- | --- |
| Minimum distinct assets | At least five distinct shares/actions for award eligibility | At least five investment instruments | Both are stored; the stricter five-share reading is used for award screening. |
| 50% concentration | Prohibits purchases in a single share above 50% of portfolio value during the period | Says no more than 50% of portfolio value in one instrument | Both cumulative share purchases and current position weight are screened. Holdings alone cannot certify award eligibility. |
| FIBRAs | Not named in the rules body's list of shares, ETFs and investment funds | Four FIBRAs appear in the annex | Listed in guide snapshot but flagged as a source conflict. |

The [official homepage FAQ](https://www.retoactinver.com/) and regulation put the enrollment deadline at October 4; the participant guide page 7 says October 2. This date conflict does not affect the competition-period fields used for order checks and is preserved in the rules provenance.

The page `https://www.retoactinver.com/es-mx/general` redirects to `/inicio`; its visible content matches the homepage FAQ. It was not treated as an independent source.

## Known verification gaps

1. The exact symbol/series in the logged-in simulator search has not been checked. The current snapshot only promises guide-annex membership.
2. The sources do not settle whether Actinver measures five assets as any guide instrument or only shares, nor whether concentration means peak holding weight or period purchase notional. Both readings must pass before the software says `COMPLIANT`; official award eligibility remains `INDETERMINATE` while these conflicts remain.
3. The calendar classifies scheduled weekdays and listed 2026 holidays only. It cannot predict exceptional suspensions or unlisted shortened sessions.
4. The one-day unfilled-order expiration is published without saying whether “day” means a calendar or business day.
5. The annex supplies no point-in-time sector, liquidity, currency or exact-series attributes. Those values remain unknown rather than being backfilled from present-day sources.

Raw snapshots in `research/source_material/` are preserved and never rewritten by the normalizer. The generator reads those sources and writes only the derived snapshot:

```powershell
python scripts/build_universe_snapshot.py --verified-at-utc <ISO-8601-UTC>
```
