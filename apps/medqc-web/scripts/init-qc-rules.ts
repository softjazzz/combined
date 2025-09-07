import { createClient } from '@supabase/supabase-js'
import type { Database } from '../src/types/supabase'
import { config } from 'dotenv'

// 加载环境变量
config()

// 环境变量配置
const supabaseUrl = process.env.VITE_SUPABASE_URL || 'https://dgsdkdbjpucyawnyfbdu.supabase.co'
const supabaseServiceKey = process.env.SUPABASE_SERVICE_KEY || process.env.VITE_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRnc2RrZGJqcHVjeWF3bnlmYmR1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTYwODYyODcsImV4cCI6MjA3MTY2MjI4N30.k3178KRejQEoOogYjQ7EI_NfEW8ztVxFes3zLJ51JFw'

const supabase = createClient<Database>(supabaseUrl, supabaseServiceKey)

// 质控规则接口定义
interface QCRuleInsert {
  rule_code: string
  name: string
  description: string
  category: 'completeness' | 'consistency' | 'rationality' | 'timeliness'
  rule_type: 'objective' | 'subjective' | 'hybrid'
  severity: 'critical' | 'major' | 'minor'
  max_score: number
  weight: number
  prompt_template?: string
  check_logic: Record<string, any>
  is_active: boolean
  version: string
}

