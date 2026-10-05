# M1 Phase Report — Rules & Eligible Universe

## Scope and outcome

M1 implementation began after M0 was merged to `main` as `fcff0242c781661f6518e14b3d6978887d12f7f8`. The user explicitly instructed that human approval gates are waived from this point forward. Only M1 rules, universe and related validation were implemented; no strategies or backtests were added.

## Sources checked

Checked on 2026-10-05 at 07:57 UTC:

- [Official rules page](https://www.retoactinver.com/bases-y-mecanica), body titled “Mecánica Reto Actinver 2026,” with regulatory sections (5), (6), (8), (11), (12), and (13). The browser displays a stale 2025 page title despite 2026 body text.
- [Official 2026 participant guide PDF](https://www.retoactinver.com/documents/d/reto-actinver/guia-participante_reto-actinver-2026), pages 18–20 and annex pages 29–41.
- [Official homepage and FAQ](https://www.retoactinver.com/), current 2026 dates and simulation description.
- `https://www.retoactinver.com/es-mx/general` redirects to `/inicio`, so it did not provide an independent rules page.

## Produced

- Ruleset `actinver-2026-rules-v1`, with provenance, effective competition dates, capital, order behavior, costs, buying power, short-sale rules, valuation/corporate-action treatment and explicit ambiguities.
- Point-in-time guide-annex snapshot `actinver-2026-guide-annex-v1` with all 207 listed records, stable repository IDs and category counts 40/100/23/40/4.
- A reproducible generator that reads the preserved raw source snapshots, checks the full symbol sets category-by-category, and writes only `data/metadata/`.
- Rule and universe structural schemas, date queries, snapshot diffs, order/portfolio constraint screens and a CLI.
- The rule checks return an indeterminate status where required history is absent or published interpretations conflict. Simulator platform symbols and series remain null and separate from guide symbols.

## Discrepancies and remaining evidence gaps

1. Five qualifying assets are described as five investment instruments in the guide but five distinct shares/actions in the rules. Both interpretations are stored; the stricter share interpretation is used for conservative screening.
2. The 50% limit is described as a current portfolio allocation in the guide and as purchases in one share during the period in the rules. Both tests are modeled; portfolio holdings alone cannot certify award eligibility.
3. The guide lists four FIBRAs but the rules body does not explicitly name FIBRAs. Those records remain guide-listed and carry a rulebook-conflict flag.
4. The exact symbol/series in the authenticated simulator search was not available from public sources. No login, cookies or simulated orders were accessed; platform symbols remain unverified.
5. At this report's initial review, the BMV holiday calendar was not included. The supplemental capture below resolves that gap for listed 2026 non-working dates. The guide still provides no point-in-time liquidity, sector, currency or per-instrument validity attributes, and order expiry is published as one day without specifying calendar-day versus business-day basis.
6. The sources conflict on enrollment cutoff (guide: October 2; regulation and homepage FAQ: October 4) and the rules-page title says 2025 while its body is explicitly 2026. The discrepancies are recorded in provenance.
7. The official guide PDF was read from Actinver's public URL, but its binary was not saved in `research/source_material/`; stored SHA-256 values fingerprint the preserved Markdown table and compact symbol list, not the PDF bytes.

## Verification

- `python -m pip install -e .` — PASS; installed PyYAML 6.0.3 and the editable project.
- `python -m unittest discover -s tests -v` — PASS; 41 tests.
- `actinver-m1 audit` — PASS; rules structure, source fingerprints and all 207 category counts verified.
- `actinver-m1 eligible --as-of 2026-10-05` — PASS; returns 207 guide-annex records, each explicitly marked platform-symbol-unverified.
- `python -m compileall -q src scripts tests` — PASS.
- Initial GitHub Actions run `37281474397` (run 103) failed only the raw-source fingerprint test because Windows CRLF and Linux LF bytes hashed differently. The generator and verifier now canonicalize text line endings to LF without editing raw files; the full local suite and source audit pass after that fix. The failed run artifact is `11332970763` (SHA-256 `806477a3cdecb79963795a91394eeb21efdb1ad012b04f8901df9382b43d32be`).

No broad research or financial experiments were run; none are in M1 scope.

## Status

M1 OPEN — BLOCKERS REMAIN

## Exact next step

Obtain a point-in-time export of exact symbols/series shown in the authenticated Reto Actinver simulator from an authorized source, compare it with `actinver-2026-guide-annex-v1`, update the snapshot, and rerun the M1 audit before claiming operational eligibility. The simulator mapping is still unverified, so M1 remains OPEN.

## Supplemental BMV calendar capture — 2026-10-05

The [official Grupo BMV 2026 holiday calendar](https://www.bmv.com.mx/es/Grupo_BMV/Calendario_de_dias_festivos/_rid/662/_mod/TAB_DIAS_FEST) was retrieved directly with HTTP 200 at 08:15:08 UTC. The original HTML is preserved at `research/source_material/bmv_2026_holidays_official.html`. The canonicalized-LF SHA-256 recorded in the ruleset is `7702be0373cd46f46a3c273b5dcf02285e94206a44e073f9a8a7cf7ff8eee164`. Its table lists 11 non-working dates in 2026, including Monday 2026-11-02 during the competition.

`actinver-m1 market-day` reports weekends and listed 2026 BMV holidays as `CLOSED`, ordinary listed-year weekdays as `SCHEDULED_SESSION`, and dates without a calendar-year snapshot as `UNKNOWN`. It does not model exceptional suspensions or shortened sessions. The one-day order-expiry ambiguity remains unresolved.

Local follow-up verification:

- `python -m unittest discover -s tests -v` — PASS; 43 tests.
- `actinver-m1 audit` — PASS; all 207 source records, universe fingerprints and the BMV source-capture fingerprint verified.
- `actinver-m1 market-day --as-of 2026-11-02` — PASS; reports the official Día de muertos closure.
- `actinver-m1 market-day --as-of 2026-11-03` — PASS; reports a scheduled session.
- `python -m pip check` — PASS.
- `python -m compileall -q src scripts tests` — PASS.
- Calendar follow-up CI run `37283575486` on commit `22c3aef04c2c3a2f8cfc552cf9ca93192ad61f9b` — PASS; all workflow steps completed successfully. Artifact `11333381383`, SHA-256 `0d333c11d4129aaad9b9ef82a9ea362602fc86532ed957be5790d8994d73b6a9`.
