-- ============================================================================
-- Migration 010: 质控抽查任务管理
-- ============================================================================
-- 功能: 质控任务的创建、抽样、分配、执行和统计
-- 依赖: medical_records 表
-- ============================================================================

-- 质控抽查任务表
CREATE TABLE IF NOT EXISTS qc_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_number TEXT UNIQUE NOT NULL,          -- 任务编号 QC-YYYYMMDD-XXXX
    task_name TEXT NOT NULL,                   -- 任务名称
    task_type TEXT NOT NULL DEFAULT 'one_time', -- 类型: one_time=单次, scheduled=定时
    schedule_config JSONB,                     -- 定时配置 { cron, next_run, ... }

    -- 病历范围
    date_range JSONB,                          -- { start, end }
    department_filter TEXT[],                  -- 科室筛选
    record_ids TEXT[],                         -- 指定病案号

    -- 抽样规则
    sampling_method TEXT NOT NULL DEFAULT 'all', -- 抽样方式: all=全部, count=总数, percentage=百分比
    sampling_config JSONB DEFAULT '{}',          -- { total, by_department, percentage, ... }

    -- 任务分配
    assign_method TEXT NOT NULL DEFAULT 'keep',  -- 分配方式: keep=保持原有, by_department=按科室, by_ratio=按比例, by_type=按类型
    assignee_config JSONB DEFAULT '{}',          -- 分配配置

    -- 状态
    status TEXT NOT NULL DEFAULT 'draft',       -- draft|sampling|assigned|in_progress|completed|cancelled
    progress INTEGER DEFAULT 0,                -- 进度百分比 0-100
    total_records INTEGER DEFAULT 0,           -- 总病历数
    completed_records INTEGER DEFAULT 0,       -- 已完成数

    -- 创建人
    creator_id TEXT NOT NULL,
    creator_name TEXT NOT NULL DEFAULT '',

    -- 时间
    deadline TIMESTAMP WITH TIME ZONE,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 任务-病历关联表
CREATE TABLE IF NOT EXISTS qc_task_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES qc_tasks(id) ON DELETE CASCADE,
    record_id TEXT NOT NULL,                   -- 病历ID（兼容字符串型外键）
    assignee_id TEXT,
    assignee_name TEXT,
    status TEXT DEFAULT 'pending',              -- pending|in_progress|completed|skipped
    qc_result_id TEXT,                         -- 关联质控结果
    score INTEGER,                             -- 质控评分
    defect_count INTEGER DEFAULT 0,            -- 缺陷数
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_qc_tasks_status ON qc_tasks(status);
CREATE INDEX IF NOT EXISTS idx_qc_tasks_creator ON qc_tasks(creator_id);
CREATE INDEX IF NOT EXISTS idx_qc_tasks_created_at ON qc_tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_qc_task_records_task ON qc_task_records(task_id);
CREATE INDEX IF NOT EXISTS idx_qc_task_records_assignee ON qc_task_records(assignee_id);
CREATE INDEX IF NOT EXISTS idx_qc_task_records_status ON qc_task_records(status);

-- 自动更新 updated_at
CREATE OR REPLACE FUNCTION update_qc_tasks_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_qc_tasks_updated_at ON qc_tasks;
CREATE TRIGGER trigger_qc_tasks_updated_at
    BEFORE UPDATE ON qc_tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_qc_tasks_updated_at();

-- 任务进度统计视图
CREATE OR REPLACE VIEW v_qc_task_progress AS
SELECT
    t.id AS task_id,
    t.task_name,
    t.task_number,
    t.status AS task_status,
    t.total_records,
    t.completed_records,
    CASE
        WHEN t.total_records > 0
        THEN ROUND((t.completed_records::NUMERIC / t.total_records) * 100, 1)
        ELSE 0
    END AS progress_pct,
    COUNT(DISTINCT tr.id) AS assigned_count,
    COUNT(DISTINCT tr.id) FILTER (WHERE tr.status = 'completed') AS done_count,
    COUNT(DISTINCT tr.id) FILTER (WHERE tr.status = 'in_progress') AS working_count,
    COUNT(DISTINCT tr.id) FILTER (WHERE tr.status = 'pending') AS pending_count,
    AVG(tr.score) FILTER (WHERE tr.score IS NOT NULL) AS avg_score,
    SUM(tr.defect_count) AS total_defects,
    t.deadline,
    t.created_at,
    t.creator_name
FROM qc_tasks t
LEFT JOIN qc_task_records tr ON t.id = tr.task_id
GROUP BY t.id;

-- RLS
ALTER TABLE qc_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE qc_task_records ENABLE ROW LEVEL SECURITY;

-- 默认策略：service_role 可全部操作
CREATE POLICY "service_role_full_access_qc_tasks"
    ON qc_tasks FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "service_role_full_access_qc_task_records"
    ON qc_task_records FOR ALL
    USING (auth.role() = 'service_role');

-- 注释
COMMENT ON TABLE qc_tasks IS '质控抽查任务表';
COMMENT ON TABLE qc_task_records IS '质控任务-病历关联表';
COMMENT ON COLUMN qc_tasks.sampling_method IS '抽样方式: all=全部, count=总数, percentage=百分比';
COMMENT ON COLUMN qc_tasks.assign_method IS '分配方式: keep=保持原有, by_department=按科室, by_ratio=按比例, by_type=按类型';