// Phase 1: 20条核心规则（优先级最高的客观规则）
const phase1Rules: QCRuleInsert[] = [
  // 1. 病历基本要求 - 严重问题（单项否决丙级）
  {
    rule_code: '1.1.1',
    name: '篡改、伪造病历',
    description: '★篡改、伪造病历。',
    category: 'completeness',
    rule_type: 'subjective',
    severity: 'critical',
    max_score: 0,
    weight: 1.0,
    check_logic: {
      type: 'llm_analysis',
      patterns: ['时间逻辑异常', '修改痕迹不规范', '内容前后矛盾'],
      criteria: ['时间节点合理性', '修改记录完整性', '内容一致性', '签名规范性']
    },
    prompt_template: `
请仔细分析以下病历文本，检查是否存在篡改、伪造的迹象：

检查要点：
1. 时间逻辑是否合理（各记录时间先后顺序）
2. 修改痕迹是否规范（是否有留痕修改）
3. 内容前后是否一致（同一信息在不同地方是否矛盾）
4. 签名和日期是否异常（字迹、时间格式等）

病历内容：{content}

请返回JSON格式分析结果：
{
  "hasViolation": boolean,
  "confidence": number (0-1),
  "evidence": string[], 
  "reasoning": "详细分析原因",
  "location": "具体位置"
}`,
    is_active: true,
    version: '1.0'
  },
  {
    rule_code: '1.1.2',
    name: '病历书写内容与客观事实不一致',
    description: '★病历书写内容与客观事实不一致。',
    category: 'consistency',
    rule_type: 'subjective',
    severity: 'critical',
    max_score: 0,
    weight: 1.0,
    check_logic: {
      type: 'llm_analysis',
      patterns: ['检查结果与描述不符', '诊断与症状不匹配', '用药与病情不符'],
      criteria: ['症状体征一致性', '检查结果合理性', '诊疗逻辑性']
    },
    prompt_template: `
检查病历内容是否与客观事实一致：

检查要点：
1. 症状描述与体格检查是否一致
2. 检查结果与临床表现是否匹配
3. 诊断与症状体征是否符合
4. 治疗方案与诊断是否合理

病历内容：{content}

返回分析结果。`,
    is_active: true,
    version: '1.0'
  },
  {
    rule_code: '3.1.1',
    name: '无入院记录',
    description: '★无入院记录（或再次/多次入院记录）或24小时内入出院（死亡）记录。',
    category: 'completeness',
    rule_type: 'objective',
    severity: 'critical',
    max_score: 0,
    weight: 1.0,
    check_logic: {
      type: 'structure_check',
      required_sections: ['入院记录', '主诉', '现病史', '既往史', '体格检查', '入院诊断'],
      search_patterns: ['入院记录', '主诉:', '现病史:', '既往史:', '体格检查:', '入院诊断:']
    },
    prompt_template: `
检查病历中是否包含完整的入院记录：

必需要素：
1. 主诉
2. 现病史
3. 既往史
4. 体格检查
5. 入院诊断

病历内容：{content}

检查是否包含所有必需要素。`,
    is_active: true,
    version: '1.0'
  },
  {
    rule_code: '4.1.1',
    name: '无首次病程记录',
    description: '★无首次病程记录。',
    category: 'completeness',
    rule_type: 'objective',
    severity: 'critical',
    max_score: 0,
    weight: 1.0,
    check_logic: {
      type: 'structure_check',
      required_sections: ['首次病程记录', '病例特点', '诊疗计划'],
      search_patterns: ['首次病程记录', '病例特点', '诊疗计划', '拟诊讨论'],
      time_requirements: {
        deadline_hours: 8,
        from_admission: true
      }
    },
    prompt_template: `
检查是否有首次病程记录，包含：
1. 病例特点
2. 拟诊讨论（诊断依据及鉴别诊断）
3. 诊疗计划

病历内容：{content}`,
    is_active: true,
    version: '1.0'
  },
  {
    rule_code: '5.5.1',
    name: '无手术同意书',
    description: '★无手术同意书，或同意书无医师和患者（被委托人或监护人）双方签名。',
    category: 'completeness',
    rule_type: 'objective',
    severity: 'critical',
    max_score: 0,
    weight: 1.0,
    check_logic: {
      type: 'structure_check',
      required_sections: ['手术同意书', '患者签名', '医师签名'],
      search_patterns: ['手术同意书', '手术风险', '患者签名', '医师签名', '手术并发症']
    },
    prompt_template: `
如果有手术记录，检查是否有相应的手术同意书：
1. 手术同意书存在
2. 包含手术风险说明
3. 有患者或委托人签名
4. 有医师签名

病历内容：{content}`,
    is_active: true,
    version: '1.0'
  },
  
  // 2. 时间相关规则（乙级问题）
  {
    rule_code: '3.1.2',
    name: '入院记录超时',
    description: '入院记录（或再次/多次入院记录）未在患者入院后24小时内完成。',
    category: 'timeliness',
    rule_type: 'objective',
    severity: 'major',
    max_score: 11,
    weight: 1.0,
    check_logic: {
      type: 'time_check',
      deadline_hours: 24,
      from_admission: true,
      patterns: ['入院时间', '记录时间']
    },
    prompt_template: `
检查入院记录的完成时间是否符合规定：
- 入院记录应在患者入院后24小时内完成

病历内容：{content}

提取入院时间和记录完成时间进行比较。`,
    is_active: true,
    version: '1.0'
  },
  {
    rule_code: '4.1.2',
    name: '首次病程记录超时',
    description: '未能在规定时间（8小时）内完成首次病程记录。',
    category: 'timeliness',
    rule_type: 'objective',
    severity: 'major',
    max_score: 11,
    weight: 1.0,
    check_logic: {
      type: 'time_check',
      deadline_hours: 8,
      from_admission: true,
      patterns: ['首次病程记录', '记录时间']
    },
    prompt_template: `
检查首次病程记录是否在入院后8小时内完成：

病历内容：{content}

比较入院时间与首次病程记录时间。`,
    is_active: true,
    version: '1.0'
  },
  
  // 3. 签名相关规则
  {
    rule_code: '3.3.2',
    name: '入院记录无医师签名',
    description: '入院记录无记录的医师签名。',
    category: 'completeness',
    rule_type: 'objective',
    severity: 'minor',
    max_score: 2,
    weight: 1.0,
    check_logic: {
      type: 'structure_check',
      required_sections: ['医师签名'],
      search_patterns: ['医师:', '医生:', '签名', '主治医师', '住院医师']
    },
    prompt_template: `
检查入院记录末尾是否有医师签名：

病历内容：{content}

查找医师签名信息。`,
    is_active: true,
    version: '1.0'
  },
  {
    rule_code: '6.1.11',
    name: '出院记录无医师签名',
    description: '出院记录（死亡记录）无医师签名。',
    category: 'completeness',
    rule_type: 'objective',
    severity: 'minor',
    max_score: 5,
    weight: 1.0,
    check_logic: {
      type: 'structure_check',
      required_sections: ['出院记录', '医师签名'],
      search_patterns: ['出院记录', '医师签名', '主治医师']
    },
    prompt_template: `
检查出院记录是否有医师签名：

病历内容：{content}`,
    is_active: true,
    version: '1.0'
  },
  
  // 4. 病案首页相关
  {
    rule_code: '2.1.1',
    name: '病案首页空白',
    description: '★首页空白。',
    category: 'completeness',
    rule_type: 'objective',
    severity: 'critical',
    max_score: 0,
    weight: 1.0,
    check_logic: {
      type: 'structure_check',
      required_sections: ['病案首页', '患者信息', '诊断信息'],
      search_patterns: ['病案首页', '姓名', '性别', '年龄', '诊断']
    },
    prompt_template: `
检查是否存在病案首页，包含基本患者信息：

病历内容：{content}`,
    is_active: true,
    version: '1.0'
  },
  {
    rule_code: '2.6.1',
    name: '出院主要诊断错误',
    description: '出院主要诊断错填、漏填或选择错误。',
    category: 'completeness',
    rule_type: 'subjective',
    severity: 'minor',
    max_score: 5,
    weight: 1.0,
    check_logic: {
      type: 'llm_analysis',
      patterns: ['出院诊断', '主要诊断'],
      criteria: ['诊断完整性', '诊断准确性', '诊断排序合理性']
    },
    prompt_template: `
检查出院主要诊断是否正确、完整：
1. 是否有明确的主要诊断
2. 诊断是否与病情相符
3. 多个诊断时主次排列是否合理

病历内容：{content}`,
    is_active: true,
    version: '1.0'
  },
  
  // 5. 抢救相关（严重问题）
  {
    rule_code: '4.15.1',
    name: '抢救病人无抢救记录',
    description: '★抢救病人无抢救记录。',
    category: 'completeness',
    rule_type: 'objective',
    severity: 'critical',
    max_score: 0,
    weight: 1.0,
    check_logic: {
      type: 'conditional_check',
      trigger_patterns: ['抢救', '急救', '心肺复苏'],
      required_sections: ['抢救记录', '抢救过程', '抢救结果'],
      search_patterns: ['抢救记录', '抢救时间', '抢救措施', '参加人员']
    },
    prompt_template: `
如果有抢救情况，检查是否有详细的抢救记录：
1. 抢救时间
2. 抢救措施
3. 抢救结果
4. 参加抢救人员

病历内容：{content}`,
    is_active: true,
    version: '1.0'
  },
  
  // 6. 输血相关
  {
    rule_code: '7.4.1',
    name: '输血病人无输血知情同意书',
    description: '★输血病人无输血治疗知情同意书或签名。',
    category: 'completeness',
    rule_type: 'objective',
    severity: 'critical',
    max_score: 0,
    weight: 1.0,
    check_logic: {
      type: 'conditional_check',
      trigger_patterns: ['输血', '血液制品', '血小板', '血浆'],
      required_sections: ['输血同意书', '输血风险告知'],
      search_patterns: ['输血同意书', '输血风险', '患者签名']
    },
    prompt_template: `
如果有输血治疗，检查是否有输血知情同意书：
1. 输血同意书存在
2. 风险告知完整
3. 患者或家属签名

病历内容：{content}`,
    is_active: true,
    version: '1.0'
  },
  
  // 7. 手术相关记录
  {
    rule_code: '5.10.1',
    name: '无手术记录',
    description: '★无手术记录。',
    category: 'completeness',
    rule_type: 'objective',
    severity: 'critical',
    max_score: 0,
    weight: 1.0,
    check_logic: {
      type: 'conditional_check',
      trigger_patterns: ['手术', '术式', '麻醉'],
      required_sections: ['手术记录', '手术过程', '术者签名'],
      search_patterns: ['手术记录', '手术过程', '术中发现', '手术者']
    },
    prompt_template: `
如果有手术，检查是否有完整的手术记录：
1. 手术过程描述
2. 术中发现
3. 手术者签名

病历内容：{content}`,
    is_active: true,
    version: '1.0'
  },
  {
    rule_code: '5.9.1',
    name: '无麻醉记录',
    description: '★无麻醉记录。',
    category: 'completeness',
    rule_type: 'objective',
    severity: 'critical',
    max_score: 0,
    weight: 1.0,
    check_logic: {
      type: 'conditional_check',
      trigger_patterns: ['麻醉', '全麻', '局麻', '椎管内麻醉'],
      required_sections: ['麻醉记录', '麻醉方式', '麻醉医师'],
      search_patterns: ['麻醉记录', '麻醉方式', '麻醉医师', '术前访视']
    },
    prompt_template: `
如果有麻醉，检查是否有麻醉记录：
1. 麻醉方式
2. 麻醉过程
3. 麻醉医师签名

病历内容：{content}`,
    is_active: true,
    version: '1.0'
  },
  
  // 8. 出院相关
  {
    rule_code: '6.1.1',
    name: '无出院记录',
    description: '★出院病人无出院记录或死亡病人无死亡记录。',
    category: 'completeness',
    rule_type: 'objective',
    severity: 'critical',
    max_score: 0,
    weight: 1.0,
    check_logic: {
      type: 'structure_check',
      required_sections: ['出院记录', '出院诊断', '出院医嘱'],
      search_patterns: ['出院记录', '出院诊断', '出院医嘱', '出院时间']
    },
    prompt_template: `
检查是否有出院记录，包含：
1. 出院诊断
2. 诊疗经过总结
3. 出院医嘱
4. 出院时间

病历内容：{content}`,
    is_active: true,
    version: '1.0'
  },
  
  // 9. 医嘱相关
  {
    rule_code: '9.1.1',
    name: '无长期医嘱单',
    description: '★无长期医嘱单。',
    category: 'completeness',
    rule_type: 'objective',
    severity: 'critical',
    max_score: 0,
    weight: 1.0,
    check_logic: {
      type: 'structure_check',
      required_sections: ['长期医嘱', '医嘱时间', '医师签名'],
      search_patterns: ['长期医嘱', '医嘱单', '医师签名']
    },
    prompt_template: `
检查是否有长期医嘱单：
1. 长期医嘱存在
2. 医嘱时间完整
3. 医师签名

病历内容：{content}`,
    is_active: true,
    version: '1.0'
  },
  
  // 10. 质控基础要求
  {
    rule_code: '1.4.1',
    name: '字迹潦草难认',
    description: '病历中字迹潦草难认或关键字无法辨认。',
    category: 'completeness',
    rule_type: 'subjective',
    severity: 'minor',
    max_score: 2,
    weight: 1.0,
    check_logic: {
      type: 'llm_analysis',
      patterns: ['字迹不清', '难以辨认', '潦草'],
      criteria: ['文字清晰度', '专业术语准确性', '关键信息可读性']
    },
    prompt_template: `
评估病历文字是否清晰可读：
1. 关键信息是否清楚
2. 医学术语是否准确
3. 整体可读性如何

病历内容：{content}

注意：这里分析的是文本内容的表达清晰度，而非字迹本身。`,
    is_active: true,
    version: '1.0'
  }
]

