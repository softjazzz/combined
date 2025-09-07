// Dynamic Prompt Generator
// This service generates LLM prompts dynamically based on rule configurations

import type { 
  EnhancedQCRule, 
  QCExecutionContext,
  QualityLogicConfig,
  ScoringConfig,
  DepartmentOverride
} from '@/types/enhanced-qc-rule'

import type {
  GeneratedPrompt,
  PromptTemplate,
  RuleContext,
  CompiledPromptTemplate,
  ValidationResult
} from '@/types/llm-integration'

// Prompt Template Library
class PromptTemplateLibrary {
  private templates: Map<string, PromptTemplate> = new Map()

  constructor() {
    this.initializeTemplates()
  }

  private initializeTemplates(): void {
    // Document Completeness Check Template (Rules 6-7)
    this.templates.set('completeness_check', {
      name: '文书完整性检查',
      systemMessage: `你是一位资深的医疗质控专家，专门负责医疗文书完整性检查。`,
      
      userPromptTemplate: `
请对以下医疗文书进行完整性检查：

文书类型：{{ruleInfo.category}}
检查规则：{{ruleInfo.name}}
规则描述：{{ruleInfo.description}}

待检查文书：
{{#each applicableDocuments}}
文书类型：{{this.type}}
创建时间：{{this.timestamp}}
内容：
{{this.content}}

{{/each}}

检查要求：
{{checkingCriteria}}

评分标准：
{{scoringGuidelines}}

{{#if departmentContext.hasOverrides}}
科室特殊要求：
{{departmentContext.specialRequirements}}
{{/if}}

请严格按照以下JSON格式返回检查结果：
{
  "ruleId": "{{ruleInfo.id}}",
  "isCompliant": boolean,
  "completenessScore": number, // 0-100
  "findings": [
    {
      "type": "missing_section|missing_content|format_error",
      "severity": "critical|major|minor",
      "description": "具体问题描述",
      "location": "问题位置",
      "evidence": "支持证据",
      "recommendation": "改进建议",
      "scoreDeduction": number
    }
  ],
  "overallAssessment": "整体评估",
  "confidence": number // 0-100
}
`,
      
      outputSchema: {
        type: 'object',
        required: ['ruleId', 'isCompliant', 'completenessScore', 'findings'],
        properties: {
          ruleId: { type: 'string' },
          isCompliant: { type: 'boolean' },
          completenessScore: { type: 'number', minimum: 0, maximum: 100 },
          findings: {
            type: 'array',
            items: {
              type: 'object',
              required: ['type', 'severity', 'description'],
              properties: {
                type: { type: 'string', enum: ['missing_section', 'missing_content', 'format_error'] },
                severity: { type: 'string', enum: ['critical', 'major', 'minor'] },
                description: { type: 'string' },
                location: { type: 'string' },
                evidence: { type: 'string' },
                recommendation: { type: 'string' },
                scoreDeduction: { type: 'number' }
              }
            }
          },
          overallAssessment: { type: 'string' },
          confidence: { type: 'number', minimum: 0, maximum: 100 }
        }
      },
      variables: [
        { name: 'ruleInfo', type: 'object', required: true, description: '规则基本信息' },
        { name: 'applicableDocuments', type: 'array', required: true, description: '适用文书列表' },
        { name: 'checkingCriteria', type: 'string', required: true, description: '检查标准' },
        { name: 'scoringGuidelines', type: 'string', required: true, description: '评分指导' }
      ]
    })

    // Duplication Detection Template (Rule 8)
    this.templates.set('duplication_analysis', {
      name: '重复内容检测',
      systemMessage: `你是一位医疗质控专家，专门负责检测病历文书中的重复内容。`,
      
      userPromptTemplate: `
请分析以下病历文书是否存在重复内容：

检查规则：{{ruleInfo.name}}
规则描述：{{ruleInfo.description}}

{{#each applicableDocuments}}
文书{{@index}}（{{this.type}}）：
创建时间：{{this.timestamp}}
内容：
{{this.content}}

{{/each}}

检查要求：
{{checkingCriteria}}

请重点检查：
1. 各文书各章节内容是否一致（如首次病程与现病史重复）
2. 不同文书间是否存在复制粘贴的重复内容
3. 同一患者不同时间点的文书是否过度重复

请严格按照以下JSON格式返回分析结果：
{
  "ruleId": "{{ruleInfo.id}}",
  "hasDuplication": boolean,
  "duplications": [
    {
      "type": "section_duplication|document_duplication|temporal_duplication",
      "source": {
        "documentIndex": number,
        "section": "章节名称",
        "content": "重复内容片段"
      },
      "target": {
        "documentIndex": number,
        "section": "章节名称", 
        "content": "重复内容片段"
      },
      "similarityScore": number, // 0-100
      "severity": "critical|major|minor",
      "description": "重复描述",
      "suggestion": "改进建议"
    }
  ],
  "overallDuplicationScore": number, // 0-100
  "confidence": number
}
`,
      
      outputSchema: {
        type: 'object',
        required: ['ruleId', 'hasDuplication', 'duplications'],
        properties: {
          ruleId: { type: 'string' },
          hasDuplication: { type: 'boolean' },
          duplications: { type: 'array' },
          overallDuplicationScore: { type: 'number' },
          confidence: { type: 'number' }
        }
      },
      variables: []
    })

    // Writing Alerts Template (Rule 16)
    this.templates.set('alert_generation', {
      name: '书写预警生成',
      systemMessage: `你是一位医疗质控专家，负责生成书写预警和提醒。`,
      
      userPromptTemplate: `
请分析以下病历数据，生成相应的书写预警：

检查规则：{{ruleInfo.name}}
当前时间：{{currentTime}}

病历文书：
{{#each applicableDocuments}}
文书类型：{{this.type}}
创建时间：{{this.timestamp}}
状态：{{this.status}}
内容摘要：{{this.summary}}

{{/each}}

{{#if auxiliaryData.orders}}
相关医嘱：
{{#each auxiliaryData.orders}}
- {{this.type}}: {{this.content}} ({{this.timestamp}})
{{/each}}
{{/if}}

检查要求：
{{checkingCriteria}}

请生成以下类型的预警：
1. 待超时文书预警
2. 待书写内容提醒
3. 必填项缺失警告
4. 时效性提醒

请严格按照以下JSON格式返回结果：
{
  "ruleId": "{{ruleInfo.id}}",
  "alerts": [
    {
      "type": "timeout_warning|missing_content|required_field|timeliness",
      "priority": "high|medium|low",
      "title": "预警标题",
      "message": "详细预警信息",
      "deadline": "截止时间（如适用）",
      "actionRequired": "需要采取的行动",
      "relatedDocument": "相关文书ID"
    }
  ],
  "summary": "预警汇总",
  "confidence": number
}
`,
      
      outputSchema: {
        type: 'object',
        required: ['ruleId', 'alerts'],
        properties: {
          ruleId: { type: 'string' },
          alerts: { type: 'array' },
          summary: { type: 'string' },
          confidence: { type: 'number' }
        }
      },
      variables: []
    })
  }

