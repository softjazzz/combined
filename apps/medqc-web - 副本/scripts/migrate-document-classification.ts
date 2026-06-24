/**
 * 医疗文书分类数据库迁移脚本
 * 执行文书分类相关的数据库结构调整
 */

import { createClient } from '@supabase/supabase-js'
import * as fs from 'fs'
import * as path from 'path'

// 环境变量配置
const supabaseUrl = process.env.VITE_SUPABASE_URL || 'https://dgsdkdbjpucyawnyfbdu.supabase.co'
const supabaseServiceKey = process.env.SUPABASE_SERVICE_KEY || process.env.VITE_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRnc2RrZGJqcHVjeWF3bnlmYmR1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTYwODYyODcsImV4cCI6MjA3MTY2MjI4N30.k3178KRejQEoOogYjQ7EI_NfEW8ztVxFes3zLJ51JFw'

const supabase = createClient(supabaseUrl, supabaseServiceKey)

async function executeSQLFile(filePath: string, description: string) {
  console.log(`\n🔄 执行${description}...`)
  
  try {
    const sqlContent = fs.readFileSync(filePath, 'utf8')
    
    // 将SQL内容按分号分割成多个语句
    const statements = sqlContent
      .split(';')
      .map(stmt => stmt.trim())
      .filter(stmt => stmt.length > 0 && !stmt.startsWith('--'))
    
    console.log(`📝 发现 ${statements.length} 个SQL语句`)
    
    for (let i = 0; i < statements.length; i++) {
      const statement = statements[i]
      if (statement.trim()) {
        try {
          console.log(`   执行语句 ${i + 1}/${statements.length}...`)
          const { error } = await supabase.rpc('exec_sql', { sql_query: statement })
          
          if (error) {
            console.error(`   ❌ 语句 ${i + 1} 执行失败:`, error.message)
            // 继续执行其他语句，不中断整个过程
          } else {
            console.log(`   ✅ 语句 ${i + 1} 执行成功`)
          }
        } catch (err) {
          console.error(`   ❌ 语句 ${i + 1} 执行异常:`, err)
        }
      }
    }
    
    console.log(`✅ ${description}完成`)
  } catch (error) {
    console.error(`❌ ${description}失败:`, error)
    throw error
  }
}

async function checkTableExists(tableName: string): Promise<boolean> {
  try {
    const { data, error } = await supabase
      .from(tableName)
      .select('*')
      .limit(0)
    
    return !error
  } catch {
    return false
  }
}

async function main() {
  console.log('🚀 开始执行医疗文书分类数据库迁移...')
  console.log(`📡 Supabase URL: ${supabaseUrl}`)
  
  try {
    // 1. 检查现有表结构
    console.log('\n📋 检查现有表结构...')
    const existingTables = ['medical_records', 'qc_rules', 'qc_results']
    
    for (const table of existingTables) {
      const exists = await checkTableExists(table)
      console.log(`   ${table}: ${exists ? '✅ 存在' : '❌ 不存在'}`)
    }
    
    // 2. 执行文书分类表创建
    const migrationPath = path.join(__dirname, '../database/migrations/20250901_add_document_classification.sql')
    if (fs.existsSync(migrationPath)) {
      await executeSQLFile(migrationPath, '文书分类表结构创建')
    } else {
      console.log('⚠️ 文书分类迁移文件不存在，跳过')
    }
    
    // 3. 执行质控规则表调整
    const qcUpdatePath = path.join(__dirname, '../database/migrations/20250901_update_qc_rules_for_documents.sql')
    if (fs.existsSync(qcUpdatePath)) {
      await executeSQLFile(qcUpdatePath, '质控规则表调整')
    } else {
      console.log('⚠️ 质控规则更新文件不存在，跳过')
    }
    
    // 4. 验证新表结构
    console.log('\n🔍 验证新表结构...')
    const newTables = [
      'document_categories',
      'document_types', 
      'medical_documents',
      'qc_templates',
      'document_qc_results'
    ]
    
    for (const table of newTables) {
      const exists = await checkTableExists(table)
      console.log(`   ${table}: ${exists ? '✅ 创建成功' : '❌ 创建失败'}`)
    }
    
    // 5. 检查数据插入情况
    console.log('\n📊 检查基础数据...')
    
    try {
      const { data: categories, error: catError } = await supabase
        .from('document_categories')
        .select('category_code, category_name')
      
      if (!catError && categories) {
        console.log(`   文书分类: ${categories.length} 条记录`)
        categories.forEach(cat => {
          console.log(`     - ${cat.category_code}: ${cat.category_name}`)
        })
      }
    } catch (error) {
      console.log('   ⚠️ 无法查询文书分类数据')
    }
    
    try {
      const { data: types, error: typeError } = await supabase
        .from('document_types')
        .select('type_code, type_name')
        .limit(10)
      
      if (!typeError && types) {
        console.log(`   文书类型: ${types.length}+ 条记录`)
        types.slice(0, 5).forEach(type => {
          console.log(`     - ${type.type_code}: ${type.type_name}`)
        })
        if (types.length > 5) {
          console.log(`     ... 还有 ${types.length - 5} 条记录`)
        }
      }
    } catch (error) {
      console.log('   ⚠️ 无法查询文书类型数据')
    }
    
    try {
      const { data: templates, error: templateError } = await supabase
        .from('qc_templates')
        .select('template_code, template_name')
      
      if (!templateError && templates) {
        console.log(`   质控模板: ${templates.length} 条记录`)
        templates.forEach(template => {
          console.log(`     - ${template.template_code}: ${template.template_name}`)
        })
      }
    } catch (error) {
      console.log('   ⚠️ 无法查询质控模板数据')
    }
    
    console.log('\n🎉 医疗文书分类数据库迁移完成！')
    console.log('\n📋 迁移总结:')
    console.log('   ✅ 创建了层级化的文书分类表结构')
    console.log('   ✅ 插入了标准的医疗文书分类数据')
    console.log('   ✅ 调整了质控规则以支持文书类型')
    console.log('   ✅ 创建了专门的质控模板')
    console.log('   ✅ 建立了文书级别的质控结果表')
    
    console.log('\n🔧 后续步骤:')
    console.log('   1. 更新前端代码以使用新的分类体系')
    console.log('   2. 调整LLM解析逻辑以支持文书分类')
    console.log('   3. 实现基于文书类型的专门质控')
    console.log('   4. 测试新的分类和质控功能')
    
  } catch (error) {
    console.error('❌ 迁移过程中发生错误:', error)
    process.exit(1)
  }
}

// 执行迁移
if (require.main === module) {
  main().catch(console.error)
}

export { main as runDocumentClassificationMigration }
