-- 接入库字段合同登记；应用表结构由 MedQC Alembic 000056 管理。
-- 不回填 CDM、不修改 raw、抽取批次或 checkpoint。
BEGIN;

INSERT INTO sync_ops.source_target_contract (
    source_interface, source_field, cdm_target, bundle_usage, qc_family,
    transform_authority, status, evidence
) VALUES (
    'web.daily_course_record', 'record_datetime', 'cdm.daily_course_record:record_datetime',
    'bundle:major_documents', 'document_time', 'explicit_projection_contract_v2',
    'direct', 'source:cache-field-study-20261026-20261028;target:alembic-20261029_000056'
)
ON CONFLICT (source_interface, source_field, cdm_target, bundle_usage, qc_family)
DO UPDATE SET
    transform_authority = EXCLUDED.transform_authority,
    status = EXCLUDED.status,
    evidence = EXCLUDED.evidence,
    updated_at = now();

COMMIT;
