-- 05_precheck_cdm_sys_realign.sql
-- 测试库 schema 整合前检查：对象位置、行数、search_path

SELECT now() AS check_time;
SELECT current_database() AS db_name, current_user AS db_user, current_setting('search_path') AS search_path;

SELECT version_num FROM alembic_version;

SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_name IN (
  'mr','diagnosis','mr_surgery','mr_cost',
  'admission_record','discharge_record',
  'medical_insurance_settlement','medical_insurance_settlement_cost',
  'sync_visit_status','sync_watermarks'
)
ORDER BY table_name, table_schema;

SELECT 'public.mr' AS target, COUNT(*) AS row_count FROM public.mr
UNION ALL
SELECT 'public.diagnosis', COUNT(*) FROM public.diagnosis
UNION ALL
SELECT 'public.mr_surgery', COUNT(*) FROM public.mr_surgery
UNION ALL
SELECT 'public.mr_cost', COUNT(*) FROM public.mr_cost
UNION ALL
SELECT 'public.medical_insurance_settlement', COUNT(*) FROM public.medical_insurance_settlement
UNION ALL
SELECT 'public.medical_insurance_settlement_cost', COUNT(*) FROM public.medical_insurance_settlement_cost
UNION ALL
SELECT 'public.sync_visit_status', COUNT(*) FROM public.sync_visit_status
UNION ALL
SELECT 'public.sync_watermarks', COUNT(*) FROM public.sync_watermarks;
