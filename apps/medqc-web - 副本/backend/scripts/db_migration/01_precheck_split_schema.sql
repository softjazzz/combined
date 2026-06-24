-- 01_precheck_split_schema.sql
-- 迁移前检查：对象分布、版本号、search_path

SELECT now() AS check_time;
SELECT current_database() AS db_name, current_user AS db_user, current_setting('search_path') AS search_path;

SELECT version_num FROM alembic_version;

-- 关键表位置
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_name IN (
  'qc_tasks','qc_task_records','qc_results','qc_defects','qc_defect_history',
  'qc_appeals','qc_appeal_reviews','qc_remediation_tasks','qc_remediation_history',
  'qc_rules','scoring_rules','scoring_config','notifications',
  'sys_users','sys_departments','medical_records','medical_documents'
)
ORDER BY table_schema, table_name;

-- 关键视图位置
SELECT table_schema, table_name AS view_name
FROM information_schema.views
WHERE table_name IN (
  'v_qc_task_progress','qc_appeals_statistics','qc_remediation_statistics',
  'qc_assignee_workload','qc_statistics_view','v_qc_coder_ranking'
)
ORDER BY table_schema, table_name;
