// LLM-Integrated Rules Service
// This service extends the basic rules service with LLM integration capabilities

import type {
  EnhancedQCRule,
  CreateEnhancedRuleRequest,
  EnhancedRuleFilter,
  BatchUpdateResult,
  ImportResult,
  RuleImportConfig,
} from '@/types/enhanced-qc-rule'

import type {
  LLMExecutionConfig,
  CompiledPromptTemplate,
  RuleTestResult,
  ConfigurationCache,
  RealTimeSyncManager,
} from '@/types/llm-integration'

import { supabase } from '@/lib/backend-store'

type ImportedRule = Partial<EnhancedQCRule> & { id: string; rule_code?: string }
type RpcRuleLike = {
  rule_implementation?: string
  alert_level?: string
  core_system_related?: boolean
  department_overrides?: Array<{ department_id?: string }>
}
type SupabaseErrorLike = {
  message?: unknown
  code?: unknown
}

const createConfigurationCache = (): ConfigurationCache => {
  const store = new Map<string, unknown>()

  return {
    get: (key: string) => store.get(key),
    set: (key: string, value: unknown) => {
      store.set(key, value)
    },
    invalidate: (key: string) => {
      store.delete(key)
    },
    invalidateRule: (ruleId: string) => {
      for (const key of store.keys()) {
        if (key.includes(ruleId)) {
          store.delete(key)
        }
      }
    },
    clear: () => {
      store.clear()
    },
  }
}

const createRealTimeSyncManager = (): RealTimeSyncManager => ({
  notifyRuleUpdate: (rule: EnhancedQCRule) => console.log('Rule updated:', rule.id),
  notifyRuleDelete: (ruleId: string) => console.log('Rule deleted:', ruleId),
  subscribeToUpdates: (_callback: (event: unknown) => void) => {
    console.log('Subscribed to rule updates')
  },
  unsubscribe: (_callback: (event: unknown) => void) => {
    console.log('Unsubscribed from rule updates')
  },
})

function getErrorMessage(error: unknown): string {
  if (typeof error === 'object' && error !== null && 'message' in error) {
    const message = (error as SupabaseErrorLike).message
    if (typeof message === 'string' && message.trim()) {
      return message
    }
  }

  return error instanceof Error ? error.message : String(error)
}

function getSupabaseErrorCode(error: unknown): string | undefined {
  if (typeof error === 'object' && error !== null && 'code' in error) {
    const code = (error as SupabaseErrorLike).code
    return typeof code === 'string' ? code : undefined
  }
  return undefined
}

// Base Enhanced Rules Service (to be extended)
class BaseEnhancedRulesService {
  async getEnhancedRules(filter?: EnhancedRuleFilter): Promise<EnhancedQCRule[]> {
    // Migration 006: 优先使用 RPC 函数获取规则
    if (filter?.document_type) {
      try {
        const { data, error } = await supabase.rpc('get_applicable_rules', {
          p_document_type: filter.document_type,
          p_is_active: true,
        })

        if (error) throw error

        // 应用其他筛选条件
        let rules: RpcRuleLike[] = (data || []) as RpcRuleLike[]

        if (filter?.implementation_type) {
          rules = rules.filter(
            (r: RpcRuleLike) => r.rule_implementation === filter.implementation_type,
          )
        }

        if (filter?.alert_level) {
          rules = rules.filter((r: RpcRuleLike) => r.alert_level === filter.alert_level)
        }

        if (filter?.core_system_only) {
          rules = rules.filter((r: RpcRuleLike) => r.core_system_related === true)
        }

        if (filter?.department_id) {
          rules = rules.filter((r: RpcRuleLike) =>
            r.department_overrides?.some((d) => d.department_id === filter.department_id),
          )
        }

        return rules.map((rule) => rule as EnhancedQCRule)
      } catch (error) {
        console.warn('RPC function not available, falling back to query:', error)
      }
    }

    // 回退方案：使用传统查询
    let query = supabase.from('qc_rules').select('*').eq('is_active', true)

    if (filter?.document_type) {
      query = query.or(
        `applicable_documents.cs.{${filter.document_type}},` +
          `applicable_documents.is.null,` +
          `applicable_documents.eq.{}`,
      )
    }

    if (filter?.implementation_type) {
      query = query.eq('rule_implementation', filter.implementation_type)
    }

    if (filter?.alert_level) {
      query = query.eq('alert_level', filter.alert_level)
    }

    if (filter?.core_system_only) {
      query = query.eq('core_system_related', true)
    }

    if (filter?.department_id) {
      query = query.contains('department_overrides', [{ department_id: filter.department_id }])
    }

    if (filter?.search) {
      query = query.or(
        `name.ilike.%${filter.search}%,description.ilike.%${filter.search}%,rule_code.ilike.%${filter.search}%`,
      )
    }

    if (filter?.ruleIds && filter.ruleIds.length > 0) {
      query = query.in('id', filter.ruleIds)
    }

    if (filter?.category) {
      query = query.eq('category', filter.category)
    }

    const { data, error } = await query.order('created_at', { ascending: false })

    if (error) {
      console.error('Error fetching enhanced rules:', error)
      throw new Error(`Failed to fetch rules: ${getErrorMessage(error)}`)
    }

    return (data ?? []) as EnhancedQCRule[]
  }

