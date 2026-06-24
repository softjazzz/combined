/**
 * 测试质控演示功能的文书类别筛选逻辑
 * 验证选择"入院记录"时是否只显示相关的质控点
 */

import { lookupRuleCategories } from '../src/qc/ruleDocumentMapping'

// 模拟从 API 获取的规则数据
const mockRules = [
  {
    id: 'sc-004',
    name: '诊断与临床表现符合性',
    description: '入院诊断应根据患者入院时情况综合分析，主次排列有序',
    applicable_documents: ['admission_record', 'discharge_record', 'progress_note']
  },
  {
    id: 'sc-046',
    name: '病理结果记录完整性',
    description: '取材情况和病理结果应在相应记录中有记录',
    applicable_documents: ['examination_report']
  },
  {
    id: 'sc-015',
    name: '医嘱变化合理性分析',
    description: '病程中对治疗措施、药物、医嘱变化应有记录和分析',
    applicable_documents: ['progress_note']
  },
  {
    id: 'sc-062',
    name: '值班诊疗活动记录',
    description: '值班期间所有诊疗活动必须及时记入病历',
    applicable_documents: ['discharge_record']
  }
]

// 模拟文书类别映射
const DOCUMENT_TYPE_TO_CATEGORY = {
  'admission_record': 'admission_record',
  'progress_note': 'progress_note',
  'discharge_record': 'discharge_record',
  'operation_record': 'operation_record',
  'examination_report': 'examination_report',
  'consent_form': 'consent_form'
}

// 模拟选择的文书类别代码
const selectedDocTypeCodes = ['admission_record']

function testRuleFiltering() {
  console.log('🧪 测试质控演示功能的文书类别筛选逻辑')
  console.log('📋 选择的文书类别:', selectedDocTypeCodes)
  console.log('')

  const codes = new Set(selectedDocTypeCodes)
  
  const labelToCode: Record<string, string> = {
    '入院记录': 'admission_record',
    '病程记录': 'progress_note',
    '出院记录': 'discharge_record',
    '手术相关记录': 'operation_record',
    '手术记录': 'operation_record',
    '辅助检查': 'examination_report',
    '检查记录': 'examination_report',
    '知情同意书': 'consent_form'
  }

  const normalize = (d: string): string | undefined => {
    if (!d) return undefined
    const s = String(d).trim()
    if (['admission_record','progress_note','discharge_record','operation_record','examination_report','consent_form'].includes(s)) return s
    return labelToCode[s]
  }

  console.log('📊 规则筛选结果:')
  console.log('')

  mockRules.forEach((rule, index) => {
    // 获取规则的文书类别
    const mapped = lookupRuleCategories(rule)
    const raw: string[] = mapped.length > 0 ? mapped : (rule.applicable_documents || [])
    const norm = raw.map(normalize).filter((x): x is string => !!x)
    
    let applicable = false
    if (codes.size === 1) {
      const [only] = Array.from(codes)
      // 修正：规则的文书类别列表中包含选中的类别即为适用
      applicable = norm.length > 0 && norm.some(d => codes.has(d))
      // 额外保护：若只选了入院记录，名称/描述命中手术相关关键词则不视为适用
      if (only === 'admission_record') {
        const text = `${rule.name || ''} ${rule.description || ''}`
        if (/手术|术前|术后|术中|麻醉|植入|出入量|出院|死亡/.test(text)) {
          applicable = false
        }
      }
    } else {
      applicable = norm.some(d => codes.has(d))
    }

    const status = applicable ? '✅ 适用' : '❌ 不适用'
    const reason = applicable ? '匹配入院记录类别' : '不匹配入院记录类别'
    
    console.log(`${index + 1}. ${rule.name}`)
    console.log(`   状态: ${status}`)
    console.log(`   原始文书类别: ${JSON.stringify(rule.applicable_documents)}`)
    console.log(`   标准化后: ${JSON.stringify(norm)}`)
    console.log(`   原因: ${reason}`)
    console.log('')
  })

  // 统计结果
  const applicableRules = mockRules.filter((rule) => {
    const mapped = lookupRuleCategories(rule)
    const raw: string[] = mapped.length > 0 ? mapped : (rule.applicable_documents || [])
    const norm = raw.map(normalize).filter((x): x is string => !!x)
    
    if (codes.size === 1) {
      const [only] = Array.from(codes)
      let applicable = norm.length > 0 && norm.some(d => codes.has(d))
      if (only === 'admission_record') {
        const text = `${rule.name || ''} ${rule.description || ''}`
        if (/手术|术前|术后|术中|麻醉|植入|出入量|出院|死亡/.test(text)) {
          applicable = false
        }
      }
      return applicable
    } else {
      return norm.some(d => codes.has(d))
    }
  })

  console.log('📈 筛选统计:')
  console.log(`   总规则数: ${mockRules.length}`)
  console.log(`   适用规则数: ${applicableRules.length}`)
  console.log(`   适用规则: ${applicableRules.map(r => r.name).join(', ')}`)
  
  // 验证期望结果
  const expectedApplicableRules = ['诊断与临床表现符合性'] // 只有这个规则应该适用于入院记录
  const actualApplicableRules = applicableRules.map(r => r.name)
  
  console.log('')
  console.log('🎯 验证结果:')
  if (JSON.stringify(expectedApplicableRules.sort()) === JSON.stringify(actualApplicableRules.sort())) {
    console.log('✅ 测试通过！筛选逻辑正确工作')
  } else {
    console.log('❌ 测试失败！筛选逻辑有问题')
    console.log(`   期望: ${JSON.stringify(expectedApplicableRules)}`)
    console.log(`   实际: ${JSON.stringify(actualApplicableRules)}`)
  }
}

// 运行测试
testRuleFiltering()
