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

## Perplexity Pro

Primary role:
- live web research;
- qualitative company/event research;
- current news discovery;
- source triangulation;
- fast source verification;
- recurring MANUAL research briefs;
- file-assisted research;
- current-market/context discovery.

Use Perplexity Pro Search / Research for:
- overnight news;
- earnings/guidance/filings;
- analyst revisions when sourced;
- commodity/FX/macro shocks;
- official Actinver updates;
- competitor/product/source discovery;
- qualitative dossiers;
- verifying claims before they enter the repo.

If Projects are available, keep a dedicated Actinver project with:
- the eligible-universe file;
- project instructions;
- recurring research threads;
- source documents.

Do NOT assume Perplexity Computer, an authenticated browser session, or scheduled tasks are available unless they are visible in the current account/environment.

Codex may use an installed `agent-browser` skill (`vercel:agent-browser`) or an equivalent available browser-control tool for local UI verification and read-only web inspection. Check that the tool is available and follow its current skill instructions. For UI changes, verify relevant desktop/mobile layouts and key navigation. Browser output is not a substitute for source verification or quantitative evidence. Never automate Actinver login or order entry; execution remains manual.

Perplexity Pro must NOT become the source of truth for:
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

Do not hard-code any Perplexity model name into the workflow. If a model such as Fable 5.1 appears in the user's model selector, it may be tested for synthesis quality, but availability can change.

The architecture depends on ROLE, not model brand.