  async createEnhancedRule(ruleData: CreateEnhancedRuleRequest): Promise<EnhancedQCRule> {
    const { data, error } = await supabase
      .from('qc_rules')
      .insert([
        {
          ...ruleData,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          version: '1.0',
        },
      ])
      .select()
      .single()

    if (error) {
      console.error('Error creating enhanced rule:', error)
      throw new Error(`Failed to create rule: ${getErrorMessage(error)}`)
    }

    return data as EnhancedQCRule
  }

  async updateEnhancedRule(id: string, updates: Partial<EnhancedQCRule>): Promise<EnhancedQCRule> {
    const { data, error } = await supabase
      .from('qc_rules')
      .update({
        ...updates,
        updated_at: new Date().toISOString(),
      })
      .eq('id', id)
      .select()
      .single()

    if (error) {
      console.error('Error updating enhanced rule:', error)
      throw new Error(`Failed to update rule: ${getErrorMessage(error)}`)
    }

    return data as EnhancedQCRule
  }

  async deleteRule(id: string): Promise<void> {
    const { error } = await supabase.from('qc_rules').delete().eq('id', id)

    if (error) {
      console.error('Error deleting rule:', error)
      throw new Error(`Failed to delete rule: ${getErrorMessage(error)}`)
    }
  }

  async getRuleById(id: string): Promise<EnhancedQCRule | null> {
    const { data, error } = await supabase.from('qc_rules').select('*').eq('id', id).single()

    if (error) {
      if (getSupabaseErrorCode(error) === 'PGRST116') {
        return null // Rule not found
      }
      console.error('Error fetching rule by ID:', error)
      throw new Error(`Failed to fetch rule: ${getErrorMessage(error)}`)
    }

    return data as EnhancedQCRule
  }

  async batchUpdateRuleStatus(
    ruleIds: string[],
    isActive: boolean,
    reason?: string,
  ): Promise<BatchUpdateResult> {
    const { data, error } = await supabase.rpc('batch_update_rule_status', {
      rule_ids: ruleIds,
      new_status: isActive,
      reason: reason || `Batch ${isActive ? 'enable' : 'disable'} rules`,
      user_id: null, // Will be set by RLS
    })

    if (error) {
      console.error('Error in batch update:', error)
      throw new Error(`Batch update failed: ${getErrorMessage(error)}`)
    }

    const batchResult = (data ?? {}) as {
      success_count?: number
      error_count?: number
      errors?: string[]
    }

    return {
      successCount: batchResult.success_count || 0,
      errorCount: batchResult.error_count || 0,
      errors: batchResult.errors || [],
      updatedRules: ruleIds,
    }
  }

