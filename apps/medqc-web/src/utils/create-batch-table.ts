/**
 * 临时工具：创建批量处理任务表
 * 在浏览器控制台中调用此函数来创建表
 */

import { supabase } from '@/lib/supabase'

// 创建表的SQL语句
const CREATE_TABLE_SQL = `
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

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_batch_tasks_user_id ON public.batch_processing_tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_batch_tasks_status ON public.batch_processing_tasks(status);
CREATE INDEX IF NOT EXISTS idx_batch_tasks_created_at ON public.batch_processing_tasks(created_at DESC);

-- 启用RLS
ALTER TABLE public.batch_processing_tasks ENABLE ROW LEVEL SECURITY;

-- 创建策略
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

-- 授予权限
GRANT SELECT, INSERT, UPDATE, DELETE ON public.batch_processing_tasks TO authenticated;
`

/**
 * 创建批量处理任务表
 * 在浏览器控制台中调用：window.createBatchTable()
 */
export async function createBatchTable() {
  try {
    console.log('🔄 开始创建批量处理任务表...')
    
    // 尝试直接插入一条测试记录来检查表是否存在
    const { data: user } = await supabase.auth.getUser()
    if (!user.user) {
      console.error('❌ 用户未登录')
      return false
    }

    // 先检查表是否存在
    const { error: checkError } = await supabase
      .from('batch_processing_tasks')
      .select('count(*)')
      .limit(1)

    if (!checkError) {
      console.log('✅ 批量处理任务表已存在')
      return true
    }

    console.log('⚠️ 表不存在，需要手动创建')
    console.log('📋 请在Supabase控制台执行以下SQL：')
    console.log('-----------------------------------')
    console.log(CREATE_TABLE_SQL)
    console.log('-----------------------------------')
    console.log('🔗 Supabase控制台地址：https://supabase.com/dashboard/project/YOUR_PROJECT/sql')
    
    return false
  } catch (error) {
    console.error('❌ 检查表失败:', error)
    return false
  }
}

/**
 * 创建测试数据
 */
export async function createTestData() {
  try {
    const { data: user } = await supabase.auth.getUser()
    if (!user.user) {
      console.error('❌ 用户未登录')
      return false
    }

    console.log('👤 当前用户ID:', user.user.id)

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

    const { data, error } = await supabase
      .from('batch_processing_tasks')
      .insert(testTasks)
      .select()

    if (error) {
      console.error('❌ 创建测试数据失败:', error)
      return false
    }

    console.log('✅ 测试数据创建成功:', data)
    return true
  } catch (error) {
    console.error('❌ 创建测试数据失败:', error)
    return false
  }
}

/**
 * 测试表访问权限
 */
export async function testTableAccess() {
  try {
    console.log('🔍 测试表访问权限...')

    const { data: user } = await supabase.auth.getUser()
    if (!user.user) {
      console.error('❌ 用户未登录')
      return false
    }

    console.log('👤 当前用户ID:', user.user.id)

    // 测试查询
    const { data, error } = await supabase
      .from('batch_processing_tasks')
      .select('*')
      .limit(5)

    if (error) {
      console.error('❌ 查询失败:', error)
      return false
    }

    console.log('✅ 查询成功，数据:', data)
    return true
  } catch (error) {
    console.error('❌ 测试失败:', error)
    return false
  }
}

// 将函数暴露到全局对象，方便在控制台调用
if (typeof window !== 'undefined') {
  ;(window as any).createBatchTable = createBatchTable
  ;(window as any).createTestData = createTestData
  ;(window as any).testTableAccess = testTableAccess
  console.log('🛠️ 批量表创建工具已加载')
  console.log('📝 在控制台中调用：')
  console.log('   window.createBatchTable() - 检查表并显示创建SQL')
  console.log('   window.createTestData() - 创建测试数据')
  console.log('   window.testTableAccess() - 测试表访问权限')
}
