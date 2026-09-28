# Architecture — Reto Actinver 2026

## 1. Goal

Construir un sistema modular en el que:
- el razonamiento lingüístico esté separado del cálculo financiero;
- la investigación esté separada de producción;
- prediction esté separada de tournament decision;
- cada resultado importante sea reproducible;
- la ejecución final de órdenes siga siendo humana.

## 2. Layer model

```text
Layer 0 — Source Material
official rules / participant guide / eligible universe / papers / market data / events / news

Layer 1 — Research Intelligence
ChatGPT Research / Perplexity / manual specialist roles
outputs: dossiers, source maps, hypotheses, uncertainty

Layer 2 — Research Orchestration
Codex
outputs: ExperimentSpec, code changes, tests, workflow inputs

Layer 3 — Deterministic Execution
Python + GitHub Actions / remote runner
outputs: datasets, metrics, backtests, simulations, artifacts

Layer 4 — Scientific Validation
OOS / walk-forward / leakage / costs / execution / robustness / multiple testing

Layer 5 — Alpha Engine
only promoted evidence
outputs: return distributions, probabilities, uncertainty

Layer 6 — Risk & Constraints
cash / exposure / correlation / liquidity / concentration / official rules

Layer 7 — Tournament Brain
rank / leader gap / days remaining / scenarios / opponent uncertainty
objective: P(final_rank = 1)

Layer 8 — Decision Interface
Trade Sheet / morning report / event update / cockpit / evidence drawer

Layer 9 — Human Execution
manual entry in Reto Actinver
```

## 3. Critical separations

### Language vs mathematics
LLMs can structure text and reason about evidence. Numerical claims must come from deterministic code when they are computationally testable.

### Research vs promoted logic
Research modules may fail and be discarded. Promoted modules require explicit validation state.

### Alpha vs Tournament
Alpha asks:
> What distribution of returns is plausible?

Tournament Brain asks:
> Given those distributions and current contest state, what portfolio best serves P(#1)?

### Raw source vs normalized data
Raw evidence in `research/source_material/` is immutable source context.
Normalized operational data belongs in `data/metadata/` or data pipelines.

## 4. Core contracts

### ExperimentSpec

Minimum target fields:
```text
experiment_id
hypothesis
strategy_family
dataset_version
universe_version
features
target
horizon
train_period
validation_period
test_period
parameters
transaction_cost_model
execution_model
benchmark
promotion_criteria
seed
commit_sha
```

### ExperimentResult

```text
experiment_id
commit_sha
dataset_version
universe_version
in_sample_metrics
validation_metrics
out_of_sample_metrics
cost_adjusted_metrics
turnover
drawdown
bootstrap_results
stability_results
leakage_checks
multiple_testing_context
promotion_status
rejection_reason
artifacts
```

### EventFeatures

```text
ticker/entity
event_type
event_time
first_public_time
source
source_quality
novelty
direction
surprise
guidance_direction
materiality
confidence
raw_source_ref
extraction_version
```

### AlphaCandidate

```text
symbol
generated_at
horizon
return_distribution
probability_thresholds
alpha_score
believability_score
liquidity
catalysts
invalidation
supporting_experiments
data_as_of
```

### TournamentState

```text
capital
cash
holdings
current_return
rank
leader_return_or_capital
days_remaining
official_constraints
leaderboard_uncertainty
```

### TradeInstruction

```text
action
symbol
target_size
entry_range
do_not_chase
invalidation
targets_or_exit_logic
horizon
alpha_rationale
tournament_rationale
risk
confidence
data_as_of
```

## 5. Repository responsibilities

```text
config/                versioned project/rule/research configuration
data/raw/              immutable ingested datasets (when license permits)
data/interim/          deterministic transformations
data/processed/        research-ready outputs
data/metadata/         manifests, universe, provenance

research/source_material/ raw human/official evidence snapshots
research/papers/          paper records
research/hypotheses/      falsifiable ideas
research/accepted/        promoted research evidence
research/rejected/        negative scientific memory

experiments/specs/      ExperimentSpec
experiments/results/    machine-readable ExperimentResult

src/actinver/data/       data interfaces/pipelines
src/actinver/execution/  Actinver execution semantics
src/actinver/features/   point-in-time features
src/actinver/strategies/ research implementations
src/actinver/validation/ OOS/robustness/multiple testing
src/actinver/portfolio/  risk/portfolio primitives
src/actinver/tournament/ rank objective/scenarios
src/actinver/news/       event extraction/ingestion
src/actinver/reporting/  trade sheets/reports/cockpit contracts
```

Do not fill these modules before their phase owns them.

## 6. GitHub Actions contract

A research workflow should eventually:
1. receive explicit inputs;
2. checkout exact code;
3. install pinned/reproducible dependencies;
4. identify data/universe/config versions;
5. run validation/tests first;
6. execute deterministic work;
7. emit structured result files;
8. upload artifacts;
9. preserve enough logs to diagnose failures;
10. run with least privilege.

M0 only needs the smallest proof of this contract.

## 7. M0 proof-of-harness

Required conceptual path:

```text
workflow_dispatch / CI
        ↓
clean runner
        ↓
install tiny package
        ↓
unit tests
        ↓
deterministic smoke experiment
        ↓
JSON result
        ↓
schema/basic validation
        ↓
GitHub Actions artifact
```

The smoke experiment has no market meaning.

## 8. Reproducibility identity

A meaningful result should be recoverable from:
```text
commit SHA
+ data version
+ universe version
+ config/parameters
+ dependency versions
+ seed
```

## 9. Compute boundary

Local:
- lint;
- unit tests;
- schemas;
- small deterministic examples.

Remote/Actions:
- broad backtests;
- universe-wide jobs;
- bootstrap;
- Monte Carlo;
- ML;
- large ingestion;
- batch news/event processing.

Strict intraday monitoring, if later needed, must be a separate service/runner using the same validated contracts.

## 10. Agent boundary

Research roles may operate in parallel on independent questions.

Production-code writes should remain single-writer by default (Codex) to avoid conflicting mutable state.

See:
- `docs/AGENT_ROLES.md`
- `docs/manual_agent_workflow.md`

## 11. Security and licensing

- never commit secrets;
- least-privilege workflow permissions;
- licensed/proprietary raw data is not committed unless allowed;
- verify external code licenses before reuse;
- preserve source provenance;
- never log credentials.

## 12. Final execution boundary

No component should directly submit or modify orders in the Reto Actinver portal.

The repository ends at an explainable decision/trade instruction. Human execution is mandatory.
