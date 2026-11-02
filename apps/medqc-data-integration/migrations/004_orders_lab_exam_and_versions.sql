-- 仅用于正式 ingest 存储合同。禁止直接在 DSH 临时验收表结构上执行。
BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema='sync_ops' AND table_name='source_schema'
                     AND column_name='column_names')
       OR NOT EXISTS (SELECT 1 FROM information_schema.columns
                      WHERE table_schema='cache_raw' AND table_name='source_record'
                        AND column_name='source_window_start') THEN
        RAISE EXCEPTION 'formal ingest storage contract required';
    END IF;
END $$;

INSERT INTO sync_ops.source_interface
    (interface_name,procedure_name,argument_count,key_fields,publish_target,is_enabled,evidence_version)
VALUES
    ('web.inpat_drug_order','web.inpat_drug_order',2,'["institute_id","patient_id","visit_id","order_id"]'::jsonb,
     'cdm.inpat_drug_order',true,'cache-field-study/2026-10-26..2026-10-28@sha256:019be2d92c74bd8bce0b01c31098890e7fed1df16ba7392a1e2f63c34af08d71;projection-acceptance@sha256:e2f2b3079e8847b0c991f0b9a44bf25f1ca15e9256585207c0eb27be4fb2ce1b'),
    ('web.inpat_nondrug_order','web.inpat_nondrug_order',2,'["institute_id","patient_id","visit_id","order_id"]'::jsonb,
     'cdm.inpat_nondrug_order',true,'cache-field-study/2026-10-26..2026-10-28@sha256:019be2d92c74bd8bce0b01c31098890e7fed1df16ba7392a1e2f63c34af08d71;projection-acceptance@sha256:e2f2b3079e8847b0c991f0b9a44bf25f1ca15e9256585207c0eb27be4fb2ce1b'),
    ('web.labtest_master','web.labtest_master',1,'["institute_id","patient_id","visit_id","test_id"]'::jsonb,
     'cdm.labtest_master',true,'cache-field-study/2026-10-26..2026-10-28@sha256:019be2d92c74bd8bce0b01c31098890e7fed1df16ba7392a1e2f63c34af08d71;projection-acceptance@sha256:e2f2b3079e8847b0c991f0b9a44bf25f1ca15e9256585207c0eb27be4fb2ce1b'),
    ('web.labtest_item','web.labtest_item',1,'["institute_id","patient_id","visit_id","test_id","test_item_id"]'::jsonb,
     'cdm.labtest_item',true,'cache-field-study/2026-10-26..2026-10-28@sha256:019be2d92c74bd8bce0b01c31098890e7fed1df16ba7392a1e2f63c34af08d71;projection-acceptance@sha256:e2f2b3079e8847b0c991f0b9a44bf25f1ca15e9256585207c0eb27be4fb2ce1b'),
    ('web.labtest_item_report','web.labtest_item_report',1,'["institute_id","patient_id","visit_id","test_id","print_order_id"]'::jsonb,
     'cdm.labtest_item_report',true,'cache-field-study/2026-10-26..2026-10-28@sha256:019be2d92c74bd8bce0b01c31098890e7fed1df16ba7392a1e2f63c34af08d71;projection-acceptance@sha256:e2f2b3079e8847b0c991f0b9a44bf25f1ca15e9256585207c0eb27be4fb2ce1b'),
    ('web.exam_item_report','web.exam_item_report',2,'["institute_id","patient_id","visit_id","exam_id","exam_item_id"]'::jsonb,
     'cdm.exam_item_report',true,'cache-field-study/2026-10-26..2026-10-28@sha256:019be2d92c74bd8bce0b01c31098890e7fed1df16ba7392a1e2f63c34af08d71;projection-acceptance@sha256:e2f2b3079e8847b0c991f0b9a44bf25f1ca15e9256585207c0eb27be4fb2ce1b')
ON CONFLICT (interface_name) DO UPDATE SET
    procedure_name=EXCLUDED.procedure_name,argument_count=EXCLUDED.argument_count,
    key_fields=EXCLUDED.key_fields,publish_target=EXCLUDED.publish_target,
    is_enabled=EXCLUDED.is_enabled,evidence_version=EXCLUDED.evidence_version,updated_at=now();

CREATE TABLE IF NOT EXISTS cache_raw.source_record_version (
    interface_name text NOT NULL,
    source_key_hash text NOT NULL CHECK (length(source_key_hash)=64),
    batch_id bigint NOT NULL REFERENCES sync_ops.sync_batch(batch_id),
    schema_hash text NOT NULL,
    schema_hash_version text NOT NULL,
    row_hash text NOT NULL CHECK (length(row_hash)=64),
    source_key jsonb NOT NULL,
    payload jsonb NOT NULL,
    observed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (interface_name,source_key_hash,batch_id),
    FOREIGN KEY (interface_name,schema_hash)
        REFERENCES sync_ops.source_schema(interface_name,schema_hash)
);

-- 升级既有正式库时仅保存当前可见版本，不能宣称恢复升级前的历史。
INSERT INTO cache_raw.source_record_version
    (interface_name,source_key_hash,batch_id,schema_hash,schema_hash_version,
     row_hash,source_key,payload,observed_at)
SELECT interface_name,source_key_hash,last_batch_id,schema_hash,schema_hash_version,
       row_hash,source_key,payload,local_sync_completed_at
FROM cache_raw.source_record AS current_row
WHERE NOT EXISTS (
    SELECT 1 FROM cache_raw.source_record_version AS previous
    WHERE previous.interface_name=current_row.interface_name
      AND previous.source_key_hash=current_row.source_key_hash
)
ON CONFLICT (interface_name,source_key_hash,batch_id) DO NOTHING;

COMMIT;
