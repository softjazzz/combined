import { supabase } from '@/lib/supabase'
import type { Database } from '@/types/supabase'

// 类型定义
type QCRule = Database['public']['Tables']['qc_rules']['Row']
type QCRuleInsert = Database['public']['Tables']['qc_rules']['Insert']
type QCRuleUpdate = Database['public']['Tables']['qc_rules']['Update']

export interface RuleFilter {
  category?: string
  severity?: string
  rule_type?: string
  is_active?: boolean
  search?: string
}

export interface RuleStatistics {
  total: number
  active: number
  inactive: number
  critical: number
  major: number
  minor: number
  categories: {
    completeness: number
    consistency: number
    rationality: number
    timeliness: number
  }
  types: {
    objective: number
    subjective: number
    hybrid: number
  }
}

export class RulesService {
  /**
   * 获取所有规则
   */
  static async getAllRules(): Promise<QCRule[]> {
    const { data, error } = await supabase
      .from('qc_rules')
      .select('*')
      .order('rule_code', { ascending: true })

    if (error) {
      throw new Error(`获取规则失败: ${error.message}`)
    }

    return data || []
  }

  /**
   * 根据条件筛选规则
   */
  static async getRulesWithFilter(filter: RuleFilter): Promise<QCRule[]> {
    let query = supabase.from('qc_rules').select('*')

    // 应用筛选条件
    if (filter.category) {
      query = query.eq('category', filter.category)
    }

    if (filter.severity) {
      query = query.eq('severity', filter.severity)
    }

    if (filter.rule_type) {
      query = query.eq('rule_type', filter.rule_type)
    }

    if (filter.is_active !== undefined) {
      query = query.eq('is_active', filter.is_active)
    }

    // 搜索功能
    if (filter.search) {
      query = query.or(
        `name.ilike.%${filter.search}%,description.ilike.%${filter.search}%,rule_code.ilike.%${filter.search}%`,
      )
    }

    query = query.order('rule_code', { ascending: true })

    const { data, error } = await query

    if (error) {
      throw new Error(`筛选规则失败: ${error.message}`)
    }

    return data || []
  }

  /**
   * 根据ID获取单个规则
   */
  static async getRuleById(id: string): Promise<QCRule | null> {
    const { data, error } = await supabase.from('qc_rules').select('*').eq('id', id).single()

    if (error) {
      if (error.code === 'PGRST116') {
        return null // 未找到记录
      }
      throw new Error(`获取规则失败: ${error.message}`)
    }

    return data
  }

  /**
   * 创建新规则
   */
  static async createRule(rule: QCRuleInsert): Promise<QCRule> {
    if (!rule.rule_code) {
      throw new Error('规则编码不能为空')
    }
    // 检查规则编码是否已存在
    const existingRule = await this.getRuleByCode(rule.rule_code)
    if (existingRule) {
      throw new Error(`规则编码 ${rule.rule_code} 已存在`)
    }

    const { data, error } = await supabase.from('qc_rules').insert([rule]).select().single()

    if (error) {
      throw new Error(`创建规则失败: ${error.message}`)
    }

    return data
  }

  /**
   * 更新规则
   */
  static async updateRule(id: string, updates: QCRuleUpdate): Promise<QCRule> {
    // 如果更新规则编码，检查是否与其他规则冲突
    if (updates.rule_code) {
      const existingRule = await this.getRuleByCode(updates.rule_code)
      if (existingRule && existingRule.id !== id) {
        throw new Error(`规则编码 ${updates.rule_code} 已被其他规则使用`)
      }
    }

    const { data, error } = await supabase
      .from('qc_rules')
      .update(updates)
      .eq('id', id)
      .select()
      .single()

    if (error) {
      throw new Error(`更新规则失败: ${error.message}`)
    }

    return data
  }

  /**
   * 删除规则
   */
  static async deleteRule(id: string): Promise<void> {
    // 检查规则是否被引用
    const { data: executions } = await supabase
      .from('qc_rule_executions')
      .select('id')
      .eq('rule_id', id)
      .limit(1)

    if (executions && executions.length > 0) {
      throw new Error('该规则已有执行记录，不能删除。建议停用规则。')
    }

    const { error } = await supabase.from('qc_rules').delete().eq('id', id)

    if (error) {
      throw new Error(`删除规则失败: ${error.message}`)
    }
  }

  /**
   * 批量删除规则
   */
  static async deleteRules(ids: string[]): Promise<void> {
    // 检查是否有规则被引用
    const { data: executions } = await supabase
      .from('qc_rule_executions')
      .select('rule_id')
      .in('rule_id', ids)

    if (executions && executions.length > 0) {
      const referencedIds = [...new Set(executions.map((e) => e.rule_id))]
      throw new Error(`规则 ${referencedIds.join(', ')} 已有执行记录，不能删除`)
    }

    const { error } = await supabase.from('qc_rules').delete().in('id', ids)

    if (error) {
      throw new Error(`批量删除规则失败: ${error.message}`)
    }
  }

