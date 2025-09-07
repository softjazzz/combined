import { createClient } from '@supabase/supabase-js'
import { config } from 'dotenv'

// 加载环境变量
config()

const supabaseUrl = process.env.VITE_SUPABASE_URL!
const supabaseServiceKey = process.env.VITE_SUPABASE_ANON_KEY!

const supabase = createClient(supabaseUrl, supabaseServiceKey)

async function verifySchema() {
  console.log('🔍 验证数据库Schema...\n')
  
  const checks = [
    {
      name: '医疗记录表 (medical_records)',
      test: async () => {
        const { data, error } = await supabase
          .from('medical_records')
          .select('*')
          .limit(1)
        return { success: !error, error }
      }
    },
    {
      name: '质控规则表 (qc_rules)',
      test: async () => {
        const { data, error } = await supabase
          .from('qc_rules')
          .select('*')
          .limit(1)
        return { success: !error, error }
      }
    },
    {
      name: '质控结果表 (qc_results)',
      test: async () => {
        const { data, error } = await supabase
          .from('qc_results')
          .select('*')
          .limit(1)
        return { success: !error, error }
      }
    },
    {
      name: '用户角色表 (user_roles)',
      test: async () => {
        const { data, error } = await supabase
          .from('user_roles')
          .select('*')
          .limit(1)
        return { success: !error, error }
      }
    }
  ]
  
  let allPassed = true
  
  for (const check of checks) {
    try {
      const result = await check.test()
      if (result.success) {
        console.log('✅', check.name)
      } else {
        console.log('❌', check.name, '- 错误:', result.error?.message)
        allPassed = false
      }
    } catch (error) {
      console.log('❌', check.name, '- 异常:', error)
      allPassed = false
    }
  }
  
  console.log('\n' + '='.repeat(50))
  if (allPassed) {
    console.log('🎉 所有表结构验证通过！')
    console.log('✨ 现在可以运行增强schema迁移: pnpm run db:migrate')
    console.log('📝 然后初始化质控规则: pnpm run db:init-rules')
  } else {
    console.log('⚠️  部分表结构验证失败，请检查SQL执行结果')
    console.log('💡 建议重新在Supabase Dashboard中执行基础schema SQL')
  }
  console.log('='.repeat(50))
}

// 执行验证
verifySchema()

export { verifySchema } 