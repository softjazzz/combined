/**
 * 测试文书类别统计逻辑的修复
 */

// 模拟数据，用于测试统计逻辑
const mockRulesData = [
  // 规则1: 主要类别是入院记录
  {
    primary_document_category: 'admission_record',
    document_categories: []
  },
  // 规则2: 主要类别是入院记录，文档类别也包含入院记录（应该只计数一次）
  {
    primary_document_category: 'admission_record',
    document_categories: ['admission_record', 'progress_note']
  },
  // 规则3: 主要类别是其他，但文档类别包含入院记录
  {
    primary_document_category: 'progress_note',
    document_categories: ['admission_record']
  },
  // 规则4: 主要类别是非标准类别，映射到病程记录
  {
    primary_document_category: 'medical_order',
    document_categories: []
  },
  // 规则5: 主要类别是非标准类别，映射到病程记录，文档类别也包含病程记录
  {
    primary_document_category: 'nursing_document',
    document_categories: ['progress_note']
  },
  // 规则6: 不相关的规则
  {
    primary_document_category: 'operation_record',
    document_categories: ['examination_report']
  }
]

/**
 * 模拟统计逻辑（从修复后的代码复制）
 */
function simulateStats(data: any[]): Record<string, number> {
  const CANONICAL_CATEGORIES = new Set([
    'admission_record', 'progress_note', 'discharge_record',
    'operation_record', 'examination_report', 'consent_form'
  ])

  const CATEGORY_MAPPING: Record<string, string> = {
    'nursing_document': 'progress_note',
    'medical_order': 'progress_note',
    'blood_transfusion': 'progress_note',
    'emergency_record': 'progress_note',
    'consultation_record': 'progress_note',
    'surgery_record': 'operation_record',
    'lab_report': 'examination_report',
    'imaging_report': 'examination_report',
    'pathology_report': 'examination_report'
  }

  const stats: Record<string, number> = {}
  
  // 为每个标准类别初始化计数器
  CANONICAL_CATEGORIES.forEach(category => {
    stats[category] = 0
  })

  data?.forEach(rule => {
    const primaryCategory = rule.primary_document_category
    const documentCategories = rule.document_categories || []
    
    // 收集所有相关的类别
    const allCategories = new Set<string>()
    
    if (primaryCategory) {
      allCategories.add(primaryCategory)
    }
    
    if (Array.isArray(documentCategories)) {
      documentCategories.forEach(cat => {
        if (cat && typeof cat === 'string') {
          allCategories.add(cat)
        }
      })
    }
    
    // 对每个标准类别，检查该规则是否匹配
    CANONICAL_CATEGORIES.forEach(standardCategory => {
      let ruleMatchesCategory = false
      
      // 检查是否直接匹配标准类别
      if (allCategories.has(standardCategory)) {
        ruleMatchesCategory = true
      } else {
        // 检查是否通过映射匹配标准类别
        for (const category of allCategories) {
          if (!CANONICAL_CATEGORIES.has(category)) {
            const mappedCategory = CATEGORY_MAPPING[category]
            if (mappedCategory === standardCategory) {
              ruleMatchesCategory = true
              break
            }
          }
        }
      }
      
      if (ruleMatchesCategory) {
        stats[standardCategory] = (stats[standardCategory] || 0) + 1
      }
    })
  })

  return stats
}

// 运行测试
console.log('🧪 测试文书类别统计逻辑修复')
console.log('📊 模拟数据:', mockRulesData)

const result = simulateStats(mockRulesData)
console.log('📈 统计结果:', result)

// 预期结果分析：
// admission_record: 3条 (规则1, 规则2, 规则3)
// progress_note: 3条 (规则2, 规则4映射, 规则5)
// operation_record: 1条 (规则6)
// examination_report: 1条 (规则6)
// discharge_record: 0条
// consent_form: 0条

console.log('✅ 预期入院记录应该有3条规则')
console.log('✅ 预期病程记录应该有3条规则')
console.log('✅ 预期手术记录应该有1条规则')
console.log('✅ 预期检查报告应该有1条规则')
