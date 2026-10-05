# M8 Reference Research

Checked for M8 design on 2026-10-05. These sources informed the rank-aware
comparison design; no code or data was copied into this repository.

| Reference | License/activity and fit | Classification |
|---|---|---|
| [stanek-fi/rank_optimization](https://github.com/stanek-fi/rank_optimization) | Public R/DVC replication of rank optimization in the M6 forecasting competition. GitHub has no declared license; the repository is small and has little recent activity. Useful for studying rank objectives, competition simulations, and right-tail tradeoffs. M6's objective and assumptions are not Actinver rules. | STUDY ONLY |
| [stanek-fi/M6](https://github.com/stanek-fi/M6) | Public archive of M6 competition code, with no declared GitHub license. It reflects the M6 horizon, universe, and scoring system; the authors describe manual transformations and mixed results from investment-selection methods. | STUDY ONLY |
| [Mcompetitions/M6-methods](https://github.com/Mcompetitions/M6-methods) | Active public M6 benchmark/methods repository, with no declared GitHub license. Its data, assets, submissions, and evaluation measures are M6-specific. | STUDY ONLY |
| [A Note on the M6 Forecasting Competition: Rank Optimization](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4527154) | The paper studies rank probability and describes cases where higher win probability can come with weaker expected investment outcomes. The paper page reserves rights; this repository paraphrases the concept and does not reproduce text, figures, or data. | STUDY ONLY |

The project objective and portfolio constraints are specific to Reto Actinver,
so the M8 simulator is **BUILD CUSTOM**. It uses joint scenarios, explicit
leaderboard outcomes, locked selection/holdout splits, seeded common random
numbers, a finite feasible-allocation search, and separate rank, return, risk,
and Sharpe comparisons. M6 scoring, short positions, downloaded data, and
third-party code are not reused. No dependency was added.

\n