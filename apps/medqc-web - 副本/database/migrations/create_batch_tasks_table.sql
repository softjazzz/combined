-- 创建批量处理任务表的简化版本
-- 可以在Supabase控制台的SQL编辑器中执行

-- 创建批量处理任务表
CREATE TABLE IF NOT EXISTS batch_processing_tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  task_type VARCHAR(50) NOT NULL,
  status VARCHAR(20) DEFAULT 'pending',
  total_items INTEGER NOT NULL DEFAULT 0,
  processed_items INTEGER DEFAULT 0,
  failed_items INTEGER DEFAULT 0,
  progress_percentage DECIMAL(5,2) DEFAULT 0,
  error_details JSONB,
  metadata JSONB,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  started_at TIMESTAMP WITH TIME ZONE,
  completed_at TIMESTAMP WITH TIME ZONE
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_batch_tasks_user_id ON batch_processing_tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_batch_tasks_status ON batch_processing_tasks(status);
CREATE INDEX IF NOT EXISTS idx_batch_tasks_created_at ON batch_processing_tasks(created_at DESC);

-- 启用行级安全策略
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

-- 授予权限
GRANT SELECT, INSERT, UPDATE, DELETE ON batch_processing_tasks TO authenticated;
