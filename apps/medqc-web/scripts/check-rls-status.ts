import { createClient } from '@supabase/supabase-js'
import * as dotenv from 'dotenv'

// 加载环境变量
dotenv.config()

const supabaseUrl = process.env.VITE_SUPABASE_URL!
const supabaseKey = process.env.VITE_SUPABASE_ANON_KEY!

const supabase = createClient(supabaseUrl, supabaseKey)

async function checkRLSStatus() {
  try {
    console.log('🔍 检查RLS策略状态...\n')
    
    // 检查主要表的RLS状态
    const tables = [
      'medical_records',
      'qc_results', 
      'qc_rules',
      'user_roles',
      'analytics_results',
      'report_instances',
      'alert_records'
    ]
    
    for (const tableName of tables) {
      console.log(`📋 检查表: ${tableName}`)
      
      // 尝试查询数据以测试访问权限
      const { data, error } = await supabase
        .from(tableName)
        .select('*')
        .limit(1)
      
      if (error) {
        if (error.message.includes('row-level security')) {
          console.log(`  🔒 RLS已启用 - ${error.message}`)
        } else if (error.message.includes('does not exist')) {
          console.log(`  ❌ 表不存在`)
        } else {
          console.log(`  ⚠️  其他错误: ${error.message}`)
        }
      } else {
        console.log(`  ✅ 可正常访问 (${data?.length || 0} 条记录)`)
      }
    }
    
    console.log('\n🎯 RLS状态总结:')
    console.log('- 如果看到"row-level security"错误，说明RLS已启用')
    console.log('- 如果看到"可正常访问"，说明RLS可能已禁用或有开放策略')
    
  } catch (error) {
    console.error('❌ 检查RLS状态失败:', error)
  }
}

checkRLSStatus() 