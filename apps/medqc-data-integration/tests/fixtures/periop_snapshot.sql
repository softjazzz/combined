
CREATE SCHEMA IF NOT EXISTS cache_raw;
CREATE SCHEMA IF NOT EXISTS sync_ops;

CREATE TABLE IF NOT EXISTS cache_raw.snapshot_batch (
  batch_id bigserial PRIMARY KEY,
  interface_name text NOT NULL,
  source_date date NOT NULL,
  round_no int NOT NULL,
  status text NOT NULL,
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  result_set_count int,
  row_count int,
  columns_json jsonb,
  schema_hash char(64),
  schema_hash_version text,
  error_class text,
  error_sqlstate text,
  error_native text,
  error_code text,
  UNIQUE (interface_name, source_date, round_no)
);

CREATE TABLE IF NOT EXISTS cache_raw.result_set (
  batch_id bigint NOT NULL REFERENCES cache_raw.snapshot_batch(batch_id),
  result_set_index int NOT NULL,
  columns_json jsonb NOT NULL,
  column_types_json jsonb NOT NULL,
  row_count int NOT NULL,
  PRIMARY KEY (batch_id, result_set_index)
);

CREATE TABLE IF NOT EXISTS cache_raw.snapshot_row (
  batch_id bigint NOT NULL REFERENCES cache_raw.snapshot_batch(batch_id),
  result_set_index int NOT NULL,
  row_number int NOT NULL,
  values_json jsonb NOT NULL,
  row_hash char(64) NOT NULL,
  schema_hash char(64) NOT NULL,
  PRIMARY KEY (batch_id, result_set_index, row_number)
);

CREATE TABLE IF NOT EXISTS sync_ops.source_schema (
  interface_name text NOT NULL,
  schema_hash char(64) NOT NULL,
  schema_hash_version text NOT NULL,
  column_count int NOT NULL,
  column_names_json jsonb NOT NULL,
  first_seen_at timestamptz NOT NULL DEFAULT now(),
  last_seen_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (interface_name, schema_hash)
);

CREATE TABLE IF NOT EXISTS sync_ops.ingest_audit (
  audit_id bigserial PRIMARY KEY,
  batch_id bigint,
  interface_name text NOT NULL,
  source_date date NOT NULL,
  round_no int NOT NULL,
  phase text NOT NULL,
  event text NOT NULL,
  status text NOT NULL,
  code text,
  at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sync_ops.key_validation (
  interface_name text NOT NULL,
  source_date date NOT NULL,
  round_no int NOT NULL,
  candidate_key text NOT NULL,
  total_rows int NOT NULL,
  distinct_keys int NOT NULL,
  null_keys int NOT NULL,
  duplicate_keys int NOT NULL,
  status text NOT NULL,
  checked_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (interface_name, source_date, round_no, candidate_key)
);

CREATE TABLE IF NOT EXISTS cache_raw.record_current (
  interface_name text NOT NULL,
  key_hash char(64) NOT NULL,
  key_json jsonb NOT NULL,
  row_hash char(64) NOT NULL,
  schema_hash char(64) NOT NULL,
  payload_json jsonb NOT NULL,
  batch_id bigint NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (interface_name, key_hash)
);

CREATE TABLE IF NOT EXISTS cache_raw.record_version (
  interface_name text NOT NULL,
  key_hash char(64) NOT NULL,
  row_hash char(64) NOT NULL,
  schema_hash char(64) NOT NULL,
  payload_json jsonb NOT NULL,
  batch_id bigint NOT NULL,
  seen_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (interface_name, key_hash, row_hash)
);

GRANT USAGE ON SCHEMA cache_raw, sync_ops TO medqc_sync;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA cache_raw, sync_ops TO medqc_sync;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA cache_raw, sync_ops TO medqc_sync;
ALTER DEFAULT PRIVILEGES IN SCHEMA cache_raw GRANT SELECT, INSERT, UPDATE ON TABLES TO medqc_sync;
ALTER DEFAULT PRIVILEGES IN SCHEMA sync_ops GRANT SELECT, INSERT, UPDATE ON TABLES TO medqc_sync;
ALTER DEFAULT PRIVILEGES IN SCHEMA cache_raw GRANT USAGE, SELECT ON SEQUENCES TO medqc_sync;
ALTER DEFAULT PRIVILEGES IN SCHEMA sync_ops GRANT USAGE, SELECT ON SEQUENCES TO medqc_sync;
