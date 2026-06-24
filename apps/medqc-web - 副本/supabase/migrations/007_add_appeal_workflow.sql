-- ============================================
-- Migration 007: 申诉流程管理
-- ============================================
-- 创建日期: 2025-10-09
-- 描述: 添加质控结果申诉流程管理功能
-- 功能:
--   1. 申诉记录表
--   2. 申诉审核表
--   3. 申诉状态跟踪
--   4. 申诉处理流程
-- ============================================

-- 1. 创建申诉状态枚举类型
DO $$ BEGIN
  CREATE TYPE appeal_status AS ENUM (
    'pending',      -- 待审核
    'reviewing',    -- 审核中
    'approved',     -- 已通过
    'rejected',     -- 已拒绝
    'withdrawn'     -- 已撤回
  );
EXCEPTION
  WHEN duplicate_object THEN null;
END $$;

-- 2. 创建申诉优先级枚举类型
DO $$ BEGIN
  CREATE TYPE appeal_priority AS ENUM (
    'low',          -- 低优先级
    'medium',       -- 中优先级
    'high',         -- 高优先级
    'urgent'        -- 紧急
  );
EXCEPTION
  WHEN duplicate_object THEN null;
END $$;

-- 3. 创建申诉记录表
CREATE TABLE IF NOT EXISTS qc_appeals (
  -- 基本信息
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  appeal_number TEXT UNIQUE NOT NULL,  -- 申诉编号（格式：AP-YYYYMMDD-XXXX）

  -- 关联信息
  qc_result_id UUID NOT NULL REFERENCES qc_results(id) ON DELETE CASCADE,
  record_id UUID NOT NULL REFERENCES medical_records(id) ON DELETE CASCADE,

  -- 申诉信息
  appeal_type TEXT NOT NULL,  -- 申诉类型：'defect'（缺陷申诉）, 'score'（评分申诉）
  defect_item TEXT,           -- 申诉的具体缺陷项（如果是缺陷申诉）
  reason TEXT NOT NULL,       -- 申诉理由
  evidence JSONB DEFAULT '[]', -- 证据材料（文件、图片等）

  -- 申诉状态
  status appeal_status NOT NULL DEFAULT 'pending',
  priority appeal_priority NOT NULL DEFAULT 'medium',

  -- 申诉人信息
  appellant_id UUID NOT NULL,          -- 申诉人ID
  appellant_name TEXT NOT NULL,        -- 申诉人姓名
  appellant_department TEXT,           -- 申诉人科室

  -- 审核信息
  reviewer_id UUID,                    -- 审核人ID
  reviewer_name TEXT,                  -- 审核人姓名
  review_result TEXT,                  -- 审核结果说明
  review_date TIMESTAMP WITH TIME ZONE, -- 审核时间

  -- 处理信息
  resolution TEXT,                     -- 处理决定
  resolution_date TIMESTAMP WITH TIME ZONE, -- 处理时间

  -- 备注
  notes TEXT,                          -- 备注

  -- 时间戳
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  -- 约束
  CONSTRAINT valid_appeal_type CHECK (appeal_type IN ('defect', 'score'))
);

-- 4. 创建申诉审核历史表
CREATE TABLE IF NOT EXISTS qc_appeal_reviews (
  -- 基本信息
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  appeal_id UUID NOT NULL REFERENCES qc_appeals(id) ON DELETE CASCADE,

  -- 审核信息
  reviewer_id UUID NOT NULL,           -- 审核人ID
  reviewer_name TEXT NOT NULL,         -- 审核人姓名
  reviewer_role TEXT NOT NULL,         -- 审核人角色

  -- 审核意见
  action TEXT NOT NULL,                -- 审核动作：'approve'（批准）, 'reject'（拒绝）, 'request_info'（要求补充）
  comment TEXT,                        -- 审核意见

  -- 附加信息
  metadata JSONB DEFAULT '{}',         -- 其他元数据

  -- 时间戳
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  -- 约束
  CONSTRAINT valid_review_action CHECK (action IN ('approve', 'reject', 'request_info', 'forward'))
);

-- 5. 创建申诉统计视图
CREATE OR REPLACE VIEW qc_appeals_statistics AS
SELECT
  status,
  appeal_type,
  priority,
  COUNT(*) as count,
  AVG(EXTRACT(EPOCH FROM (COALESCE(resolution_date, NOW()) - created_at))) as avg_resolution_time_seconds,
  MIN(created_at) as earliest_appeal,
  MAX(created_at) as latest_appeal