  async exportRulesConfig(ruleIds: string[]): Promise<unknown> {
    const rules = await this.getEnhancedRules({ ruleIds })

    return {
      exportedAt: new Date().toISOString(),
      version: '1.0',
      rules: rules,
      metadata: {
        totalRules: rules.length,
        exportedBy: 'system', // Will be enhanced with user info
      },
    }
  }

  async importRulesConfig(configData: unknown, options: RuleImportConfig): Promise<ImportResult> {
    const result: ImportResult = {
      importedCount: 0,
      skippedCount: 0,
      errorCount: 0,
      errors: [],
      warnings: [],
    }

    if (
      typeof configData !== 'object' ||
      configData === null ||
      !('rules' in configData) ||
      !Array.isArray((configData as { rules: unknown[] }).rules)
    ) {
      throw new Error('Invalid configuration data: missing rules array')
    }

    const importRules = (configData as { rules: unknown[] }).rules.filter(
      (item): item is ImportedRule =>
        typeof item === 'object' &&
        item !== null &&
        typeof (item as { id?: unknown }).id === 'string',
    )

    for (const ruleData of importRules) {
      try {
        // Check if rule already exists
        const existingRule = await this.getRuleById(ruleData.id)

        if (existingRule) {
          switch (options.conflictResolution) {
            case 'skip':
              result.skippedCount++
              continue
            case 'overwrite':
              await this.updateEnhancedRule(ruleData.id, ruleData)
              result.importedCount++
              break
            case 'merge': {
              // Implement merge logic
              const mergedData = { ...existingRule, ...ruleData }
              await this.updateEnhancedRule(ruleData.id, mergedData)
              result.importedCount++
              break
            }
          }
        } else {
          await this.createEnhancedRule(ruleData as CreateEnhancedRuleRequest)
          result.importedCount++
        }
      } catch (error) {
        result.errorCount++
        result.errors.push(`Rule ${ruleData.rule_code ?? ruleData.id}: ${getErrorMessage(error)}`)
      }
    }

    return result
  }
}

// LLM-Integrated Rules Service
export class LLMIntegratedRulesService extends BaseEnhancedRulesService {
  private configurationCache: ConfigurationCache
  private realTimeSync: RealTimeSyncManager

  constructor() {
    super()
    this.configurationCache = createConfigurationCache()
    this.realTimeSync = createRealTimeSyncManager()
  }

  async updateEnhancedRule(id: string, updates: Partial<EnhancedQCRule>): Promise<EnhancedQCRule> {
    // 1. Update rule configuration
    const updatedRule = await super.updateEnhancedRule(id, updates)

    // 2. Real-time sync to LLM execution engine
    await this.syncRuleToLLMEngine(updatedRule)

    // 3. Clear related cache
    this.configurationCache.invalidateRule?.(id)

    // 4. Notify real-time sync manager
    this.realTimeSync.notifyRuleUpdate(updatedRule)

    return updatedRule
  }

  private async syncRuleToLLMEngine(rule: EnhancedQCRule): Promise<void> {
    try {
      // 1. Generate new LLM execution configuration
      const llmConfig = this.mapRuleToLLMExecution(rule)

      // 2. Pre-compile prompt template
      const promptTemplate = await this.precompilePromptTemplate(rule)

      // 3. Validate configuration
      await this.validateLLMConfiguration(llmConfig, promptTemplate)

      // 4. Store configuration for execution engine
      await this.storeLLMConfiguration(rule.id, {
        llmConfig,
        promptTemplate,
        lastUpdated: new Date().toISOString(),
      })

      console.log(`Rule ${rule.id} synchronized to LLM engine successfully`)
    } catch (error: unknown) {
      console.error(`Failed to sync rule ${rule.id} to LLM engine:`, error)
      throw new Error(`规则同步失败: ${getErrorMessage(error)}`)
    }
  }

