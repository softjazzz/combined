import { createClient } from '@supabase/supabase-js'

const supabaseUrl = 'https://afsbjvihjfsngobccnjx.supabase.co'
const supabaseAnonKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFmc2JqdmloamZzbmdvYmNjbmp4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTIwNDE4NzQsImV4cCI6MjA2NzYxNzg3NH0.wA1Ho-pJrvPfF8k5npURDV8lL14nYdsImr8xJ5_Xvqg'

const supabase = createClient(supabaseUrl, supabaseAnonKey)

// 部门列表
const departments = [
  '内科', '外科', '妇产科', '儿科', '骨科', 
  '心内科', '神经内科', '呼吸内科', '消化内科', '肾内科',
  '普外科', '胸外科', '泌尿外科', '神经外科', '心外科'
]

// 患者姓名列表
const patientNames = [
  '张三', '李四', '王五', '赵六', '孙七', '周八', '吴九', '郑十',
  '陈明', '刘华', '杨强', '黄丽', '林峰', '何静', '罗勇', '高敏',
  '马超', '朱磊', '胡娟', '郭亮', '梁红', '宋涛', '唐婷', '韩军'
]

// 病历内容模板
const medicalRecordTemplates = [
  {
    chief_complaint: '胸痛3小时',
    present_illness: '患者3小时前无明显诱因出现胸痛，呈压榨性，伴出汗，无发热，无咳嗽咳痰。',
    past_history: '既往体健，否认高血压、糖尿病史。',
    diagnosis: '急性心肌梗死',
    treatment: '给予阿司匹林、氯吡格雷抗血小板，阿托伐他汀调脂，美托洛尔控制心率。'
  },
  {
    chief_complaint: '发热、咳嗽2天',
    present_illness: '患者2天前开始发热，体温最高38.5℃，伴咳嗽，咳少量白痰，无胸痛。',
    past_history: '既往有高血压病史5年，规律服用降压药。',
    diagnosis: '肺炎',
    treatment: '给予头孢曲松抗感染，对症支持治疗。'
  },
  {
    chief_complaint: '腹痛、腹泻1天',
    present_illness: '患者1天前进食不洁食物后出现腹痛、腹泻，大便呈水样，无发热。',
    past_history: '既往体健，无特殊病史。',
    diagnosis: '急性胃肠炎',
    treatment: '给予补液、止泻、调节肠道菌群治疗。'
  },
  {
    chief_complaint: '头痛、头晕3天',
    present_illness: '患者3天前开始头痛、头晕，呈持续性，伴恶心，无呕吐。',
    past_history: '既往有高血压病史10年，血压控制不佳。',
    diagnosis: '高血压脑病',
    treatment: '给予降压、脱水、营养神经治疗。'
  },
  {
    chief_complaint: '右下腹痛6小时',
    present_illness: '患者6小时前开始右下腹痛，呈持续性，伴恶心、呕吐，无发热。',
    past_history: '既往体健，无手术史。',
    diagnosis: '急性阑尾炎',
    treatment: '急诊阑尾切除术，术后给予抗感染治疗。'
  }
]

// 生成病历内容
function generateMedicalRecord(template: any, patientName: string, department: string): string {
  return `
【主诉】${template.chief_complaint}

【现病史】${template.present_illness}

【既往史】${template.past_history}

【体格检查】
一般情况：神志清楚，精神可，体温36.8℃，脉搏78次/分，呼吸18次/分，血压120/80mmHg。
专科检查：根据具体疾病进行相应检查。

【辅助检查】
血常规、生化全套、心电图等检查结果正常范围内。

【诊断】${template.diagnosis}

【治疗方案】${template.treatment}

【医嘱】
1. 一级护理
2. 普通饮食
3. 按医嘱用药
4. 观察病情变化

科室：${department}
患者：${patientName}
`.trim()
}

// 生成质控问题
function generateQCIssues(score: number) {
  const issues = []
  
  if (score < 90) {
    issues.push({
      category: '完整性',
      description: '病历记录不够完整',
      severity: 'medium'
    })
  }
  
  if (score < 80) {
    issues.push({
      category: '一致性',
      description: '诊断与治疗不够一致',
      severity: 'major'
    })
  }
  
  if (score < 70) {
    issues.push({
      category: '合理性',
      description: '用药剂量需要调整',
      severity: 'critical'
    })
  }
  
  return issues
}

// 修正generateQCSuggestions函数，返回数组而不是字符串
function generateQCSuggestions(score: number): string[] {
  const suggestions = []
  
  if (score < 90) {
    suggestions.push('补充完善病历记录')
  }
  
  if (score < 80) {
    suggestions.push('确保诊断与治疗方案一致')
  }
  
  if (score < 70) {
    suggestions.push('调整用药剂量和频次')
  }
  
  return suggestions.length > 0 ? suggestions : ['质量良好，无需改进']
}

