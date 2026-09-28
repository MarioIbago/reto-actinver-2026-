# Reference Projects — Reto Actinver 2026

This file is a curated map of external open-source projects worth studying before implementing major components.

These projects are **references, not automatic dependencies**. Codex must not copy architecture, code, assumptions, execution semantics, data conventions, or licenses blindly. For every project considered for direct reuse, verify:
- current license and compatibility;
- maintenance/activity;
- data model assumptions;
- asset-class/exchange assumptions;
- point-in-time behavior;
- execution semantics;
- whether the component helps our specific objective: maximize scientifically defensible P(final_rank = 1) in Reto Actinver 2026.

## A. Tournament / rank optimization — highest priority for M8

### stanek-fi/rank_optimization
https://github.com/stanek-fi/rank_optimization

Replication repository for "A Note on the M6 Forecasting Competition: Rank Optimization".

Why study:
- directly addresses rank optimization in an investment competition;
- contains simulated and bootstrapped competition runs;
- includes leaderboard comparison, scaling effects, position effects and competition statistics;
- uses DVC for reproducible experiments.

Use for:
- conceptual design of Tournament Brain;
- modeling rank-dependent objective functions;
- competitor/leaderboard simulation ideas;
- experiment reproducibility patterns.

Do NOT assume M6 constraints equal Actinver constraints.

### stanek-fi/M6
https://github.com/stanek-fi/M6

Published code used for actual M6 competition submissions.

Why study:
- shows how a live competition codebase evolves under time pressure;
- useful for observing forecast → allocation → competition workflow;
- includes links to rank-optimization work.

### Mcompetitions/M6-methods
https://github.com/Mcompetitions/M6-methods

Official/community M6 data, benchmarks and submitted methods.

Why study:
- benchmark construction;
- competition evaluation;
- relationship between forecasts and portfolio decisions;
- submitted decision weights and ranking probabilities.

## B. Execution/backtesting architecture — M3/M4

### QuantConnect/Lean
https://github.com/QuantConnect/Lean

Large algorithmic-trading engine with Python/C# support.

Why study:
- event-driven architecture;
- securities/portfolio/accounting abstractions;
- order lifecycle;
- transaction models;
- backtest reproducibility.

Use as architecture reference, not as a reason to inherit its exchange assumptions.

### NautilusTrader
https://github.com/nautechsystems/nautilus_trader

Production-grade event-driven trading engine.

Why study:
- deterministic event-driven simulation;
- explicit order/execution state;
- quote/trade/tick handling;
- backtest/live parity;
- modular adapters and message bus.

This is especially relevant to the design of ActinverExecutionSimulator.

### backtesting.py
https://github.com/kernc/backtesting.py

Compact Python backtesting framework.

Why study:
- small/simple API;
- readable baseline architecture;
- interactive result visualization.

Good reference for simplicity. Not sufficient by itself for Actinver execution semantics.

## C. Portfolio optimization / risk — M7/M8

### skfolio
https://github.com/skfolio/skfolio

Portfolio optimization library built around a scikit-learn-style API.

Why study:
- cross-validation-friendly portfolio models;
- stress testing;
- transaction-cost-aware portfolio optimization;
- estimator-style interfaces.

Strong candidate for reusable concepts and possibly direct library use after evaluation.

### Riskfolio-Lib
https://github.com/dcajasn/Riskfolio-Lib

Portfolio optimization with many convex risk measures.

Why study:
- broad risk-measure support;
- Kelly/log-growth formulations;
- CVXPY-based optimization;
- drawdown/tail-risk tools.

Useful for scenario comparisons, but Tournament Brain requires a custom rank objective beyond standard portfolio optimization.

### PyPortfolioOpt
https://github.com/PyPortfolio/PyPortfolioOpt

Classical and modern portfolio optimization tools.

Why study:
- simple baselines;
- efficient frontier;
- Black-Litterman;
- hierarchical risk parity.

Main value for this project: baseline/control implementation, not final tournament objective.

## D. Experiment tracking / scientific memory — M0/M4/M5

### MLflow
https://github.com/mlflow/mlflow

Experiment/evaluation/tracking platform.

Why study:
- experiment IDs;
- parameters;
- metrics;
- artifacts;
- model/evaluation lineage.

Do not automatically adopt MLflow. Compare its complexity against our lightweight ExperimentSpec / ExperimentResult ledger.

### DVC patterns in rank_optimization
https://github.com/stanek-fi/rank_optimization

This repository itself is a useful example of data/versioned experiment pipelines.

Why study:
- data lineage;
- reproducible experiment commands;
- pipeline stages;
- deterministic reruns.

## E. News / NLP — M6

### ProsusAI/finBERT
https://github.com/ProsusAI/finBERT

Financial-domain BERT sentiment model.

Why study:
- historical baseline for finance-specific text classification;
- comparison target against LLM structured extraction.

Important: sentiment alone is NOT our target architecture. Our design is:
news/event → structured point-in-time features → statistical validation → conditional return distribution.

FinBERT should be used as a baseline where appropriate, not as proof of trading alpha.

### OpenBB
https://github.com/OpenBB-finance/OpenBB

Open financial data platform for analysts, quants and AI agents.