  getTemplate(templateType: string): PromptTemplate {
    const template = this.templates.get(templateType)
    if (!template) {
      throw new Error(`Template not found: ${templateType}`)
    }
    return template
  }

  renderTemplate(template: PromptTemplate, context: any): string {
    let rendered = template.userPromptTemplate
    
    // Simple template rendering (in production, use a proper template engine like Handlebars)
    rendered = this.simpleTemplateRender(rendered, context)
    
    return rendered
  }

  private simpleTemplateRender(template: string, context: any): string {
    // Replace {{variable}} patterns with context values
    return template.replace(/\{\{([^}]+)\}\}/g, (match: any,  path: any) => {
      const value = this.getNestedValue(context, path.trim())
      return value !== undefined ? String(value) : match
    })
  }

  private getNestedValue(obj: any, path: string): any {
    return path.split('.').reduce((current: any,  key: any) => {
      if (key.includes('#each')) {
        // Handle simple array iteration (simplified)
        const arrayPath = key.replace('#each ', '')
        const array = this.getNestedValue(obj, arrayPath)
        if (Array.isArray(array)) {
          return array.map((item, index) => ({ ...item, '@index': index }))
        }
      }
      return current?.[key]
    }, obj)
  }
}

// Context Builder
class ContextBuilder {
  buildRuleContext(rule: EnhancedQCRule, executionContext: QCExecutionContext): RuleContext {
    return {
      ruleInfo: {
        id: rule.id,
        name: rule.name,
        description: rule.description,
        category: rule.category,
        severity: rule.severity
      },
      
      applicableDocuments: executionContext.documents.filter(doc =>
        rule.applicable_documents.includes(doc.type)
      ),
      
      checkingCriteria: this.convertQualityLogicToPrompt(rule.quality_logic),
      
      scoringGuidelines: this.convertScoringConfigToPrompt(rule.scoring_config),
      
      departmentContext: this.buildDepartmentContext(
        rule.department_overrides,
        executionContext.departmentId
      ),
      
      auxiliaryData: {
        orders: executionContext.orders,
        reports: executionContext.reports,
        timeline: executionContext.timeline
      }
    }
  }

