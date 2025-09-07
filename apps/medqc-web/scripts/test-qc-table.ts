#!/usr/bin/env node
import 'dotenv/config'
import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.VITE_SUPABASE_URL!
const supabaseKey = process.env.VITE_SUPABASE_ANON_KEY!

const supabase = createClient(supabaseUrl, supabaseKey)

async function testQCTable() {
  try {
    console.log('🔍 测试qc_results表结构...\n')
    
    // 1. 检查表是否存在
    console.log('📋 检查qc_results表是否存在...')
    const { data: existingData, error: existingError } = await supabase
      .from('qc_results')
      .select('*')
      .limit(0)
    
    if (existingError) {
      console.error('❌ qc_results表不存在或有错误:', existingError.message)
      return
    }
    
    console.log('✅ qc_results表存在')
    
    // 2. 尝试插入测试数据
    console.log('\n📝 尝试插入测试QC结果...')
    
    const testQCData = {
      record_id: '00000000-0000-0000-0000-000000000001', // 假设的ID
      analysis_result: {
        overallScore: 85,
        categoryScores: {
          completeness: 90,
          consistency: 85,
          rationality: 80,
          timeliness: 85
        },
        grade: 'B',
        suggestions: ['建议完善病史记录']
      },
      overall_score: 85,
      completeness_score: 90,
      consistency_score: 85,
      rationality_score: 80,
      timeliness_score: 85,
      grade: 'B',
      issues: [],
      suggestions: ['建议完善病史记录'],
      ai_model: 'deepseek-v3',
      analysis_time_ms: 5000,
      confidence_score: 0.95,
      rule_version: '1.0'
    }
    
    const { data: insertResult, error: insertError } = await supabase
      .from('qc_results')
      .insert(testQCData)
      .select()
      .single()
    
    if (insertError) {
      console.error('❌ 插入测试数据失败:', insertError.message)
      
      // 检查具体是哪个字段有问题
      if (insertError.message.includes('column')) {
        console.log('💡 这通常意味着表结构中缺少某些字段')
        console.log('💡 请确保已执行database-update.sql脚本')
      }
    } else {
      console.log('✅ 测试数据插入成功!')
      console.log(`   QC结果ID: ${insertResult.id}`)
      console.log(`   总分: ${insertResult.overall_score}`)
      console.log(`   AI模型: ${insertResult.ai_model}`)
      
      // 清理测试数据
      await supabase
        .from('qc_results')
        .delete()
        .eq('id', insertResult.id)
      
      console.log('🧹 测试数据已清理')
    }
    
  } catch (error) {
    console.error('❌ 测试过程异常:', error)
  }
}

testQCTable()
  .then(() => {
    console.log('\n🎉 QC表结构测试完成')
    process.exit(0)
  })
  .catch(error => {
    console.error('❌ 测试过程异常:', error)
    process.exit(1)
  }) 