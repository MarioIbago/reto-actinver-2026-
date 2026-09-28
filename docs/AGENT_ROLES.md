# AGENT ROLES — Reto Actinver 2026

## Purpose

Avoid duplicated work, contradictory outputs, and agents overwriting each other.

## ChatGPT Research

Primary role:
- deep academic research;
- tournament theory;
- statistical validation standards;
- market microstructure;
- strategy-family evidence;
- research dossiers for Codex.

Expected output:
`research/dossiers/<topic>.md`

ChatGPT Research should prioritize primary/academic sources and explicitly separate:
- strong evidence;
- mixed evidence;
- negative evidence;
- hypotheses;
- speculation.

## Perplexity Computer

Primary role:
- live web research;
- qualitative company/event research;
- current news discovery;
- source triangulation;
- recurring monitoring;
- browser-based data extraction;
- research dashboards/reports/spreadsheets;
- lightweight prototypes OUTSIDE the core quant engine unless explicitly authorized.

Best use cases:
- overnight news;
- earnings/guidance/filings;
- analyst revisions;
- commodity/FX/macro shocks;
- official Actinver updates;
- competitor/product/source discovery;
- qualitative dossiers;
- monitoring a list of eligible instruments.

Perplexity Computer must NOT become the source of truth for:
- statistical alpha validation;
- backtest results;
- promotion/rejection of strategies;
- final portfolio optimization;
- core repository code.

## Codex

Primary role:
- implementation inside this repository;
- tests;
- CI;
- data pipelines;
- execution simulator;
- validation engine;
- experiment harness;
- alpha models;
- Tournament Brain;
- decision cockpit code.

Codex is the only default agent allowed to change core project code.

## Human owner

Primary role:
- provide Actinver universe/rules/screenshots/data unavailable elsewhere;
- approve phase transitions;
- execute final trades manually;
- resolve account/platform-specific issues.

## Coordination rule

Research agents produce artifacts.
Codex consumes artifacts.
Codex does not silently reinterpret research conclusions.
Research agents do not silently change production code.

## Model-specific note

If Perplexity Computer exposes Claude Fable 5.1 in the orchestrator/model selector, it is a strong candidate for:
- long synthesis;
- multi-source qualitative research;
- adversarial company/event analysis;
- research planning.

Do not hard-code a model name into workflows. Model availability can change.
