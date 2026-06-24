#!/usr/bin/env node
/**
 * DRG 数据库表创建脚本
 * 执行方式：npm run db:init-drg
 */

import { createClient } from '@supabase/supabase-js'
import { readFileSync } from 'fs'
import { join, dirname } from 'path'
import { fileURLToPath } from 'url'
import dotenv from 'dotenv'

// 加载环境变量
dotenv.config()

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

// Supabase 配置
const supabaseUrl = process.env.VITE_SUPABASE_URL
const supabaseKey = process.env.VITE_SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseKey) {
  console.error('❌ 错误：请配置 VITE_SUPABASE_URL 和 VITE_SUPABASE_ANON_KEY 环境变量')
  process.exit(1)
}

const supabase = createClient(supabaseUrl, supabaseKey)

async function createDRGTables() {
  console.log('========================================')
  console.log('🚀 开始创建 DRG 数据库表...')
  console.log('========================================\n')

  try {
    // 读取 SQL 文件
    const sqlFilePath = join(__dirname, 'create-drg-tables.sql')
    console.log(`📄 读取 SQL 文件: ${sqlFilePath}`)
    const sql = readFileSync(sqlFilePath, 'utf-8')

    // 执行 SQL（Supabase 客户端可能不支持直接执行 DDL，需要使用 REST API）
    console.log('⏳ 执行 SQL 创建表...\n')

    // 方法1：使用 Supabase REST API 执行 SQL（需要 service_role key）
    // const { data, error } = await supabase.rpc('exec_sql', { sql_query: sql })

    // 方法2：分段执行（推荐在 Supabase Dashboard SQL Editor 中执行）
    console.log('⚠️  注意：Supabase 客户端不支持直接执行 DDL 语句')
    console.log('请选择以下方式之一执行建表 SQL：\n')
    console.log('方式1（推荐）：在 Supabase Dashboard 中执行')
    console.log('  1. 打开 Supabase Dashboard: ' + supabaseUrl.replace('https://', 'https://app.supabase.com/project/'))
    console.log('  2. 进入 "SQL Editor"')
    console.log('  3. 复制 create-drg-tables.sql 的内容并执行\n')

    console.log('方式2：使用 PostgreSQL 客户端')
    console.log('  psql -h <your-db-host> -U postgres -d postgres -f scripts/migrations/create-drg-tables.sql\n')

    console.log('方式3：使用 Supabase CLI（如果已安装）')
    console.log('  supabase db push\n')

    console.log('========================================')
    console.log('📋 SQL 文件内容预览：')
    console.log('========================================\n')
    console.log(sql.substring(0, 500) + '...\n')

    console.log('✅ SQL 文件准备完成')
    console.log('📂 文件位置: scripts/migrations/create-drg-tables.sql')

    // 尝试验证表是否已存在
    console.log('\n🔍 检查表是否已存在...')
    await checkTablesExist()

  } catch (error) {
    console.error('❌ 错误:', error)
    process.exit(1)
  }
}

/**
 * 检查表是否已存在
 */
async function checkTablesExist() {
  const tables = [
    'case_front_page',
    'case_front_page_diagnoses',
    'case_front_page_procedures',
    'drg_groupings',
    'coding_suggestions',
    'drg_alerts',
    'icd10_codes',
    'icd9_procedures'
  ]

  for (const tableName of tables) {
    const { data, error } = await supabase.from(tableName).select('*').limit(1)

    if (error) {
      if (error.code === 'PGRST116' || error.message.includes('does not exist')) {
        console.log(`   ⚪ ${tableName} - 未创建`)
      } else {
        console.log(`   ⚠️  ${tableName} - 检查失败: ${error.message}`)
      }
    } else {
      console.log(`   ✅ ${tableName} - 已存在`)
    }
  }
}

/**
 * 插入示例数据（可选）
 */
async function insertSampleData() {
  console.log('\n========================================')
  console.log('📊 是否插入示例数据？')
  console.log('========================================\n')

  // 这里可以添加示例数据插入逻辑
  console.log('💡 提示：可以使用 Mock 数据文件进行测试')
  console.log('   位置: src/data/drg/mock-*.ts\n')
}

// 主函数
async function main() {
  await createDRGTables()

  // 可选：插入示例数据
  // await insertSampleData()

  console.log('\n========================================')
  console.log('✨ 完成！')
  console.log('========================================')
  console.log('\n下一步：')
  console.log('  1. 在 Supabase Dashboard 执行 SQL')
  console.log('  2. 运行前端开发服务器: npm run dev')
  console.log('  3. 使用 Mock 数据模式进行开发（VITE_USE_DRG_MOCK=true）\n')
}

main().catch(console.error)
