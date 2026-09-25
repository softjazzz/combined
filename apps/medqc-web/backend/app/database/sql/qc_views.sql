-- QC business views aligned with current router expectations.
-- Apply after base tables are created.

DROP VIEW IF EXISTS v_qc_task_progress;
CREATE VIEW v_qc_task_progress AS
SELECT
    t.id AS task_id,
    t.task_name AS task_name,
    COUNT(r.id) AS total_records,
    SUM(CASE WHEN r.status = 'completed' THEN 1 ELSE 0 END) AS completed_records,
    CASE
        WHEN COUNT(r.id) = 0 THEN 0
        ELSE ROUND(SUM(CASE WHEN r.status = 'completed' THEN 1.0 ELSE 0 END) * 100.0 / COUNT(r.id), 1)
    END AS progress_pct,
    SUM(CASE WHEN r.status = 'pending' THEN 1 ELSE 0 END) AS pending_count,
    SUM(CASE WHEN r.status = 'in_progress' THEN 1 ELSE 0 END) AS working_count,
    SUM(CASE WHEN r.status = 'completed' THEN 1 ELSE 0 END) AS done_count,
    AVG(r.score) AS avg_score,
    CASE
        WHEN COUNT(r.id) FILTER (WHERE r.status = 'completed') = 0 THEN NULL
        WHEN COUNT(r.id) FILTER (WHERE r.status = 'completed' AND r.defect_count IS NULL) > 0 THEN NULL
        ELSE SUM(r.defect_count) FILTER (WHERE r.status = 'completed')
    END AS total_defects
FROM qc_tasks t
LEFT JOIN qc_task_records r ON r.task_id = t.id
GROUP BY t.id, t.task_name;


DROP VIEW IF EXISTS qc_appeals_statistics;
CREATE VIEW qc_appeals_statistics AS
SELECT
    status,
    appeal_type,
    priority,
    COUNT(*) AS count,
    0.0 AS avg_resolution_time_seconds
FROM qc_appeals
GROUP BY status, appeal_type, priority;


DROP VIEW IF EXISTS qc_remediation_statistics;
CREATE VIEW qc_remediation_statistics AS
SELECT
    status,
    severity,
    defect_type,
    COUNT(*) AS count,
    0.0 AS avg_completion_time_seconds
FROM qc_remediation_tasks
GROUP BY status, severity, defect_type;


DROP VIEW IF EXISTS qc_assignee_workload;
CREATE VIEW qc_assignee_workload AS
SELECT
    assignee_id,
    assignee_name,
    assignee_department,
    COUNT(*) AS total_tasks,
    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending_tasks,
    SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) AS in_progress_tasks,
    SUM(CASE WHEN status = 'overdue' THEN 1 ELSE 0 END) AS overdue_tasks,
    0.0 AS avg_completion_days
FROM qc_remediation_tasks
WHERE assignee_id IS NOT NULL AND assignee_id <> ''
GROUP BY assignee_id, assignee_name, assignee_department;


DROP VIEW IF EXISTS qc_statistics_view;
CREATE VIEW qc_statistics_view AS
SELECT
    d.record_id,
    COUNT(d.id) AS total_documents,
    COUNT(*) FILTER (WHERE d.qc_status = 'passed') AS passed_count,
    COUNT(*) FILTER (WHERE d.qc_status = 'warning') AS warning_count,
    COUNT(*) FILTER (WHERE d.qc_status = 'failed') AS failed_count,
    COUNT(*) FILTER (WHERE d.qc_status = 'pending') AS pending_count,
    ROUND(AVG(d.qc_score)::numeric, 2) AS avg_qc_score,
    MAX(d.qc_last_analyzed) AS last_analyzed_time
FROM medical_documents d
WHERE d.status = 'active'
GROUP BY d.record_id;


DROP VIEW IF EXISTS v_qc_coder_ranking;
CREATE VIEW v_qc_coder_ranking AS
SELECT
    coder_id AS user_id,
    coder_name AS name,
    department_name AS department,
    SUM(qc_count) AS qc_count,
    SUM(recheck_count) AS recheck_count,
    SUM(defect_found) AS defect_found,
    ROUND(
      CASE WHEN SUM(qc_count) = 0 THEN 0
      ELSE SUM(passed_count)::numeric * 100.0 / SUM(qc_count)
      END, 1
    ) AS pass_rate,
    ROUND(SUM(qc_count)::numeric / GREATEST(COUNT(DISTINCT stat_date), 1), 1) AS avg_daily
FROM qc_coder_workload_daily
WHERE stat_date >= CURRENT_DATE - INTERVAL '30 day'
GROUP BY coder_id, coder_name, department_name;
