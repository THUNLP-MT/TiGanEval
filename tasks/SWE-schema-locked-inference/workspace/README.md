# Tabular training and serving pipeline

`pipeline/` holds the model pipeline behind the scoring service.

- `pipeline/protocol.py` is the frozen runtime contract and ships with the
  warehouse and app clients, so it is read-only here. It defines the `Frame` of
  raw rows, `canonical_value` for normalising one raw cell, `FeatureSpec` with
  its include, exclude, drop-constant, and drop-duplicate settings, the
  deterministic `Model` whose output depends on the order and width of its
  inputs, `MATRIX_LOG` recording every design matrix the model was given,
  `RunDirectory`, and `SchemaError`. It also fixes the artifact layout —
  `ARTIFACT_VERSION`, `SCHEMA_KEYS`, `DROP_REASONS`,
  `feature_schema_problems`, `write_feature_schema`, `read_feature_schema`,
  `run_description` — and the two answers the endpoint may give,
  `scored_response` and `rejected_response`.
- `pipeline/pipeline.py` implements `fit`, `evaluate`, `predict`, `export`, and
  `serve`. It is yours to change.
- `pipeline/support.py` is empty and yours.

`serve(row, run)` answers with `{"status": int, "body": {...}}`; the other
consumers return their values directly. A run directory is all a consumer gets:
the training frame is not available after the run finishes. A record the fitted
feature space cannot accept is refused while the row is being built, before the
model is asked for anything, so `MATRIX_LOG` records no input for it.

Recorded run rehearsals are under `project_records/`.
`run_project(action="replay", record="project_records/<name>.json")` runs one
rehearsal against a copy of the workspace and reports the raw timeline: every
operation, its result or error, the design matrices the model received, and the
artifacts each run left behind. A replay does not change the working project
and does not deliver anything for review.

`run_experiment` runs a Python script you write against a throwaway copy of the
workspace, with `pipeline/` importable, so you can build your own frames,
specifications, and requests instead of only re-running the recordings.
