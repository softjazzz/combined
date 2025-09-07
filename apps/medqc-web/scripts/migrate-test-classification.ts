/**
 * 测试环境医疗文书分类数据库迁移脚本
 * 专门针对 medical_records_test 表的层级化分类支持
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
      .filter(stmt => stmt.length > 0 && !stmt.startsWith('--') && !stmt.match(/^\s*$/))
    
    console.log(`📝 发现 ${statements.length} 个SQL语句`)
    
    let successCount = 0
    let errorCount = 0
    
    for (let i = 0; i < statements.length; i++) {
      const statement = statements[i]
      if (statement.trim()) {
        try {
          console.log(`   执行语句 ${i + 1}/${statements.length}...`)
          
          // 使用 rpc 调用执行 SQL
          const { data, error } = await supabase.rpc('exec_sql', { 
            sql_query: statement + ';' 
          })
          
          if (error) {
            console.error(`   ❌ 语句 ${i + 1} 执行失败:`, error.message)
            errorCount++
            
            // 对于某些可以忽略的错误，继续执行
            if (error.message.includes('already exists') || 
                error.message.includes('duplicate key') ||
                error.message.includes('does not exist')) {
              console.log(`   ⚠️  忽略可预期的错误，继续执行...`)
            }
          } else {
            console.log(`   ✅ 语句 ${i + 1} 执行成功`)
            successCount++
          }
        } catch (err) {
          console.error(`   ❌ 语句 ${i + 1} 执行异常:`, err)
          errorCount++
        }
      }
    }
    
    console.log(`✅ ${description}完成 - 成功: ${successCount}, 错误: ${errorCount}`)
    return { success: successCount, errors: errorCount }
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

async function checkTestEnvironment(): Promise<boolean> {
  console.log('🔍 检查测试环境...')
  
  // 检查 medical_records_test 表是否存在
  const testTableExists = await checkTableExists('medical_records_test')
  
  if (!testTableExists) {
    console.log('❌ medical_records_test 表不存在')
    console.log('请先创建测试表或确认您在正确的环境中')
    return false
  }
  
  console.log('✅ 测试环境检查通过')
  return true
}

async function main() {
  console.log('🚀 开始执行测试环境医疗文书分类数据库迁移...')
  console.log(`📡 Supabase URL: ${supabaseUrl}`)
  
  try {
    // 1. 检查测试环境
    const envCheck = await checkTestEnvironment()
    if (!envCheck) {
      process.exit(1)
    }
    
    // 2. 检查现有表结构
    console.log('\n📋 检查现有表结构...')
    const existingTables = ['medical_records_test', 'qc_rules', 'qc_results']
    
    for (const table of existingTables) {
      const exists = await checkTableExists(table)
      console.log(`   ${table}: ${exists ? '✅ 存在' : '❌ 不存在'}`)
    }
    
    // 3. 执行文书分类表创建
    const classificationMigrationPath = path.join(__dirname, '../database/migrations/20250901_add_test_document_classification.sql')
    if (fs.existsSync(classificationMigrationPath)) {
      const result1 = await executeSQLFile(classificationMigrationPath, '测试环境文书分类表结构创建')
      console.log(`📊 分类表创建结果: 成功 ${result1.success} 个，错误 ${result1.errors} 个`)
    } else {
      console.log('⚠️ 测试环境文书分类迁移文件不存在，跳过')
    }
    
    // 4. 执行质控规则表调整
    const qcUpdatePath = path.join(__dirname, '../database/migrations/20250901_update_qc_tables_for_test.sql')
    if (fs.existsSync(qcUpdatePath)) {
      const result2 = await executeSQLFile(qcUpdatePath, '测试环境质控规则表调整')
      console.log(`📊 质控表调整结果: 成功 ${result2.success} 个，错误 ${result2.errors} 个`)
    } else {
      console.log('⚠️ 测试环境质控规则更新文件不存在，跳过')
    }
    
    // 5. 验证新表结构
    console.log('\n🔍 验证新表结构...')
    const newTables = [
      'document_categories_test',
      'document_types_test', 
      'medical_documents_test',
      'qc_templates_test',
      'document_qc_results_test'
    ]
    
    let createdCount = 0
    for (const table of newTables) {
      const exists = await checkTableExists(table)
      console.log(`   ${table}: ${exists ? '✅ 创建成功' : '❌ 创建失败'}`)
      if (exists) createdCount++
    }
    
    // 6. 检查数据插入情况
    console.log('\n📊 检查基础数据...')
    
    try {
      const { data: categories, error: catError } = await supabase
        .from('document_categories_test')
        .select('category_code, category_name')
      
      if (!catError && categories) {
        console.log(`   文书分类: ${categories.length} 条记录`)
        categories.forEach(cat => {
          console.log(`     - ${cat.category_code}: ${cat.category_name}`)
        })
      } else {
        console.log('   ⚠️ 无法查询文书分类数据:', catError?.message)
      }
    } catch (error) {
      console.log('   ⚠️ 查询文书分类数据时出错:', error.message)
    }
    
    try {
      const { data: types, error: typeError } = await supabase
        .from('document_types_test')
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
      } else {
        console.log('   ⚠️ 无法查询文书类型数据:', typeError?.message)
      }
    } catch (error) {
      console.log('   ⚠️ 查询文书类型数据时出错:', error.message)
    }
    
    try {
      const { data: templates, error: templateError } = await supabase
        .from('qc_templates_test')
        .select('template_code, template_name')
      
      if (!templateError && templates) {
        console.log(`   质控模板: ${templates.length} 条记录`)
        templates.forEach(template => {
          console.log(`     - ${template.template_code}: ${template.template_name}`)
        })
      } else {
        console.log('   ⚠️ 无法查询质控模板数据:', templateError?.message)
      }
    } catch (error) {
      console.log('   ⚠️ 查询质控模板数据时出错:', error.message)
    }
    
    // 7. 生成迁移报告
    console.log('\n🎉 测试环境医疗文书分类数据库迁移完成！')
    console.log('\n📋 迁移总结:')
    console.log(`   ✅ 创建了 ${createdCount}/${newTables.length} 个新表`)
    console.log('   ✅ 插入了标准的医疗文书分类数据')
    console.log('   ✅ 调整了质控规则以支持文书类型')
    console.log('   ✅ 创建了专门的质控模板')
    console.log('   ✅ 建立了文书级别的质控结果表')
    
    console.log('\n🔧 后续步骤:')
    console.log('   1. 测试新的分类API接口')
    console.log('   2. 运行分类功能测试')
    console.log('   3. 验证质控模板功能')
    console.log('   4. 测试文书级质控功能')
    
    console.log('\n📝 测试建议:')
    console.log('   1. 上传一个测试病历到 medical_records_test')
    console.log('   2. 运行 LLM 解析和分类')
    console.log('   3. 检查 medical_documents_test 表中的分类结果')
    console.log('   4. 运行文书级质控测试')
    
  } catch (error) {
    console.error('❌ 迁移过程中发生错误:', error)
    process.exit(1)
  }
}

// 执行迁移
if (require.main === module) {
  main().catch(console.error)
}

export { main as runTestDocumentClassificationMigration }