  private mapRuleToLLMExecution(rule: EnhancedQCRule): LLMExecutionConfig {
    // Map rule categories to LLM execution configurations
    const categoryMappings = {
      completeness: {
        llmCapability: 'structural_analysis',
        promptTemplate: 'completeness_check',
        batchable: true,
        complexity: 'low' as const,
      },
      duplication: {
        llmCapability: 'semantic_similarity',
        promptTemplate: 'duplication_analysis',
        batchable: true,
        complexity: 'medium' as const,
      },
      consistency: {
        llmCapability: 'logical_reasoning',
        promptTemplate: 'consistency_analysis',
        batchable: false,
        complexity: 'high' as const,
      },
      multi_source: {
        llmCapability: 'cross_modal_analysis',
        promptTemplate: 'multi_source_analysis',
        batchable: false,
        complexity: 'high' as const,
      },
      authenticity: {
        llmCapability: 'medical_reasoning',
        promptTemplate: 'authenticity_analysis',
        batchable: false,
        complexity: 'very_high' as const,
      },
      treatment_analysis: {
        llmCapability: 'clinical_reasoning',
        promptTemplate: 'treatment_analysis',
        batchable: false,
        complexity: 'very_high' as const,
      },
      diagnosis: {
        llmCapability: 'diagnostic_reasoning',
        promptTemplate: 'diagnosis_analysis',
        batchable: false,
        complexity: 'very_high' as const,
      },
      specialty_logic: {
        llmCapability: 'specialty_reasoning',
        promptTemplate: 'specialty_analysis',
        batchable: false,
        complexity: 'very_high' as const,
      },
      writing_alerts: {
        llmCapability: 'predictive_analysis',
        promptTemplate: 'alert_generation',
        batchable: true,
        complexity: 'medium' as const,
      },
    }

    const baseMapping = categoryMappings[rule.category] || categoryMappings['completeness']

    return {
      ruleId: rule.id,
      ruleCode: rule.rule_code,
      llmCapability: baseMapping.llmCapability,
      promptTemplate: baseMapping.promptTemplate,
      batchable: baseMapping.batchable,
      complexity: baseMapping.complexity,

      llmParameters: {
        temperature: this.mapAlertLevelToTemperature(rule.alert_level),
        maxTokens: this.mapComplexityToTokens(baseMapping.complexity),
        systemMessage: this.generateSystemMessage(rule),
        responseFormat: 'json',
      },

      executionConfig: {
        requiresSpecialtyKnowledge: rule.core_system_related,
        departmentSpecific: rule.department_overrides?.length > 0,
        multiModal: rule.applicable_documents.length > 1,
        priority: this.mapSeverityToPriority(rule.severity),
      },
    }
  }

  private mapAlertLevelToTemperature(alertLevel: string): number {
    const temperatureMap: Record<string, number> = {
      critical: 0.05, // Extremely low temperature for consistency
      major: 0.1, // Low temperature for accuracy
      minor: 0.15, // Slightly higher for flexibility
    }
    return temperatureMap[alertLevel] || 0.1
  }

  private mapComplexityToTokens(complexity: string): number {
    const tokenMap: Record<string, number> = {
      low: 1000,
      medium: 2000,
      high: 4000,
      very_high: 6000,
    }
    return tokenMap[complexity] || 2000
  }

  private generateSystemMessage(rule: EnhancedQCRule): string {
    const baseMessage = `你是一位资深的医疗质控专家，具有丰富的临床经验和质控管理经验。`

    const specialtyMessage = rule.core_system_related
      ? `你正在执行核心医疗制度相关的质控检查，请严格按照国家卫健委的相关规范进行分析。`
      : `请基于医疗质控标准进行专业分析。`

    const implementationMessage = this.getImplementationMessage(rule.rule_implementation)

    return `${baseMessage}\n${specialtyMessage}\n${implementationMessage}`
  }

  private getImplementationMessage(implementation: string): string {
    const messages: Record<string, string> = {
      semantic_llm: '请重点进行语义分析和医学逻辑推理，深入理解医疗内容的含义和关联性。',
      logical_program: '请按照结构化的检查标准进行分析，重点关注格式规范和必填项完整性。',
      hybrid_analysis: '请结合结构化检查和语义分析，进行全面的质控评估。',
    }
    return messages[implementation] || messages['hybrid_analysis']
  }