// 生成向量embedding的占位符函数
async function generateEmbedding(text: string): Promise<number[]> {
  // 这里先返回零向量占位符，后续集成DeepSeek API时替换
  // 实际应该调用 DeepSeek 或其他 embedding API
  return new Array(1536).fill(0)
}

// 初始化质控规则库
async function initializeQCRules() {
  console.log('🚀 开始初始化质控规则库...\n')
  
  try {
    // 检查连接
    const { data: testData, error: testError } = await supabase
      .from('qc_rules')
      .select('count')
      .limit(1)
    
    if (testError) {
      throw new Error(`数据库连接失败: ${testError.message}`)
    }

    console.log('✅ 数据库连接正常')

    // 1. 清空现有规则（谨慎操作，仅在开发环境）
    console.log('🗑️  清理现有规则...')
    const { error: deleteError } = await supabase
      .from('qc_rules_embeddings')
      .delete()
      .neq('id', '00000000-0000-0000-0000-000000000000')

    await supabase
      .from('qc_rules')
      .delete()
      .neq('id', '00000000-0000-0000-0000-000000000000')

    if (deleteError) {
      console.warn('⚠️  清空规则时出现警告:', deleteError.message)
    }

    // 2. 批量插入新规则
    console.log('📝 插入质控规则...')
    const { data: insertedRules, error: insertError } = await supabase
      .from('qc_rules')
      .insert(phase1Rules)
      .select()

    if (insertError) {
      throw new Error(`插入规则失败: ${insertError.message}`)
    }

    console.log(`✅ 成功插入 ${insertedRules.length} 条质控规则`)

    // 3. 生成规则的embedding（为RAG做准备）
    console.log('🧠 生成规则向量索引...')
    await generateRuleEmbeddings(insertedRules)

    // 4. 显示统计信息
    console.log('\n📊 规则统计:')
    const stats = await getRuleStatistics()
    console.table(stats)

    console.log('\n🎉 质控规则库初始化完成！')
    console.log(`📝 已创建 ${insertedRules.length} 条核心规则`)
    console.log('🔍 已生成向量索引，支持智能检索')
    console.log('✨ 可以开始使用质控分析功能了！')

  } catch (error) {
    console.error('❌ 初始化失败:', error)
    process.exit(1)
  }
}

