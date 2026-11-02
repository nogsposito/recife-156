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