FROM qc_appeals
GROUP BY status, appeal_type, priority;

-- 6. 创建索引
CREATE INDEX IF NOT EXISTS idx_qc_appeals_status ON qc_appeals(status);
CREATE INDEX IF NOT EXISTS idx_qc_appeals_priority ON qc_appeals(priority);
CREATE INDEX IF NOT EXISTS idx_qc_appeals_qc_result ON qc_appeals(qc_result_id);
CREATE INDEX IF NOT EXISTS idx_qc_appeals_record ON qc_appeals(record_id);
CREATE INDEX IF NOT EXISTS idx_qc_appeals_appellant ON qc_appeals(appellant_id);
CREATE INDEX IF NOT EXISTS idx_qc_appeals_reviewer ON qc_appeals(reviewer_id);
CREATE INDEX IF NOT EXISTS idx_qc_appeals_created ON qc_appeals(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_qc_appeals_number ON qc_appeals(appeal_number);

CREATE INDEX IF NOT EXISTS idx_qc_appeal_reviews_appeal ON qc_appeal_reviews(appeal_id);
CREATE INDEX IF NOT EXISTS idx_qc_appeal_reviews_reviewer ON qc_appeal_reviews(reviewer_id);
CREATE INDEX IF NOT EXISTS idx_qc_appeal_reviews_created ON qc_appeal_reviews(created_at DESC);

-- 7. 创建触发器：自动更新 updated_at
CREATE OR REPLACE FUNCTION update_qc_appeals_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_qc_appeals_updated_at
  BEFORE UPDATE ON qc_appeals
  FOR EACH ROW
  EXECUTE FUNCTION update_qc_appeals_updated_at();

-- 8. 创建触发器：生成申诉编号
CREATE OR REPLACE FUNCTION generate_appeal_number()
RETURNS TRIGGER AS $$
DECLARE
  date_prefix TEXT;
  seq_number TEXT;
  new_number TEXT;
BEGIN
  -- 生成日期前缀 (AP-YYYYMMDD)
  date_prefix := 'AP-' || TO_CHAR(NOW(), 'YYYYMMDD');

  -- 获取当天的序列号
  SELECT LPAD(
    (COUNT(*) + 1)::TEXT,
    4,
    '0'
  ) INTO seq_number
  FROM qc_appeals
  WHERE appeal_number LIKE date_prefix || '%';

  -- 组合完整编号
  new_number := date_prefix || '-' || seq_number;

  NEW.appeal_number := new_number;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_generate_appeal_number
  BEFORE INSERT ON qc_appeals
  FOR EACH ROW
  WHEN (NEW.appeal_number IS NULL OR NEW.appeal_number = '')
  EXECUTE FUNCTION generate_appeal_number();

-- 9. 添加注释
COMMENT ON TABLE qc_appeals IS '质控结果申诉记录表';
COMMENT ON COLUMN qc_appeals.id IS '申诉ID';
COMMENT ON COLUMN qc_appeals.appeal_number IS '申诉编号';
COMMENT ON COLUMN qc_appeals.qc_result_id IS '关联的质控结果ID';
COMMENT ON COLUMN qc_appeals.record_id IS '关联的病历ID';
COMMENT ON COLUMN qc_appeals.appeal_type IS '申诉类型';
COMMENT ON COLUMN qc_appeals.reason IS '申诉理由';
COMMENT ON COLUMN qc_appeals.status IS '申诉状态';
COMMENT ON COLUMN qc_appeals.priority IS '申诉优先级';

COMMENT ON TABLE qc_appeal_reviews IS '申诉审核历史表';
COMMENT ON COLUMN qc_appeal_reviews.appeal_id IS '申诉ID';
COMMENT ON COLUMN qc_appeal_reviews.action IS '审核动作';
COMMENT ON COLUMN qc_appeal_reviews.comment IS '审核意见';

COMMENT ON VIEW qc_appeals_statistics IS '申诉统计视图';

-- 10. 插入示例数据（可选，用于测试）
-- INSERT INTO qc_appeals (
--   qc_result_id,
--   record_id,
--   appeal_type,
--   reason,
--   appellant_id,
--   appellant_name,
--   appellant_department
-- ) VALUES (
--   'uuid-of-qc-result',
--   'uuid-of-record',
--   'defect',
--   '该缺陷判定不准确，实际情况是...',
--   'uuid-of-appellant',
--   '张医生',
--   '心内科'
-- );

-- ============================================
-- Migration 完成
-- ============================================
