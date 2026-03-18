-- 03_rollback_to_public.sql
-- 紧急回滚：将 split schema 对象搬回 public（与 000002 downgrade 等价）

-- 视图先回滚
ALTER VIEW IF EXISTS qc.v_qc_task_progress SET SCHEMA public;
ALTER VIEW IF EXISTS qc.qc_appeals_statistics SET SCHEMA public;
ALTER VIEW IF EXISTS qc.qc_remediation_statistics SET SCHEMA public;
ALTER VIEW IF EXISTS qc.qc_assignee_workload SET SCHEMA public;
ALTER VIEW IF EXISTS qc.qc_statistics_view SET SCHEMA public;
ALTER VIEW IF EXISTS qc.v_qc_coder_ranking SET SCHEMA public;

-- cdm 兼容对象
ALTER TABLE IF EXISTS cdm.medical_records SET SCHEMA public;
ALTER TABLE IF EXISTS cdm.medical_documents SET SCHEMA public;

-- sys 对象
ALTER TABLE IF EXISTS sys.sys_users SET SCHEMA public;
ALTER TABLE IF EXISTS sys.sys_departments SET SCHEMA public;
ALTER TABLE IF EXISTS sys.sys_roles SET SCHEMA public;
ALTER TABLE IF EXISTS sys.sys_role_permissions SET SCHEMA public;

-- qc 对象
ALTER TABLE IF EXISTS qc.qc_tasks SET SCHEMA public;
ALTER TABLE IF EXISTS qc.qc_task_records SET SCHEMA public;
ALTER TABLE IF EXISTS qc.qc_results SET SCHEMA public;
ALTER TABLE IF EXISTS qc.qc_defects SET SCHEMA public;
ALTER TABLE IF EXISTS qc.qc_defect_history SET SCHEMA public;
ALTER TABLE IF EXISTS qc.qc_appeals SET SCHEMA public;
ALTER TABLE IF EXISTS qc.qc_appeal_reviews SET SCHEMA public;
ALTER TABLE IF EXISTS qc.qc_remediation_tasks SET SCHEMA public;
ALTER TABLE IF EXISTS qc.qc_remediation_history SET SCHEMA public;
ALTER TABLE IF EXISTS qc.qc_rules SET SCHEMA public;
ALTER TABLE IF EXISTS qc.scoring_rules SET SCHEMA public;
ALTER TABLE IF EXISTS qc.scoring_config SET SCHEMA public;
ALTER TABLE IF EXISTS qc.notifications SET SCHEMA public;
ALTER TABLE IF EXISTS qc.qc_coder_workload_daily SET SCHEMA public;
