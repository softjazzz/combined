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

// 简单的病历内容
const generateSimpleContent = (patientName: string, department: string) => {
  return `
【患者基本信息】
患者姓名：${patientName}
科室：${department}
入院时间：${new Date().toLocaleDateString()}

【主诉】
患者因相关症状就诊

【现病史】
患者病情描述...

【既往史】
无特殊既往史

【体格检查】
体格检查结果...

【辅助检查】
相关检查结果...

【诊断】
初步诊断...

【治疗方案】
治疗计划...
`.trim()
}

// 生成随机日期
function getRandomDate(daysAgo: number): string {
  const date = new Date()
  date.setDate(date.getDate() - Math.floor(Math.random() * daysAgo))
  return date.toISOString()
}

async function createSimpleTestData() {
  console.log('🚀 开始创建简化测试数据...\n')
  
  try {
    // 1. 清空现有数据
    console.log('1. 清空现有数据...')
    await supabase.from('medical_records').delete().neq('id', '00000000-0000-0000-0000-000000000000')
    console.log('✅ 现有数据已清空\n')
    
    // 2. 创建病案记录 (只使用确定存在的字段)
    console.log('2. 创建病案记录...')
    const recordsToCreate = []
    
    for (let i = 0; i < 20; i++) {
      const department = departments[Math.floor(Math.random() * departments.length)]
      const patientName = patientNames[Math.floor(Math.random() * patientNames.length)]
      const content = generateSimpleContent(patientName, department)
      const createdAt = getRandomDate(30)
      
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
    
    // 3. 为每条记录更新qc_score字段 (如果存在)
    console.log('3. 更新质控评分...')
    for (const record of records) {
      const score = Math.floor(Math.random() * 40) + 60 // 60-100分
      
      await supabase
        .from('medical_records')
        .update({ qc_score: score })
        .eq('id', record.id)
    }
    
    console.log('✅ 质控评分更新完成\n')
    
    console.log('🎉 简化测试数据创建完成！')
    console.log(`📊 统计信息:`)
    console.log(`- 病案记录: ${records.length} 条`)
    console.log(`- 涉及科室: ${departments.length} 个`)
    console.log(`- 时间范围: 最近30天内`)
    
  } catch (error) {
    console.error('❌ 创建测试数据失败:', error)
  }
}

// 运行脚本
createSimpleTestData().catch(console.error)

export { createSimpleTestData } 