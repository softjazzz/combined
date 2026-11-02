BEGIN;

ALTER TABLE sync_ops.source_interface
    ADD COLUMN IF NOT EXISTS evidence_version text NOT NULL DEFAULT 'legacy/unversioned';
ALTER TABLE sync_ops.sync_batch
    ADD COLUMN IF NOT EXISTS evidence_version text NOT NULL DEFAULT 'legacy/unversioned';
ALTER TABLE sync_ops.publish_batch
    ADD COLUMN IF NOT EXISTS evidence_version text NOT NULL DEFAULT 'legacy/unversioned';

INSERT INTO sync_ops.source_interface (
    interface_name, procedure_name, argument_count, key_fields, publish_target,
    is_enabled, evidence_version
) VALUES
    ('web.mr', 'web.mr', 1,
     '["institute_id","patient_id","visit_id"]'::jsonb,
     'cdm.mr', true,
     'cache-field-study/2026-10-26..2026-10-28@sha256:019be2d92c74bd8bce0b01c31098890e7fed1df16ba7392a1e2f63c34af08d71'),
    ('web.admission_record', 'web.admission_record', 1,
     '["institute_id","patient_id","visit_id","documentid"]'::jsonb,
     'cdm.admission_record', true,
     'cache-field-study/2026-10-26..2026-10-28@sha256:019be2d92c74bd8bce0b01c31098890e7fed1df16ba7392a1e2f63c34af08d71'),
    ('web.first_course_record', 'web.first_course_record', 1,
     '["institute_id","patient_id","visit_id","documentid"]'::jsonb,
     'cdm.first_course_record', true,
     'cache-field-study/2026-10-26..2026-10-28@sha256:019be2d92c74bd8bce0b01c31098890e7fed1df16ba7392a1e2f63c34af08d71'),
    ('web.daily_course_record', 'web.daily_course_record', 1,
     '["institute_id","patient_id","visit_id","document_id"]'::jsonb,
     'cdm.daily_course_record', true,
     'cache-field-study/2026-10-26..2026-10-28@sha256:019be2d92c74bd8bce0b01c31098890e7fed1df16ba7392a1e2f63c34af08d71'),
    ('web.senior_course_record', 'web.senior_course_record', 1,
     '["institute_id","patient_id","visit_id","documentid"]'::jsonb,
     'cdm.senior_course_record', true,
     'cache-field-study/2026-10-26..2026-10-28@sha256:019be2d92c74bd8bce0b01c31098890e7fed1df16ba7392a1e2f63c34af08d71'),
    ('web.consultation_record', 'web.consultation_record', 1,
     '["institute_id","patient_id","visit_id","documentid"]'::jsonb,
     'cdm.consultation_record', true,
     'cache-field-study/2026-10-26..2026-10-28@sha256:019be2d92c74bd8bce0b01c31098890e7fed1df16ba7392a1e2f63c34af08d71'),
    ('web.discharge_record', 'web.discharge_record', 1,
     '["institute_id","patient_id","visit_id","document_id"]'::jsonb,
     'cdm.discharge_record', true,
     'cache-field-study/2026-10-26..2026-10-28@sha256:019be2d92c74bd8bce0b01c31098890e7fed1df16ba7392a1e2f63c34af08d71')
ON CONFLICT (interface_name) DO UPDATE SET
    procedure_name = EXCLUDED.procedure_name,
    argument_count = EXCLUDED.argument_count,
    key_fields = EXCLUDED.key_fields,
    publish_target = EXCLUDED.publish_target,
    is_enabled = EXCLUDED.is_enabled,
    evidence_version = EXCLUDED.evidence_version,
    updated_at = now();

INSERT INTO sync_ops.source_target_contract (
    source_interface, source_field, cdm_target, bundle_usage, qc_family,
    transform_authority, status, evidence
) VALUES
    ('web.mr', '*:148-source-columns', 'cdm.mr:*:77-source+1-local',
     'bundle:index_coding_settlement', 'frontpage', 'explicit_projection_contract',
     'direct', 'cache-field-study-20261026-20261028:148-columns'),
    ('web.admission_record', '*:25-source-columns', 'cdm.admission_record:owned-fields',
     'bundle:major_documents', 'document_content', 'explicit_alias_projection',
     'direct', 'cache-field-study-20261026-20261028:25-columns'),
    ('web.first_course_record', '*:29-source-columns', 'cdm.first_course_record:owned-fields',
     'bundle:major_documents', 'document_content', 'explicit_alias_projection',
     'direct', 'cache-field-study-20261026-20261028:29-columns'),
    ('web.daily_course_record', '*:34-source-columns', 'cdm.daily_course_record:owned-fields',
     'bundle:major_documents', 'document_content', 'explicit_projection_contract',
     'direct', 'cache-field-study-20261026-20261028:34-columns'),
    ('web.senior_course_record', '*:24-source-columns', 'cdm.senior_course_record:owned-fields',
     'bundle:major_documents', 'document_content', 'explicit_alias_projection',
     'direct', 'cache-field-study-20261026-20261028:24-columns'),
    ('web.consultation_record', '*:24-source-columns', 'cdm.consultation_record:owned-fields',
     'bundle:major_documents', 'document_content', 'explicit_alias_projection',
     'direct', 'cache-field-study-20261026-20261028:24-columns'),
    ('web.discharge_record', '*:29-source-columns', 'cdm.discharge_record:owned-fields',
     'bundle:major_documents', 'document_content', 'explicit_projection_contract',
     'direct', 'cache-field-study-20261026-20261028:29-columns')
ON CONFLICT (source_interface, source_field, cdm_target, bundle_usage, qc_family)
DO UPDATE SET
    transform_authority = EXCLUDED.transform_authority,
    status = EXCLUDED.status,
    evidence = EXCLUDED.evidence,
    updated_at = now();

COMMIT;