Why study:
- provider abstraction;
- normalized financial-data interfaces;
- research workflows;
- data-agent ergonomics.

Potential inspiration for data-provider abstraction and research tooling.

## F. UI / UX — M9 and late-stage decision cockpit

UI should not become a separate trading product. The target is a **decision cockpit** for one competition participant.

### FreqUI
https://github.com/freqtrade/frequi

Web frontend for Freqtrade.

Study:
- positions/trades presentation;
- status/health views;
- separation between engine and frontend;
- interaction density;
- operational monitoring.

Do not reuse crypto-specific assumptions.

### TradingView Lightweight Charts
https://github.com/tradingview/lightweight-charts

High-performance financial charting library.

Study/use candidate for:
- price/volume charts;
- entry/invalidation/target overlays;
- event markers;
- portfolio/trade review.

Verify attribution/license requirements before integration.

### OpenTerminalUI
https://github.com/Marcikschmid/OpenTerminal

Terminal-style research/trading UI.

Study:
- multi-panel quant workspace;
- screener/research separation;
- portfolio lab;
- model/backtest presentation;
- terminal-style information architecture.

Treat as UX inspiration. Independently verify maturity, data assumptions and licensing before any reuse.

### BackDash
https://github.com/sajalkmr/backdash

Visual quantitative backtest dashboard.

Study:
- asynchronous backtest UX;
- progress/cancellation;
- result analytics;
- strategy builder concepts.

The drag-and-drop strategy-builder concept is NOT a priority for us; result visualization is more relevant.

### QuantNova
https://github.com/yashvardhancse/QuantNova

GUI-based quantitative backtesting foundation.

Study:
- frontend/backend boundary;
- strategy/backtest visualization;
- beginner-friendly interaction model.

Use as UX architecture reference, not as quant evidence.

### Ghostfolio
https://github.com/ghostfolio/ghostfolio

Open-source portfolio/wealth dashboard.

Study:
- portfolio composition views;
- performance attribution;
- responsive dashboard information hierarchy;
- clean holdings presentation.

It is not a tournament/trading engine; UX reference only.

## G. Proposed Actinver UI information architecture

Do not build this in M0. Preserve as target UX for M9.

### 1. Competition Header
- current capital;
- rank;
- leader capital/return;
- gap to leader;
- days/sessions remaining;
- data freshness;
- risk mode: DEFEND / NEUTRAL / CATCH-UP.

### 2. Action Queue
The most important panel:
- BUY;
- SELL;
- HOLD;
- NO TRADE;
- CANCEL/REPRICE suggestion where applicable.

Each action should show:
- ticker;
- size;
- entry range;
- do-not-chase level;
- invalidation/stop;
- targets/exit logic;
- horizon;
- catalyst;
- P(upside threshold);
- P(downside threshold);
- confidence/believability;
- estimated contribution to P(#1).

### 3. Candidate Radar
Ranked candidates with:
- Alpha Score;
- Believability Score;
- event/news status;
- volume/liquidity;
- estimated return distribution;
- right-tail probability;
- correlation with current book.

### 4. Portfolio / Tournament Panel
- holdings;
- exposure;
- concentration;
- cash;
- rule compliance;
- scenario distribution;
- simulated final-rank distribution;
- P(#1).

### 5. Evidence Drawer
For any recommendation:
- model/features;
- analogous historical cases;
- relevant news;
- validation status;
- experiment IDs;
- known failure modes;
- Bear Analyst objections.

### 6. Timeline / Event Feed
Only material events:
- earnings;
- guidance;
- filings;
- macro/FX/commodity shock;
- analyst revisions;
- official Actinver changes.

### 7. Research Health
Not necessarily on the daily trading screen:
- promoted/rejected hypotheses;
- OOS metrics;
- data quality;
- stale pipelines;
- failed workflows.

## H. UX principles

1. Action first, explanation second.
2. Always display data timestamp/freshness.
3. Never show precision unsupported by data.
4. Make NO TRADE a first-class action.
5. Separate Alpha confidence from Tournament utility.
6. Clearly show rule violations before an action reaches the user.
7. Store every recommendation for post-mortem analysis.
8. Avoid a Bloomberg clone: optimize for this competition and this single user.
9. Mobile-friendly emergency view may be useful, but desktop cockpit is primary.
10. The UI never executes Actinver orders automatically.

## I. Build-vs-borrow policy

Before implementing a component, Codex must classify it as:
- BUILD CUSTOM — Actinver-specific logic or tournament objective;
- ADAPT — generic library with a thin project-specific wrapper;
- STUDY ONLY — useful architecture/UX but wrong assumptions or licensing;
- IGNORE — does not materially improve the objective.

Likely initial classification:
- Tournament Brain: BUILD CUSTOM.
- ActinverExecutionSimulator: BUILD CUSTOM, inspired by Lean/Nautilus.
- Portfolio math: ADAPT where skfolio/Riskfolio/PyPortfolioOpt help.
- Experiment ledger: BUILD LIGHTWEIGHT first; compare with MLflow/DVC.
- News structured extraction: BUILD CUSTOM; FinBERT as baseline.
- Charts: ADAPT likely.
- UI shell: BUILD CUSTOM; study FreqUI/OpenTerminalUI/Ghostfolio/BackDash.
