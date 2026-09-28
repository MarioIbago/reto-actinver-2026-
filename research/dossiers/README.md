# Research Dossiers

This directory stores deep-research outputs that precede implementation.

A dossier is **not code** and **not a trading recommendation**. It is an evidence package for later conversion into falsifiable hypotheses and ExperimentSpec objects.

## Required sections

Each serious dossier should include:

1. Research question
2. Why it matters for Reto Actinver
3. Relevant horizon(s)
4. Primary / academic sources
5. Strong evidence
6. Mixed or contradictory evidence
7. Negative evidence
8. Transferability limits to Mexico/BMV/SIC/Actinver
9. Data requirements
10. Point-in-time / leakage risks
11. Candidate falsifiable hypotheses
12. Suggested baselines
13. Suggested validation design
14. Open questions
15. What Codex should test
16. What NOT to infer

## Rules

- Prefer primary and academic sources.
- Separate evidence from interpretation.
- Preserve contradictory findings.
- Do not claim alpha from literature alone.
- Do not write BUY/SELL recommendations.
- Do not silently convert another market/horizon into an Actinver conclusion.
- Link every implementation hypothesis back to the dossier/source that motivated it.

## Workflow

```text
ChatGPT Research / Perplexity / human research
        ↓
research/dossiers/<topic>.md
        ↓
falsifiable hypothesis
        ↓
ExperimentSpec
        ↓
Codex implementation
        ↓
validation
```

Research dossiers may be produced in parallel with M0 because they do not change production code or phase gates.
