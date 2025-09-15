/**
 * 文书类别服务
 * 管理文书类别配置和质控规则的文书类别映射
 */

import { supabase } from '@/lib/supabase'
import { DocumentCategory, DOCUMENT_CATEGORY_CONFIG } from '@/types/medical'
import { DocumentCategoryConfig, EnhancedQCRule, QCRuleFilterParams } from '@/types/quality-control'

export class DocumentCategoryService {
  /**
   * 获取所有文书类别配置
   */
  static async getDocumentCategories(): Promise<DocumentCategoryConfig[]> {
    const { data, error } = await supabase
      .from('document_category_config')
      .select('*')
      .eq('is_active', true)
      .order('sort_order')

    if (error) {
      console.error('获取文书类别配置失败:', error)
      throw new Error(`获取文书类别配置失败: ${error.message}`)
    }

    try {
      const canonical = new Set([
        'admission_record','progress_note','discharge_record','operation_record','examination_report','consent_form'
      ])
      const codes = (data || []).map((r: any) => r.category_code)
      const extras = Array.from(new Set(codes.filter((c: any) => !canonical.has(String(c)))))
      console.log('📚 从数据库加载到的文书类别 config count=', data?.length || 0,
        (data || []).map((r: any) => ({ code: r.category_code, name: r.category_name })))
      if (extras.length > 0) {
        console.warn('⚠️ 发现非标准文书类别(应当仅为6大类):', extras)
      }
    } catch {}

    return data || []
  }

  /**
   * 获取文书类别统计信息
   */
  static async getDocumentCategoryStats(): Promise<Record<string, number>> {
    const { data, error } = await supabase
      .from('qc_rules')
      .select('primary_document_category')
      .not('primary_document_category', 'is', null)

    if (error) {
      console.error('获取文书类别统计失败:', error)
      throw new Error(`获取文书类别统计失败: ${error.message}`)
    }

    // 统计每个类别的规则数量
    const stats: Record<string, number> = {}
    data?.forEach(rule => {
      const category = rule.primary_document_category
      if (category) {
        stats[category] = (stats[category] || 0) + 1
      }
    })

    return stats
  }

  /**
   * 根据文书类别获取质控规则
   */
  static async getQCRulesByDocumentCategory(
    documentCategory: DocumentCategory,
    options: {
      includeMultiCategory?: boolean // 是否包含适用于多个类别的规则
      activeOnly?: boolean
    } = {}
  ): Promise<EnhancedQCRule[]> {
    const { includeMultiCategory = true, activeOnly = true } = options

    let query = supabase
      .from('qc_rules')
      .select('*')

    if (includeMultiCategory) {
      // 包含主要类别是目标类别，或者文书类别数组包含目标类别的规则
      query = query.or(`primary_document_category.eq.${documentCategory},document_categories.cs.{${documentCategory}}`)
    } else {
      // 只包含主要类别是目标类别的规则
      query = query.eq('primary_document_category', documentCategory)
    }

    if (activeOnly) {
      query = query.eq('is_active', true)
    }

    query = query.order('execution_order').order('name')

    const { data, error } = await query

    if (error) {
      console.error('获取质控规则失败:', error)
      throw new Error(`获取质控规则失败: ${error.message}`)
    }

    return data || []
  }