  private convertQualityLogicToPrompt(qualityLogic: QualityLogicConfig): string {
    const checkTypeInstructions: Record<string, string> = {
      'content_analysis': `
请进行深入的内容分析，重点关注：
- 医学术语的准确性和完整性
- 临床逻辑的合理性和连贯性
- 关键信息的记录完整性
`,
      'format_validation': `
请进行格式规范性检查，重点关注：
- 文书结构的完整性
- 必填项的填写情况
- 格式规范的符合性
`,
      'time_constraint': `
请进行时间相关的检查，重点关注：
- 文书书写的及时性
- 时间逻辑的合理性
- 时效性要求的符合性
`,
      'cross_reference': `
请进行交叉引用检查，重点关注：
- 不同文书间的一致性
- 相关数据的关联性
- 信息的互相印证
`
    }

    let instructions = checkTypeInstructions[qualityLogic.check_type] || 
                      checkTypeInstructions['content_analysis']

    if (qualityLogic.logic_expression) {
      instructions += `\n检查逻辑：${qualityLogic.logic_expression}\n`
    }

    if (qualityLogic.validation_criteria?.length > 0) {
      instructions += `\n验证标准：\n`
      qualityLogic.validation_criteria.forEach((criteria: any,  index: any) => {
        instructions += `${index + 1}. ${criteria.field} ${criteria.operator} ${criteria.value || ''} - ${criteria.description}\n`
      })
    }

    if (qualityLogic.llm_prompt_template) {
      instructions += `\n特殊分析要求：${qualityLogic.llm_prompt_template}\n`
    }

    return instructions
  }

  private convertScoringConfigToPrompt(scoringConfig: ScoringConfig): string {
    let guidelines = `
评分标准：
- 默认扣分：${scoringConfig.default_deduction}分
- 最大扣分：${scoringConfig.max_deduction}分
- 权重因子：${scoringConfig.weight_factor}

请根据发现的问题严重程度，在上述范围内给出合理的扣分建议。
`

    if (scoringConfig.custom_scoring_rules?.length > 0) {
      guidelines += `\n自定义扣分规则：\n`
      scoringConfig.custom_scoring_rules.forEach((rule, index) => {
        guidelines += `${index + 1}. 当${rule.condition}时，扣${rule.deduction}分 - ${rule.description}\n`
      })
    }

    return guidelines
  }

  private buildDepartmentContext(
    departmentOverrides: DepartmentOverride[],
    departmentId?: string
  ): any {
    if (!departmentId || !departmentOverrides?.length) {
      return { hasOverrides: false }
    }

    const override = departmentOverrides.find(o => o.department_id === departmentId)
    if (!override) {
      return { hasOverrides: false }
    }

    return {
      hasOverrides: true,
      specialRequirements: `科室${override.department_name}的特殊要求已应用`
    }
  }
}

// Main Dynamic Prompt Generator
export class DynamicPromptGenerator {
  private templateLibrary: PromptTemplateLibrary
  private contextBuilder: ContextBuilder

  constructor() {
    this.templateLibrary = new PromptTemplateLibrary()
    this.contextBuilder = new ContextBuilder()
  }

  async generatePrompt(
    rule: EnhancedQCRule,
    executionContext: QCExecutionContext
  ): Promise<GeneratedPrompt> {
    
    // 1. Get base template
    const baseTemplate = this.templateLibrary.getTemplate(
      this.mapRuleToTemplateType(rule)
    )
    
    // 2. Build rule-specific context
    const ruleContext = this.contextBuilder.buildRuleContext(rule, executionContext)
    
    // 3. Generate dynamic prompt
    const dynamicPrompt = this.templateLibrary.renderTemplate(baseTemplate, ruleContext)
    
    // 4. Add current time context
    const contextualPrompt = this.addContextualInformation(dynamicPrompt, executionContext)
    
    return {
      systemMessage: baseTemplate.systemMessage,
      userPrompt: contextualPrompt,
      parameters: {
        temperature: this.mapAlertLevelToTemperature(rule.alert_level),
        maxTokens: this.mapCategoryToTokens(rule.category),
        responseFormat: 'json'
      },
      expectedOutputSchema: baseTemplate.outputSchema
    }
  }

