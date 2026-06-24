// @ts-nocheck
// Integrated QC Engine
// This is the main engine that orchestrates the entire LLM-based quality control process

import type {
  EnhancedQCRule,
  QCExecutionContext,
  ComprehensiveQCResult,
  QCRuleResult,
  EnhancedRuleFilter,
  MedicalDocument,
  MedicalOrder,
  LabReport,
  MedicalTimeline
} from '@/types/enhanced-qc-rule'

import type {
  QCExecutionPlan,
  QCTask,
  QCExecutionResult,
  RuleTestResult,
  ExecutionMetrics,
  IntegratedQCEngine as IIntegratedQCEngine
} from '@/types/llm-integration'

import { llmIntegratedRulesService } from './llm-integrated-rules-service'
import { dynamicPromptGenerator } from './dynamic-prompt-generator'
import { qcExecutionOrchestrator } from './qc-execution-orchestrator'

// Performance Optimizer
class QCPerformanceOptimizer { async createExecutionPlan(
    rules: EnhancedQCRule[],
    context: QCExecutionContext
  ): Promise<QCExecutionPlan> {
    
    // 1. Analyze rules and create execution tasks
    const tasks = await this.createExecutionTasks(rules, context)
    
    // 2. Group tasks into optimal batches
    const batches = this.createOptimalBatches(tasks)
    
    // 3. Estimate execution metrics
    const estimatedTime = this.estimateExecutionTime(batches)
    const estimatedCost = this.estimateCost(batches)
    
    return {
      totalRules: rules.length,
      totalBatches: batches.length,
      estimatedExecutionTime: estimatedTime,
      estimatedCost: estimatedCost,
      batches: batches
    }
  }

  private async createExecutionTasks(
    rules: EnhancedQCRule[],
    context: QCExecutionContext
  ): Promise<QCTask[]> {
    const tasks: QCTask[] = []
    
    for (const rule of rules) {
      // Filter documents applicable to this rule
      const applicableDocuments = context.documents.filter(doc =>
        rule.applicable_documents.includes(doc.type)
      )
      
      if (applicableDocuments.length === 0) {
        continue // Skip rules with no applicable documents
      }
      
      // Create rule context
      const ruleContext = {
        ruleInfo: {
          id: rule.id,
          name: rule.name,
          description: rule.description,
          category: rule.category,
          severity: rule.severity
        },
        applicableDocuments,
        checkingCriteria: this.buildCheckingCriteria(rule),
        scoringGuidelines: this.buildScoringGuidelines(rule),
        departmentContext: this.buildDepartmentContext(rule, context.departmentId),
        auxiliaryData: {
          orders: context.orders,
          reports: context.reports,
          timeline: context.timeline
        }
      }
      
      // Generate prompt asynchronously
      const generatedPrompt = dynamicPromptGenerator.generatePrompt(rule, context)
      
      const task: QCTask = {
        id: `task_${rule.id}_${Date.now()}`,
        rule,
        context,
        ruleContext,
        generatedPrompt,
        startTime: Date.now(),
        priority: this.calculatePriority(rule)
      }
      
      tasks.push(task)
    }
    
    return tasks
  }

  private createOptimalBatches(tasks: QCTask[]): unknown[] {
    const batches: unknown[] = []
    const batchableRules = ['completeness', 'duplication', 'writing_alerts']
    
    // Group batchable tasks
    const batchableTasks = tasks.filter(task => 
      batchableRules.includes(task.rule.category) && 
      task.rule.rule_implementation !== 'semantic_llm'
    )
    
    // Group non-batchable tasks
    const individualTasks = tasks.filter(task => 
      !batchableRules.includes(task.rule.category) || 
      task.rule.rule_implementation === 'semantic_llm'
    )
    
    // Create batches for batchable tasks (max 3 per batch)
    for (let i = 0; i < batchableTasks.length; i += 3) {
      const batchTasks = batchableTasks.slice(i, i + 3)
      batches.push({
        id: `batch_${Date.now()}_${i}`,
        type: 'batch',
        canBatchProcess: true,
        tasks: batchTasks,
        estimatedTokens: batchTasks.reduce((sum, task) => sum + this.estimateTaskTokens(task), 0),
        priority: Math.max(...batchTasks.map(task => task.priority))
      })
    }
    
    // Create individual batches for complex tasks
    individualTasks.forEach((task: unknown,  index: unknown) => {
      batches.push({
        id: `single_${task.id}`,
        type: 'single',
        canBatchProcess: false,
        tasks: [task],
        estimatedTokens: this.estimateTaskTokens(task),
        priority: task.priority
      })
    })
    
    // Sort batches by priority
    return batches.sort((a, b) => b.priority - a.priority)
  }

