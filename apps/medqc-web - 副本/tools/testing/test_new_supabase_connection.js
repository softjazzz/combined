#!/usr/bin/env node

/**
 * 测试新 Supabase 项目连接
 * 验证配置是否正确，数据库是否可访问
 */

import { createClient } from '@supabase/supabase-js'
import { config } from 'dotenv'

// 加载环境变量
config()

// 新的 Supabase 配置
const supabaseUrl = 'https://dgsdkdbjpucyawnyfbdu.supabase.co'
const supabaseAnonKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRnc2RrZGJqcHVjeWF3bnlmYmR1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTYwODYyODcsImV4cCI6MjA3MTY2MjI4N30.k3178KRejQEoOogYjQ7EI_NfEW8ztVxFes3zLJ51JFw'

console.log('🚀 测试新 Supabase 项目连接...\n')

// 创建 Supabase 客户端
const supabase = createClient(supabaseUrl, supabaseAnonKey)

async function testConnection() {
  try {
    console.log('📡 连接信息:')
    console.log(`   URL: ${supabaseUrl}`)
    console.log(`   Key: ${supabaseAnonKey.substring(0, 20)}...`)
    console.log()

    // 1. 测试基本连接
    console.log('1️⃣ 测试基本连接...')
    const { data: healthCheck, error: healthError } = await supabase
      .from('departments')
      .select('count', { count: 'exact', head: true })
    
    if (healthError) {
      console.log('❌ 连接失败:', healthError.message)
      return false
    }
    console.log('✅ 基本连接成功')

    // 2. 检查表是否存在
    console.log('\n2️⃣ 检查核心表是否存在...')
    const tables = [
      'departments',
      'user_profiles', 
      'medical_records',
      'qc_rules',
      'qc_results',
      'batch_processing_tasks'
    ]

    for (const table of tables) {
      try {
        const { error } = await supabase
          .from(table)
          .select('*')
          .limit(0)
        
        if (error) {
          console.log(`❌ 表 ${table} 不存在或无法访问:`, error.message)
        } else {
          console.log(`✅ 表 ${table} 存在`)
        }
      } catch (err) {
        console.log(`❌ 检查表 ${table} 时出错:`, err.message)
      }
    }

    // 3. 检查初始数据
    console.log('\n3️⃣ 检查初始数据...')
    
    // 检查科室数据
    const { data: departments, error: deptError } = await supabase
      .from('departments')
      .select('*')
    
    if (deptError) {
      console.log('❌ 无法获取科室数据:', deptError.message)
    } else {
      console.log(`✅ 科室数据: ${departments.length} 条记录`)
      if (departments.length > 0) {
        console.log('   示例科室:', departments.slice(0, 3).map(d => d.name).join(', '))
      }
    }

    // 检查分析指标数据
    const { data: metrics, error: metricsError } = await supabase
      .from('analytics_metrics')
      .select('*')
    
    if (metricsError) {
      console.log('❌ 无法获取分析指标数据:', metricsError.message)
    } else {
      console.log(`✅ 分析指标数据: ${metrics.length} 条记录`)
      if (metrics.length > 0) {
        console.log('   示例指标:', metrics.slice(0, 3).map(m => m.metric_name).join(', '))
      }
    }

    // 检查质控规则数据
    const { data: rules, error: rulesError } = await supabase
      .from('qc_rules')
      .select('*')
    
    if (rulesError) {
      console.log('❌ 无法获取质控规则数据:', rulesError.message)
    } else {
      console.log(`✅ 质控规则数据: ${rules.length} 条记录`)
      if (rules.length > 0) {
        console.log('   示例规则:', rules.slice(0, 3).map(r => r.name).join(', '))
      }
    }

    // 4. 检查视图
    console.log('\n4️⃣ 检查统计视图...')
    const views = [
      'v_department_qc_stats',
      'v_doctor_performance', 
      'v_qc_trends'
    ]

    for (const view of views) {
      try {
        const { error } = await supabase
          .from(view)
          .select('*')
          .limit(0)
        
        if (error) {
          console.log(`❌ 视图 ${view} 不存在或无法访问:`, error.message)
        } else {
          console.log(`✅ 视图 ${view} 存在`)
        }
      } catch (err) {
        console.log(`❌ 检查视图 ${view} 时出错:`, err.message)
      }
    }

    // 5. 测试插入操作（如果有权限）
    console.log('\n5️⃣ 测试写入权限...')
    try {
      // 尝试插入一个测试科室
      const testDept = {
        name: '测试科室_' + Date.now(),
        code: 'TEST_' + Date.now(),
        description: '连接测试用临时科室',
        category: 'clinical'
      }

      const { data: insertData, error: insertError } = await supabase
        .from('departments')
        .insert(testDept)
        .select()

      if (insertError) {
        console.log('❌ 写入测试失败:', insertError.message)
      } else {
        console.log('✅ 写入测试成功')
        
        // 清理测试数据
        if (insertData && insertData.length > 0) {
          await supabase
            .from('departments')
            .delete()
            .eq('id', insertData[0].id)
          console.log('✅ 测试数据已清理')
        }
      }
    } catch (err) {
      console.log('❌ 写入测试出错:', err.message)
    }

    console.log('\n🎉 连接测试完成!')
    return true

  } catch (error) {
    console.error('❌ 测试过程中发生错误:', error)
    return false
  }
}

// 运行测试
testConnection().then(success => {
  if (success) {
    console.log('\n✅ 新 Supabase 项目配置正确，可以正常使用!')
  } else {
    console.log('\n❌ 新 Supabase 项目配置有问题，请检查数据库初始化!')
    process.exit(1)
  }
}).catch(error => {
  console.error('\n💥 测试失败:', error)
  process.exit(1)
})
