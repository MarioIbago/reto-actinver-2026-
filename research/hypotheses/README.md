# Research hypotheses

Each JSON file in this directory is a versioned, falsifiable hypothesis. The
M5 batch plan binds it to an executable M4 validation case by file hash; the
case contains the exact dataset/universe identifiers, temporal splits,
parameter variants, benchmark, costs, seed, and promotion criteria.

The research factory requires a preregistered hypothesis file and a
preregistered case fingerprint before it runs. It stores all negative results,
run failures, evidence gaps, and decisions in a separate append-only JSONL
ledger. `research/ledger.jsonl` remains the historical M0 smoke ledger.

`TORN-001_rank_vs_expected_return.json` is a planned tournament hypothesis
from the research dossier. It is intentionally not executable in M5: its
portfolio/opponent simulator belongs to M8, and no tournament data or
authorized market return distributions currently exist.
