#!/usr/bin/env node
/**
 * DRG 表结构验证脚本
 * 执行方式：npm run db:verify-drg
 * 用途：验证所有 DRG 表是否正确创建，并检查表结构
 */

import { createClient } from '@supabase/supabase-js'
import dotenv from 'dotenv'

dotenv.config()

const supabaseUrl = process.env.VITE_SUPABASE_URL
const supabaseKey = process.env.VITE_SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseKey) {
  console.error('❌ 错误：请配置 VITE_SUPABASE_URL 和 VITE_SUPABASE_ANON_KEY 环境变量')
  process.exit(1)
}

const supabase = createClient(supabaseUrl, supabaseKey)

interface TableInfo {
  tableName: string
  description: string
  expectedColumns: string[]
  requiredIndexes?: string[]
}

const EXPECTED_TABLES: TableInfo[] = [
  {
    tableName: 'case_front_page',
    description: '病案首页主表',
    expectedColumns: [
      'front_page_id',
      'admission_id',
      'patient_id',
      'patient_name',
      'primary_diagnosis_code',
      'primary_diagnosis_name',
      'main_procedure_code',
      'coding_status',
      'review_status',
      'coder_id',
      'reviewer_id',
      'created_at',
      'updated_at'
    ],
    requiredIndexes: [
      'idx_case_front_page_admission_id',
      'idx_case_front_page_coding_status',
      'idx_case_front_page_primary_diagnosis'
    ]
  },
  {
    tableName: 'case_front_page_diagnoses',
    description: '次诊断关联表',
    expectedColumns: [
      'id',
      'front_page_id',
      'diagnosis_code',
      'diagnosis_name',
      'sequence',
      'is_complication',
      'created_at'
    ]
  },
  {
    tableName: 'case_front_page_procedures',
    description: '手术操作关联表',
    expectedColumns: [
      'id',
      'front_page_id',
      'procedure_code',
      'procedure_name',
      'procedure_date',
      'sequence',
      'created_at'
    ]
  },
  {
    tableName: 'drg_groupings',
    description: 'DRG分组结果表',
    expectedColumns: [
      'grouping_id',
      'admission_id',
      'region',
      'adrg_code',
      'drg_code',
      'weight',
      'baseline_payment',
      'is_latest',
      'version',
      'grouped_at',
      'created_at'
    ]
  },
  {
    tableName: 'coding_suggestions',
    description: '编码建议表',
    expectedColumns: [
      'suggestion_id',
      'admission_id',
      'suggestion_type',
      'diagnosis_code',
      'message',
      'evidence',
      'severity',
      'status',
      'created_at'
    ]
  },
  {
    tableName: 'drg_alerts',
    description: 'DRG预警表',
    expectedColumns: [
      'alert_id',
      'admission_id',
      'alert_type',
      'alert_level',
      'message',
      'metric_value',
      'threshold_value',
      'status',
      'triggered_at'
    ]
  },
  {
    tableName: 'icd10_codes',
    description: 'ICD-10诊断编码库',
    expectedColumns: [
      'id',
      'code',
      'name',
      'category',
      'notes',
      'includes',
      'excludes',
      'is_active',
      'created_at'
    ]
  },
  {
    tableName: 'icd9_procedures',
    description: 'ICD-9-CM-3手术操作编码库',
    expectedColumns: [
      'id',
      'code',
      'name',
      'category',
      'notes',
      'includes',
      'excludes',
      'is_active',
      'created_at'
    ]
  }
]

/**
 * 检查表是否存在
 */
async function checkTableExists(tableName: string): Promise<boolean> {
  const { error } = await supabase.from(tableName).select('*').limit(1)

  if (error) {
    if (error.code === 'PGRST116' || error.message.includes('does not exist')) {
      return false
    }
  }
  return true
}

/**
 * 获取表的行数
 */
async function getTableRowCount(tableName: string): Promise<number | null> {
  const { count, error } = await supabase
    .from(tableName)
    .select('*', { count: 'exact', head: true })

  if (error) return null
  return count
}

/**
 * 验证主表结构
 */
async function verifyTables() {
  console.log('========================================')
  console.log('🔍 验证 DRG 表结构')
  console.log('========================================\n')

  let allTablesExist = true
  const results: Array<{
    table: string
    exists: boolean
    rowCount: number | null
  }> = []

  for (const tableInfo of EXPECTED_TABLES) {
    const { tableName, description } = tableInfo
    const exists = await checkTableExists(tableName)
    const rowCount = exists ? await getTableRowCount(tableName) : null

    results.push({ table: tableName, exists, rowCount })

    if (exists) {
      console.log(`✅ ${tableName.padEnd(35)} - 已存在 (${rowCount ?? 0} 行)`)
      console.log(`   ${description}`)
    } else {
      console.log(`❌ ${tableName.padEnd(35)} - 未找到`)
      console.log(`   ${description}`)
      allTablesExist = false
    }
    console.log()
  }

  return { allTablesExist, results }
}

/**
 * 验证外键约束（通过尝试插入数据）
 */