  private buildCheckingCriteria(rule: EnhancedQCRule): string {
    let criteria = `规则类型：${rule.category}\n`
    criteria += `检查重点：${rule.description}\n`
    
    if (rule.quality_logic?.validation_criteria) {
      criteria += '验证标准：\n'
      rule.quality_logic.validation_criteria.forEach((criterion, index) => {
        criteria += `${index + 1}. ${criterion.description}\n`
      })
    }
    
    return criteria
  }

  private buildScoringGuidelines(rule: EnhancedQCRule): string {
    const config = rule.scoring_config
    return `
评分标准：
- 默认扣分：${config.default_deduction}分
- 最大扣分：${config.max_deduction}分
- 权重因子：${config.weight_factor}

请根据问题严重程度合理扣分。
`
  }

  private buildDepartmentContext(rule: EnhancedQCRule, departmentId?: string): Record<string, unknown> {
    if (!departmentId || !rule.department_overrides?.length) {
      return { hasOverrides: false }
    }
    
    const override = rule.department_overrides.find(o => o.department_id === departmentId)
    return {
      hasOverrides: !!override,
      specialRequirements: override ? `科室${override.department_name}特殊要求已应用` : undefined
    }
  }

  private calculatePriority(rule: EnhancedQCRule): number {
    let priority = 5 // Base priority
    
    // Increase priority for critical rules
    if (rule.severity === 'critical') priority += 5
    else if (rule.severity === 'major') priority += 3
    
    // Increase priority for core system rules
    if (rule.core_system_related) priority += 2
    
    // Increase priority for high alert level
    if (rule.alert_level === 'critical') priority += 3
    else if (rule.alert_level === 'major') priority += 1
    
    return Math.min(priority, 10) // Cap at 10
  }

  private estimateTaskTokens(task: QCTask): number {
    const baseTokens = 500 // Base prompt tokens
    const documentTokens = task.ruleContext.applicableDocuments.reduce(
      (sum, doc) => sum + Math.min(doc.content.length / 4, 1000), // Rough token estimation
      0
    )
    
    const complexityMultiplier = {
      'completeness': 1.0,
      'duplication': 1.5,
      'consistency': 2.0,
      'multi_source': 2.5,
      'authenticity': 3.0,
      'treatment_analysis': 3.0,
      'diagnosis': 2.8,
      'specialty_logic': 3.2,
      'writing_alerts': 0.8
    }
    
    const multiplier = complexityMultiplier[task.rule.category] || 1.0
    return Math.floor((baseTokens + documentTokens) * multiplier)
  }

  private estimateExecutionTime(batches: unknown[]): number {
    return batches.reduce((total: unknown,  batch: unknown) => {
      const baseTime = batch.type === 'batch' ? 3000 : 2000 // ms
      const tokenTime = batch.estimatedTokens * 0.1 // 0.1ms per token
      return total + baseTime + tokenTime
    }, 0)
  }

  private estimateCost(batches: unknown[]): number {
    const costPerToken = 0.00002 // $0.00002 per token
    const totalTokens = batches.reduce((sum, batch) => sum + batch.estimatedTokens, 0)
    return totalTokens * costPerToken
  }
}

// Main Integrated QC Engine
export class IntegratedQCEngine implements IIntegratedQCEngine {
  private performanceOptimizer: QCPerformanceOptimizer

  constructor() {
    this.performanceOptimizer = new QCPerformanceOptimizer()
  }

  async executeQualityControl(
    patientData,
    departmentId?: string,
    ruleFilter?: EnhancedRuleFilter
  ): Promise<ComprehensiveQCResult> {
    
    console.log('Starting integrated QC execution...')
    
    try {
      // 1. Get applicable rules
      const applicableRules = await this.getApplicableRules(patientData, departmentId, ruleFilter)
      
      if (applicableRules.length === 0) {
        return this.createEmptyResult(patientData.patientId)
      }
      
      // 2. Build execution context
      const executionContext = this.buildExecutionContext(patientData, departmentId)
      
      // 3. Create execution plan
      const executionPlan = await this.performanceOptimizer.createExecutionPlan(
        applicableRules, 
        executionContext
      )
      
      console.log(`Execution plan created: ${executionPlan.totalBatches} batches, estimated time: ${executionPlan.estimatedExecutionTime}ms`)
      
      // 4. Execute quality control
      const executionResults = await qcExecutionOrchestrator.execute(executionPlan)
      
      // 5. Process and consolidate results
      const comprehensiveResult = this.consolidateResults(
        executionResults,
        patientData.patientId,
        executionPlan
      )
      
      console.log('QC execution completed successfully')
      return comprehensiveResult
      
    } catch (error) {
      console.error('QC execution failed:', error)
      throw new Error(`质控执行失败: ${error.message}`)
    }
  }

