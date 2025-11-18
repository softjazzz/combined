#!/usr/bin/env node
/**
 * ICD 编码数据导入脚本
 * 执行方式：npm run db:import-icd
 *
 * 数据来源：
 * - ICD-10 国家临床版 2.0
 * - ICD-9-CM-3 手术操作编码
 */

import { createClient } from '@supabase/supabase-js'
import { readFileSync, existsSync } from 'fs'
import { join, dirname } from 'path'
import { fileURLToPath } from 'url'
import dotenv from 'dotenv'

dotenv.config()

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const supabaseUrl = process.env.VITE_SUPABASE_URL
const supabaseKey = process.env.VITE_SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseKey) {
  console.error('❌ 错误：请配置 VITE_SUPABASE_URL 和 VITE_SUPABASE_ANON_KEY 环境变量')
  process.exit(1)
}

const supabase = createClient(supabaseUrl, supabaseKey)

interface ICDCodeData {
  code: string
  name: string
  category?: string
  notes?: string
  includes?: string[]
  excludes?: string[]
  is_active?: boolean
}

/**
 * 从 Mock 数据导入（开发/测试用）
 */
async function importFromMockData() {
  console.log('📦 从 Mock 数据导入...\n')

  try {
    // 动态导入 Mock 数据
    const mockIcdCodesPath = join(__dirname, '../../src/data/drg/mock-icd-codes.ts')

    if (!existsSync(mockIcdCodesPath)) {
      console.error('❌ Mock 数据文件不存在')
      return
    }

    // 读取并解析 TypeScript 文件（简单方法：使用 tsx）
    const { mockICD10Codes, mockICD9Procedures } = await import('../../src/data/drg/mock-icd-codes.js')

    // 导入 ICD-10 编码
    console.log('📥 导入 ICD-10 编码...')
    for (const code of mockICD10Codes) {
      const { error } = await supabase
        .from('icd10_codes')
        .upsert({
          code: code.code,
          name: code.name,
          category: code.category,
          notes: code.notes,
          includes: code.includes,
          excludes: code.excludes,
          is_active: true
        }, { onConflict: 'code' })

      if (error) {
        console.error(`   ❌ ${code.code} 导入失败: ${error.message}`)
      } else {
        console.log(`   ✅ ${code.code} - ${code.name}`)
      }
    }

    // 导入 ICD-9-CM-3 编码
    console.log('\n📥 导入 ICD-9-CM-3 手术操作编码...')
    for (const proc of mockICD9Procedures) {
      const { error } = await supabase
        .from('icd9_procedures')
        .upsert({
          code: proc.code,
          name: proc.name,
          category: proc.category,
          notes: proc.notes,
          includes: proc.includes,
          excludes: proc.excludes,
          is_active: true
        }, { onConflict: 'code' })

      if (error) {
        console.error(`   ❌ ${proc.code} 导入失败: ${error.message}`)
      } else {
        console.log(`   ✅ ${proc.code} - ${proc.name}`)
      }
    }

    console.log('\n✅ Mock 数据导入完成！')

  } catch (error) {
    console.error('❌ 导入失败:', error)
    throw error
  }
}

/**
 * 从 JSON 文件导入（生产用）
 */
async function importFromJSONFiles(icd10Path?: string, icd9Path?: string) {
  console.log('📦 从 JSON 文件导入...\n')

  // ICD-10 导入
  if (icd10Path && existsSync(icd10Path)) {
    console.log(`📥 导入 ICD-10 编码: ${icd10Path}`)
    const icd10Data: ICDCodeData[] = JSON.parse(readFileSync(icd10Path, 'utf-8'))

    let successCount = 0
    let errorCount = 0

    for (const code of icd10Data) {
      const { error } = await supabase
        .from('icd10_codes')
        .upsert({
          code: code.code,
          name: code.name,
          category: code.category || null,
          notes: code.notes || null,
          includes: code.includes || [],
          excludes: code.excludes || [],
          is_active: code.is_active !== false
        }, { onConflict: 'code' })

      if (error) {
        console.error(`   ❌ ${code.code} 导入失败: ${error.message}`)
        errorCount++
      } else {
        successCount++
        if (successCount % 100 === 0) {
          console.log(`   ✅ 已导入 ${successCount} 条`)
        }
      }
    }

    console.log(`\n✅ ICD-10 导入完成: 成功 ${successCount}, 失败 ${errorCount}`)
  }

  // ICD-9-CM-3 导入
  if (icd9Path && existsSync(icd9Path)) {
    console.log(`\n📥 导入 ICD-9-CM-3 编码: ${icd9Path}`)
    const icd9Data: ICDCodeData[] = JSON.parse(readFileSync(icd9Path, 'utf-8'))

    let successCount = 0
    let errorCount = 0

    for (const proc of icd9Data) {
      const { error } = await supabase
        .from('icd9_procedures')
        .upsert({
          code: proc.code,
          name: proc.name,
          category: proc.category || null,
          notes: proc.notes || null,
          includes: proc.includes || [],
          excludes: proc.excludes || [],
          is_active: proc.is_active !== false
        }, { onConflict: 'code' })

      if (error) {
        console.error(`   ❌ ${proc.code} 导入失败: ${error.message}`)
        errorCount++
      } else {
        successCount++
        if (successCount % 100 === 0) {
          console.log(`   ✅ 已导入 ${successCount} 条`)
        }
      }
    }

    console.log(`\n✅ ICD-9-CM-3 导入完成: 成功 ${successCount}, 失败 ${errorCount}`)
  }
}

