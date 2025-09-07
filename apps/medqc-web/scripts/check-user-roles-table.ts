import { createClient } from '@supabase/supabase-js'
import * as dotenv from 'dotenv'

// 加载环境变量
dotenv.config()

const supabaseUrl = process.env.VITE_SUPABASE_URL!
const supabaseKey = process.env.VITE_SUPABASE_ANON_KEY!

const supabase = createClient(supabaseUrl, supabaseKey)

async function checkUserRolesTable() {
  try {
    console.log('🔍 检查 user_roles 表结构...')
    
    // 尝试查询表结构 - 使用 rpc 调用
    const { data, error } = await supabase.rpc('get_table_columns', {
      table_name: 'user_roles'
    })
    
    if (error) {
      console.log('⚠️  无法使用 rpc 查询，尝试直接查询数据...')
      
      // 直接查询数据来推断结构
      const { data: roleData, error: roleError } = await supabase
        .from('user_roles')
        .select('*')
        .limit(1)
      
      if (roleError) {
        console.error('❌ 查询角色数据失败:', roleError)
        return
      }
      
      if (roleData && roleData.length > 0) {
        console.log('📋 从数据推断的字段:')
        console.log(Object.keys(roleData[0]))
        
        const hasDepartment = roleData[0].hasOwnProperty('department')
        
        if (hasDepartment) {
          console.log('✅ department 字段存在')
        } else {
          console.log('❌ department 字段不存在')
          console.log('🔧 需要添加 department 字段')
        }
      } else {
        console.log('⚠️  表为空，无法确定结构')
      }
    } else {
      console.log('📋 user_roles 表字段:')
      console.table(data)
    }
    
    // 尝试查询包含 department 的数据
    try {
      const { data: testData, error: testError } = await supabase
        .from('user_roles')
        .select('id, user_id, role, department')
        .limit(1)
      
      if (testError) {
        console.log('❌ department 字段不存在，错误:', testError.message)
      } else {
        console.log('✅ department 字段存在并可查询')
      }
    } catch (err) {
      console.log('❌ department 字段查询失败')
    }
    
  } catch (error) {
    console.error('❌ 检查失败:', error)
  }
}

checkUserRolesTable() 