-- 创建批量处理任务表
CREATE TABLE IF NOT EXISTS batch_processing_tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  task_type VARCHAR(50) NOT NULL CHECK (task_type IN ('upload', 'analysis', 'export')),
  status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
  total_items INTEGER NOT NULL CHECK (total_items > 0),
  processed_items INTEGER DEFAULT 0 CHECK (processed_items >= 0),
  failed_items INTEGER DEFAULT 0 CHECK (failed_items >= 0),
  progress_percentage DECIMAL(5,2) DEFAULT 0 CHECK (progress_percentage >= 0 AND progress_percentage <= 100),
  error_details JSONB,
  metadata JSONB, -- 存储任务相关的额外信息
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  started_at TIMESTAMP WITH TIME ZONE,
  completed_at TIMESTAMP WITH TIME ZONE,
  
  -- 约束检查
  CONSTRAINT valid_progress CHECK (processed_items <= total_items),
  CONSTRAINT valid_failed_items CHECK (failed_items <= processed_items),
  CONSTRAINT valid_timestamps CHECK (
    (started_at IS NULL OR started_at >= created_at) AND
    (completed_at IS NULL OR completed_at >= COALESCE(started_at, created_at))
  )
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_batch_tasks_user_id ON batch_processing_tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_batch_tasks_status ON batch_processing_tasks(status);
CREATE INDEX IF NOT EXISTS idx_batch_tasks_created_at ON batch_processing_tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_batch_tasks_user_status ON batch_processing_tasks(user_id, status);

-- 创建复合索引用于查询用户的活跃任务
CREATE INDEX IF NOT EXISTS idx_batch_tasks_user_active ON batch_processing_tasks(user_id, status) 
WHERE status IN ('pending', 'processing');

-- 添加注释
COMMENT ON TABLE batch_processing_tasks IS '批量处理任务表，用于跟踪文件上传、分析等批量操作的进度';
COMMENT ON COLUMN batch_processing_tasks.task_type IS '任务类型：upload(上传), analysis(分析), export(导出)';
COMMENT ON COLUMN batch_processing_tasks.status IS '任务状态：pending(待处理), processing(处理中), completed(已完成), failed(失败)';
COMMENT ON COLUMN batch_processing_tasks.total_items IS '总项目数量';
COMMENT ON COLUMN batch_processing_tasks.processed_items IS '已处理项目数量';
COMMENT ON COLUMN batch_processing_tasks.failed_items IS '失败项目数量';
COMMENT ON COLUMN batch_processing_tasks.progress_percentage IS '进度百分比(0-100)';
COMMENT ON COLUMN batch_processing_tasks.error_details IS '错误详情，JSON格式存储';
COMMENT ON COLUMN batch_processing_tasks.metadata IS '任务元数据，存储任务相关的额外信息';

-- 启用行级安全策略 (RLS)
ALTER TABLE batch_processing_tasks ENABLE ROW LEVEL SECURITY;

-- 创建RLS策略：用户只能访问自己的任务
CREATE POLICY "Users can view own batch tasks" ON batch_processing_tasks
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own batch tasks" ON batch_processing_tasks
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own batch tasks" ON batch_processing_tasks
  FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own batch tasks" ON batch_processing_tasks
  FOR DELETE USING (auth.uid() = user_id);

-- 创建管理员策略：管理员可以查看所有任务
CREATE POLICY "Admins can view all batch tasks" ON batch_processing_tasks
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM user_roles 
      WHERE user_id = auth.uid() 
      AND role IN ('admin', 'qc_manager')
    )
  );

-- 创建触发器函数：自动更新进度百分比
CREATE OR REPLACE FUNCTION update_batch_task_progress()
RETURNS TRIGGER AS $$
BEGIN
  -- 自动计算进度百分比
  IF NEW.total_items > 0 THEN
    NEW.progress_percentage = ROUND((NEW.processed_items::DECIMAL / NEW.total_items::DECIMAL) * 100, 2);
  END IF;
  
  -- 自动设置开始时间
  IF OLD.status = 'pending' AND NEW.status = 'processing' AND NEW.started_at IS NULL THEN
    NEW.started_at = NOW();
  END IF;
  
  -- 自动设置完成时间
  IF OLD.status IN ('pending', 'processing') AND NEW.status IN ('completed', 'failed') AND NEW.completed_at IS NULL THEN
    NEW.completed_at = NOW();
  END IF;
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 创建触发器
CREATE TRIGGER trigger_update_batch_task_progress
  BEFORE UPDATE ON batch_processing_tasks
  FOR EACH ROW
  EXECUTE FUNCTION update_batch_task_progress();