  /**
   * 切换规则状态
   */
  static async toggleRuleStatus(id: string, isActive: boolean): Promise<QCRule> {
    return this.updateRule(id, { is_active: isActive })
  }

  /**
   * 批量更新规则状态
   */
  static async batchUpdateRuleStatus(ids: string[], isActive: boolean): Promise<void> {
    const { error } = await supabase.from('qc_rules').update({ is_active: isActive }).in('id', ids)

    if (error) {
      throw new Error(`批量更新规则状态失败: ${error.message}`)
    }
  }

  /**
   * 根据规则编码获取规则
   */
  static async getRuleByCode(ruleCode: string): Promise<QCRule | null> {
    const { data, error } = await supabase
      .from('qc_rules')
      .select('*')
      .eq('rule_code', ruleCode)
      .single()

    if (error) {
      if (error.code === 'PGRST116') {
        return null
      }
      throw new Error(`获取规则失败: ${error.message}`)
    }

    return data
  }

  /**
   * 获取规则统计信息
   */
  static async getRuleStatistics(): Promise<RuleStatistics> {
    const rules = await this.getAllRules()

    const stats: RuleStatistics = {
      total: rules.length,
      active: rules.filter((r) => r.is_active).length,
      inactive: rules.filter((r) => !r.is_active).length,
      critical: rules.filter((r) => r.severity === 'critical').length,
      major: rules.filter((r) => r.severity === 'major').length,
      minor: rules.filter((r) => r.severity === 'minor').length,
      categories: {
        completeness: rules.filter((r) => r.category === 'completeness').length,
        consistency: rules.filter((r) => r.category === 'consistency').length,
        rationality: rules.filter((r) => r.category === 'rationality').length,
        timeliness: rules.filter((r) => r.category === 'timeliness').length,
      },
      types: {
        objective: rules.filter((r) => r.rule_type === 'objective').length,
        subjective: rules.filter((r) => r.rule_type === 'subjective').length,
        hybrid: rules.filter((r) => r.rule_type === 'hybrid').length,
      },
    }

    return stats
  }

  /**
   * 获取激活的规则
   */
  static async getActiveRules(): Promise<QCRule[]> {
    return this.getRulesWithFilter({ is_active: true })
  }

  /**
   * 根据分类获取规则
   */
  static async getRulesByCategory(category: string): Promise<QCRule[]> {
    return this.getRulesWithFilter({ category })
  }

  /**
   * 根据严重程度获取规则
   */
  static async getRulesBySeverity(severity: string): Promise<QCRule[]> {
    return this.getRulesWithFilter({ severity })
  }

  /**
   * 验证规则配置
   */
  static validateRuleConfig(rule: QCRuleInsert | QCRuleUpdate): string[] {
    const errors: string[] = []

    // 规则编码格式验证
    if (rule.rule_code && !/^\d+(\.\d+)*$/.test(rule.rule_code)) {
      errors.push('规则编码格式不正确，应为数字和点的组合，如: 1.1.1')
    }

    // 名称长度验证
    if (rule.name && (rule.name.length < 2 || rule.name.length > 100)) {
      errors.push('规则名称长度应在2-100个字符之间')
    }

    // 描述长度验证
    if (rule.description && (rule.description.length < 10 || rule.description.length > 500)) {
      errors.push('规则描述长度应在10-500个字符之间')
    }

    // 分数范围验证
    if (rule.max_score !== undefined && (rule.max_score < 0 || rule.max_score > 100)) {
      errors.push('最大扣分应在0-100之间')
    }

    // 权重范围验证
    if (rule.weight !== undefined && (rule.weight < 0.1 || rule.weight > 5.0)) {
      errors.push('权重应在0.1-5.0之间')
    }

    return errors
  }

  /**
   * 导出规则配置
   */
  static async exportRules(format: 'json' | 'csv' = 'json'): Promise<string> {
    const rules = await this.getAllRules()

    if (format === 'json') {
      return JSON.stringify(rules, null, 2)
    } else {
      // CSV格式导出
      const headers = [
        '规则编码',
        '规则名称',
        '描述',
        '分类',
        '类型',
        '严重程度',
        '最大扣分',
        '权重',
        '状态',
        '版本',
      ]
      const csvRows = [headers.join(',')]

      rules.forEach((rule) => {
        const row = [
          rule.rule_code,
          `"${rule.name}"`,
          `"${rule.description}"`,
          rule.category,
          rule.rule_type,
          rule.severity,
          rule.max_score.toString(),
          rule.weight.toString(),
          rule.is_active ? '激活' : '停用',
          rule.version,
        ]
        csvRows.push(row.join(','))
      })

      return csvRows.join('\n')
    }
  }
}
