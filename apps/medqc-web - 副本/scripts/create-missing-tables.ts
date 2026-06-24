import { createClient } from '@supabase/supabase-js'
import type { Database } from '../src/types/supabase'
import { config } from 'dotenv'

// 加载环境变量
config()

// 环境变量配置
const supabaseUrl = process.env.VITE_SUPABASE_URL || 'https://afsbjvihjfsngobccnjx.supabase.co'
const supabaseServiceKey = process.env.SUPABASE_SERVICE_KEY || process.env.VITE_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFmc2JqdmloamZzbmdvYmNjbmp4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTIwNDE4NzQsImV4cCI6MjA2NzYxNzg3NH0.wA1Ho-pJrvPfF8k5npURDV8lL14nYdsImr8xJ5_Xvqg'

const supabase = createClient<Database>(supabaseUrl, supabaseServiceKey)

/**
 * 创建缺失的质控相关表
 */
async function createMissingTables() {
  console.log('🔧 开始创建缺失的质控表...')
  
  try {
    // 1. 创建 qc_rule_executions 表
    console.log('📝 创建 qc_rule_executions 表...')
    const createExecutionsTable = `
      CREATE TABLE IF NOT EXISTS qc_rule_executions (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          record_id UUID NOT NULL REFERENCES medical_records(id) ON DELETE CASCADE,
          rule_id UUID NOT NULL REFERENCES qc_rules(id) ON DELETE CASCADE,
          execution_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
          passed BOOLEAN NOT NULL,
          score INTEGER NOT NULL,
          max_score INTEGER NOT NULL,
          deduction INTEGER NOT NULL DEFAULT 0,
          confidence DECIMAL(3,2) NOT NULL DEFAULT 0.0,
          execution_duration INTEGER NOT NULL DEFAULT 0,
          error_message TEXT,
          created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
      );
    `
    
    const { error: execError } = await supabase.rpc('exec_sql', { sql: createExecutionsTable })
    if (execError) {
      console.log('⚠️  使用直接SQL创建 qc_rule_executions 表...')
      // 如果 exec_sql 不存在，尝试直接执行
      const { error: directError } = await supabase
        .from('qc_rule_executions')
        .select('id')
        .limit(1)
      
      if (directError && directError.code === '42P01') {
        console.log('❌ qc_rule_executions 表不存在，需要手动创建')
      }
    } else {
      console.log('✅ qc_rule_executions 表创建成功')
    }

    // 2. 创建 qc_issues 表
    console.log('📝 创建 qc_issues 表...')
    const createIssuesTable = `
      CREATE TABLE IF NOT EXISTS qc_issues (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          execution_id UUID NOT NULL REFERENCES qc_rule_executions(id) ON DELETE CASCADE,
          code VARCHAR(50) NOT NULL,
          description TEXT NOT NULL,
          severity VARCHAR(20) NOT NULL CHECK (severity IN ('critical', 'major', 'minor')),
          location TEXT,
          suggestion TEXT,
          deduction INTEGER NOT NULL DEFAULT 0,
          category VARCHAR(50) NOT NULL,
          created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
      );
    `
    
    const { error: issuesError } = await supabase.rpc('exec_sql', { sql: createIssuesTable })
    if (issuesError) {
      console.log('⚠️  使用直接SQL创建 qc_issues 表...')
      const { error: directError } = await supabase
        .from('qc_issues')
        .select('id')
        .limit(1)
      
      if (directError && directError.code === '42P01') {
        console.log('❌ qc_issues 表不存在，需要手动创建')
      }
    } else {
      console.log('✅ qc_issues 表创建成功')
    }

    // 3. 创建索引
    console.log('📝 创建索引...')
    const createIndexes = `
      CREATE INDEX IF NOT EXISTS idx_qc_rule_executions_record ON qc_rule_executions(record_id);
      CREATE INDEX IF NOT EXISTS idx_qc_rule_executions_rule ON qc_rule_executions(rule_id);
      CREATE INDEX IF NOT EXISTS idx_qc_rule_executions_time ON qc_rule_executions(execution_time);
      CREATE INDEX IF NOT EXISTS idx_qc_issues_execution ON qc_issues(execution_id);
      CREATE INDEX IF NOT EXISTS idx_qc_issues_severity ON qc_issues(severity);
    `
    
    const { error: indexError } = await supabase.rpc('exec_sql', { sql: createIndexes })
    if (indexError) {
      console.log('⚠️  索引创建可能失败，但不影响基本功能')
    } else {
      console.log('✅ 索引创建成功')
    }

    // 4. 验证表是否创建成功
    console.log('🔍 验证表创建结果...')
    
    const tables = ['qc_rule_executions', 'qc_issues']
    for (const tableName of tables) {
      try {
        const { error } = await supabase
          .from(tableName as any)
          .select('*')
          .limit(1)
        
        if (error && error.code === '42P01') {
          console.log(`❌ 表 ${tableName} 仍然不存在`)
        } else {
          console.log(`✅ 表 ${tableName} 验证成功`)
        }
      } catch (e) {
        console.log(`⚠️  表 ${tableName} 验证时出现异常:`, e)
      }
    }

    console.log('🎉 缺失表创建过程完成')
    
  } catch (error) {
    console.error('❌ 创建缺失表时发生错误:', error)
    throw error
  }
}

