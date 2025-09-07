import { config } from 'dotenv'
import { createClient } from '@supabase/supabase-js'

// 加载环境变量
config()

const supabaseUrl = process.env.VITE_SUPABASE_URL
const supabaseKey = process.env.VITE_SUPABASE_ANON_KEY

console.log('🧪 测试Edge Function质控分析...\n')

async function testEdgeFunction() {
  try {
    const supabase = createClient(supabaseUrl, supabaseKey)
    
    console.log('📋 准备测试病历内容...')
    
    const testContent = `
入院记录

患者：张三，男，45岁
主诉：胸闷气短3天
现病史：患者3天前无明显诱因出现胸闷气短，活动后加重，伴有轻微咳嗽，无发热、胸痛等症状。
既往史：高血压病史5年，规律服用降压药物。
体格检查：T 36.5℃，P 88次/分，R 20次/分，BP 140/90mmHg
心肺听诊：心率齐，无杂音，双肺呼吸音粗，无干湿啰音。
辅助检查：
- 心电图：窦性心律，ST段轻度下移
- 胸部X线：双肺纹理增粗，心影增大
- 血常规：白细胞 6.5×10^9/L，血红蛋白 135g/L
- 生化：肌酐 85μmol/L，尿素氮 6.2mmol/L
诊断：
1. 心力衰竭（心功能II级）
2. 高血压病3级
治疗方案：
1. 利尿剂：呋塞米 40mg bid
2. ACEI：依那普利 10mg bid
3. β受体阻滞剂：美托洛尔 25mg bid
4. 低盐饮食，限制水分摄入
医师签名：李医生
日期：2024年1月15日
    `.trim()
    
    console.log('🚀 调用Edge Function...')
    
    const { data, error } = await supabase.functions.invoke('qc-analysis', {
      body: {
        record_id: 'test-record-' + Date.now(),
        content: testContent,
        analysis_mode: 'comprehensive'
      }
    })
    
    if (error) {
      throw error
    }
    
    console.log('✅ Edge Function调用成功！')
    console.log('\n📊 分析结果:')
    console.log('='.repeat(50))
    
    if (data && data.success && data.data) {
      const result = data.data
      
      console.log(`📝 总体评分: ${result.summary.total_score}分`)
      console.log(`🏆 质控等级: ${result.summary.grade}`)
      console.log(`📋 总体评价: ${result.summary.overall_assessment}`)
      
      console.log('\n📊 各项评分:')
      result.item_scores.forEach(item => {
        console.log(`  ${item.item_name}: ${item.actual_score}/${item.total_score}分 (扣分: ${item.deduction}分)`)
      })
      
      console.log('\n⚠️  发现问题:')
      result.issues.forEach((issue, index) => {
        console.log(`  ${index + 1}. [${issue.severity}] ${issue.description}`)
        console.log(`     建议: ${issue.suggestion}`)
      })
      
      console.log('\n✨ 优点:')
      result.strengths.forEach((strength, index) => {
        console.log(`  ${index + 1}. ${strength}`)
      })
      
      console.log('\n💡 改进建议:')
      result.recommendations.forEach((rec, index) => {
        console.log(`  ${index + 1}. ${rec}`)
      })
      
    } else {
      console.log('❌ 分析结果格式异常')
      console.log(JSON.stringify(data, null, 2))
    }
    
  } catch (error) {
    console.error('❌ Edge Function调用失败:', error.message)
    if (error.context) {
      console.error('详细信息:', error.context)
    }
  }
}

async function main() {
  console.log('配置信息:')
  console.log(`- Supabase URL: ${supabaseUrl}`)
  console.log(`- 测试时间: ${new Date().toLocaleString()}`)
  console.log()
  
  await testEdgeFunction()
  
  console.log('\n🎯 测试完成！')
}

main().catch(console.error) 