  private async getApplicableRules(
    patientData: unknown,
    departmentId?: string,
    ruleFilter?: EnhancedRuleFilter
  ): Promise<EnhancedQCRule[]> {
    
    // Build filter based on patient data and parameters
    const filter: EnhancedRuleFilter = {
      ...ruleFilter,
      department_id: departmentId
    }
    
    // Add document type filter based on available documents
    if (patientData.documents && patientData.documents.length > 0) {
      const documentTypes = [...new Set(patientData.documents.map((doc) => doc.type))]
      // For now, we'll get all rules and filter later - in production, optimize this
    }
    
    const rules = await llmIntegratedRulesService.getEnhancedRules(filter)
    
    // Filter rules that have applicable documents
    return rules.filter(rule => {
      if (!patientData.documents) return false
      
      const hasApplicableDoc = patientData.documents.some((doc) =>
        rule.applicable_documents.includes(doc.type)
      )
      
      return hasApplicableDoc
    })
  }

  private buildExecutionContext(patientData: unknown, departmentId?: string): QCExecutionContext {
    return {
      patientId: patientData.patientId || 'unknown',
      executionId: `exec_${Date.now()}`,
      documents: patientData.documents || [],
      orders: patientData.orders || [],
      reports: patientData.reports || [],
      timeline: patientData.timeline || { events:  [], admissionTime: new Date().toISOString() },
      departmentId
    }
  }

  private consolidateResults(
    executionResults: QCExecutionResult[],
    patientId: string,
    executionPlan: QCExecutionPlan
  ): ComprehensiveQCResult {
    
    const ruleResults: QCRuleResult[] = executionResults.map(result => result.result)
    
    // Calculate overall score
    const totalScore = ruleResults.reduce((sum, result) => sum + (result.score || 0), 0)
    const averageScore = ruleResults.length > 0 ? totalScore / ruleResults.length : 0
    
    // Determine risk level
    const riskLevel = this.calculateRiskLevel(ruleResults)
    
    // Generate summary
    const summary = this.generateSummary(ruleResults)
    
    // Calculate total execution time
    const totalExecutionTime = executionResults.reduce((sum, result) => sum + result.executionTime, 0)
    
    return {
      executionId: `result_${Date.now()}`,
      patientId,
      overallScore: Math.round(averageScore),
      riskLevel,
      ruleResults,
      summary,
      executionTime: totalExecutionTime,
      timestamp: new Date().toISOString(),
      crossRuleAnalysis: this.performCrossRuleAnalysis(ruleResults)
    }
  }

  private calculateRiskLevel(results: QCRuleResult[]): 'low' | 'medium' | 'high' | 'critical' {
    const criticalIssues = results.filter(r => 
      r.findings.some(f => f.severity === 'critical')
    ).length
    
    const majorIssues = results.filter(r => 
      r.findings.some(f => f.severity === 'major')
    ).length
    
    if (criticalIssues > 0) return 'critical'
    if (majorIssues > 2) return 'high'
    if (majorIssues > 0) return 'medium'
    return 'low'
  }

  private generateSummary(results: QCRuleResult[]): string {
    const totalRules = results.length
    const compliantRules = results.filter(r => r.isCompliant).length
    const nonCompliantRules = totalRules - compliantRules
    
    const totalFindings = results.reduce((sum, r) => sum + r.findings.length, 0)
    
    return `共检查${totalRules}项规则，其中${compliantRules}项合规，${nonCompliantRules}项存在问题。总计发现${totalFindings}个质控问题。`
  }

  private performCrossRuleAnalysis(results: QCRuleResult[]): Record<string, unknown> {
    // Simple cross-rule analysis
    const categories = new Set(results.map(r => r.ruleCode.split('.')[0]))
    const systemicIssues = categories.size < results.length / 2 ? '发现系统性质量问题' : '问题相对分散'
    
    return {
      correlatedIssues: '部分问题可能存在关联性',
      systemicProblems: systemicIssues,
      priorityRecommendations: '建议优先处理严重级别的质控问题'
    }
  }

  private createEmptyResult(patientId: string): ComprehensiveQCResult {
    return {
      executionId: `empty_${Date.now()}`,
      patientId,
      overallScore: 100,
      riskLevel: 'low',
      ruleResults: [],
      summary: '未找到适用的质控规则',
      executionTime: 0,
      timestamp: new Date().toISOString()
    }
  }

  async updateRuleConfiguration(ruleId: string, config: unknown): Promise<void> {
    // This would update the rule configuration and sync with LLM engine
    console.log(`Updating rule configuration for ${ruleId}:`, config)
  }

  async testRule(ruleId: string): Promise<RuleTestResult> {
    return llmIntegratedRulesService.testRuleConfiguration(ruleId)
  }

  getExecutionMetrics(): ExecutionMetrics {
    return qcExecutionOrchestrator.getExecutionMetrics()
  }
}

// Export singleton instance
export const integratedQCEngine = new IntegratedQCEngine()

