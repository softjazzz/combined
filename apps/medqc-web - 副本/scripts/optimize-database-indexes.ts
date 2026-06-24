#!/usr/bin/env node
/**
 * 数据库索引优化脚本
 * 创建必要的索引以提升查询性能
 */

import { createClient } from '@supabase/supabase-js'
import { config } from 'dotenv'

// 加载环境变量
config()

const supabaseUrl = process.env.VITE_SUPABASE_URL!
const supabaseServiceKey = process.env.SUPABASE_SERVICE_KEY || process.env.VITE_SUPABASE_ANON_KEY!

if (!supabaseUrl || !supabaseServiceKey) {
  console.error('❌ 缺少必要的环境变量')
  console.error('需要: VITE_SUPABASE_URL 和 SUPABASE_SERVICE_KEY (或 VITE_SUPABASE_ANON_KEY)')
  process.exit(1)
}

const supabase = createClient(supabaseUrl, supabaseServiceKey)

// 索引定义
const indexes = [
  // medical_records 表索引
  {
    name: 'idx_medical_records_department_status',
    table: 'medical_records',
    columns: ['department', 'status'],
    type: 'btree',
    description: '按科室和状态筛选病案'
  },
  {
    name: 'idx_medical_records_created_at',
    table: 'medical_records',
    columns: ['created_at'],
    type: 'btree',
    description: '按创建时间排序'
  },
  {
    name: 'idx_medical_records_patient_name',
    table: 'medical_records',
    columns: ['patient_name'],
    type: 'btree',
    description: '按患者姓名搜索'
  },
  {
    name: 'idx_medical_records_admission_date',
    table: 'medical_records',
    columns: ['admission_date'],
    type: 'btree',
    description: '按入院日期查询'
  },
  {
    name: 'idx_medical_records_content_fts',
    table: 'medical_records',
    columns: ['content'],
    type: 'gin',
    expression: 'to_tsvector(\'english\', content)',
    description: '病历内容全文搜索'
  },

  // qc_results 表索引
  {
    name: 'idx_qc_results_record_id',
    table: 'qc_results',
    columns: ['record_id'],
    type: 'btree',
    description: '按病案ID查询质控结果'
  },
  {
    name: 'idx_qc_results_analysis_time',
    table: 'qc_results',
    columns: ['analysis_time'],
    type: 'btree',
    description: '按分析时间排序'
  },
  {
    name: 'idx_qc_results_overall_score',
    table: 'qc_results',
    columns: ['overall_score'],
    type: 'btree',
    description: '按总体评分查询'
  },
  {
    name: 'idx_qc_results_grade',
    table: 'qc_results',
    columns: ['grade'],
    type: 'btree',
    description: '按等级分组统计'
  },
  {
    name: 'idx_qc_results_record_analysis_time',
    table: 'qc_results',
    columns: ['record_id', 'analysis_time'],
    type: 'btree',
    description: '复合索引：病案ID + 分析时间'
  },

  // qc_rules 表索引
  {
    name: 'idx_qc_rules_category_active',
    table: 'qc_rules',
    columns: ['category', 'is_active'],
    type: 'btree',
    description: '按类别和激活状态查询规则'
  },
  {
    name: 'idx_qc_rules_severity',
    table: 'qc_rules',
    columns: ['severity'],
    type: 'btree',
    description: '按严重程度查询规则'
  },

  // qc_rule_executions 表索引
  {
    name: 'idx_qc_rule_executions_result_id',
    table: 'qc_rule_executions',
    columns: ['qc_result_id'],
    type: 'btree',
    description: '按质控结果ID查询规则执行记录'
  },
  {
    name: 'idx_qc_rule_executions_rule_id',
    table: 'qc_rule_executions',
    columns: ['rule_id'],
    type: 'btree',
    description: '按规则ID查询执行记录'
  },
  {
    name: 'idx_qc_rule_executions_execution_time',
    table: 'qc_rule_executions',
    columns: ['execution_time'],
    type: 'btree',
    description: '按执行时间排序'
  },

  // user_roles 表索引
  {
    name: 'idx_user_roles_user_id',
    table: 'user_roles',
    columns: ['user_id'],
    type: 'btree',
    description: '按用户ID查询角色'
  },
  {
    name: 'idx_user_roles_role',
    table: 'user_roles',
    columns: ['role'],
    type: 'btree',
    description: '按角色查询用户'
  },
  {
    name: 'idx_user_roles_department',
    table: 'user_roles',
    columns: ['department'],
    type: 'btree',
    description: '按科室查询用户'
  }
]

/**
 * 创建单个索引
 */
