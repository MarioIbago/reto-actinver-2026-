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
5. The BMV holiday calendar and source-provided liquidity, sector, currency and per-instrument validity attributes were not included in the reviewed source set. Order expiry is published as one day but the calendar/business-day basis is unspecified.
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

Obtain a point-in-time export or user-supplied list of exact symbols/series shown in the authenticated Reto Actinver simulator, and a sourced BMV holiday calendar. Compare them with `actinver-2026-guide-annex-v1`, update the snapshots, and rerun the M1 audit before claiming operational eligibility.
