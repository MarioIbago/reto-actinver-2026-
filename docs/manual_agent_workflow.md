# Agent Workflow — Manual Research and Bounded Native Subagents

## Why

OpenAI recommends starting with a single capable agent and adding multi-agent orchestration only when work splits into independent, bounded tasks. Google ADK similarly emphasizes modular specialists, but multi-agent architecture should be introduced deliberately rather than by default.

Official references:
- https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/
- https://developers.openai.com/api/docs/guides/agents-api/multi-agent
- https://developers.openai.com/api/docs/guides/evaluation-best-practices
- https://developers.googleblog.com/developers-guide-to-multi-agent-patterns-in-adk/

## Project rule

Default research workflow:
- **research may use simulated specialist roles**;
- **Codex remains the single writer of production code**;
- no two coding agents should edit the same files in parallel;
- a custom multi-agent SDK/service is postponed until we have evals showing it helps.

On 10 October 2026 the owner explicitly requested three real native Codex
subagents for the daily 07:00 CDMX routine: investigator, accountant and FOMO.
That bounded operational delegation is authorized; it does not introduce a
custom orchestration service or claim a measured improvement. Follow
[the daily contract](daily_0700_operations.md), keep Codex as the sole report
writer and evaluate quality/coverage against a single investigator. The
accountant consumes manually captured evidence; portal interaction stays manual.

## Simulated research team

### 1. Manager
Owns the question, assigns bounded work, merges findings.

### 2. Scientific Researcher
Papers, empirical evidence, statistical methodology, replication.

### 3. Market / Qualitative Researcher
Current company facts, catalysts, news, filings, macro/sector context.

### 4. Skeptic / Falsifier
Looks for contradictory evidence, leakage, stale assumptions, hidden costs, transferability failures.

### 5. Synthesizer
Produces one evidence-weighted dossier for Codex.

## Good parallel tasks
- compare independent papers;
- research several independent strategy families;
- verify separate instruments/events;
- audit different failure modes;
- compare external libraries.

## Bad parallel tasks
- several agents editing the same module;
- ordered implementation where step B depends on step A;
- tiny tasks that one agent can finish quickly;
- multiple agents changing the same configuration or dataset.

## Promotion rule
We do not build custom multi-agent infrastructure until:
1. single-agent/manual-role workflow is working;
2. we have repeated tasks worth parallelizing;
3. we define evals;
4. multi-agent improves quality/coverage enough to justify cost/complexity.
