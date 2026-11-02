BEGIN;

-- 在既有001控制库上向前增加列；不猜测历史任务的数据面绑定身份。
ALTER TABLE sync_control.job ADD COLUMN binding_identity varchar(67);
ALTER TABLE sync_control.job ADD COLUMN next_retry_at timestamptz;
ALTER TABLE sync_control.job ADD CONSTRAINT job_binding_identity_format
    CHECK (binding_identity IS NULL OR binding_identity ~ '^v1:[0-9a-f]{64}$');
ALTER TABLE sync_control.job ADD CONSTRAINT job_retry_only_failed
    CHECK (next_retry_at IS NULL OR status='failed');
CREATE INDEX job_retry_due ON sync_control.job(next_retry_at,created_at,job_id)
    WHERE status='failed' AND next_retry_at IS NOT NULL;

COMMIT;