  /**
   * 获取增强的质控规则列表（支持文书类别筛选）
   */
  static async getEnhancedQCRules(filters: QCRuleFilterParams = {}): Promise<{
    data: EnhancedQCRule[]
    total: number
  }> {
    const {
      keyword,
      category,
      document_category,
      rule_type,
      severity,
      is_active,
      page = 1,
      pageSize = 20
    } = filters

    let query = supabase
      .from('qc_rules')
      .select('*', { count: 'exact' })

    // 关键词搜索
    if (keyword) {
      query = query.or(`name.ilike.%${keyword}%,description.ilike.%${keyword}%,rule_code.ilike.%${keyword}%`)
    }

    // 规则分类筛选
    if (category) {
      query = query.eq('category', category)
    }

    // 文书类别筛选
    if (document_category) {
      query = query.or(`primary_document_category.eq.${document_category},document_categories.cs.{${document_category}}`)
    }

    // 规则类型筛选
    if (rule_type) {
      query = query.eq('rule_type', rule_type)
    }

    // 严重程度筛选
    if (severity) {
      query = query.eq('severity', severity)
    }

    // 激活状态筛选
    if (is_active !== undefined) {
      query = query.eq('is_active', is_active)
    }

    // 分页
    const from = (page - 1) * pageSize
    const to = from + pageSize - 1
    query = query.range(from, to)

    // 排序
    query = query.order('primary_document_category').order('execution_order').order('name')

    const { data, error, count } = await query

    if (error) {
      console.error('获取质控规则失败:', error)
      throw new Error(`获取质控规则失败: ${error.message}`)
    }

    try {
      const canonical = new Set([
        'admission_record','progress_note','discharge_record','operation_record','examination_report','consent_form'
      ])
      const primaries = Array.from(new Set((data || []).map((r: any) => r.primary_document_category).filter(Boolean)))
      const nonCanonicalPrim = primaries.filter((c: any) => !canonical.has(String(c)))
      if (nonCanonicalPrim.length > 0) {
        console.warn('⚠️ 非标准 primary_document_category 值:', nonCanonicalPrim)
      }
      const sample = (data || []).slice(0, 200)
      const rawFromJson = Array.from(new Set(sample.flatMap((r: any) => {
        try {
          const arr = (r?.check_logic?.applicable_documents) || []
          return Array.isArray(arr) ? arr : []
        } catch { return [] }
      }).filter(Boolean)))
      const suspicious = rawFromJson.filter((v: any) => !canonical.has(String(v)))
      if (suspicious.length > 0) {
        console.warn('🔎 check_logic.applicable_documents 中的非标准值(示例):', suspicious.slice(0, 20))
      }
    } catch {}

    return {
      data: data || [],
      total: count || 0
    }
  }

  /**
   * 更新规则的文书类别映射
   */
  static async updateRuleDocumentCategories(
    ruleId: string,
    documentCategories: DocumentCategory[],
    primaryCategory: DocumentCategory,
    targetSections: string[] = []
  ): Promise<void> {
    const { error } = await supabase
      .from('qc_rules')
      .update({
        document_categories: documentCategories,
        primary_document_category: primaryCategory,
        target_sections: targetSections,
        updated_at: new Date().toISOString()
      })
      .eq('id', ruleId)

    if (error) {
      console.error('更新规则文书类别失败:', error)
      throw new Error(`更新规则文书类别失败: ${error.message}`)
    }
  }

  /**
   * 获取文书类别的显示配置
   */
  static getDocumentCategoryDisplayConfig(category: DocumentCategory) {
    return DOCUMENT_CATEGORY_CONFIG[category] || {
      label: category,
      description: '',
      color: '#666666',
      icon: 'FileOutlined',
      sortOrder: 999
    }
  }

  /**
   * 获取所有文书类别的选项列表（用于下拉框等）
   */
  static getDocumentCategoryOptions() {
    return Object.entries(DOCUMENT_CATEGORY_CONFIG)
      .sort(([, a], [, b]) => a.sortOrder - b.sortOrder)
      .map(([value, config]) => ({
        value: value as DocumentCategory,
        label: config.label,
        description: config.description,
        color: config.color,
        icon: config.icon
      }))
  }

  /**
   * 批量更新规则的文书类别（用于数据迁移或批量操作）
   */
  static async batchUpdateRuleCategories(updates: Array<{
    ruleId: string
    documentCategories: DocumentCategory[]
    primaryCategory: DocumentCategory
    targetSections?: string[]
  }>): Promise<void> {
    const promises = updates.map(update =>
      this.updateRuleDocumentCategories(
        update.ruleId,
        update.documentCategories,
        update.primaryCategory,
        update.targetSections
      )
    )

    await Promise.all(promises)
  }
}