// 生成随机日期
function getRandomDate(daysAgo: number): string {
  const date = new Date()
  date.setDate(date.getDate() - Math.floor(Math.random() * daysAgo))
  return date.toISOString()
}

// 生成随机评分
function getRandomScore(): number {
  const rand = Math.random()
  if (rand < 0.3) return Math.floor(Math.random() * 10) + 90 // 30% 高分
  if (rand < 0.7) return Math.floor(Math.random() * 10) + 80 // 40% 中等分
  return Math.floor(Math.random() * 20) + 60 // 30% 低分
}

async function createTestData() {
  console.log('🚀 开始创建测试数据...\n')
  
  try {
    // 1. 清空现有数据
    console.log('1. 清空现有数据...')
    await supabase.from('qc_results').delete().neq('id', '00000000-0000-0000-0000-000000000000')
    await supabase.from('medical_records').delete().neq('id', '00000000-0000-0000-0000-000000000000')
    console.log('✅ 现有数据已清空\n')
    
    // 2. 创建病案记录
    console.log('2. 创建病案记录...')
    const recordsToCreate = []
    
    for (let i = 0; i < 30; i++) {
      const department = departments[Math.floor(Math.random() * departments.length)]
      const patientName = patientNames[Math.floor(Math.random() * patientNames.length)]
      const template = medicalRecordTemplates[Math.floor(Math.random() * medicalRecordTemplates.length)]
      const content = generateMedicalRecord(template, patientName, department)
      const createdAt = getRandomDate(30) // 最近30天内
      
      recordsToCreate.push({
        patient_name: patientName,
        department,
        content,
        status: 'completed',
        created_at: createdAt,
        updated_at: createdAt
      })
    }
    
    const { data: records, error: recordsError } = await supabase
      .from('medical_records')
      .insert(recordsToCreate)
      .select()
    
    if (recordsError) {
      throw recordsError
    }
    
    console.log(`✅ 已创建 ${records.length} 条病案记录\n`)
    
    // 3. 创建质控结果
    console.log('3. 创建质控结果...')
    const qcResultsToCreate = []
    
    for (let i = 0; i < records.length; i++) {
      const record = records[i]
      const score = getRandomScore()
      const issues = generateQCIssues(score)
      const suggestions = generateQCSuggestions(score)
      
      qcResultsToCreate.push({
        record_id: record.id,
        score: score,
        issues: issues,
        suggestions: suggestions.join('; '), // 转换为字符串格式
        analysis_time: record.created_at
      })
    }
    
    const { data: qcResults, error: qcError } = await supabase
      .from('qc_results')
      .insert(qcResultsToCreate)
      .select()
    
    if (qcError) {
      throw qcError
    }
    
    console.log(`✅ 已创建 ${qcResults.length} 条质控结果\n`)
    
    // 4. 统计信息
    console.log('📊 测试数据统计:')
    console.log(`- 病案记录: ${records.length} 条`)
    console.log(`- 质控结果: ${qcResults.length} 条`)
    console.log(`- 涉及科室: ${departments.length} 个`)
    console.log(`- 时间范围: 最近30天`)
    
    // 按部门统计
    const departmentStats = {}
    records.forEach(record => {
      if (!departmentStats[record.department]) {
        departmentStats[record.department] = 0
      }
      departmentStats[record.department]++
    })
    
    console.log('\n📈 部门分布:')
    Object.entries(departmentStats).forEach(([dept, count]) => {
      console.log(`- ${dept}: ${count} 条`)
    })
    
    // 评分分布
    const scoreRanges = {
      '90-100分': 0,
      '80-89分': 0,
      '70-79分': 0,
      '60-69分': 0,
      '60分以下': 0
    }
    
    qcResults.forEach(result => {
      const score = result.score
      if (score >= 90) scoreRanges['90-100分']++
      else if (score >= 80) scoreRanges['80-89分']++
      else if (score >= 70) scoreRanges['70-79分']++
      else if (score >= 60) scoreRanges['60-69分']++
      else scoreRanges['60分以下']++
    })
    
    console.log('\n📊 评分分布:')
    Object.entries(scoreRanges).forEach(([range, count]) => {
      console.log(`- ${range}: ${count} 条`)
    })
    
    console.log('\n🎉 测试数据创建完成！')
    console.log('现在可以在系统中查看病案记录和质控结果了。')
    
  } catch (error) {
    console.error('❌ 创建测试数据失败:', error)
    throw error
  }
}

// 运行脚本
createTestData().catch(console.error)

export { createTestData } 