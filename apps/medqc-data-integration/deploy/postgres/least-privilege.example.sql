-- 由 DBA 在 psql 中先设置两个角色变量；本文件不创建角色、不包含口令。
-- \set ingest_role medqc_ingest_runtime
-- \set publisher_role medqc_cdm_publisher

GRANT USAGE ON SCHEMA cache_raw, sync_ops TO :"ingest_role";
GRANT SELECT, INSERT, UPDATE, DELETE
    ON ALL TABLES IN SCHEMA cache_raw, sync_ops TO :"ingest_role";
GRANT USAGE, SELECT
    ON ALL SEQUENCES IN SCHEMA cache_raw, sync_ops TO :"ingest_role";

-- 在独立 business DB medqc 中执行以下两句；不要把 raw schema 授予发布身份。
GRANT USAGE ON SCHEMA cdm TO :"publisher_role";
GRANT SELECT, INSERT, UPDATE ON TABLE cdm.mr TO :"publisher_role";
