/**
 * 数据库初始化工具
 * 用于创建批量处理任务表和相关配置
 */

import { supabase } from '@/lib/supabase'

// 批量处理任务表创建SQL
const CREATE_BATCH_TASKS_TABLE = `
-- 创建批量处理任务表
CREATE TABLE IF NOT EXISTS public.batch_processing_tasks (
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
`

// 创建索引SQL
const CREATE_INDEXES = `
-- 创建索引
CREATE INDEX IF NOT EXISTS idx_batch_tasks_user_id ON public.batch_processing_tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_batch_tasks_status ON public.batch_processing_tasks(status);
CREATE INDEX IF NOT EXISTS idx_batch_tasks_created_at ON public.batch_processing_tasks(created_at DESC);
`

// 启用RLS和创建策略SQL
const SETUP_RLS = `
-- 启用行级安全策略
ALTER TABLE public.batch_processing_tasks ENABLE ROW LEVEL SECURITY;

-- 创建RLS策略
DROP POLICY IF EXISTS "Users can view own batch tasks" ON public.batch_processing_tasks;
CREATE POLICY "Users can view own batch tasks" ON public.batch_processing_tasks
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own batch tasks" ON public.batch_processing_tasks;
CREATE POLICY "Users can insert own batch tasks" ON public.batch_processing_tasks
    FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own batch tasks" ON public.batch_processing_tasks;
CREATE POLICY "Users can update own batch tasks" ON public.batch_processing_tasks
    FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own batch tasks" ON public.batch_processing_tasks;
CREATE POLICY "Users can delete own batch tasks" ON public.batch_processing_tasks
    FOR DELETE USING (auth.uid() = user_id);
`

// 授予权限SQL
const GRANT_PERMISSIONS = `
-- 授予权限
GRANT SELECT, INSERT, UPDATE, DELETE ON public.batch_processing_tasks TO authenticated;
GRANT USAGE ON SCHEMA public TO authenticated;
`

/**
 * 初始化批量处理任务表
 */
export async function initBatchTasksTable(): Promise<boolean> {
  try {
    console.log('🔄 开始初始化批量处理任务表...')

    // 检查表是否存在
    const { error: checkError } = await supabase
      .from('batch_processing_tasks')
      .select('count(*)')
      .limit(1)

    if (!checkError) {
      console.log('✅ 批量处理任务表已存在')
      return true
    }

    console.log('❌ 批量处理任务表不存在')
    console.log('📋 请在Supabase控制台手动创建表')
    console.log('🔗 控制台地址：https://supabase.com/dashboard/project/afsbjvihjfsngobccnjx/sql')
    console.log('📝 请执行以下SQL脚本：')
    console.log('-----------------------------------')
    console.log(CREATE_BATCH_TASKS_TABLE)
    console.log(CREATE_INDEXES)
    console.log(SETUP_RLS)
    console.log(GRANT_PERMISSIONS)
    console.log('-----------------------------------')

    return false

  } catch (error) {
    console.error('❌ 初始化批量处理任务表失败:', error)
    return false
  }
}

/**
 * 检查批量处理任务表是否存在
 */
export async function checkBatchTasksTable(): Promise<boolean> {
  try {
    const { error } = await supabase
      .from('batch_processing_tasks')
      .select('count(*)')
      .limit(1)

    return !error
  } catch (error) {
    console.error('检查批量处理任务表失败:', error)
    return false
  }
}

/**
 * 创建测试数据
 */
export async function createTestBatchTasks(): Promise<boolean> {
  try {
    const { data: user } = await supabase.auth.getUser()
    if (!user.user) {
      console.error('用户未登录，无法创建测试数据')
      return false
    }

    const testTasks = [
      {
        user_id: user.user.id,
        task_type: 'upload',
        total_items: 10,
        processed_items: 10,
        failed_items: 0,
        status: 'completed',
        progress_percentage: 100,
        completed_at: new Date().toISOString()
      },
      {
        user_id: user.user.id,
        task_type: 'analysis',
        total_items: 5,
        processed_items: 3,
        failed_items: 1,
        status: 'processing',
        progress_percentage: 60
      }
    ]

    const { error } = await supabase
      .from('batch_processing_tasks')
      .insert(testTasks)

    if (error) {
      console.error('创建测试数据失败:', error)
      return false
    }

    console.log('✅ 测试数据创建成功')
    return true
  } catch (error) {
    console.error('创建测试数据失败:', error)
    return false
  }
}

/**
 * 自动初始化数据库（在开发环境中调用）
 */
export async function autoInitDatabase(): Promise<void> {
  if (process.env.NODE_ENV !== 'development') {
    return
  }

  console.log('🚀 开发环境：自动初始化数据库...')
  
  // 检查表是否存在
  const tableExists = await checkBatchTasksTable()
  
  if (!tableExists) {
    console.log('⚠️ 批量处理任务表不存在，尝试初始化...')
    const initSuccess = await initBatchTasksTable()
    
    if (!initSuccess) {
      console.error('❌ 自动初始化失败，请手动执行 database-init.sql 脚本')
      console.log('📝 请在Supabase控制台的SQL编辑器中执行以下脚本：')
      console.log('   1. 打开 https://supabase.com/dashboard/project/YOUR_PROJECT/sql')
      console.log('   2. 复制并执行 database-init.sql 文件中的内容')
    }
  } else {
    console.log('✅ 批量处理任务表已存在')
  }
}
