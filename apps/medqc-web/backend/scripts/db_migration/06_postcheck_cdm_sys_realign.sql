-- 06_postcheck_cdm_sys_realign.sql
-- 测试库 schema 整合后检查：对象落位、行数、public 残留

SELECT now() AS check_time;
SELECT current_database() AS db_name, current_user AS db_user, current_setting('search_path') AS search_path;

SELECT version_num FROM alembic_version;

SELECT table_schema, table_name
FROM information_schema.tables
WHERE (table_schema = 'cdm' AND table_name IN (
  'mr','diagnosis','mr_surgery','mr_cost',
  'admission_record','discharge_record',
  'medical_insurance_settlement','medical_insurance_settlement_cost'
))
   OR (table_schema = 'sys' AND table_name IN ('sync_visit_status','sync_watermarks'))
ORDER BY table_schema, table_name;

SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
    'mr','diagnosis','mr_surgery','mr_cost',
    'admission_record','discharge_record',
    'medical_insurance_settlement','medical_insurance_settlement_cost',
    'sync_visit_status','sync_watermarks'
  )
ORDER BY table_name;

SELECT 'cdm.mr' AS target, COUNT(*) AS row_count FROM cdm.mr
UNION ALL
SELECT 'cdm.diagnosis', COUNT(*) FROM cdm.diagnosis
UNION ALL
SELECT 'cdm.mr_surgery', COUNT(*) FROM cdm.mr_surgery
UNION ALL
SELECT 'cdm.mr_cost', COUNT(*) FROM cdm.mr_cost
UNION ALL
SELECT 'cdm.medical_insurance_settlement', COUNT(*) FROM cdm.medical_insurance_settlement
UNION ALL
SELECT 'cdm.medical_insurance_settlement_cost', COUNT(*) FROM cdm.medical_insurance_settlement_cost
UNION ALL
SELECT 'sys.sync_visit_status', COUNT(*) FROM sys.sync_visit_status
UNION ALL
SELECT 'sys.sync_watermarks', COUNT(*) FROM sys.sync_watermarks;
