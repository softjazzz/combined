/**
 * 检查 SC-062 和 SC-015 规则的文书类别配置
 * 分析为什么它们会出现在入院记录的筛选列表中
 */

import { createClient } from '@supabase/supabase-js'

// Supabase 配置
const supabaseUrl = process.env.VITE_SUPABASE_URL || 'https://dgsdkdbjpucyawnyfbdu.supabase.co'
const supabaseServiceKey = process.env.SUPABASE_SERVICE_KEY || process.env.VITE_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRnc2RrZGJqcHVjeWF3bnlmYmR1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTYwODYyODcsImV4cCI6MjA3MTY2MjI4N30.k3178KRejQEoOogYjQ7EI_NfEW8ztVxFes3zLJ51JFw'

const supabase = createClient(supabaseUrl, supabaseServiceKey)

async function checkRuleCategories() {
  console.log('🔍 检查 SC-062 和 SC-015 规则的文书类别配置...')
  
  try {
    // 查询这两个规则的详细信息
    const { data: rules, error } = await supabase
      .from('qc_rules')
      .select('rule_code, name, description, primary_document_category, document_categories')
      .in('rule_code', ['SC-062', 'SC-015'])
      .order('rule_code')
    
    if (error) {
      console.error('❌ 查询规则失败:', error)
      return
    }
    
    if (!rules || rules.length === 0) {
      console.log('⚠️  未找到 SC-062 和 SC-015 规则')
      return
    }
    
    console.log('\n📋 规则详细信息:')
    rules.forEach(rule => {
      console.log(`\n🔸 ${rule.rule_code}: ${rule.name}`)
      console.log(`   描述: ${rule.description}`)
      console.log(`   主要文书类别: ${rule.primary_document_category}`)
      console.log(`   文书类别数组: ${JSON.stringify(rule.document_categories)}`)
      
      // 分析为什么会出现在入院记录列表中
      const hasAdmissionRecord = rule.primary_document_category === 'admission_record' || 
                                (rule.document_categories && rule.document_categories.includes('admission_record'))
      
      if (hasAdmissionRecord) {
        console.log(`   ❌ 问题: 该规则包含 admission_record，会出现在入院记录筛选中`)
      } else {
        console.log(`   ✅ 正常: 该规则不应该出现在入院记录筛选中`)
      }
    })
    
    // 检查所有包含 admission_record 的规则
    console.log('\n🔍 检查所有包含 admission_record 的规则...')
    const { data: admissionRules, error: admissionError } = await supabase
      .from('qc_rules')
      .select('rule_code, name, primary_document_category, document_categories')
      .or('primary_document_category.eq.admission_record,document_categories.cs.{admission_record}')
      .order('rule_code')
    
    if (admissionError) {
      console.error('❌ 查询入院记录规则失败:', admissionError)
      return
    }
    
    console.log(`\n📊 总共有 ${admissionRules?.length || 0} 条规则包含 admission_record:`)
    admissionRules?.forEach(rule => {
      const isPrimary = rule.primary_document_category === 'admission_record'
      const isInArray = rule.document_categories && rule.document_categories.includes('admission_record')
      
      console.log(`   ${rule.rule_code}: ${rule.name}`)
      console.log(`      主要类别: ${rule.primary_document_category} ${isPrimary ? '✅' : ''}`)
      console.log(`      数组包含: ${isInArray ? '✅' : '❌'}`)
    })
    
  } catch (error) {
    console.error('❌ 检查过程中发生错误:', error)
  }
}

// 运行检查脚本
checkRuleCategories().then(() => {
  console.log('\n🎉 规则类别检查完成!')
  process.exit(0)
}).catch(error => {
  console.error('💥 检查脚本执行失败:', error)
  process.exit(1)
})
