-- 病案质控系统数据库初始化脚本
-- 请在Supabase SQL编辑器中执行此脚本

-- 1. 创建批量处理任务表
CREATE TABLE IF NOT EXISTS public.batch_processing_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    task_type VARCHAR(50) NOT NULL CHECK (task_type IN ('upload', 'analysis', 'export')),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    total_items INTEGER NOT NULL DEFAULT 0 CHECK (total_items >= 0),
    processed_items INTEGER DEFAULT 0 CHECK (processed_items >= 0),
    failed_items INTEGER DEFAULT 0 CHECK (failed_items >= 0),
    progress_percentage DECIMAL(5,2) DEFAULT 0 CHECK (progress_percentage >= 0 AND progress_percentage <= 100),
    error_details JSONB,
    metadata JSONB,
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

-- 2. 创建索引
CREATE INDEX IF NOT EXISTS idx_batch_tasks_user_id ON public.batch_processing_tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_batch_tasks_status ON public.batch_processing_tasks(status);
CREATE INDEX IF NOT EXISTS idx_batch_tasks_created_at ON public.batch_processing_tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_batch_tasks_user_status ON public.batch_processing_tasks(user_id, status);

-- 3. 启用行级安全策略 (RLS)
ALTER TABLE public.batch_processing_tasks ENABLE ROW LEVEL SECURITY;

-- 4. 创建RLS策略：用户只能访问自己的任务
CREATE POLICY "Users can view own batch tasks" ON public.batch_processing_tasks
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own batch tasks" ON public.batch_processing_tasks
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own batch tasks" ON public.batch_processing_tasks
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own batch tasks" ON public.batch_processing_tasks
    FOR DELETE USING (auth.uid() = user_id);

-- 5. 创建管理员策略：管理员可以查看所有任务
CREATE POLICY "Admins can view all batch tasks" ON public.batch_processing_tasks
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.user_roles 
            WHERE user_id = auth.uid() 
            AND role IN ('admin', 'qc_manager')
        )
    );

-- 6. 创建触发器函数：自动更新进度百分比
CREATE OR REPLACE FUNCTION public.update_batch_task_progress()
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

-- 7. 创建触发器
DROP TRIGGER IF EXISTS trigger_update_batch_task_progress ON public.batch_processing_tasks;
CREATE TRIGGER trigger_update_batch_task_progress
    BEFORE UPDATE ON public.batch_processing_tasks
    FOR EACH ROW
    EXECUTE FUNCTION public.update_batch_task_progress();

-- 8. 授予权限
GRANT SELECT, INSERT, UPDATE, DELETE ON public.batch_processing_tasks TO authenticated;
GRANT USAGE ON SCHEMA public TO authenticated;

-- 9. 创建一些测试数据（可选）
-- INSERT INTO public.batch_processing_tasks (user_id, task_type, total_items, status) 
-- VALUES 
--     (auth.uid(), 'upload', 10, 'completed'),
--     (auth.uid(), 'analysis', 5, 'processing');

-- 10. 验证表创建
SELECT 
    table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns 
WHERE table_name = 'batch_processing_tasks' 
    AND table_schema = 'public'
ORDER BY ordinal_position;
