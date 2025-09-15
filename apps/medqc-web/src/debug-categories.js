// Debug script to test document category loading
// Run this in browser console or as a separate script

import { DocumentCategoryService } from './services/document-category-service'

async function debugCategories() {
  try {
    console.log('=== 调试文书类别加载 ===')
    
    // 1. 测试直接API调用
    console.log('1. 直接调用 getDocumentCategories():')
    const categories = await DocumentCategoryService.getDocumentCategories()
    console.log('返回的类别数量:', categories.length)
    console.log('类别详情:', categories)
    
    // 2. 测试显示配置
    console.log('2. 测试显示配置:')
    categories.forEach(cat => {
      const displayConfig = DocumentCategoryService.getDocumentCategoryDisplayConfig(cat.category_code)
      console.log(`${cat.category_code}: ${cat.category_name} -> 显示配置:`, displayConfig)
    })
    
    // 3. 测试质控规则加载
    console.log('3. 测试质控规则加载:')
    const rules = await DocumentCategoryService.getEnhancedQCRules({ page: 1, pageSize: 10 })
    console.log('规则数量:', rules.data.length)
    console.log('前5个规则的文书类别:', rules.data.slice(0, 5).map(r => ({
      code: r.rule_code,
      primary: r.primary_document_category,
      categories: r.document_categories
    })))
    
  } catch (error) {
    console.error('调试过程中出错:', error)
  }
}

// 如果在浏览器环境中，自动执行
if (typeof window !== 'undefined') {
  debugCategories()
}

export { debugCategories }
