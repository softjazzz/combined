/**
 * 文书类别服务
 * 管理文书类别配置和质控规则的文书类别映射
 */

import { supabase } from '@/lib/supabase'
import { DocumentCategory, DOCUMENT_CATEGORY_CONFIG } from '@/types/medical'
import { DocumentCategoryConfig, EnhancedQCRule, QCRuleFilterParams } from '@/types/quality-control'
import { lookupRuleCategories, normalizeCategories } from '@/qc/ruleDocumentMapping'

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
      const codes = (data || []).map((r: unknown) => r.category_code)
      const extras = Array.from(new Set(codes.filter((c: unknown) => !canonical.has(String(c)))))
      console.log('📚 从数据库加载到的文书类别 config count=', data?.length || 0,
        (data || []).map((r: unknown) => ({ code: r.category_code, name: r.category_name })))
      if (extras.length > 0) {
        console.warn('⚠️ 发现非标准文书类别(应当仅为6大类):', extras)
      }
    } catch {}

    return data || []
  }

  /**
   * 获取文书类别统计信息
   * 只返回6个标准类别的统计，将非标准类别映射到标准类别
   * 修复：与查询逻辑保持一致，同时检查 primary_document_category 和 document_categories
   */
  static async getDocumentCategoryStats(): Promise<Record<string, number>> {
    const { data, error } = await supabase
      .from('qc_rules')
      .select('primary_document_category, document_categories')

    if (error) {
      console.error('获取文书类别统计失败:', error)
      throw new Error(`获取文书类别统计失败: ${error.message}`)
    }

    // 定义6个标准类别
    const CANONICAL_CATEGORIES = new Set([
      'admission_record', 'progress_note', 'discharge_record',
      'operation_record', 'examination_report', 'consent_form'
    ])

    // 非标准类别到标准类别的映射
    const CATEGORY_MAPPING: Record<string, string> = {
      'nursing_document': 'progress_note',
      'medical_order': 'progress_note',
      'blood_transfusion': 'progress_note',
      'emergency_record': 'progress_note', // 映射到病程记录，但不会在UI中显示
      'consultation_record': 'progress_note',
      'surgery_record': 'operation_record',
      'lab_report': 'examination_report',
      'imaging_report': 'examination_report',
      'pathology_report': 'examination_report'
    }

    // 统计每个类别的规则数量，只保留标准类别
    const stats: Record<string, number> = {}

    // 为每个标准类别初始化计数器
    CANONICAL_CATEGORIES.forEach(category => {
      stats[category] = 0
    })

    data?.forEach(rule => {
      const primaryCategory = rule.primary_document_category
      const documentCategories = rule.document_categories || []

      // 收集所有相关的类别（与后端查询逻辑一致）
      const allCategories = new Set<string>()

      // 添加主要类别
      if (primaryCategory) {
        allCategories.add(primaryCategory)
      }

      // 添加文档类别数组中的类别
      if (Array.isArray(documentCategories)) {
        documentCategories.forEach(cat => {
          if (cat && typeof cat === 'string') {
            allCategories.add(cat)
          }
        })
      }

      // 对每个标准类别，检查该规则是否匹配（避免重复计数）
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

        // 如果匹配，则计数加1（每个规则对每个标准类别最多计数一次）
        if (ruleMatchesCategory) {
          stats[standardCategory] = (stats[standardCategory] || 0) + 1
        }
      })
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

    // 调试：检查原始数据结构
    console.log('🔍 [原始数据] 查询返回条数:', (data || []).length)
    if (data && data.length > 0) {
      const sample = data[0]
      console.log('🔍 [原始数据] 第一条记录字段:', {
        id: sample.id,
        rule_code: sample.rule_code,
        name: sample.name,
        primary_document_category: sample.primary_document_category,
        document_categories: sample.document_categories,
        字段类型: {
          primary: typeof sample.primary_document_category,
          categories: typeof sample.document_categories,
          categories_isArray: Array.isArray(sample.document_categories)
        }
      })
    }

    // 归一化：确保 document_categories 是数组；缺失时基于名称/描述做兜底推断，填充 primary/document_categories（仅内存，不改库）
    console.log('🔍 [DocumentCategoryService] 开始归一化处理，原始数据条数:', (data || []).length)

    const normalized: unknown[] = (data || []).map((r: unknown, index: number) => {
      const originalPrimary = r?.primary_document_category
      const originalCategories = r?.document_categories

      const categories = normalizeCategories(r?.document_categories)
      r.document_categories = categories

      const normalizedPrimary = normalizeCategories(
        r?.primary_document_category ? [r.primary_document_category] : []
      )
      let primary = normalizedPrimary[0] as DocumentCategory | undefined
      if (primary) {
        r.primary_document_category = primary
        ;(r as any)._resolved_primary_category = primary
      }

      if (!primary && categories.length > 0) {
        primary = categories[0] as DocumentCategory
        r.primary_document_category = primary
        ;(r as any)._resolved_primary_category = primary
      }

      if (!primary) {
        const inferred = lookupRuleCategories(r)
        if (inferred && inferred.length > 0) {
          primary = inferred[0] as DocumentCategory
          r.primary_document_category = primary
          const merged = new Set([...(categories || []), ...inferred])
          r.document_categories = Array.from(merged)
          ;(r as any)._resolved_primary_category = primary

          if (index < 5) {
            console.log(`🔧 [推断] 规则 ${r.rule_code || r.id}: "${r.name}" -> ${primary}`, {
              原始primary: originalPrimary,
              原始categories: originalCategories,
              推断结果: inferred,
              最终primary: primary,
              最终categories: r.document_categories
            })
          }
        }
      } else {
        const merged = new Set([...(categories || []), primary])
        if (merged.size !== (r.document_categories?.length || 0)) {
          r.document_categories = Array.from(merged)
        }
        ;(r as any)._resolved_primary_category = primary
      }

      return r
    })

    // 统计归一化结果
    const withPrimary = normalized.filter(r => r.primary_document_category).length
    const withCategories = normalized.filter(r => r.document_categories && r.document_categories.length > 0).length
    console.log('📊 [归一化统计]', {
      总数: normalized.length,
      有primary的: withPrimary,
      有categories的: withCategories,
      覆盖率: `${Math.round(withPrimary / normalized.length * 100)}%`
    })

    const debugSample = normalized.slice(0, 20).map((r: unknown) => ({
      rule_code: r.rule_code,
      name: r.name,
      primary: r.primary_document_category,
      categories: r.document_categories
    }))
    console.log('🧾 [归一化示例]', debugSample)

    const resolvedSummary = normalized.reduce<Record<string, number>>((acc, r: unknown) => {
      const key = r._resolved_primary_category || r.primary_document_category || '未解析'
      acc[key] = (acc[key] || 0) + 1
      return acc
    }, {})
    console.log('📈 [归一化类别分布]', resolvedSummary)

    const missingPrimary = normalized.filter(r => !r.primary_document_category)
    if (missingPrimary.length > 0) {
      console.warn('⚠️ [归一化] 仍有缺失 primary 的规则:', missingPrimary.map((r: unknown) => r.rule_code))
    }

    try {
      const canonical = new Set([
        'admission_record','progress_note','discharge_record','operation_record','examination_report','consent_form'
      ])
      const primaries = Array.from(new Set((normalized || []).map((r: unknown) => r.primary_document_category).filter(Boolean)))
      const nonCanonicalPrim = primaries.filter((c: unknown) => !canonical.has(String(c)))
      if (nonCanonicalPrim.length > 0) {
        console.warn('⚠️ 非标准 primary_document_category 值:', nonCanonicalPrim)
      }
      const sample = (normalized || []).slice(0, 200)
      const rawFromJson = Array.from(new Set(sample.flatMap((r: unknown) => {
        try {
          const arr = (r?.check_logic?.applicable_documents) || []
          return Array.isArray(arr) ? arr : []
        } catch { return [] }
      }).filter(Boolean)))
      const suspicious = rawFromJson.filter((v: unknown) => !canonical.has(String(v)))
      if (suspicious.length > 0) {
        console.warn('🔎 check_logic.applicable_documents 中的非标准值(示例):', suspicious.slice(0, 20))
      }
    } catch {}

    return {
      data: normalized || [],
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
    const config = DOCUMENT_CATEGORY_CONFIG[category]
    if (config) {
      return config
    }

    // 如果找不到配置，尝试映射到标准类别
    const categoryStr = String(category || '').toLowerCase()

    // 映射非标准类别到标准类别
    const mappings: Record<string, keyof typeof DOCUMENT_CATEGORY_CONFIG> = {
      'medical_order': 'progress_note',
      'nursing_document': 'progress_note',
      'blood_transfusion': 'progress_note',
      'emergency_record': 'progress_note', // 急诊记录映射到病程记录
      '输血记录': 'progress_note',
      '医嘱记录': 'progress_note',
      '护理记录': 'progress_note',
      '急诊记录': 'progress_note'
    }

    const mappedCategory = mappings[categoryStr]
    if (mappedCategory && DOCUMENT_CATEGORY_CONFIG[mappedCategory]) {
      return DOCUMENT_CATEGORY_CONFIG[mappedCategory]
    }

    // 最后的fallback - 返回"未分类"而不是英文代码
    return {
      label: '未分类',
      description: '未识别的文书类别',
      color: '#666666',
      icon: 'FileOutlined',
      sortOrder: 999
    }
  }

  /**
   * 获取所有文书类别的选项列表（用于下拉框等）
   * 注意：此方法仅返回硬编码的6个标准类别，不从数据库加载
   * 如需从数据库加载，请使用 getDocumentCategories() 方法
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