/**
 * 使用 SQL 文件方式创建表（备用方案）
 */
async function createTablesWithSQL() {
  console.log('🔧 使用SQL文件方式创建表...')
  
  const sqlStatements = [
    // 创建 qc_rule_executions 表
    `CREATE TABLE IF NOT EXISTS qc_rule_executions (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      record_id UUID NOT NULL,
      rule_id UUID NOT NULL,
      execution_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
      passed BOOLEAN NOT NULL,
      score INTEGER NOT NULL,
      max_score INTEGER NOT NULL,
      deduction INTEGER NOT NULL DEFAULT 0,
      confidence DECIMAL(3,2) NOT NULL DEFAULT 0.0,
      execution_duration INTEGER NOT NULL DEFAULT 0,
      error_message TEXT,
      created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );`,
    
    // 创建 qc_issues 表
    `CREATE TABLE IF NOT EXISTS qc_issues (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      execution_id UUID NOT NULL,
      code VARCHAR(50) NOT NULL,
      description TEXT NOT NULL,
      severity VARCHAR(20) NOT NULL CHECK (severity IN ('critical', 'major', 'minor')),
      location TEXT,
      suggestion TEXT,
      deduction INTEGER NOT NULL DEFAULT 0,
      category VARCHAR(50) NOT NULL,
      created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );`,
    
    // 创建索引
    `CREATE INDEX IF NOT EXISTS idx_qc_rule_executions_record ON qc_rule_executions(record_id);`,
    `CREATE INDEX IF NOT EXISTS idx_qc_rule_executions_rule ON qc_rule_executions(rule_id);`,
    `CREATE INDEX IF NOT EXISTS idx_qc_rule_executions_time ON qc_rule_executions(execution_time);`,
    `CREATE INDEX IF NOT EXISTS idx_qc_issues_execution ON qc_issues(execution_id);`,
    `CREATE INDEX IF NOT EXISTS idx_qc_issues_severity ON qc_issues(severity);`
  ]
  
  for (let i = 0; i < sqlStatements.length; i++) {
    try {
      console.log(`执行SQL语句 ${i + 1}/${sqlStatements.length}...`)
      const { error } = await supabase.rpc('exec_sql', { sql: sqlStatements[i] })
      if (error) {
        console.log(`⚠️  SQL语句 ${i + 1} 执行警告:`, error.message)
      } else {
        console.log(`✅ SQL语句 ${i + 1} 执行成功`)
      }
    } catch (e) {
      console.log(`❌ SQL语句 ${i + 1} 执行失败:`, e)
    }
  }
}

/**
 * 主函数
 */
async function main() {
  try {
    // 首先尝试标准方式创建
    await createMissingTables()
    
    // 如果标准方式失败，尝试SQL文件方式
    console.log('\n🔄 尝试备用方案...')
    await createTablesWithSQL()
    
    console.log('\n✅ 表创建过程完成，请手动验证表是否存在')
    console.log('💡 提示：如果表仍然不存在，可能需要在Supabase控制台手动创建')
    
  } catch (error) {
    console.error('❌ 主函数执行失败:', error)
    process.exit(1)
  }
}

// 如果直接运行此脚本
if (import.meta.url === `file://${process.argv[1]}`) {
  main()
    .then(() => {
      console.log('脚本执行完成')
      process.exit(0)
    })
    .catch((error) => {
      console.error('脚本执行失败:', error)
      process.exit(1)
    })
}

export { createMissingTables, createTablesWithSQL }
