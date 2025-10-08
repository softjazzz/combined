// Test script to verify document category standardization
// Run this in browser console to test the changes

console.log('=== 测试文书类别标准化 ===')

// Test 1: 测试推断逻辑
import { lookupRuleCategories } from './src/qc/ruleDocumentMapping.js'

const testRules = [
  { name: '输血记录完整性检查', description: '检查输血记录是否完整' },
  { name: '医嘱记录准确性', description: '检查医嘱记录的准确性' },
  { name: '急诊记录时效性', description: '检查急诊记录的时效性' },
  { name: '入院记录完整性', description: '检查入院记录完整性' }
]

console.log('1. 测试规则类别推断:')
testRules.forEach(rule => {
  const categories = lookupRuleCategories(rule)
  console.log(`规则: "${rule.name}" -> 类别: ${categories.join(', ')}`)
})

// Test 2: 测试文书类别服务
import { DocumentCategoryService } from './src/services/document-category-service.js'

console.log('\n2. 测试文书类别加载:')
DocumentCategoryService.getDocumentCategories()
  .then(categories => {
    console.log('从数据库加载的类别数量:', categories.length)
    categories.forEach(cat => {
      console.log(`- ${cat.category_code}: ${cat.category_name}`)
    })
    
    // 验证只有6个标准类别
    const canonical = new Set([
      'admission_record','progress_note','discharge_record',
      'operation_record','examination_report','consent_form'
    ])
    const nonCanonical = categories.filter(c => !canonical.has(c.category_code))
    if (nonCanonical.length > 0) {
      console.warn('⚠️ 发现非标准类别:', nonCanonical.map(c => c.category_code))
    } else {
      console.log('✅ 所有类别都是标准类别')
    }
  })
  .catch(error => {
    console.error('❌ 加载失败:', error.message)
  })

console.log('\n3. 测试硬编码选项:')
const options = DocumentCategoryService.getDocumentCategoryOptions()
console.log('硬编码选项数量:', options.length)
options.forEach(opt => {
  console.log(`- ${opt.value}: ${opt.label}`)
})

console.log('\n=== 测试完成 ===')
