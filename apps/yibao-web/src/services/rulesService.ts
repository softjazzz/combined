import { supabase } from '@/lib/supabase'
import type {
  Rule,
  RuleQueryParams,
  RuleQueryResponse,
  RuleStatistics,
  CreateRuleRequest,
  UpdateRuleRequest,
  RuleTestRequest,
  RuleTestResult,
  RuleValidationResult,
  RuleExportData,
  RuleImportResult,
  ApiResponse
} from '@/types/rules'

/**
 * 规则管理服务
 */
export class RulesService {
  /**
   * 获取规则列表
   */
  async getRules(params: RuleQueryParams = {}): Promise<RuleQueryResponse> {
    const {
      page = 1,
      pageSize = 15,
      keyword,
      enabled,
      severity,
      rule_type,
      category_id,
      updated_after,
      updated_before,
      sort_by = 'updated_at',
      sort_order = 'desc'
    } = params

    const offset = (page - 1) * pageSize

    let query = supabase
      .from('yibao_rules')
      .select('*', { count: 'exact' })
      .range(offset, offset + pageSize - 1)
      .order(sort_by, { ascending: sort_order === 'asc' })

    // 应用筛选条件
    if (keyword) {
      query = query.or(`name.ilike.%${keyword}%,code.ilike.%${keyword}%,description.ilike.%${keyword}%`)
    }
    if (enabled !== undefined) {
      query = query.eq('enabled', enabled)
    }
    if (severity) {
      query = query.eq('severity', severity)
    }
    if (rule_type) {
      query = query.eq('rule_type', rule_type)
    }
    if (category_id) {
      query = query.eq('category_id', category_id)
    }
    if (updated_after) {
      query = query.gte('updated_at', updated_after)
    }
    if (updated_before) {
      query = query.lte('updated_at', updated_before)
    }

    const { data, count, error } = await query

    if (error) {
      throw new Error(`获取规则列表失败: ${error.message}`)
    }

    return {
      data: data || [],
      total: count || 0,
      page,
      pageSize
    }
  }

  /**
   * 获取规则详情
   */
  async getRuleById(id: number): Promise<Rule> {
    const { data, error } = await supabase
      .from('yibao_rules')
      .select('*')
      .eq('id', id)
      .single()

    if (error) {
      throw new Error(`获取规则详情失败: ${error.message}`)
    }

    return data
  }

  /**
   * 创建规则
   */
  async createRule(request: CreateRuleRequest): Promise<Rule> {
    const { rule, conditions, actions, triggers } = request

    // 开始事务
    const { data: ruleData, error: ruleError } = await supabase
      .from('yibao_rules')
      .insert({
        ...rule,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      })
      .select()
      .single()

    if (ruleError) {
      throw new Error(`创建规则失败: ${ruleError.message}`)
    }

    const ruleId = ruleData.id

    // 创建条件
    if (conditions.length > 0) {
      const { error: conditionsError } = await supabase
        .from('yibao_rule_conditions')
        .insert(conditions.map(condition => ({
          ...condition,
          rule_id: ruleId
        })))

      if (conditionsError) {
        throw new Error(`创建规则条件失败: ${conditionsError.message}`)
      }
    }

    // 创建动作
    if (actions.length > 0) {
      const { error: actionsError } = await supabase
        .from('yibao_rule_actions')
        .insert(actions.map(action => ({
          ...action,
          rule_id: ruleId
        })))

      if (actionsError) {
        throw new Error(`创建规则动作失败: ${actionsError.message}`)
      }
    }

    // 创建触发器
    if (triggers.length > 0) {
      const { error: triggersError } = await supabase
        .from('yibao_rule_triggers')
        .insert(triggers.map(trigger => ({
          ...trigger,
          rule_id: ruleId
        })))

      if (triggersError) {
        throw new Error(`创建规则触发器失败: ${triggersError.message}`)
      }
    }

    return ruleData
  }

  /**
   * 更新规则
   */
  async updateRule(request: UpdateRuleRequest): Promise<Rule> {
    const { rule, conditions, actions, triggers } = request
    const ruleId = rule.id

    // 更新规则基本信息
    const { data: ruleData, error: ruleError } = await supabase
      .from('yibao_rules')
      .update({
        ...rule,
        updated_at: new Date().toISOString()
      })
      .eq('id', ruleId)
      .select()
      .single()

    if (ruleError) {
      throw new Error(`更新规则失败: ${ruleError.message}`)
    }

    // 删除旧的条件、动作、触发器
    await Promise.all([
      supabase.from('yibao_rule_conditions').delete().eq('rule_id', ruleId),
      supabase.from('yibao_rule_actions').delete().eq('rule_id', ruleId),
      supabase.from('yibao_rule_triggers').delete().eq('rule_id', ruleId)
    ])

    // 重新创建条件、动作、触发器
    if (conditions.length > 0) {
      await supabase
        .from('yibao_rule_conditions')
        .insert(conditions.map(condition => ({
          ...condition,
          rule_id: ruleId
        })))
    }

    if (actions.length > 0) {
      await supabase
        .from('yibao_rule_actions')
        .insert(actions.map(action => ({
          ...action,
          rule_id: ruleId
        })))
    }

    if (triggers.length > 0) {
      await supabase
        .from('yibao_rule_triggers')
        .insert(triggers.map(trigger => ({
          ...trigger,
          rule_id: ruleId
        })))
    }

    return ruleData
  }

