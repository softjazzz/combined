import { createClient } from '@supabase/supabase-js'

const supabaseUrl = 'https://mjjejcjhglbhfhxjxnqk.supabase.co'
const supabaseKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1qamVqY2poZ2xiaGZoeGp4bnFrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzY4NjIzMjIsImV4cCI6MjA1MjQzODMyMn0.qd8lsj4P5VvvJRnUhQwlXQOOkWPOQJfOQfJEYuVlhYw'

const supabase = createClient(supabaseUrl, supabaseKey)

async function testScoreDistribution() {
  try {
    console.log('测试评分分布API...')
    
    // 直接测试数据库查询（模拟前端API逻辑）
    const { data: records, error } = await supabase
      .from('medical_records')
      .select('qc_score')
      .not('qc_score', 'is', null)
    
    if (error) {
      console.log('❌ 数据库查询失败:', error)
      return
    }
    
    console.log('✅ 数据库查询成功，找到', records.length, '条记录')
    
    // 计算分布（模拟前端API逻辑）
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

    // 显示具体的评分数据
    console.log('\n评分详情:')
    records.slice(0, 10).forEach((record, index) => {
      console.log(`  记录${index + 1}: ${record.qc_score}分`)
    })
    
    if (records.length > 10) {
      console.log(`  ... 还有${records.length - 10}条记录`)
    }

    console.log('\n✅ 评分分布API逻辑测试成功！')
    
  } catch (error) {
    console.log('❌ 测试失败:', {
      message: error.message,
      details: error.stack,
      hint: error.hint || '',
      code: error.code || ''
    })
  }
}

testScoreDistribution().catch(error => {
  console.log('💥 测试异常:', {
    message: error.message,
    details: error.stack,
    hint: error.hint || '',
    code: error.code || ''
  })
})