/**
 * 统计已导入的编码数量
 */
async function showStatistics() {
  console.log('\n========================================')
  console.log('📊 ICD 编码库统计')
  console.log('========================================\n')

  // ICD-10 统计
  const { count: icd10Count, error: icd10Error } = await supabase
    .from('icd10_codes')
    .select('*', { count: 'exact', head: true })

  if (icd10Error) {
    console.error(`❌ ICD-10 统计失败: ${icd10Error.message}`)
  } else {
    console.log(`ICD-10 诊断编码: ${icd10Count} 条`)
  }

  // ICD-9-CM-3 统计
  const { count: icd9Count, error: icd9Error } = await supabase
    .from('icd9_procedures')
    .select('*', { count: 'exact', head: true })

  if (icd9Error) {
    console.error(`❌ ICD-9-CM-3 统计失败: ${icd9Error.message}`)
  } else {
    console.log(`ICD-9-CM-3 手术操作编码: ${icd9Count} 条`)
  }

  console.log()
}

/**
 * 主函数
 */
async function main() {
  console.log('\n')
  console.log('╔════════════════════════════════════════╗')
  console.log('║   ICD 编码数据导入工具                 ║')
  console.log('╚════════════════════════════════════════╝')
  console.log('\n')

  // 解析命令行参数
  const args = process.argv.slice(2)
  const mode = args[0] || 'mock' // mock | json

  try {
    if (mode === 'mock') {
      // 从 Mock 数据导入（用于开发/测试）
      console.log('模式: Mock 数据导入（开发/测试）\n')
      await importFromMockData()

    } else if (mode === 'json') {
      // 从 JSON 文件导入（用于生产）
      const icd10Path = args[1] // 第二个参数：ICD-10 JSON 文件路径
      const icd9Path = args[2]  // 第三个参数：ICD-9-CM-3 JSON 文件路径

      if (!icd10Path && !icd9Path) {
        console.error('❌ 错误：请提供 JSON 文件路径\n')
        console.log('用法：')
        console.log('  npm run db:import-icd json <icd10.json> <icd9.json>')
        console.log('\nJSON 文件格式示例:')
        console.log(JSON.stringify([
          {
            code: 'I21.001',
            name: '急性前壁ST段抬高型心肌梗死',
            category: '循环系统疾病',
            notes: '限于有ST段抬高的急性前壁心肌梗死',
            includes: ['急性前壁心肌梗死伴ST段抬高'],
            excludes: ['陈旧性心肌梗死(I25.2)'],
            is_active: true
          }
        ], null, 2))
        process.exit(1)
      }

      console.log('模式: JSON 文件导入（生产）\n')
      await importFromJSONFiles(icd10Path, icd9Path)

    } else {
      console.error('❌ 错误：无效的导入模式\n')
      console.log('用法：')
      console.log('  npm run db:import-icd mock           # 从 Mock 数据导入')
      console.log('  npm run db:import-icd json <icd10.json> <icd9.json>  # 从 JSON 文件导入')
      process.exit(1)
    }

    // 显示统计信息
    await showStatistics()

    console.log('✨ 导入完成！\n')
    console.log('下一步:')
    console.log('  1. 运行验证脚本: npm run db:verify-drg')
    console.log('  2. 启动开发服务器: npm run dev\n')

  } catch (error) {
    console.error('❌ 导入过程出错:', error)
    process.exit(1)
  }
}

main()
