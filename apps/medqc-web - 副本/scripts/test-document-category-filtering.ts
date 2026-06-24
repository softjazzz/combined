#!/usr/bin/env node
/**
 * 测试质控演示功能中的文书类别与质控点关联筛选
 * 验证修复后的筛选逻辑是否正确工作
 */

import { lookupRuleCategories } from '../src/qc/ruleDocumentMapping'
import { DOCUMENT_TYPE_TO_CATEGORY } from '../src/utils/documentTypeUtils'

// 模拟测试数据
const mockRules = [
  {
    id: 'SC-004',
    name: '入院诊断应根据患者入院时情况综合分析，主次排列有序',
    description: '入院诊断应根据患者入院时情况综合分析，主次排列有序',
    category: 'completeness',
    severity: 'medium',
    primary_document_category: 'admission_record',
    document_categories: ['admission_record', 'progress_note', 'discharge_record']
  },
  {
    id: 'SC-015',
    name: '医嘱变化合理性分析',
    description: '医嘱变化应有合理的医学依据',
    category: 'rationality',
    severity: 'medium',
    primary_document_category: 'progress_note',
    document_categories: ['progress_note', 'discharge_record']
  },
  {
    id: 'SC-062',
    name: '值班诊疗活动记录',
    description: '值班期间的诊疗活动应有完整记录',
    category: 'completeness',
    severity: 'medium',
    primary_document_category: 'progress_note',
    document_categories: ['progress_note', 'operation_record']
  },
  {
    id: 'PATHOLOGY-001',
    name: '病理结果记录完整性',
    description: '病理检查结果应完整记录',
    category: 'completeness',
    severity: 'high',
    primary_document_category: 'examination_report',
    document_categories: ['examination_report']
  }
]

const mockDocuments = [
  {
    id: 'doc-1',
    title: '入院记录',
    type: 'admission_record',
    created_at: '2024-01-01'
  }
]

// 测试函数：模拟 QCRulesDemoPanel 中的筛选逻辑
function testDocumentCategoryFiltering() {
  console.log('🧪 测试质控演示功能中的文书类别筛选逻辑\n')

  // 1. 获取选中文书对应的标准类别代码
  const selectedDocTypeCodes = mockDocuments.map(d => {
    const typeCode = d.type || ''
    const cat = (DOCUMENT_TYPE_TO_CATEGORY as any)[typeCode]
    let mapped = cat as string | undefined
    if (!mapped) {
      const s = (typeCode || '').toLowerCase()
      if (s.includes('admission')) mapped = 'admission_record'
      else if (s.includes('discharge')) mapped = 'discharge_record'
      else if (s.includes('operation') || s.includes('surgery')) mapped = 'operation_record'
      else if (s.includes('imaging') || s.includes('lab') || s.includes('examination')) mapped = 'examination_report'
      else mapped = 'progress_note'
    }
    return mapped
  }).filter(Boolean)

  console.log('📄 选中的文书类别代码:', selectedDocTypeCodes)

  // 2. 筛选适用的规则
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

  const rulesWithApplicability = mockRules.map((r: any) => {
    // 使用与组件相同的逻辑
    const mapped = lookupRuleCategories(r)
    const raw: string[] = mapped.length > 0 ? mapped : (r.document_categories || [])
    const norm = raw.map(normalize).filter((x): x is string => !!x)
    
    let applicable = false
    if (codes.size === 1) {
      const [only] = Array.from(codes)
      applicable = norm.length > 0 && norm.some(d => codes.has(d))
      
      // 额外保护：若只选了入院记录，名称/描述命中手术相关关键词则不视为适用
      if (only === 'admission_record') {
        const text = `${r.name || ''} ${r.description || ''}`
        if (/手术|术前|术后|术中|麻醉|植入|出入量|出院|死亡/.test(text)) {
          applicable = false
        }
      }
    } else {
      applicable = norm.some(d => codes.has(d))
    }
    
    return { ...r, _applicable: applicable, _disabled: !applicable, _categories: norm }
  })

  // 3. 显示筛选结果
  console.log('\n📋 规则筛选结果:')
  console.log('=' .repeat(80))
  
  rulesWithApplicability.forEach(rule => {
    const status = rule._applicable ? '✅ 适用' : '❌ 不适用'
    console.log(`${status} | ${rule.id} | ${rule.name}`)
    console.log(`     文书类别: [${rule._categories.join(', ')}]`)
    console.log(`     主要类别: ${rule.primary_document_category}`)
    console.log('')
  })

  // 4. 验证预期结果
  const applicableRules = rulesWithApplicability.filter(r => r._applicable)
  const nonApplicableRules = rulesWithApplicability.filter(r => !r._applicable)
  
  console.log('📊 筛选统计:')
  console.log(`   适用规则: ${applicableRules.length} 条`)
  console.log(`   不适用规则: ${nonApplicableRules.length} 条`)
  
  console.log('\n🎯 预期验证:')
  
  // 验证 SC-004 应该适用（入院记录相关）
  const sc004 = applicableRules.find(r => r.id === 'SC-004')
  if (sc004) {
    console.log('✅ SC-004 正确显示为适用（入院诊断相关）')
  } else {
    console.log('❌ SC-004 应该适用但被错误筛选掉了')
  }
  
  // 验证病理规则应该不适用
  const pathologyRule = nonApplicableRules.find(r => r.id === 'PATHOLOGY-001')
  if (pathologyRule) {
    console.log('✅ PATHOLOGY-001 正确被筛选掉（病理检查不适用于入院记录）')
  } else {
    console.log('❌ PATHOLOGY-001 应该被筛选掉但错误显示为适用')
  }
  
  // 验证医嘱变化规则应该不适用（主要是病程记录）
  const sc015 = nonApplicableRules.find(r => r.id === 'SC-015')
  if (sc015) {
    console.log('✅ SC-015 正确被筛选掉（医嘱变化主要适用于病程记录）')
  } else {
    console.log('❌ SC-015 应该被筛选掉但错误显示为适用')
  }

  console.log('\n🎉 测试完成！')
  
  return {
    total: mockRules.length,
    applicable: applicableRules.length,
    nonApplicable: nonApplicableRules.length,
    success: sc004 && pathologyRule && sc015
  }
}

// 运行测试
const result = testDocumentCategoryFiltering()
process.exit(result.success ? 0 : 1)
