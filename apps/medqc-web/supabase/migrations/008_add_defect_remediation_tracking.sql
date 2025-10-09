-- ============================================
-- Migration 008: 缺陷整改跟踪
-- ============================================
-- 创建日期: 2025-10-09
-- 描述: 添加质控缺陷整改跟踪和闭环管理功能
-- 功能:
--   1. 整改任务表
--   2. 整改记录表
--   3. 整改状态跟踪
--   4. 整改验收流程
-- ============================================

-- 1. 创建整改状态枚举类型
DO $$ BEGIN
  CREATE TYPE remediation_status AS ENUM (
    'pending',       -- 待整改
    'in_progress',   -- 整改中
    'submitted',     -- 已提交（待验收）
    'approved',      -- 已通过
    'rejected',      -- 已退回
    'overdue',       -- 已逾期
    'closed'         -- 已关闭
  );
EXCEPTION
  WHEN duplicate_object THEN null;
END $$;

-- 2. 创建整改优先级枚举类型
DO $$ BEGIN
  CREATE TYPE remediation_priority AS ENUM (
    'low',       -- 低优先级
    'medium',    -- 中优先级
    'high',      -- 高优先级
    'critical'   -- 严重
  );
EXCEPTION
  WHEN duplicate_object THEN null;
END $$;

-- 3. 创建整改任务表
CREATE TABLE IF NOT EXISTS qc_remediation_tasks (
  -- 基本信息
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_number TEXT UNIQUE NOT NULL,  -- 整改任务编号（格式：RM-YYYYMMDD-XXXX）

  -- 关联信息
  qc_result_id UUID NOT NULL REFERENCES qc_results(id) ON DELETE CASCADE,
  record_id UUID NOT NULL REFERENCES medical_records(id) ON DELETE CASCADE,

  -- 缺陷信息
  defect_type TEXT NOT NULL,          -- 缺陷类型
  defect_description TEXT NOT NULL,   -- 缺陷描述
  defect_location TEXT,               -- 缺陷位置（页码、章节等）
  severity remediation_priority NOT NULL DEFAULT 'medium', -- 严重程度

  -- 整改要求
  remediation_requirement TEXT NOT NULL, -- 整改要求
  deadline TIMESTAMP WITH TIME ZONE,     -- 截止时间

  -- 责任人信息
  assignee_id UUID NOT NULL,          -- 整改负责人ID
  assignee_name TEXT NOT NULL,        -- 整改负责人姓名
  assignee_department TEXT,           -- 整改负责人科室

  -- 整改状态
  status remediation_status NOT NULL DEFAULT 'pending',

  -- 整改提交信息
  remediation_description TEXT,       -- 整改说明
  remediation_evidence JSONB DEFAULT '[]', -- 整改证据（截图、文档等）
  submitted_at TIMESTAMP WITH TIME ZONE,   -- 提交时间

  -- 验收信息
  reviewer_id UUID,                   -- 验收人ID
  reviewer_name TEXT,                 -- 验收人姓名
  review_comment TEXT,                -- 验收意见
  reviewed_at TIMESTAMP WITH TIME ZONE, -- 验收时间

  -- 备注
  notes TEXT,                         -- 备注

  -- 时间戳
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  closed_at TIMESTAMP WITH TIME ZONE   -- 关闭时间
);

