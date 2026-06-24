// 测试前端统计API函数
import { createClient } from '@supabase/supabase-js'

const supabaseUrl = 'https://mjjejcjhglbhfhxjxnqk.supabase.co'
const supabaseKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1qamVqY2poZ2xiaGZoeGp4bnFrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzY4NjIzMjIsImV4cCI6MjA1MjQzODMyMn0.qd8lsj4P5VvvJRnUhQwlXQOOkWPOQJfOQfJEYuVlhYw'

const supabase = createClient(supabaseUrl, supabaseKey)

// 模拟前端API函数：获取QC评分分布
async function getQCScoreDistribution() {
  try {
    console.log('🔍 获取QC评分分布...')
    
    const { data: records, error } = await supabase
      .from('medical_records')
      .select('qc_score')
      .not('qc_score', 'is', null)

    if (error) {
      console.error('❌ 数据库查询失败:', error)
      throw error
    }

    console.log(`✅ 成功获取 ${records.length} 条评分记录`)

    // 计算评分分布
    const scoreRanges = [
      { range: '90-100分', min: 90, max: 100 },
      { range: '80-89分', min: 80, max: 89 },
      { range: '70-79分', min: 70, max: 79 },
      { range: '60-69分', min: 60, max: 69 },
      { range: '60分以下', min: 0, max: 59 }
    ]

    const total = records.length
    const distribution = []

    scoreRanges.forEach(range => {
      const count = records.filter(r => 
        r.qc_score >= range.min && r.qc_score <= range.max
      ).length
      
      distribution.push({
        scoreRange: range.range,
        count,
        percentage: total > 0 ? Math.round((count / total) * 100 * 10) / 10 : 0
      })
    })

    console.log('📊 评分分布统计:')
    distribution.forEach(item => {
      console.log(`  ${item.scoreRange}: ${item.count}条 (${item.percentage}%)`)
    })

    return distribution

  } catch (error) {
    console.error('❌ 获取评分分布失败:', error)
    throw error
  }
}

// 模拟前端API函数：获取统计概览
async function getStatisticsOverview() {
  try {
    console.log('\n🔍 获取统计概览...')
    
    const { data: records, error } = await supabase
      .from('medical_records')
      .select('qc_score, status, department')

    if (error) {
      console.error('❌ 数据库查询失败:', error)
      throw error
    }

    const totalRecords = records.length
    const completedRecords = records.filter(r => r.status === 'completed').length
    const avgScore = records.filter(r => r.qc_score)
      .reduce((sum, r) => sum + r.qc_score, 0) / records.filter(r => r.qc_score).length

    const overview = {
      totalRecords,
      completedRecords,
      avgScore: Math.round(avgScore * 10) / 10,
      completionRate: Math.round((completedRecords / totalRecords) * 100 * 10) / 10
    }

    console.log('📈 统计概览:')
    console.log(`  总记录数: ${overview.totalRecords}`)
    console.log(`  已完成: ${overview.completedRecords}`)
    console.log(`  平均分: ${overview.avgScore}`)
    console.log(`  完成率: ${overview.completionRate}%`)

    return overview

  } catch (error) {
    console.error('❌ 获取统计概览失败:', error)
    throw error
  }
}

// 运行测试
async function runTests() {
  console.log('🚀 开始测试前端统计API函数...\n')
  
  try {
    // 测试1: 统计概览
    await getStatisticsOverview()
    
    // 测试2: 评分分布
    await getQCScoreDistribution()
    
    console.log('\n✅ 所有测试通过！前端统计API函数工作正常。')
    
  } catch (error) {
    console.error('\n❌ 测试失败:', error)
    process.exit(1)
  }
}

runTests() 