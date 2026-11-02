BEGIN;

CREATE SCHEMA IF NOT EXISTS cache_raw;
CREATE SCHEMA IF NOT EXISTS sync_ops;

CREATE TABLE IF NOT EXISTS sync_ops.source_interface (
    interface_name text PRIMARY KEY,
    procedure_name text NOT NULL,
    argument_count integer NOT NULL CHECK (argument_count > 0),
    key_fields jsonb NOT NULL,
    publish_target text,
    is_enabled boolean NOT NULL DEFAULT false,
    updated_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO sync_ops.source_interface (
    interface_name, procedure_name, argument_count, key_fields, publish_target, is_enabled
) VALUES (
    'web.mr', 'web.mr', 1,
    '["institute_id","patient_id","visit_id"]'::jsonb, 'cdm.mr', true
)
ON CONFLICT (interface_name) DO UPDATE SET
    procedure_name = EXCLUDED.procedure_name,
    argument_count = EXCLUDED.argument_count,
    key_fields = EXCLUDED.key_fields,
    publish_target = EXCLUDED.publish_target,
    is_enabled = EXCLUDED.is_enabled,
    updated_at = now();

CREATE TABLE IF NOT EXISTS sync_ops.source_schema (
    interface_name text NOT NULL REFERENCES sync_ops.source_interface(interface_name),
    schema_hash text NOT NULL CHECK (length(schema_hash) = 64),
    schema_hash_version text NOT NULL,
    column_count integer NOT NULL CHECK (column_count > 0),
    column_names jsonb NOT NULL,
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (interface_name, schema_hash)
);

CREATE TABLE IF NOT EXISTS sync_ops.sync_batch (
    batch_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    interface_name text NOT NULL REFERENCES sync_ops.source_interface(interface_name),
    window_start timestamptz NOT NULL,
    window_end timestamptz NOT NULL,
    status text NOT NULL CHECK (status IN ('running','succeeded','failed')),
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    rows_fetched bigint NOT NULL DEFAULT 0,
    rows_inserted bigint NOT NULL DEFAULT 0,
    rows_updated bigint NOT NULL DEFAULT 0,
    rows_unchanged bigint NOT NULL DEFAULT 0,
    checkpoint_state text CHECK (checkpoint_state IN ('advanced','held')),
    error_kind text CHECK (error_kind IS NULL OR error_kind IN (
        'configuration_error','interface_not_registered','source_connect_error',
        'source_query_error','schema_validation_error','key_validation_error',
        'lock_conflict','ingest_connect_error','ingest_write_error',
        'publish_contract_error','cdm_connect_error','cdm_write_error','unexpected_error'
    )),
    error_location text,
    CHECK (window_end > window_start),
    CHECK (
        (status = 'running' AND finished_at IS NULL)
        OR (status <> 'running' AND finished_at IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS ix_sync_batch_running
    ON sync_ops.sync_batch (started_at) WHERE status = 'running';

CREATE TABLE IF NOT EXISTS sync_ops.sync_checkpoint (
    interface_name text PRIMARY KEY REFERENCES sync_ops.source_interface(interface_name),
    last_window_start timestamptz NOT NULL,
    last_window_end timestamptz NOT NULL,
    last_batch_id bigint NOT NULL REFERENCES sync_ops.sync_batch(batch_id),
    records_total bigint NOT NULL CHECK (records_total >= 0),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (last_window_end > last_window_start)
);

CREATE TABLE IF NOT EXISTS cache_raw.source_record (
    interface_name text NOT NULL,
    source_key_hash text NOT NULL CHECK (length(source_key_hash) = 64),
    source_key jsonb NOT NULL,
    payload jsonb NOT NULL,
    schema_hash text NOT NULL,
    schema_hash_version text NOT NULL,
    row_hash text NOT NULL CHECK (length(row_hash) = 64),
    source_window_start timestamptz NOT NULL,
    source_window_end timestamptz NOT NULL,
    first_batch_id bigint NOT NULL REFERENCES sync_ops.sync_batch(batch_id),
    last_batch_id bigint NOT NULL REFERENCES sync_ops.sync_batch(batch_id),
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    local_sync_completed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (interface_name, source_key_hash),
    FOREIGN KEY (interface_name, schema_hash)
        REFERENCES sync_ops.source_schema(interface_name, schema_hash),
    CHECK (source_window_end > source_window_start)
);

CREATE INDEX IF NOT EXISTS ix_source_record_schema
    ON cache_raw.source_record (interface_name, schema_hash);
CREATE INDEX IF NOT EXISTS ix_source_record_last_batch
    ON cache_raw.source_record (last_batch_id);

CREATE TABLE IF NOT EXISTS sync_ops.publish_batch (
    publish_batch_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    interface_name text NOT NULL REFERENCES sync_ops.source_interface(interface_name),
    status text NOT NULL CHECK (status IN ('running','succeeded','failed')),
    schema_hash text,
    rows_selected bigint NOT NULL DEFAULT 0,
    rows_written bigint NOT NULL DEFAULT 0,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    error_kind text CHECK (error_kind IS NULL OR error_kind IN (
        'configuration_error','interface_not_registered','source_connect_error',
        'source_query_error','schema_validation_error','key_validation_error',
        'lock_conflict','ingest_connect_error','ingest_write_error',
        'publish_contract_error','cdm_connect_error','cdm_write_error','unexpected_error'
    )),
    error_location text,
    CHECK (
        (status = 'running' AND finished_at IS NULL)
        OR (status <> 'running' AND finished_at IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS ix_publish_batch_running
    ON sync_ops.publish_batch (started_at) WHERE status = 'running';

CREATE TABLE IF NOT EXISTS sync_ops.publish_lineage (
    publish_batch_id bigint NOT NULL
        REFERENCES sync_ops.publish_batch(publish_batch_id) ON DELETE CASCADE,
    source_batch_id bigint NOT NULL REFERENCES sync_ops.sync_batch(batch_id),
    source_key_hash text NOT NULL,
    row_hash text NOT NULL,
    PRIMARY KEY (publish_batch_id, source_key_hash)
);

CREATE TABLE IF NOT EXISTS sync_ops.inspection_batch (
    inspection_batch_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    window_start date NOT NULL,
    window_end date NOT NULL,
    status text NOT NULL CHECK (
        status IN ('running','succeeded','completed_with_failures','failed')
    ),
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    CHECK (window_end >= window_start)
);

CREATE TABLE IF NOT EXISTS sync_ops.inspection_run (
    inspection_batch_id bigint NOT NULL
        REFERENCES sync_ops.inspection_batch(inspection_batch_id) ON DELETE CASCADE,
    interface_name text NOT NULL,
    window_start date,
    window_end date,
    status text NOT NULL CHECK (status IN ('running','succeeded','failed','blocked')),
    row_count bigint NOT NULL DEFAULT 0,
    schema_hash text,
    error_kind text,
    error_location text,
    PRIMARY KEY (inspection_batch_id, interface_name, window_start, window_end)
);

CREATE TABLE IF NOT EXISTS sync_ops.inspection_schema (
    inspection_batch_id bigint NOT NULL
        REFERENCES sync_ops.inspection_batch(inspection_batch_id) ON DELETE CASCADE,
    interface_name text NOT NULL,
    schema_hash text NOT NULL,
    column_names jsonb NOT NULL,
    source_types jsonb NOT NULL,
    PRIMARY KEY (inspection_batch_id, interface_name, schema_hash)
);

CREATE TABLE IF NOT EXISTS cache_raw.source_snapshot (
    inspection_batch_id bigint NOT NULL
        REFERENCES sync_ops.inspection_batch(inspection_batch_id) ON DELETE CASCADE,
    interface_name text NOT NULL,
    window_start date NOT NULL,
    window_end date NOT NULL,
    ordinal bigint NOT NULL,
    source_key jsonb,
    source_key_hash text,
    case_key_hash text,
    key_complete boolean NOT NULL,
    schema_hash text NOT NULL,
    payload jsonb NOT NULL,
    captured_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (
        inspection_batch_id, interface_name, window_start, window_end, ordinal
    )
);

CREATE INDEX IF NOT EXISTS ix_source_snapshot_profile
    ON cache_raw.source_snapshot (inspection_batch_id, interface_name);
CREATE INDEX IF NOT EXISTS ix_source_snapshot_case
    ON cache_raw.source_snapshot (inspection_batch_id, case_key_hash);

CREATE TABLE IF NOT EXISTS sync_ops.source_column_profile (
    inspection_batch_id bigint NOT NULL
        REFERENCES sync_ops.inspection_batch(inspection_batch_id) ON DELETE CASCADE,
    interface_name text NOT NULL,
    ordinal integer NOT NULL,
    column_name text NOT NULL,
    source_type text NOT NULL,
    row_count bigint NOT NULL,
    non_null_count bigint NOT NULL,
    non_null_rate double precision NOT NULL CHECK (
        non_null_rate >= 0 AND non_null_rate <= 1
    ),
    distinct_count bigint NOT NULL,
    distinct_is_approx boolean NOT NULL,
    safe_types jsonb NOT NULL,
    min_length bigint,
    max_length bigint,
    min_date timestamptz,
    max_date timestamptz,
    candidate_key_missing_count bigint NOT NULL DEFAULT 0,
    PRIMARY KEY (inspection_batch_id, interface_name, column_name)
);

CREATE TABLE IF NOT EXISTS sync_ops.source_relation_profile (
    inspection_batch_id bigint NOT NULL
        REFERENCES sync_ops.inspection_batch(inspection_batch_id) ON DELETE CASCADE,
    interface_name text NOT NULL,
    relation_name text NOT NULL,
    relation_fields jsonb NOT NULL,
    anchor_interface text NOT NULL,
    row_count bigint NOT NULL,
    complete_rows bigint NOT NULL,
    missing_rows bigint NOT NULL,
    matched_rows bigint NOT NULL,
    orphan_rows bigint NOT NULL,
    duplicate_rows bigint NOT NULL,
    PRIMARY KEY (inspection_batch_id, interface_name, relation_name)
);

CREATE TABLE IF NOT EXISTS sync_ops.source_target_contract (
    contract_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_interface text NOT NULL,
    source_field text NOT NULL,
    cdm_target text,
    bundle_usage text,
    qc_family text,
    transform_authority text NOT NULL,
    status text NOT NULL CHECK (status IN ('direct','derived','partial','missing','blocked')),
    evidence text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_interface, source_field, cdm_target, bundle_usage, qc_family)
);

INSERT INTO sync_ops.source_target_contract (
    source_interface, source_field, cdm_target, bundle_usage, qc_family,
    transform_authority, status, evidence
) VALUES (
    'web.mr', '*:77-source-columns', 'cdm.mr:*:78-target-columns',
    'bundle:index_coding_settlement', 'unverified', 'explicit_projection_contract',
    'direct', 'frozen_v5_contract_requires_export_recheck'
)
ON CONFLICT (source_interface, source_field, cdm_target, bundle_usage, qc_family)
DO UPDATE SET
    transform_authority = EXCLUDED.transform_authority,
    status = EXCLUDED.status,
    evidence = EXCLUDED.evidence,
    updated_at = now();

COMMIT;
