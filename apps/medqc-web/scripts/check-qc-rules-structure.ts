#!/usr/bin/env node
/**
 * 检查质控规则表结构和数据
 * 分析当前文书类别映射情况
 */

import { createClient } from '@supabase/supabase-js'
import dotenv from 'dotenv'

// 加载环境变量
dotenv.config()

const supabaseUrl = process.env.VITE_SUPABASE_URL || 'https://your-project.supabase.co'
const supabaseKey = process.env.VITE_SUPABASE_ANON_KEY || 'your-anon-key'

const supabase = createClient(supabaseUrl, supabaseKey)

// 六个医疗文书类别定义
const DOCUMENT_CATEGORIES = {
  'progress_note': '病程记录',
  'admission_record': '入院记录', 
  'discharge_record': '出院记录',
  'operation_record': '手术相关记录',
  'examination_report': '辅助检查',
  'consent_form': '知情同意书'
}

async function checkQCRulesStructure() {
  console.log('🔍 检查质控规则表结构和数据...\n')

  try {
    // 1. 检查表结构
    console.log('📋 1. 检查 qc_rules 表结构:')
    const { data: tableInfo, error: tableError } = await supabase
      .from('qc_rules')
      .select('*')
      .limit(1)

    if (tableError) {
      console.error('❌ 无法访问 qc_rules 表:', tableError.message)
      return
    }

    if (tableInfo && tableInfo.length > 0) {
      const columns = Object.keys(tableInfo[0])
      console.log('✅ 表字段:', columns.join(', '))
      
      // 检查是否有文书类别相关字段
      const documentFields = columns.filter(col => 
        col.includes('document') || 
        col.includes('category') || 
        col.includes('type') ||
        col.includes('applicable')
      )
      console.log('📄 文书相关字段:', documentFields.length > 0 ? documentFields.join(', ') : '无')
    }

    // 2. 统计规则数量
    console.log('\n📊 2. 统计规则数据:')
    const { count, error: countError } = await supabase
      .from('qc_rules')
      .select('*', { count: 'exact', head: true })

    if (countError) {
      console.error('❌ 统计失败:', countError.message)
    } else {
      console.log(`✅ 总规则数量: ${count}`)
    }

    // 3. 分析规则分类
    console.log('\n🏷️ 3. 分析规则分类:')
    const { data: categories, error: catError } = await supabase
      .from('qc_rules')
      .select('category')
      .not('category', 'is', null)

    if (catError) {
      console.error('❌ 获取分类失败:', catError.message)
    } else if (categories) {
      const categoryStats = categories.reduce((acc: Record<string, number>, rule) => {
        const cat = rule.category || '未分类'
        acc[cat] = (acc[cat] || 0) + 1
        return acc
      }, {})
      
      console.log('📈 分类统计:')
      Object.entries(categoryStats).forEach(([cat, count]) => {
        console.log(`  - ${cat}: ${count} 条`)
      })
    }

    // 4. 检查文书类别字段
    console.log('\n📄 4. 检查文书类别映射:')
    
    // 尝试查找可能的文书类别字段
    const possibleFields = ['document_type', 'document_category', 'applicable_documents', 'target_documents']
    
    for (const field of possibleFields) {
      const { data: fieldData, error: fieldError } = await supabase
        .from('qc_rules')
        .select(field)
        .not(field, 'is', null)
        .limit(5)

      if (!fieldError && fieldData && fieldData.length > 0) {
        console.log(`✅ 找到字段 ${field}:`)
        fieldData.forEach((item, index) => {
          if (index < 3) { // 只显示前3个示例
            console.log(`  示例 ${index + 1}: ${JSON.stringify(item[field])}`)
          }
        })
      }
    }

    // 5. 获取规则样本
    console.log('\n📝 5. 规则样本 (前5条):')
    const { data: sampleRules, error: sampleError } = await supabase
      .from('qc_rules')
      .select('rule_code, name, category, description')
      .limit(5)

    if (sampleError) {
      console.error('❌ 获取样本失败:', sampleError.message)
    } else if (sampleRules) {
      sampleRules.forEach((rule, index) => {
        console.log(`\n  规则 ${index + 1}:`)
        console.log(`    编码: ${rule.rule_code || '无'}`)
        console.log(`    名称: ${rule.name}`)
        console.log(`    分类: ${rule.category}`)
        console.log(`    描述: ${rule.description?.substring(0, 100)}${rule.description?.length > 100 ? '...' : ''}`)
      })
    }

    console.log('\n✅ 检查完成!')
    console.log('\n📋 建议的六个文书类别:')
    Object.entries(DOCUMENT_CATEGORIES).forEach(([code, name]) => {
      console.log(`  - ${code}: ${name}`)
    })

  } catch (error) {
    console.error('❌ 检查过程中发生错误:', error)
  }
}

// 运行检查
checkQCRulesStructure().catch(console.error)