-- 创建视图：批量任务统计
CREATE OR REPLACE VIEW batch_task_statistics AS
SELECT 
  user_id,
  task_type,
  status,
  COUNT(*) as task_count,
  SUM(total_items) as total_items,
  SUM(processed_items) as processed_items,
  SUM(failed_items) as failed_items,
  AVG(progress_percentage) as avg_progress,
  MIN(created_at) as first_task_at,
  MAX(created_at) as last_task_at,
  AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_duration_seconds
FROM batch_processing_tasks
GROUP BY user_id, task_type, status;

-- 添加视图注释
COMMENT ON VIEW batch_task_statistics IS '批量任务统计视图，提供按用户、任务类型、状态的统计信息';

-- 创建函数：清理过期的已完成任务
CREATE OR REPLACE FUNCTION cleanup_old_batch_tasks(days_to_keep INTEGER DEFAULT 30)
RETURNS INTEGER AS $$
DECLARE
  deleted_count INTEGER;
BEGIN
  DELETE FROM batch_processing_tasks
  WHERE status IN ('completed', 'failed')
    AND completed_at < NOW() - INTERVAL '1 day' * days_to_keep;
  
  GET DIAGNOSTICS deleted_count = ROW_COUNT;
  
  RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- 添加函数注释
COMMENT ON FUNCTION cleanup_old_batch_tasks IS '清理指定天数前的已完成批量任务，默认保留30天';

-- 创建函数：获取用户活跃任务
CREATE OR REPLACE FUNCTION get_user_active_batch_tasks(target_user_id UUID DEFAULT auth.uid())
RETURNS TABLE (
  id UUID,
  task_type VARCHAR(50),
  status VARCHAR(20),
  total_items INTEGER,
  processed_items INTEGER,
  failed_items INTEGER,
  progress_percentage DECIMAL(5,2),
  created_at TIMESTAMP WITH TIME ZONE,
  started_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    t.id,
    t.task_type,
    t.status,
    t.total_items,
    t.processed_items,
    t.failed_items,
    t.progress_percentage,
    t.created_at,
    t.started_at
  FROM batch_processing_tasks t
  WHERE t.user_id = target_user_id
    AND t.status IN ('pending', 'processing')
  ORDER BY t.created_at DESC;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 添加函数注释
COMMENT ON FUNCTION get_user_active_batch_tasks IS '获取用户的活跃批量任务（待处理和处理中的任务）';

-- 创建实时订阅触发器函数
CREATE OR REPLACE FUNCTION notify_batch_task_change()
RETURNS TRIGGER AS $$
BEGIN
  -- 发送实时通知
  PERFORM pg_notify(
    'batch_task_change',
    json_build_object(
      'operation', TG_OP,
      'record', row_to_json(NEW),
      'old_record', CASE WHEN TG_OP = 'UPDATE' THEN row_to_json(OLD) ELSE NULL END
    )::text
  );
  
  RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- 创建实时通知触发器
CREATE TRIGGER trigger_batch_task_realtime_notify
  AFTER INSERT OR UPDATE OR DELETE ON batch_processing_tasks
  FOR EACH ROW
  EXECUTE FUNCTION notify_batch_task_change();

-- 授予必要的权限
GRANT SELECT, INSERT, UPDATE, DELETE ON batch_processing_tasks TO authenticated;
GRANT SELECT ON batch_task_statistics TO authenticated;
GRANT EXECUTE ON FUNCTION get_user_active_batch_tasks TO authenticated;
GRANT EXECUTE ON FUNCTION cleanup_old_batch_tasks TO service_role;

-- 创建示例数据（仅用于开发环境）
-- INSERT INTO batch_processing_tasks (user_id, task_type, total_items, status) 
-- VALUES 
--   (auth.uid(), 'upload', 10, 'completed'),
--   (auth.uid(), 'analysis', 5, 'processing');
