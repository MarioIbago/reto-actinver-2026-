# GitHub Actions — manual order memo

`.github/workflows/manual-order-memo.yml` validates the latest checked-in
watchlist memo and uploads `memo.md`, `memo.json` and a short summary as a
30-day GitHub Actions artifact. A push that changes a memo starts the workflow;
the Actions page can also run it manually with an optional `YYYY-MM-DD` memo
date.

The workflow checks that the memo contains all 16 tracked instruments, carries
timestamped non-actionable quote metadata and HTTPS source links, states
`NO_TRADE`, and has an empty `orders` array. Its GitHub token is read-only. It
does not fetch market data or news, call an LLM, connect to Actinver, or submit,
modify, or cancel orders. Research must be completed and verified before the
memo is committed; users must confirm fresh prices, account state, exact
simulator identity and costs before any manual entry.

Local validation:

```powershell
python -m unittest discover -s tests -p test_order_memo.py -v
python scripts/validate_order_memo.py --memo-date 2026-10-06 --output-dir $env:TEMP\manual-order-memo
```
