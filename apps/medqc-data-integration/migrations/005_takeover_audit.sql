BEGIN;

-- 原始历史逐行保存；不借此覆盖正式运行记录，也不向外导出正文。
CREATE SCHEMA IF NOT EXISTS takeover_archive;
CREATE TABLE IF NOT EXISTS takeover_archive.source_catalog (
    source_table text PRIMARY KEY,
    columns_json jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS takeover_archive.source_row (
    source_table text NOT NULL REFERENCES takeover_archive.source_catalog(source_table),
    row_number bigint NOT NULL,
    record_json jsonb NOT NULL,
    record_hash text NOT NULL CHECK (length(record_hash)=64),
    PRIMARY KEY (source_table,row_number)
);
CREATE TABLE IF NOT EXISTS sync_ops.takeover_marker (
    marker_id integer PRIMARY KEY CHECK (marker_id=1),
    source_database text NOT NULL,
    report_json jsonb NOT NULL,
    completed_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS sync_ops.takeover_batch_map (
    legacy_batch_id bigint PRIMARY KEY,
    batch_id bigint NOT NULL UNIQUE REFERENCES sync_ops.sync_batch(batch_id)
);

COMMIT;
