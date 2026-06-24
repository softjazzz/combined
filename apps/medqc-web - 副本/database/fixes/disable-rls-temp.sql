-- 临时禁用RLS进行测试
-- 在Supabase控制台执行此SQL

-- 1. 临时禁用RLS
ALTER TABLE public.batch_processing_tasks DISABLE ROW LEVEL SECURITY;

-- 2. 清空现有数据
DELETE FROM public.batch_processing_tasks;

-- 3. 插入测试数据（不依赖auth.uid()）
INSERT INTO public.batch_processing_tasks (
    user_id, 
    task_type, 
    total_items, 
    processed_items, 
    failed_items, 
    status, 
    progress_percentage, 
    completed_at
) VALUES 
    ('09e9c1f5-91ad-4407-97cb-defb8b6146ea', 'upload', 10, 10, 0, 'completed', 100, NOW()),
    ('09e9c1f5-91ad-4407-97cb-defb8b6146ea', 'analysis', 5, 3, 1, 'processing', 60, NULL),
    ('09e9c1f5-91ad-4407-97cb-defb8b6146ea', 'export', 8, 8, 0, 'completed', 100, NOW() - INTERVAL '1 hour');

-- 4. 验证数据
SELECT * FROM public.batch_processing_tasks;

-- 注意：测试完成后记得重新启用RLS
-- ALTER TABLE public.batch_processing_tasks ENABLE ROW LEVEL SECURITY;
