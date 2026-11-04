-- Operational metadata of the pipeline. Unlike the gold tables, it is never dropped, so it
-- keeps the history of every run and of its data quality checks.

CREATE SCHEMA IF NOT EXISTS ops;

CREATE TABLE IF NOT EXISTS ops.pipeline_runs (
    run_id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    started_at      timestamptz NOT NULL DEFAULT now(),
    finished_at     timestamptz,
    status          text NOT NULL DEFAULT 'running',
    years           text NOT NULL,
    changed_inputs  text,
    silver_rows     integer,
    gold_rows       integer,
    message         text
);

CREATE TABLE IF NOT EXISTS ops.quality_checks (
    run_id      bigint NOT NULL REFERENCES ops.pipeline_runs (run_id),
    check_name  text NOT NULL,
    severity    text NOT NULL,
    passed      boolean NOT NULL,
    details     text,
    PRIMARY KEY (run_id, check_name)
);

-- Latest trained version of each model, so a dashboard without the models/ folder (the
-- hosted one) can load it from the database
CREATE TABLE IF NOT EXISTS ops.model_artifacts (
    name        text PRIMARY KEY,
    trained_at  timestamptz NOT NULL DEFAULT now(),
    artifact    bytea NOT NULL
);

-- Version of each bronze input that a run read, copied from the bronze manifest
CREATE TABLE IF NOT EXISTS ops.source_versions (
    run_id       bigint NOT NULL REFERENCES ops.pipeline_runs (run_id),
    source       text NOT NULL,
    version      text,
    sha256       text,
    rows         integer,
    ingested_at  timestamptz,
    PRIMARY KEY (run_id, source)
);