-- 4. 创建整改历史记录表
CREATE TABLE IF NOT EXISTS qc_remediation_history (
  -- 基本信息
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id UUID NOT NULL REFERENCES qc_remediation_tasks(id) ON DELETE CASCADE,

  -- 操作信息
  action TEXT NOT NULL,               -- 操作：'create', 'submit', 'approve', 'reject', 'close'
  actor_id UUID NOT NULL,             -- 操作人ID
  actor_name TEXT NOT NULL,           -- 操作人姓名

  -- 变更信息
  old_status remediation_status,      -- 原状态
  new_status remediation_status,      -- 新状态
  comment TEXT,                       -- 备注

  -- 附加信息
  metadata JSONB DEFAULT '{}',        -- 其他元数据

  -- 时间戳
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. 创建整改统计视图
CREATE OR REPLACE VIEW qc_remediation_statistics AS
SELECT
  status,
  severity,
  defect_type,
  COUNT(*) as count,
  COUNT(CASE WHEN deadline < NOW() AND status NOT IN ('approved', 'closed') THEN 1 END) as overdue_count,
  AVG(EXTRACT(EPOCH FROM (COALESCE(closed_at, NOW()) - created_at))) as avg_completion_time_seconds,
  MIN(created_at) as earliest_task,
  MAX(created_at) as latest_task
FROM qc_remediation_tasks
GROUP BY status, severity, defect_type;

-- 6. 创建责任人工作负载视图
CREATE OR REPLACE VIEW qc_assignee_workload AS
SELECT
  assignee_id,
  assignee_name,
  assignee_department,
  COUNT(*) as total_tasks,
  COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_tasks,
  COUNT(CASE WHEN status = 'in_progress' THEN 1 END) as in_progress_tasks,
  COUNT(CASE WHEN deadline < NOW() AND status NOT IN ('approved', 'closed') THEN 1 END) as overdue_tasks,
  AVG(EXTRACT(EPOCH FROM (COALESCE(closed_at, NOW()) - created_at)) / 86400.0) as avg_completion_days
FROM qc_remediation_tasks
GROUP BY assignee_id, assignee_name, assignee_department;

-- 7. 创建索引
CREATE INDEX IF NOT EXISTS idx_qc_remediation_status ON qc_remediation_tasks(status);
CREATE INDEX IF NOT EXISTS idx_qc_remediation_severity ON qc_remediation_tasks(severity);
CREATE INDEX IF NOT EXISTS idx_qc_remediation_qc_result ON qc_remediation_tasks(qc_result_id);
CREATE INDEX IF NOT EXISTS idx_qc_remediation_record ON qc_remediation_tasks(record_id);
CREATE INDEX IF NOT EXISTS idx_qc_remediation_assignee ON qc_remediation_tasks(assignee_id);
CREATE INDEX IF NOT EXISTS idx_qc_remediation_reviewer ON qc_remediation_tasks(reviewer_id);
CREATE INDEX IF NOT EXISTS idx_qc_remediation_deadline ON qc_remediation_tasks(deadline);
CREATE INDEX IF NOT EXISTS idx_qc_remediation_created ON qc_remediation_tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_qc_remediation_number ON qc_remediation_tasks(task_number);

CREATE INDEX IF NOT EXISTS idx_qc_remediation_history_task ON qc_remediation_history(task_id);
CREATE INDEX IF NOT EXISTS idx_qc_remediation_history_actor ON qc_remediation_history(actor_id);
CREATE INDEX IF NOT EXISTS idx_qc_remediation_history_created ON qc_remediation_history(created_at DESC);

-- 8. 创建触发器：自动更新 updated_at
CREATE OR REPLACE FUNCTION update_qc_remediation_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_qc_remediation_updated_at
  BEFORE UPDATE ON qc_remediation_tasks
  FOR EACH ROW
  EXECUTE FUNCTION update_qc_remediation_updated_at();

-- 9. 创建触发器：生成整改任务编号
CREATE OR REPLACE FUNCTION generate_remediation_task_number()
RETURNS TRIGGER AS $$
DECLARE
  date_prefix TEXT;
  seq_number TEXT;
  new_number TEXT;
BEGIN
  -- 生成日期前缀 (RM-YYYYMMDD)
  date_prefix := 'RM-' || TO_CHAR(NOW(), 'YYYYMMDD');

  -- 获取当天的序列号
  SELECT LPAD(
    (COUNT(*) + 1)::TEXT,
    4,
    '0'
  ) INTO seq_number
  FROM qc_remediation_tasks
  WHERE task_number LIKE date_prefix || '%';

  -- 组合完整编号
  new_number := date_prefix || '-' || seq_number;

  NEW.task_number := new_number;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_generate_remediation_task_number
  BEFORE INSERT ON qc_remediation_tasks
  FOR EACH ROW
  WHEN (NEW.task_number IS NULL OR NEW.task_number = '')
  EXECUTE FUNCTION generate_remediation_task_number();

-- 10. 创建触发器：自动记录历史
CREATE OR REPLACE FUNCTION record_remediation_history()
RETURNS TRIGGER AS $$
BEGIN
  -- 只在状态变化时记录
  IF TG_OP = 'UPDATE' AND (OLD.status IS DISTINCT FROM NEW.status) THEN
    INSERT INTO qc_remediation_history (
      task_id,
      action,
      actor_id,
      actor_name,
      old_status,
      new_status,
      comment
    ) VALUES (
      NEW.id,
      'status_change',
      COALESCE(NEW.reviewer_id, NEW.assignee_id),
      COALESCE(NEW.reviewer_name, NEW.assignee_name),
      OLD.status,
      NEW.status,
      NEW.review_comment
    );
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_record_remediation_history
  AFTER UPDATE ON qc_remediation_tasks
  FOR EACH ROW
  EXECUTE FUNCTION record_remediation_history();

-- 11. 创建触发器：检查逾期任务
CREATE OR REPLACE FUNCTION check_overdue_tasks()
RETURNS void AS $$
BEGIN
  UPDATE qc_remediation_tasks
  SET status = 'overdue'
  WHERE deadline < NOW()
    AND status IN ('pending', 'in_progress')
    AND status != 'overdue';
END;
$$ LANGUAGE plpgsql;

-- 可以通过定时任务调用此函数
-- SELECT check_overdue_tasks();

-- 12. 添加注释
COMMENT ON TABLE qc_remediation_tasks IS '质控缺陷整改任务表';
COMMENT ON COLUMN qc_remediation_tasks.id IS '任务ID';
COMMENT ON COLUMN qc_remediation_tasks.task_number IS '整改任务编号';
COMMENT ON COLUMN qc_remediation_tasks.qc_result_id IS '关联的质控结果ID';
COMMENT ON COLUMN qc_remediation_tasks.defect_type IS '缺陷类型';
COMMENT ON COLUMN qc_remediation_tasks.status IS '整改状态';
COMMENT ON COLUMN qc_remediation_tasks.deadline IS '截止时间';

COMMENT ON TABLE qc_remediation_history IS '整改历史记录表';
COMMENT ON COLUMN qc_remediation_history.task_id IS '整改任务ID';
COMMENT ON COLUMN qc_remediation_history.action IS '操作类型';
COMMENT ON COLUMN qc_remediation_history.old_status IS '原状态';
COMMENT ON COLUMN qc_remediation_history.new_status IS '新状态';

COMMENT ON VIEW qc_remediation_statistics IS '整改统计视图';
COMMENT ON VIEW qc_assignee_workload IS '责任人工作负载视图';

-- ============================================
-- Migration 完成
-- ============================================