  private mapSeverityToPriority(severity: string): number {
    const priorityMap: Record<string, number> = {
      critical: 10,
      major: 7,
      minor: 4,
    }
    return priorityMap[severity] || 5
  }

  private async precompilePromptTemplate(rule: EnhancedQCRule): Promise<CompiledPromptTemplate> {
    // This would integrate with the DynamicPromptGenerator
    // For now, return a mock compiled template
    return {
      ruleId: rule.id,
      template: {
        systemMessage: this.generateSystemMessage(rule),
        userPrompt: `请分析以下医疗文书是否符合规则"${rule.name}"的要求...`,
        parameters: {
          temperature: this.mapAlertLevelToTemperature(rule.alert_level),
          maxTokens: 2000,
          responseFormat: 'json',
        },
      },
      compiledAt: new Date().toISOString(),
      isValid: true,
    }
  }

  private async validateLLMConfiguration(
    llmConfig: LLMExecutionConfig,
    promptTemplate: CompiledPromptTemplate,
  ): Promise<void> {
    if (!promptTemplate.isValid) {
      throw new Error(`提示模板编译失败: ${promptTemplate.error}`)
    }

    // Validate LLM parameters
    if (llmConfig.llmParameters.temperature < 0 || llmConfig.llmParameters.temperature > 1) {
      throw new Error('Temperature参数必须在0-1之间')
    }

    if (llmConfig.llmParameters.maxTokens < 100 || llmConfig.llmParameters.maxTokens > 8000) {
      throw new Error('MaxTokens参数必须在100-8000之间')
    }
  }

  private async storeLLMConfiguration(ruleId: string, config: unknown): Promise<void> {
    // Store the LLM configuration for the execution engine
    // This could be in a separate table or cache
    console.log(`Storing LLM config for rule ${ruleId}:`, config)
  }

  // Test rule configuration
  async testRuleConfiguration(ruleId: string): Promise<RuleTestResult> {
    const rule = await this.getRuleById(ruleId)
    if (!rule) {
      throw new Error('规则不存在')
    }

    // Create test data based on rule type
    const testData = this.createTestData(rule)

    try {
      // This would integrate with the actual LLM execution engine
      const mockResult = {
        ruleId,
        ruleName: rule.name,
        ruleCode: rule.rule_code,
        isCompliant: Math.random() > 0.3, // Mock result
        score: Math.floor(Math.random() * 100),
        findings: [],
        confidence: Math.floor(Math.random() * 40) + 60,
        executionTime: Math.floor(Math.random() * 2000) + 500,
      }

      return {
        ruleId,
        isSuccessful: true,
        executionTime: mockResult.executionTime,
        result: mockResult,
        testData,
      }
    } catch (error: unknown) {
      return {
        ruleId,
        isSuccessful: false,
        error: getErrorMessage(error),
        testData,
      }
    }
  }

  private createTestData(rule: EnhancedQCRule): Record<string, unknown> {
    // Create mock test data based on rule category and applicable documents
    return {
      patientId: 'test-patient-001',
      documents: rule.applicable_documents.map((docType) => ({
        id: `test-doc-${docType}`,
        type: docType,
        content: `测试${docType}内容...`,
        timestamp: new Date().toISOString(),
        status: 'completed',
      })),
      testType: 'configuration_validation',
      generatedAt: new Date().toISOString(),
    }
  }

  async checkSyncStatus(ruleId: string): Promise<{ isSynced: boolean; lastSyncTime?: string }> {
    // Check if rule is synchronized with LLM engine
    // This is a mock implementation
    return {
      isSynced: true,
      lastSyncTime: new Date().toISOString(),
    }
  }
}

// Export singleton instance
export const llmIntegratedRulesService = new LLMIntegratedRulesService()