async function createIndex(index: typeof indexes[0]): Promise<boolean> {
  try {
    let sql = ''
    
    if (index.type === 'gin' && index.expression) {
      // GIN索引，使用表达式
      sql = `CREATE INDEX IF NOT EXISTS ${index.name} ON ${index.table} USING gin(${index.expression})`
    } else {
      // 普通索引
      const columnList = index.columns.join(', ')
      sql = `CREATE INDEX IF NOT EXISTS ${index.name} ON ${index.table} USING ${index.type}(${columnList})`
    }

    console.log(`🔨 创建索引: ${index.name}`)
    console.log(`   SQL: ${sql}`)
    
    const { error } = await supabase.rpc('execute_sql', { sql })
    
    if (error) {
      console.error(`❌ 创建索引失败: ${index.name}`)
      console.error(`   错误: ${error.message}`)
      return false
    }
    
    console.log(`✅ 索引创建成功: ${index.name}`)
    return true
  } catch (error) {
    console.error(`❌ 创建索引异常: ${index.name}`)
    console.error(`   错误: ${error}`)
    return false
  }
}

/**
 * 检查索引是否存在
 */
async function checkIndexExists(indexName: string): Promise<boolean> {
  try {
    const { data, error } = await supabase.rpc('execute_sql', {
      sql: `
        SELECT indexname 
        FROM pg_indexes 
        WHERE indexname = '${indexName}'
      `
    })
    
    if (error) {
      console.warn(`⚠️  检查索引失败: ${indexName}`)
      return false
    }
    
    return data && data.length > 0
  } catch (error) {
    console.warn(`⚠️  检查索引异常: ${indexName}`)
    return false
  }
}

/**
 * 获取表的统计信息
 */
async function getTableStats(tableName: string): Promise<{
  rowCount: number
  indexCount: number
  tableSize: string
}> {
  try {
    const { data: rowCountData } = await supabase.rpc('execute_sql', {
      sql: `SELECT COUNT(*) as count FROM ${tableName}`
    })
    
    const { data: indexData } = await supabase.rpc('execute_sql', {
      sql: `
        SELECT COUNT(*) as count 
        FROM pg_indexes 
        WHERE tablename = '${tableName}'
      `
    })
    
    const { data: sizeData } = await supabase.rpc('execute_sql', {
      sql: `
        SELECT pg_size_pretty(pg_total_relation_size('${tableName}')) as size
      `
    })
    
    return {
      rowCount: rowCountData?.[0]?.count || 0,
      indexCount: indexData?.[0]?.count || 0,
      tableSize: sizeData?.[0]?.size || '0 bytes'
    }
  } catch (error) {
    console.warn(`⚠️  获取表统计信息失败: ${tableName}`)
    return {
      rowCount: 0,
      indexCount: 0,
      tableSize: '0 bytes'
    }
  }
}

/**
 * 主函数
 */
async function main() {
  console.log('🚀 开始数据库索引优化...\n')
  
  // 获取优化前的统计信息
  console.log('📊 优化前统计信息:')
  const tables = ['medical_records', 'qc_results', 'qc_rules', 'qc_rule_executions', 'user_roles']
  const beforeStats: Record<string, any> = {}
  
  for (const table of tables) {
    const stats = await getTableStats(table)
    beforeStats[table] = stats
    console.log(`   ${table}: ${stats.rowCount} 行, ${stats.indexCount} 个索引, ${stats.tableSize}`)
  }
  
  console.log('\n🔨 开始创建索引...\n')
  
  let created = 0
  let skipped = 0
  let failed = 0
  
  for (const index of indexes) {
    // 检查索引是否已存在
    const exists = await checkIndexExists(index.name)
    if (exists) {
      console.log(`⏭️  索引已存在，跳过: ${index.name}`)
      skipped++
      continue
    }
    
    // 创建索引
    const success = await createIndex(index)
    if (success) {
      created++
    } else {
      failed++
    }
    
    // 添加延迟避免过载
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  
  console.log('\n📊 优化后统计信息:')
  for (const table of tables) {
    const stats = await getTableStats(table)
    const before = beforeStats[table]
    const indexDiff = stats.indexCount - before.indexCount
    console.log(`   ${table}: ${stats.rowCount} 行, ${stats.indexCount} 个索引 (+${indexDiff}), ${stats.tableSize}`)
  }
  
  console.log('\n🎉 索引优化完成!')
  console.log(`✅ 创建成功: ${created} 个`)
  console.log(`⏭️  跳过已存在: ${skipped} 个`)
  console.log(`❌ 创建失败: ${failed} 个`)
  
  if (failed > 0) {
    console.log('\n⚠️  部分索引创建失败，请检查日志')
    process.exit(1)
  }
  
  console.log('\n💡 建议:')
  console.log('   - 监控查询性能变化')
  console.log('   - 定期分析慢查询日志')
  console.log('   - 根据实际使用情况调整索引')
}

// 运行脚本
if (require.main === module) {
  main().catch(error => {
    console.error('❌ 脚本执行失败:', error)
    process.exit(1)
  })
}
