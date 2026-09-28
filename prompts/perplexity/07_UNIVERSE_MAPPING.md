# PERPLEXITY PRO — ACTINVER UNIVERSE MAPPING

Use `00_GLOBAL_ROLE.md` first.

Input:
upload the Reto Actinver 2026 participant guide / eligible-universe file.

Goal:
map the eligible universe qualitatively BEFORE any trading model is built.

Important:
this is research, not a recommendation engine.

## Tasks

1. Parse the universe into:
- Mexican equities;
- SIC equities;
- ETFs;
- funds;
- FIBRAs.

2. For each instrument, collect when reasonably available:
- ticker/name;
- country;
- sector/industry;
- primary listing;
- broad risk drivers;
- FX sensitivity;
- commodity sensitivity;
- rates sensitivity;
- earnings/catalyst frequency;
- major scheduled events during the Reto window;
- whether the instrument is usually high/medium/low volatility;
- whether news flow is usually dense or sparse.

3. Create qualitative buckets:
- HIGH VOL / HIGH EVENT DENSITY;
- HIGH BETA;
- COMMODITY SENSITIVE;
- FX SENSITIVE;
- RATE SENSITIVE;
- DEFENSIVE;
- SECTOR ETF;
- BROAD MARKET ETF;
- INVERSE ETF;
- LOW-LIQUIDITY / NEEDS EXECUTION REVIEW;
- OTHER.

4. Flag anomalies or items that need verification:
- stale/deprecated tickers;
- renamed companies;
- mergers/acquisitions;
- unusual local SIC symbols;
- instruments whose exact trading symbol may differ in the Actinver search box;
- anything inconsistent with the official guide.

5. Do NOT rank instruments as “best”.
Do NOT produce BUY/SELL.
Do NOT infer historical alpha.

## Output

Create:

### A. Universe summary
Counts by category.

### B. Instrument table
One row per instrument with the fields above.

### C. Verification queue
Items that must be checked manually in the Actinver platform.

### D. Research-priority buckets
Which parts of the universe deserve separate quantitative research because they behave differently.

### E. Data implications
What historical data sources and frequencies would be needed for:
- Mexican equities;
- SIC equities;
- ETFs;
- funds;
- FIBRAs.

### F. Handoff to Codex
Suggest a normalized schema for:
`data/metadata/actinver_universe.csv`

Do not write production code.
