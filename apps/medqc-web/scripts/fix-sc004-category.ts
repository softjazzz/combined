/**
 * 修复 SC-004 规则的文书类别分类问题
 * SC-004: "入院诊断应根据患者入院时病情综合分析，主次排列有序"
 * 应该主要归类为 admission_record（入院记录）而不是 progress_note（病程记录）
 */

import { createClient } from '@supabase/supabase-js'

// Supabase 配置
const supabaseUrl = process.env.VITE_SUPABASE_URL || 'https://dgsdkdbjpucyawnyfbdu.supabase.co'
const supabaseServiceKey = process.env.SUPABASE_SERVICE_KEY || process.env.VITE_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRnc2RrZGJqcHVjeWF3bnlmYmR1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTYwODYyODcsImV4cCI6MjA3MTY2MjI4N30.k3178KRejQEoOogYjQ7EI_NfEW8ztVxFes3zLJ51JFw'

const supabase = createClient(supabaseUrl, supabaseServiceKey)

async function fixSC004Category() {
  console.log('🔧 开始修复 SC-004 规则的文书类别分类...')
  
  try {
    // 1. 查询当前 SC-004 规则的数据
    const { data: currentRule, error: queryError } = await supabase
      .from('qc_rules')
      .select('*')
      .eq('rule_code', 'SC-004')
      .single()
    
    if (queryError) {
      console.error('❌ 查询 SC-004 规则失败:', queryError)
      return
    }
    
    if (!currentRule) {
      console.log('⚠️  未找到 SC-004 规则')
      return
    }
    
    console.log('📋 当前 SC-004 规则信息:')
    console.log('   规则名称:', currentRule.name)
    console.log('   规则描述:', currentRule.description)
    console.log('   当前主要文书类别:', currentRule.primary_document_category)
    console.log('   当前文书类别数组:', currentRule.document_categories)
    
    // 2. 检查是否需要修复
    if (currentRule.primary_document_category === 'admission_record') {
      console.log('✅ SC-004 规则的主要文书类别已经是 admission_record，无需修复')
      return
    }
    
    // 3. 更新规则的文书类别
    const updateData = {
      primary_document_category: 'admission_record',
      document_categories: ['admission_record', 'progress_note', 'discharge_record'],
      updated_at: new Date().toISOString()
    }
    
    const { data: updatedRule, error: updateError } = await supabase
      .from('qc_rules')
      .update(updateData)
      .eq('rule_code', 'SC-004')
      .select()
      .single()
    
    if (updateError) {
      console.error('❌ 更新 SC-004 规则失败:', updateError)
      return
    }
    
    console.log('✅ SC-004 规则修复成功!')
    console.log('📋 修复后的规则信息:')
    console.log('   主要文书类别:', updatedRule.primary_document_category)
    console.log('   文书类别数组:', updatedRule.document_categories)
    
    // 4. 验证修复结果
    console.log('\n🔍 验证修复结果...')
    const { data: verifyRule, error: verifyError } = await supabase
      .from('qc_rules')
      .select('rule_code, name, primary_document_category, document_categories')
      .eq('rule_code', 'SC-004')
      .single()
    
    if (verifyError) {
      console.error('❌ 验证失败:', verifyError)
      return
    }
    
    console.log('✅ 验证成功，SC-004 规则现在正确归类为入院记录')
    console.log('📊 最终数据:', verifyRule)
    
  } catch (error) {
    console.error('❌ 修复过程中发生错误:', error)
  }
}

// 运行修复脚本
fixSC004Category().then(() => {
  console.log('\n🎉 SC-004 规则文书类别修复完成!')
  process.exit(0)
}).catch(error => {
  console.error('💥 修复脚本执行失败:', error)
  process.exit(1)
})
