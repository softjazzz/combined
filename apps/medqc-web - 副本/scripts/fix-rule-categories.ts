/**
 * 修复质控规则的文书类别配置
 * - SC-062 和 SC-015: 从 document_categories 中移除 admission_record
 * - SC-046: 病理结果记录完整性，从 admission_record 改为 examination_report
 */

import { createClient } from '@supabase/supabase-js'

// Supabase 配置
const supabaseUrl = process.env.VITE_SUPABASE_URL || 'https://dgsdkdbjpucyawnyfbdu.supabase.co'
const supabaseServiceKey = process.env.SUPABASE_SERVICE_KEY || process.env.VITE_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRnc2RrZGJqcHVjeWF3bnlmYmR1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTYwODYyODcsImV4cCI6MjA3MTY2MjI4N30.k3178KRejQEoOogYjQ7EI_NfEW8ztVxFes3zLJ51JFw'

const supabase = createClient(supabaseUrl, supabaseServiceKey)

async function fixRuleCategories() {
  console.log('🔧 修复质控规则的文书类别配置...')

  try {
    // 查询当前配置
    const { data: rules, error: queryError } = await supabase
      .from('qc_rules')
      .select('rule_code, name, primary_document_category, document_categories')
      .in('rule_code', ['SC-062', 'SC-015', 'SC-046'])
      .order('rule_code')
    
    if (queryError) {
      console.error('❌ 查询规则失败:', queryError)
      return
    }
    
    if (!rules || rules.length === 0) {
      console.log('⚠️  未找到目标规则')
      return
    }
    
    console.log('\n📋 当前配置:')
    rules.forEach(rule => {
      console.log(`\n🔸 ${rule.rule_code}: ${rule.name}`)
      console.log(`   主要文书类别: ${rule.primary_document_category}`)
      console.log(`   文书类别数组: ${JSON.stringify(rule.document_categories)}`)
    })
    
    // 修复 SC-015: 医嘱变化合理性分析
    // 从 ["admission_record","progress_note","discharge_record"] 改为 ["progress_note","discharge_record"]
    const { error: sc015Error } = await supabase
      .from('qc_rules')
      .update({
        document_categories: ['progress_note', 'discharge_record']
      })
      .eq('rule_code', 'SC-015')
    
    if (sc015Error) {
      console.error('❌ 更新 SC-015 失败:', sc015Error)
    } else {
      console.log('✅ SC-015 更新成功: 移除了 admission_record')
    }
    
    // 修复 SC-062: 值班诊疗活动记录
    // 从 ["progress_note","operation_record","admission_record"] 改为 ["progress_note","operation_record"]
    const { error: sc062Error } = await supabase
      .from('qc_rules')
      .update({
        document_categories: ['progress_note', 'operation_record']
      })
      .eq('rule_code', 'SC-062')
    
    if (sc062Error) {
      console.error('❌ 更新 SC-062 失败:', sc062Error)
    } else {
      console.log('✅ SC-062 更新成功: 移除了 admission_record')
    }

    // 修复 SC-046: 病理结果记录完整性
    // 从 ["admission_record"] 改为 ["examination_report"]
    const { error: sc046Error } = await supabase
      .from('qc_rules')
      .update({
        document_categories: ['examination_report']
      })
      .eq('rule_code', 'SC-046')

    if (sc046Error) {
      console.error('❌ 更新 SC-046 失败:', sc046Error)
    } else {
      console.log('✅ SC-046 更新成功: 病理结果记录完整性 -> examination_report')
    }

    // 验证修复结果
    console.log('\n🔍 验证修复结果...')
    const { data: updatedRules, error: verifyError } = await supabase
      .from('qc_rules')
      .select('rule_code, name, primary_document_category, document_categories')
      .in('rule_code', ['SC-062', 'SC-015', 'SC-046'])
      .order('rule_code')
    
    if (verifyError) {
      console.error('❌ 验证失败:', verifyError)
      return
    }
    
    console.log('\n📋 修复后配置:')
    updatedRules?.forEach(rule => {
      console.log(`\n🔸 ${rule.rule_code}: ${rule.name}`)
      console.log(`   主要文书类别: ${rule.primary_document_category}`)
      console.log(`   文书类别数组: ${JSON.stringify(rule.document_categories)}`)
      
      const hasAdmissionRecord = rule.primary_document_category === 'admission_record' || 
                                (rule.document_categories && rule.document_categories.includes('admission_record'))
      
      if (hasAdmissionRecord) {
        console.log(`   ❌ 仍然包含 admission_record`)
      } else {
        console.log(`   ✅ 已移除 admission_record`)
      }
    })
    
  } catch (error) {
    console.error('❌ 修复过程中发生错误:', error)
  }
}

// 运行修复脚本
fixRuleCategories().then(() => {
  console.log('\n🎉 规则类别修复完成!')
  process.exit(0)
}).catch(error => {
  console.error('💥 修复脚本执行失败:', error)
  process.exit(1)
})
