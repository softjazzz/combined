-- 申诉与整改流程数据库表
-- Appeal and Rectification Database Tables
-- 创建时间: 2026-01-04

-- =============================================================================
-- 1. 申诉表 (appeals)
-- =============================================================================
CREATE TABLE IF NOT EXISTS appeals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- 关联信息
    qc_result_id UUID NOT NULL,
    defect_id VARCHAR(100) NOT NULL,
    record_id UUID NOT NULL,
    
    -- 申诉人信息
    appellant_id UUID NOT NULL,
    appellant_name VARCHAR(100),
    department_id UUID,
    
    -- 申诉内容
    appeal_reason TEXT NOT NULL,
    appeal_type VARCHAR(50) NOT NULL CHECK (appeal_type IN ('incorrect_rule', 'special_case', 'other')),
    evidence_urls TEXT[],
    
    -- 审核信息
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'withdrawn')),
    reviewer_id UUID,
    reviewer_name VARCHAR(100),
    review_comment TEXT,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_appeals_status ON appeals(status);
CREATE INDEX IF NOT EXISTS idx_appeals_qc_result ON appeals(qc_result_id);
CREATE INDEX IF NOT EXISTS idx_appeals_appellant ON appeals(appellant_id);
CREATE INDEX IF NOT EXISTS idx_appeals_created ON appeals(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_appeals_department ON appeals(department_id);

-- 添加注释
COMMENT ON TABLE appeals IS '质控申诉表';
COMMENT ON COLUMN appeals.qc_result_id IS '质控结果ID';
COMMENT ON COLUMN appeals.defect_id IS '缺陷ID';
COMMENT ON COLUMN appeals.appeal_reason IS '申诉理由';
COMMENT ON COLUMN appeals.appeal_type IS '申诉类型: incorrect_rule=规则有误, special_case=特殊情况, other=其他';
COMMENT ON COLUMN appeals.status IS '状态: pending=待审核, approved=已通过, rejected=已驳回, withdrawn=已撤销';

-- =============================================================================
-- 2. 整改任务表 (rectification_tasks)
-- =============================================================================
CREATE TABLE IF NOT EXISTS rectification_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- 关联信息
    qc_result_id UUID NOT NULL,
    defect_id VARCHAR(100) NOT NULL,
    record_id UUID NOT NULL,
    appeal_id UUID,  -- 可能来自申诉驳回
    
    -- 任务信息
    task_title VARCHAR(200) NOT NULL,
    task_description TEXT NOT NULL,
    defect_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('critical', 'major', 'minor')),
    
    -- 分配信息
    assignee_id UUID NOT NULL,
    assignee_name VARCHAR(100),
    assigner_id UUID,
    assigner_name VARCHAR(100),
    department_id UUID,
    
    -- 期限
    due_date TIMESTAMP WITH TIME ZONE,
    
    -- 整改状态
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'submitted', 'approved', 'rejected')),
    
    -- 整改内容
    rectification_content TEXT,
    rectification_files TEXT[],
    submitted_at TIMESTAMP WITH TIME ZONE,
    
    -- 验收信息
    reviewer_id UUID,
    reviewer_name VARCHAR(100),
    review_comment TEXT,
    review_result VARCHAR(20) CHECK (review_result IN ('pass', 'fail')),
    reviewed_at TIMESTAMP WITH TIME ZONE,
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_tasks_status ON rectification_tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON rectification_tasks(assignee_id);
CREATE INDEX IF NOT EXISTS idx_tasks_qc_result ON rectification_tasks(qc_result_id);
CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON rectification_tasks(due_date);
CREATE INDEX IF NOT EXISTS idx_tasks_department ON rectification_tasks(department_id);
CREATE INDEX IF NOT EXISTS idx_tasks_created ON rectification_tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_severity ON rectification_tasks(severity);

-- 添加注释
COMMENT ON TABLE rectification_tasks IS '整改任务表';
COMMENT ON COLUMN rectification_tasks.task_title IS '任务标题';
COMMENT ON COLUMN rectification_tasks.severity IS '严重程度: critical=严重, major=重要, minor=一般';
COMMENT ON COLUMN rectification_tasks.status IS '状态: pending=待处理, in_progress=进行中, submitted=已提交, approved=已通过, rejected=未通过';
COMMENT ON COLUMN rectification_tasks.review_result IS '验收结果: pass=通过, fail=不通过';

-- =============================================================================
-- 3. 申诉操作日志表 (appeal_logs)
-- =============================================================================
CREATE TABLE IF NOT EXISTS appeal_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    appeal_id UUID NOT NULL,
    action VARCHAR(50) NOT NULL,  -- created, submitted, reviewed, withdrawn
    operator_id UUID,
    operator_name VARCHAR(100),
    comment TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_appeal_logs_appeal ON appeal_logs(appeal_id);
CREATE INDEX IF NOT EXISTS idx_appeal_logs_created ON appeal_logs(created_at DESC);

COMMENT ON TABLE appeal_logs IS '申诉操作日志';
COMMENT ON COLUMN appeal_logs.action IS '操作类型: created, submitted, reviewed, withdrawn';

-- =============================================================================
-- 4. 整改操作日志表 (rectification_logs)
-- =============================================================================
CREATE TABLE IF NOT EXISTS rectification_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id UUID NOT NULL,
    action VARCHAR(50) NOT NULL,  -- created, assigned, submitted, reviewed, completed
    operator_id UUID,
    operator_name VARCHAR(100),
    comment TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rectification_logs_task ON rectification_logs(task_id);
CREATE INDEX IF NOT EXISTS idx_rectification_logs_created ON rectification_logs(created_at DESC);

COMMENT ON TABLE rectification_logs IS '整改操作日志';
COMMENT ON COLUMN rectification_logs.action IS '操作类型: created, assigned, submitted, reviewed, completed';

-- =============================================================================
-- 5. 更新时间触发器
-- =============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 为 appeals 表创建触发器
DROP TRIGGER IF EXISTS update_appeals_updated_at ON appeals;
CREATE TRIGGER update_appeals_updated_at
    BEFORE UPDATE ON appeals
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 为 rectification_tasks 表创建触发器
DROP TRIGGER IF NOT EXISTS update_rectification_tasks_updated_at ON rectification_tasks;
CREATE TRIGGER update_rectification_tasks_updated_at
    BEFORE UPDATE ON rectification_tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- 6. 示例数据 (可选)
-- =============================================================================
-- 以下是示例数据，生产环境请删除或注释

-- INSERT INTO appeals (
--     qc_result_id, defect_id, record_id,
--     appellant_id, appellant_name, department_id,
--     appeal_reason, appeal_type
-- ) VALUES (
--     'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'::UUID,
--     'DEF-001',
--     'yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy'::UUID,
--     'zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz'::UUID,
--     '张医生',
--     'deptid-1'::UUID,
--     '该患者为特殊情况，不符合常规标准',
--     'special_case'
-- );
