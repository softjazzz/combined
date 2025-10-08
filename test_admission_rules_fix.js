/**
 * 测试入院记录质控规则修复
 */

// 模拟API返回的数据结构
const mockApiResponse = {
  "rules_by_document_type": {
    "admission_record": [
      {
        "rule_id": "70fd6ade-ceae-4208-97b7-7e73763acd6b",
        "name": "主诉与现病史一致性检查",
        "description": "主诉要突出病人主要症状+体征+持续时间，能导出第一诊断",
        "category": "consistency",
        "defect_level": "minor"
      },
      {
        "rule_id": "27b66a42-cd34-42d9-bf62-d1a729a13e42",
        "name": "既往史相关性检查",
        "description": "既往史应包含与当前疾病相关的既往疾病史、手术史等",
        "category": "completeness",
        "defect_level": "minor"
      }
    ],
    "progress_note": [
      {
        "rule_id": "275a305a-8d00-46c2-9285-cb4f05b99324",
        "name": "病情变化分析合理性",
        "description": "病程记录中对病情变化应有分析判断和具体处理意见",
        "category": "accuracy",
        "defect_level": "minor"
      }
    ]
  }
}

// 修复前的映射逻辑（有问题的版本）
function getApplicableRulesOld(categoryCode, rulesByDocumentType) {
  const categoryMapping = {
    'admission_record': '入院记录',
    'progress_note': '病程记录',
    'discharge_record': '出院记录',
    'operation_record': '手术相关记录',
    'examination_report': '辅助检查',
    'consent_form': '知情同意书'
  }
  
  const chineseName = categoryMapping[categoryCode]
  if (!chineseName) return []
  
  return rulesByDocumentType[chineseName] || []
}

// 修复后的映射逻辑（正确的版本）
function getApplicableRulesNew(categoryCode, rulesByDocumentType) {
  return rulesByDocumentType[categoryCode] || []
}

// 测试函数
function testRuleMapping() {
  console.log('🧪 测试入院记录质控规则映射修复\n')
  
  const rulesByDocumentType = mockApiResponse.rules_by_document_type
  const categoryCode = 'admission_record'
  
  console.log('📊 API返回的数据结构:')
  console.log('  - 键名:', Object.keys(rulesByDocumentType))
  console.log('  - admission_record规则数量:', rulesByDocumentType.admission_record?.length || 0)
  console.log('')
  
  console.log('❌ 修复前的结果:')
  const oldResult = getApplicableRulesOld(categoryCode, rulesByDocumentType)
  console.log('  - 找到的规则数量:', oldResult.length)
  console.log('  - 规则列表:', oldResult.map(r => r.name))
  console.log('')
  
  console.log('✅ 修复后的结果:')
  const newResult = getApplicableRulesNew(categoryCode, rulesByDocumentType)
  console.log('  - 找到的规则数量:', newResult.length)
  console.log('  - 规则列表:', newResult.map(r => r.name))
  console.log('')
  
  if (newResult.length > 0) {
    console.log('🎉 修复成功！现在可以正确获取入院记录的质控规则了')
    console.log('')
    console.log('📋 入院记录质控规则详情:')
    newResult.forEach((rule, index) => {
      console.log(`  ${index + 1}. ${rule.name}`)
      console.log(`     描述: ${rule.description}`)
      console.log(`     类别: ${rule.category}`)
      console.log(`     严重程度: ${rule.defect_level}`)
      console.log('')
    })
  } else {
    console.log('❌ 修复失败，仍然无法获取规则')
  }
}

// 运行测试
testRuleMapping()

// 导出测试函数（如果在Node.js环境中）
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { testRuleMapping }
}
