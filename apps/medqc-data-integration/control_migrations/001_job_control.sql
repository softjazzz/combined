BEGIN;

CREATE SCHEMA sync_control;
REVOKE ALL ON SCHEMA sync_control FROM PUBLIC;

CREATE TABLE sync_control.job (
    job_id uuid PRIMARY KEY,
    idempotency_key varchar(200) NOT NULL UNIQUE,
    request_hash char(64) NOT NULL,
    status text NOT NULL CHECK (status IN ('queued','running','recovery_required','succeeded',
        'completed_with_source_limitations','failed','cancelled')),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    lease_expires_at timestamptz,
    record_json jsonb NOT NULL CHECK (jsonb_typeof(record_json)='object'),
    CHECK (record_json->>'job_id'=job_id::text),
    CHECK (record_json->>'status'=status),
    CHECK (record_json->>'request_hash'=request_hash::text)
);
CREATE INDEX job_queue_order ON sync_control.job(status,created_at,job_id);
CREATE INDEX job_lease_expiry ON sync_control.job(lease_expires_at) WHERE status='running';
-- 即使错误部署两个worker，整个控制库也只能有一个执行或待核对任务。
CREATE UNIQUE INDEX one_active_job ON sync_control.job((1))
    WHERE status IN ('running','recovery_required');

CREATE TABLE sync_control.job_unit (
    unit_id uuid PRIMARY KEY,
    job_id uuid NOT NULL REFERENCES sync_control.job(job_id),
    sequence integer NOT NULL CHECK (sequence>=0),
    status text NOT NULL CHECK (status IN ('queued','running','succeeded','source_limited',
        'failed','cancelled')),
    record_json jsonb NOT NULL CHECK (jsonb_typeof(record_json)='object'),
    UNIQUE(job_id,sequence),
    CHECK (record_json->>'unit_id'=unit_id::text),
    CHECK (record_json->>'job_id'=job_id::text),
    CHECK (record_json->>'status'=status)
);
CREATE UNIQUE INDEX one_running_unit ON sync_control.job_unit(job_id) WHERE status='running';

CREATE TABLE sync_control.job_attempt (
    attempt_id uuid PRIMARY KEY,
    job_id uuid NOT NULL REFERENCES sync_control.job(job_id),
    number integer NOT NULL CHECK (number>0),
    status text NOT NULL CHECK (status IN ('running','recovery_required','succeeded',
        'completed_with_source_limitations','failed','cancelled')),
    record_json jsonb NOT NULL CHECK (jsonb_typeof(record_json)='object'),
    UNIQUE(job_id,number),
    CHECK (record_json->>'attempt_id'=attempt_id::text),
    CHECK (record_json->>'job_id'=job_id::text),
    CHECK (record_json->>'status'=status)
);

CREATE TABLE sync_control.schedule (
    schedule_id uuid PRIMARY KEY,
    version integer NOT NULL CHECK (version>0),
    enabled boolean NOT NULL DEFAULT false,
    next_fire_at timestamptz,
    record_json jsonb NOT NULL CHECK (jsonb_typeof(record_json)='object'),
    CHECK (record_json->>'schedule_id'=schedule_id::text),
    CHECK ((record_json->>'version')::integer=version),
    CHECK ((record_json->>'enabled')::boolean=enabled),
    CHECK ((enabled AND next_fire_at IS NOT NULL) OR (NOT enabled AND next_fire_at IS NULL))
);
CREATE INDEX schedule_due ON sync_control.schedule(next_fire_at) WHERE enabled;

CREATE TABLE sync_control.schedule_fire (
    schedule_id uuid NOT NULL REFERENCES sync_control.schedule(schedule_id),
    fire_at timestamptz NOT NULL,
    job_id uuid NOT NULL REFERENCES sync_control.job(job_id),
    version integer NOT NULL CHECK (version>0),
    record_json jsonb NOT NULL CHECK (jsonb_typeof(record_json)='object'),
    PRIMARY KEY(schedule_id,fire_at),
    CHECK (record_json->>'schedule_id'=schedule_id::text),
    CHECK (record_json->>'job_id'=job_id::text)
);

CREATE TABLE sync_control.event (
    event_id uuid PRIMARY KEY,
    job_id uuid REFERENCES sync_control.job(job_id),
    schedule_id uuid REFERENCES sync_control.schedule(schedule_id),
    created_at timestamptz NOT NULL,
    record_json jsonb NOT NULL CHECK (jsonb_typeof(record_json)='object'),
    CHECK (record_json->>'event_id'=event_id::text)
);
CREATE INDEX event_job_history ON sync_control.event(job_id,created_at);
CREATE INDEX event_schedule_history ON sync_control.event(schedule_id,created_at);

COMMIT;