  /**
   * 删除规则
   */
  async deleteRule(id: number): Promise<void> {
    const { error } = await supabase
      .from('yibao_rules')
      .delete()
      .eq('id', id)

    if (error) {
      throw new Error(`删除规则失败: ${error.message}`)
    }
  }

  /**
   * 批量删除规则
   */
  async deleteRules(ids: number[]): Promise<void> {
    const { error } = await supabase
      .from('yibao_rules')
      .delete()
      .in('id', ids)

    if (error) {
      throw new Error(`批量删除规则失败: ${error.message}`)
    }
  }

  /**
   * 切换规则启用状态
   */
  async toggleRuleEnabled(id: number, enabled: boolean): Promise<Rule> {
    const { data, error } = await supabase
      .from('yibao_rules')
      .update({ 
        enabled,
        updated_at: new Date().toISOString()
      })
      .eq('id', id)
      .select()
      .single()

    if (error) {
      throw new Error(`切换规则状态失败: ${error.message}`)
    }

    return data
  }

  /**
   * 批量切换规则启用状态
   */
  async batchToggleRules(ids: number[], enabled: boolean): Promise<void> {
    const { error } = await supabase
      .from('yibao_rules')
      .update({ 
        enabled,
        updated_at: new Date().toISOString()
      })
      .in('id', ids)

    if (error) {
      throw new Error(`批量切换规则状态失败: ${error.message}`)
    }
  }

  /**
   * 获取规则统计信息
   */
  async getRuleStatistics(): Promise<RuleStatistics> {
    // 获取总数和启用数
    const [
      { count: total },
      { count: enabled },
      { data: severityData },
      { data: typeData },
      { data: categoryData }
    ] = await Promise.all([
      supabase.from('yibao_rules').select('id', { count: 'exact', head: true }),
      supabase.from('yibao_rules').select('id', { count: 'exact', head: true }).eq('enabled', true),
      supabase.from('yibao_rules').select('severity'),
      supabase.from('yibao_rules').select('rule_type'),
      supabase.from('yibao_rules').select('category_id')
    ])

    // 统计严重级别分布
    const bySeverity = { info: 0, warn: 0, block: 0 }
    severityData?.forEach(item => {
      if (item.severity in bySeverity) {
        bySeverity[item.severity as keyof typeof bySeverity]++
      }
    })

    // 统计类型分布
    const byType: Record<string, number> = {}
    typeData?.forEach(item => {
      if (item.rule_type) {
        byType[item.rule_type] = (byType[item.rule_type] || 0) + 1
      }
    })

    // 统计分类分布
    const byCategory: Record<string, number> = {}
    categoryData?.forEach(item => {
      if (item.category_id) {
        byCategory[item.category_id] = (byCategory[item.category_id] || 0) + 1
      }
    })

    return {
      total: total || 0,
      enabled: enabled || 0,
      disabled: (total || 0) - (enabled || 0),
      bySeverity,
      byType: byType as any,
      byCategory: byCategory as any
    }
  }

  /**
   * 验证规则配置
   */
  async validateRule(request: CreateRuleRequest | UpdateRuleRequest): Promise<RuleValidationResult> {
    const errors: string[] = []
    const warnings: string[] = []

    // 验证基本信息
    if (!request.rule.code) {
      errors.push('规则编码不能为空')
    }
    if (!request.rule.name) {
      errors.push('规则名称不能为空')
    }

    // 验证条件
    if (request.conditions.length === 0) {
      warnings.push('规则没有配置条件')
    }

    // 验证动作
    if (request.actions.length === 0) {
      errors.push('规则必须配置至少一个动作')
    }

    // 验证触发器
    if (request.triggers.length === 0) {
      errors.push('规则必须配置至少一个触发事件')
    }

    return {
      valid: errors.length === 0,
      errors,
      warnings
    }
  }

  /**
   * 测试规则
   */
  async testRule(request: RuleTestRequest): Promise<RuleTestResult> {
    // 这里应该调用规则引擎API进行测试
    // 目前返回模拟数据
    return {
      rule_id: request.rule_id,
      matched: true,
      severity: 'warn',
      action_type: 'warn',
      message: '测试规则执行成功',
      execution_time: 150,
      details: {
        conditions_matched: [true],
        triggered_actions: []
      }
    }
  }
}

// 导出单例实例
export const rulesService = new RulesService()
