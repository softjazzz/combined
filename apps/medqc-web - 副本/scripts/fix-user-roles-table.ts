import { createClient } from '@supabase/supabase-js'
import * as dotenv from 'dotenv'

// 加载环境变量
dotenv.config()

const supabaseUrl = process.env.VITE_SUPABASE_URL!
const supabaseKey = process.env.VITE_SUPABASE_ANON_KEY!

const supabase = createClient(supabaseUrl, supabaseKey)

async function fixUserRolesTable() {
  try {
    console.log('🔧 修复 user_roles 表结构...')
    
    // 检查 department 字段是否存在
    const { data: testData, error: testError } = await supabase
      .from('user_roles')
      .select('department')
      .limit(1)
    
    if (testError && testError.message.includes('does not exist')) {
      console.log('📝 添加 department 字段...')
      
      // 添加 department 字段
      const { error: alterError } = await supabase.rpc('exec_sql', {
        sql: 'ALTER TABLE user_roles ADD COLUMN department VARCHAR(50);'
      })
      
      if (alterError) {
        console.log('⚠️  无法使用 rpc 添加字段，尝试直接执行...')
        
        // 如果 rpc 不可用，我们需要手动在 Supabase Dashboard 中执行
        console.log('🔧 请在 Supabase Dashboard 的 SQL Editor 中执行以下 SQL:')
        console.log('ALTER TABLE user_roles ADD COLUMN department VARCHAR(50);')
        return
      }
      
      console.log('✅ department 字段添加成功')
    } else {
      console.log('✅ department 字段已存在')
    }
    
    // 验证修复结果
    const { data: verifyData, error: verifyError } = await supabase
      .from('user_roles')
      .select('id, user_id, role, department')
      .limit(1)
    
    if (verifyError) {
      console.error('❌ 验证失败:', verifyError)
    } else {
      console.log('✅ 表结构修复完成，可以正常查询 department 字段')
    }
    
  } catch (error) {
    console.error('❌ 修复失败:', error)
  }
}

fixUserRolesTable() 