  private mapRuleToTemplateType(rule: EnhancedQCRule): string {
    const templateMap: Record<string, string> = {
      'completeness': 'completeness_check',
      'duplication': 'duplication_analysis',
      'consistency': 'consistency_analysis',
      'multi_source': 'multi_source_analysis',
      'authenticity': 'authenticity_analysis',
      'treatment_analysis': 'treatment_analysis',
      'diagnosis': 'diagnosis_analysis',
      'specialty_logic': 'specialty_analysis',
      'writing_alerts': 'alert_generation'
    }
    
    return templateMap[rule.category] || 'completeness_check'
  }

  private addContextualInformation(prompt: string, context: QCExecutionContext): string {
    const currentTime = new Date().toISOString()
    return prompt.replace('{{currentTime}}', currentTime)
  }

  private mapAlertLevelToTemperature(alertLevel: string): number {
    const temperatureMap: Record<string, number> = {
      'critical': 0.05,
      'major': 0.1,
      'minor': 0.15
    }
    return temperatureMap[alertLevel] || 0.1
  }

  private mapCategoryToTokens(category: string): number {
    const tokenMap: Record<string, number> = {
      'completeness': 1500,
      'duplication': 2000,
      'consistency': 3000,
      'multi_source': 4000,
      'authenticity': 5000,
      'treatment_analysis': 5000,
      'diagnosis': 4500,
      'specialty_logic': 5500,
      'writing_alerts': 1000
    }
    return tokenMap[category] || 2000
  }

  async precompileTemplate(rule: EnhancedQCRule): Promise<CompiledPromptTemplate> {
    try {
      // Create a mock context for template compilation
      const mockContext = this.createMockContext(rule)
      const generatedPrompt = await this.generatePrompt(rule, mockContext)
      
      return {
        ruleId: rule.id,
        template: generatedPrompt,
        compiledAt: new Date().toISOString(),
        isValid: true
      }
    } catch (error: any) {
      return {
        ruleId: rule.id,
        template: null,
        compiledAt: new Date().toISOString(),
        isValid: false,
        error: error.message
      }
    }
  }

  private createMockContext(rule: EnhancedQCRule): QCExecutionContext {
    return {
      patientId: 'mock-patient-001',
      executionId: 'mock-execution-001',
      documents: rule.applicable_documents.map(docType => ({
        id: `mock-doc-${docType}`,
        type: docType,
        content: `模拟${docType}内容...`,
        timestamp: new Date().toISOString(),
        status: 'completed'
      })),
      orders: [],
      reports: [],
      timeline: { events:  [],
        admissionTime: new Date().toISOString()
      }
    }
  }

  validatePrompt(prompt: GeneratedPrompt): ValidationResult {
    const errors: string[] = []
    const warnings: string[] = []
    const suggestions: string[] = []

    // Basic validation
    if (!prompt.systemMessage || prompt.systemMessage.trim().length === 0) {
      errors.push('System message is required')
    }

    if (!prompt.userPrompt || prompt.userPrompt.trim().length === 0) {
      errors.push('User prompt is required')
    }

    if (prompt.parameters.temperature < 0 || prompt.parameters.temperature > 1) {
      errors.push('Temperature must be between 0 and 1')
    }

    if (prompt.parameters.maxTokens < 100 || prompt.parameters.maxTokens > 8000) {
      warnings.push('MaxTokens should be between 100 and 8000 for optimal performance')
    }

    // Content validation
    if (prompt.userPrompt.length > 10000) {
      warnings.push('Prompt is very long, consider breaking it down')
    }

    if (!prompt.userPrompt.includes('JSON')) {
      suggestions.push('Consider specifying JSON output format for structured responses')
    }

    return {
      isValid: errors.length === 0,
      errors,
      warnings,
      suggestions
    }
  }
}

// Export singleton instance
export const dynamicPromptGenerator = new DynamicPromptGenerator()