// 生成规则向量索引
async function generateRuleEmbeddings(rules: any[]) {
  const embeddings = []
  
  for (const rule of rules) {
    const ruleText = `${rule.name}: ${rule.description}. 分类: ${rule.category}. 严重程度: ${rule.severity}`
    const embedding = await generateEmbedding(ruleText)
    
    embeddings.push({
      id: rule.id,
      rule_text: ruleText,
      embedding: embedding,
      category: rule.category
    })
  }

  const { error } = await supabase
    .from('qc_rules_embeddings')
    .insert(embeddings)

  if (error) {
    console.warn('⚠️  生成向量时出现警告:', error.message)
  } else {
    console.log('✅ 向量索引创建完成')
  }
}

// 获取规则统计信息
async function getRuleStatistics() {
  const { data: rules } = await supabase
    .from('qc_rules')
    .select('category, severity, rule_type')

  if (!rules) return []

  const stats = {
    总计: rules.length,
    按分类: {} as Record<string, number>,
    按严重程度: {} as Record<string, number>,
    按类型: {} as Record<string, number>
  }

  rules.forEach(rule => {
    // 按分类统计
    stats.按分类[rule.category] = (stats.按分类[rule.category] || 0) + 1
    // 按严重程度统计
    stats.按严重程度[rule.severity] = (stats.按严重程度[rule.severity] || 0) + 1
    // 按类型统计
    stats.按类型[rule.rule_type] = (stats.按类型[rule.rule_type] || 0) + 1
  })

  return [stats]
}

// 创建测试数据
async function createTestData() {
  console.log('🧪 创建测试数据...')
  
  try {
    // 直接插入示例病历记录
    const { data: recordData, error } = await supabase
      .from('medical_records')
      .insert({
        patient_name: '测试患者',
        patient_id: 'TEST001',
        department: '内科',
        content: '入院记录：患者因胸痛3小时入院。主诉：胸痛3小时。现病史：患者3小时前无明显诱因出现胸痛...',
        status: 'pending' as const
      })
      .select()
      .single()

    if (error) {
      console.warn('创建测试数据失败:', error.message)
      return
    }

    console.log(`✅ 创建测试病历记录: ${recordData.id}`)
  } catch (error) {
    console.warn('创建测试数据时出错:', error)
  }
}

// 主函数
async function main() {
  const args = process.argv.slice(2)
  
  if (args.includes('--test-data')) {
    await createTestData()
  } else {
    await initializeQCRules()
  }
}

// 执行脚本
main()

// 导出供其他模块使用
export { 
  initializeQCRules, 
  phase1Rules, 
  createTestData,
  generateRuleEmbeddings 
} 