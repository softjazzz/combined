-- 02_postcheck_split_schema.sql
-- 迁移后检查：schema 落位与 revision

SELECT now() AS check_time;
SELECT current_database() AS db_name, current_user AS db_user, current_setting('search_path') AS search_path;

SELECT version_num FROM alembic_version;

-- qc schema 对象
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema = 'qc'
  AND table_name IN (
    'qc_tasks','qc_task_records','qc_results','qc_defects','qc_defect_history',
    'qc_appeals','qc_appeal_reviews','qc_remediation_tasks','qc_remediation_history',
    'qc_rules','scoring_rules','scoring_config','notifications','qc_coder_workload_daily'
  )
ORDER BY table_name;

-- sys schema 对象
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema = 'sys'
  AND table_name IN ('sys_users','sys_departments','sys_roles','sys_role_permissions')
ORDER BY table_name;

-- cdm 兼容对象
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema = 'cdm'
  AND table_name IN ('medical_records','medical_documents')
ORDER BY table_name;

-- qc schema 视图
SELECT table_schema, table_name AS view_name
FROM information_schema.views
WHERE table_schema = 'qc'
  AND table_name IN (
    'v_qc_task_progress','qc_appeals_statistics','qc_remediation_statistics',
    'qc_assignee_workload','qc_statistics_view','v_qc_coder_ranking'
  )
ORDER BY table_name;