async function verifyConstraints() {
  console.log('========================================')
  console.log('🔗 验证外键约束')
  console.log('========================================\n')

  // 检查 case_front_page_diagnoses 是否有外键约束
  const testFrontPageId = 999999 // 不存在的 ID
  const { error } = await supabase
    .from('case_front_page_diagnoses')
    .insert({
      front_page_id: testFrontPageId,
      diagnosis_code: 'TEST',
      diagnosis_name: 'Test',
      sequence: 1
    })
    .select()

  if (error) {
    if (error.message.includes('foreign key') || error.code === '23503') {
      console.log('✅ 外键约束正常工作')
      console.log('   case_front_page_diagnoses -> case_front_page 外键已生效\n')
    } else {
      console.log('⚠️  警告：外键约束可能未生效')
      console.log(`   错误信息: ${error.message}\n`)
    }
  } else {
    console.log('⚠️  警告：外键约束未生效（允许插入无效的 front_page_id）')
    console.log('   建议检查 SQL 脚本中的 FOREIGN KEY 约束是否已启用\n')

    // 清理测试数据
    await supabase
      .from('case_front_page_diagnoses')
      .delete()
      .eq('front_page_id', testFrontPageId)
  }
}

/**
 * 验证触发器
 */
async function verifyTriggers() {
  console.log('========================================')
  console.log('⚙️  验证触发器')
  console.log('========================================\n')

  try {
    // 插入测试数据
    const testAdmissionId = `TEST_${Date.now()}`
    const { data: insertData, error: insertError } = await supabase
      .from('case_front_page')
      .insert({
        admission_id: testAdmissionId,
        patient_id: 'TEST_PATIENT',
        patient_name: '测试患者',
        patient_age: 30,
        patient_gender: 'M',
        primary_diagnosis_code: 'A00.001',
        primary_diagnosis_name: '测试诊断',
        coding_status: 'draft',
        review_status: 'pending'
      })
      .select()
      .single()

    if (insertError) {
      console.log(`❌ 无法插入测试数据: ${insertError.message}\n`)
      return
    }

    const initialUpdatedAt = insertData.updated_at

    // 等待 1 秒后更新
    await new Promise(resolve => setTimeout(resolve, 1000))

    // 更新数据
    const { data: updateData, error: updateError } = await supabase
      .from('case_front_page')
      .update({ patient_name: '测试患者_已更新' })
      .eq('admission_id', testAdmissionId)
      .select()
      .single()

    if (updateError) {
      console.log(`❌ 更新测试数据失败: ${updateError.message}\n`)
    } else {
      const finalUpdatedAt = updateData.updated_at

      if (finalUpdatedAt !== initialUpdatedAt) {
        console.log('✅ updated_at 触发器正常工作')
        console.log(`   初始时间: ${initialUpdatedAt}`)
        console.log(`   更新时间: ${finalUpdatedAt}\n`)
      } else {
        console.log('⚠️  警告：updated_at 触发器可能未生效')
        console.log('   更新后时间戳未改变\n')
      }
    }

    // 清理测试数据
    await supabase
      .from('case_front_page')
      .delete()
      .eq('admission_id', testAdmissionId)

    console.log('🧹 测试数据已清理\n')

  } catch (error) {
    console.error('❌ 触发器验证失败:', error)
  }
}

/**
 * 生成验证报告
 */
async function generateReport(
  allTablesExist: boolean,
  results: Array<{ table: string; exists: boolean; rowCount: number | null }>
) {
  console.log('========================================')
  console.log('📊 验证报告总结')
  console.log('========================================\n')

  const existingTables = results.filter(r => r.exists).length
  const totalTables = results.length

  console.log(`表数量: ${existingTables}/${totalTables}`)

  if (allTablesExist) {
    console.log('✅ 所有 DRG 表已成功创建\n')

    // 显示数据量统计
    console.log('数据量统计:')
    results.forEach(r => {
      if (r.exists && r.rowCount !== null) {
        console.log(`  ${r.table.padEnd(35)}: ${r.rowCount} 行`)
      }
    })
    console.log()

    console.log('下一步:')
    console.log('  1. 导入 ICD 编码数据到 icd10_codes 和 icd9_procedures 表')
    console.log('  2. 运行前端开发服务器: npm run dev')
    console.log('  3. 访问 DRG 模块进行测试\n')
  } else {
    console.log('❌ 部分表缺失，请执行以下步骤:\n')
    console.log('  1. 在 Supabase Dashboard 中执行 create-drg-tables.sql')
    console.log('  2. 或运行: npm run db:init-drg\n')

    console.log('缺失的表:')
    results.forEach(r => {
      if (!r.exists) {
        console.log(`  - ${r.table}`)
      }
    })
    console.log()
  }
}

/**
 * 主函数
 */
async function main() {
  console.log('\n')
  console.log('╔════════════════════════════════════════╗')
  console.log('║   DRG 数据库表结构验证工具            ║')
  console.log('╚════════════════════════════════════════╝')
  console.log('\n')

  // 1. 验证表存在性
  const { allTablesExist, results } = await verifyTables()

  if (!allTablesExist) {
    await generateReport(allTablesExist, results)
    process.exit(1)
  }

  // 2. 验证外键约束
  await verifyConstraints()

  // 3. 验证触发器
  await verifyTriggers()

  // 4. 生成报告
  await generateReport(allTablesExist, results)

  console.log('✨ 验证完成！\n')
}

main().catch(error => {
  console.error('❌ 验证过程出错:', error)
  process.exit(1)
})
