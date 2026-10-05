# M7 Signal Registry

`registry.json` is intentionally empty because the verified M5 factory ledger
has no instrument-level `PROMOTE` records. Do not add a signal based on a
synthetic test, narrative, paper result, or an M5 promotion for a different
target.

An entry must match the latest verified M5 record's hypothesis, experiment,
strategy family, feature list, authorized PIT dataset manifest, M1 universe,
net-of-cost instrument-return target, exact transaction-cost model, forecast
artifact content digest, and horizon. The M5 result must carry the matching
instrument forecast artifact metadata. It must use a quantitative source. See
`schemas/promoted_signal_registry.schema.json` and
`docs/actinver_alpha_ensemble.md`.
