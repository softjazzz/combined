// QC Execution Orchestrator
// This service orchestrates the execution of quality control rules using LLM

import type {
  QCExecutionPlan,
  QCExecutionBatch,
  QCExecutionResult,
  QCTask,
  LLMService,
  GeneratedPrompt,
  ExecutionError,
  ExecutionMonitor
} from '@/types/llm-integration'

import type { QCRuleResult, QCFinding } from '@/types/enhanced-qc-rule'

// Mock LLM Service Implementation
class MockLLMService implements LLMService {
  async analyze(prompt: string, options?: unknown): Promise<string> {
    // Simulate API call delay
    await new Promise(resolve => setTimeout(resolve, 500 + Math.random() * 1000))
    
    // Mock response based on prompt content
    if (prompt.includes('completeness')) {
      return JSON.stringify({
        ruleId: options?.ruleId || 'unknown',
        isCompliant: Math.random() > 0.3,
        completenessScore: Math.floor(Math.random() * 40) + 60,
        findings: Math.random() > 0.5 ? [{
          type: 'missing_content',
          severity: 'minor',
          description: '缺少部分必填内容',
          location: '主诉章节',
          evidence: '未发现明确的主诉描述',
          recommendation: '请补充完整的主诉信息',
          scoreDeduction: 5
        }] : [],
        overallAssessment: '文书基本完整，存在少量问题',
        confidence: Math.floor(Math.random() * 20) + 80
      })
    }
    
    if (prompt.includes('duplication')) {
      return JSON.stringify({
        ruleId: options?.ruleId || 'unknown',
        hasDuplication: Math.random() > 0.7,
        duplications: Math.random() > 0.7 ? [{
          type: 'section_duplication',
          source: { documentIndex: 0, section: '现病史', content: '患者因胸痛入院...' },
          target: { documentIndex: 1, section: '首次病程', content: '患者因胸痛入院...' },
          similarityScore: 95,
          severity: 'major',
          description: '现病史与首次病程记录内容高度重复',
          suggestion: '请避免直接复制粘贴，应根据不同文书要求进行相应调整'
        }] : [],
        overallDuplicationScore: Math.floor(Math.random() * 30) + 10,
        confidence: Math.floor(Math.random() * 20) + 75
      })
    }
    
    // Default response
    return JSON.stringify({ ruleId: options?.ruleId || 'unknown',
      isCompliant: Math.random() > 0.4,
      score: Math.floor(Math.random() * 100),
      findings:  [],
      confidence: Math.floor(Math.random() * 30) + 70
    })
  }

  async analyzeStructured(request: unknown): Promise<unknown> {
    const response = await this.analyze(request.userPrompt, { ruleId: request.ruleId })
    return {
      content: response,
      usage: {
        promptTokens: Math.floor(Math.random() * 1000) + 500,
        completionTokens: Math.floor(Math.random() * 500) + 200,
        totalTokens: Math.floor(Math.random() * 1500) + 700
      },
      model: 'mock-llm-v1',
      finishReason: 'stop',
      timestamp: new Date().toISOString()
    }
  }

  async isHealthy(): Promise<boolean> {
    return true
  }

  async getUsageStats(): Promise<unknown> {
    return {
      totalRequests: Math.floor(Math.random() * 10000),
      totalTokens: Math.floor(Math.random() * 1000000),
      averageResponseTime: Math.floor(Math.random() * 2000) + 500
    }
  }
}

// Execution Monitor Implementation
class SimpleExecutionMonitor implements ExecutionMonitor {
  private metrics = {
    totalExecutions: 0,
    successfulExecutions: 0,
    failedExecutions: 0,
    averageExecutionTime: 0,
    totalTokensUsed: 0,
    totalCost: 0,
    errorRate: 0
  }

  private performanceMetrics = {
    cacheHitRate: 0,
    averageResponseTime: 0,
    throughput: 0,
    errorRate: 0,
    costPerExecution: 0
  }

  private batchStatuses = new Map<string, string>()
  private errors: ExecutionError[] = []

  updateProgress(batchId: string, status: string): void {
    this.batchStatuses.set(batchId, status)
    console.log(`Batch ${batchId} status: ${status}`)
  }

  recordError(batchId: string, error: unknown): void {
    const executionError: ExecutionError = {
      type: 'unknown',
      message: error.message || 'Unknown error',
      details: error,
      timestamp: new Date().toISOString(),
      taskId: batchId
    }
    
    this.errors.push(executionError)
    this.metrics.failedExecutions++
    console.error(`Error in batch ${batchId}:`, error)
  }

  getMetrics() {
    return { ...this.metrics }
  }

  getPerformanceMetrics() {
    return { ...this.performanceMetrics }
  }

  recordSuccess(executionTime: number, tokensUsed: number): void {
    this.metrics.totalExecutions++
    this.metrics.successfulExecutions++
    this.metrics.totalTokensUsed += tokensUsed
    
    // Update average execution time
    const totalTime = this.metrics.averageExecutionTime * (this.metrics.totalExecutions - 1) + executionTime
    this.metrics.averageExecutionTime = totalTime / this.metrics.totalExecutions
    
    // Update error rate
    this.metrics.errorRate = this.metrics.failedExecutions / this.metrics.totalExecutions
  }
}

// Result Validator
class ResultValidator {
  validate(result, rule): QCRuleResult {
    try {
      // Parse JSON response if it's a string
      const parsedResult = typeof result === 'string' ? JSON.parse(result) : result
      
      // Validate required fields
      const validated: QCRuleResult = {
        ruleId: parsedResult.ruleId || rule.id,
        ruleName: rule.name,
        ruleCode: rule.rule_code,
        isCompliant: parsedResult.isCompliant ?? null,
        score: parsedResult.completenessScore || parsedResult.score || 0,
        findings: this.validateFindings(parsedResult.findings || []),
        confidence: parsedResult.confidence || 0,
        executionTime: 0, // Will be set by orchestrator
        medicalReasoning: parsedResult.overallAssessment || parsedResult.medicalReasoning
      }
      
      return validated
    } catch (error: unknown) {
      // Return error result if validation fails
      return {
        ruleId: rule.id,
        ruleName: rule.name,
        ruleCode: rule.rule_code,
        isCompliant: null,
        score: 0,
        findings: [{
          type: 'validation_error',
          severity: 'critical',
          description: `结果验证失败: ${error.message}`,
          recommendation: '请检查规则配置或联系技术支持',
          scoreDeduction: 0
        }],
        confidence: 0,
        executionTime: 0,
        error: error.message
      }
    }
  }

  private validateFindings(findings: unknown[]): QCFinding[] {
    if (!Array.isArray(findings)) {
      return []
    }
    
    return findings.map(finding => ({
      type: finding.type || 'unknown',
      severity: finding.severity || 'minor',
      description: finding.description || '未知问题',
      location: finding.location,
      evidence: finding.evidence,
      recommendation: finding.recommendation || '请联系质控专家',
      scoreDeduction: finding.scoreDeduction || 0,
      confidence: finding.confidence
    }))
  }
}

// Main QC Execution Orchestrator
export class QCExecutionOrchestrator {
  private llmService: LLMService
  private resultValidator: ResultValidator
  private executionMonitor: ExecutionMonitor

  constructor(llmService?: LLMService) {
    this.llmService = llmService || new MockLLMService()
    this.resultValidator = new ResultValidator()
    this.executionMonitor = new SimpleExecutionMonitor()
  }

  async execute(executionPlan: QCExecutionPlan): Promise<QCExecutionResult[]> {
    const results: QCExecutionResult[] = []
    
    console.log(`Starting execution of ${executionPlan.totalBatches} batches with ${executionPlan.totalRules} rules`)
    
    // Execute batches sequentially to avoid overwhelming the LLM service
    for (const batch of executionPlan.batches) {
      try {
        this.executionMonitor.updateProgress(batch.id, 'started')
        
        const batchResults = await this.executeBatch(batch)
        results.push(...batchResults)
        
        this.executionMonitor.updateProgress(batch.id, 'completed')
        
        // Add small delay between batches to avoid rate limiting
        await new Promise(resolve => setTimeout(resolve, 100))
        
      } catch (error) {
        this.executionMonitor.recordError(batch.id, error)
        
        // Error recovery: try to execute tasks individually
        const recoveryResults = await this.executeWithRecovery(batch)
        results.push(...recoveryResults)
      }
    }
    
    console.log(`Execution completed. Processed ${results.length} tasks`)
    return results
  }

  async executeBatch(batch: QCExecutionBatch): Promise<QCExecutionResult[]> {
    if (batch.canBatchProcess && batch.tasks.length > 1) {
      // Batch processing for compatible rules
      return this.executeBatchTasks(batch.tasks)
    } else {
      // Parallel individual processing
      const taskPromises = batch.tasks.map(task => this.executeSingleTask(task))
      return Promise.all(taskPromises)
    }
  }

  private async executeBatchTasks(tasks: QCTask[]): Promise<QCExecutionResult[]> {
    // Create consolidated prompt for batch processing
    const batchPrompt = await this.createBatchPrompt(tasks)
    
    try {
      const startTime = Date.now()
      const response = await this.llmService.analyzeStructured({
        systemMessage: batchPrompt.systemMessage,
        userPrompt: batchPrompt.userPrompt,
        temperature: batchPrompt.parameters.temperature,
        maxTokens: batchPrompt.parameters.maxTokens,
        responseFormat: 'json'
      })
      
      const executionTime = Date.now() - startTime
      
      // Parse batch response
      const batchResult = this.parseBatchResponse(response.content, tasks)
      
      // Validate and convert to execution results
      const results = tasks.map((task, index) => {
        const ruleResult = batchResult.ruleResults?.[index] || batchResult
        const validatedResult = this.resultValidator.validate(ruleResult, task.rule)
        validatedResult.executionTime = executionTime / tasks.length // Distribute time across tasks
        
        // Record metrics
        if (this.executionMonitor instanceof SimpleExecutionMonitor) {
          this.executionMonitor.recordSuccess(validatedResult.executionTime, response.usage?.totalTokens || 0)
        }
        
        return {
          taskId: task.id,
          ruleId: task.rule.id,
          result: validatedResult,
          executionTime: validatedResult.executionTime,
          status: 'success' as const
        }
      })
      
      return results
      
    } catch (error: unknown) {
      console.error('Batch execution failed:', error)
      throw error
    }
  }

  private async executeSingleTask(task: QCTask): Promise<QCExecutionResult> {
    try {
      const prompt = await task.generatedPrompt
      const startTime = Date.now()
      
      const response = await this.llmService.analyzeStructured({
        systemMessage: prompt.systemMessage,
        userPrompt: prompt.userPrompt,
        temperature: prompt.parameters.temperature,
        maxTokens: prompt.parameters.maxTokens,
        responseFormat: 'json'
      })
      
      const executionTime = Date.now() - startTime
      
      // Validate result
      const validatedResult = this.resultValidator.validate(response.content, task.rule)
      validatedResult.executionTime = executionTime
      
      // Record metrics
      if (this.executionMonitor instanceof SimpleExecutionMonitor) {
        this.executionMonitor.recordSuccess(executionTime, response.usage?.totalTokens || 0)
      }
      
      return {
        taskId: task.id,
        ruleId: task.rule.id,
        result: validatedResult,
        executionTime,
        status: 'success'
      }
      
    } catch (error: unknown) {
      return this.createErrorResult(task, error)
    }
  }

  async executeWithRecovery(batch: QCExecutionBatch): Promise<QCExecutionResult[]> {
    const results: QCExecutionResult[] = []
    
    console.log(`Executing batch ${batch.id} with recovery mode`)
    
    // Execute tasks individually to ensure partial success
    for (const task of batch.tasks) {
      try {
        const result = await this.executeSingleTask(task)
        results.push(result)
      } catch (error) {
        // Create error result but don't stop the entire batch
        const errorResult = this.createErrorResult(task, error)
        results.push(errorResult)
      }
    }
    
    return results
  }

  private async createBatchPrompt(tasks: QCTask[]): Promise<GeneratedPrompt> {
    // For batch processing, create a consolidated prompt
    const firstTask = tasks[0]
    const firstPrompt = await firstTask.generatedPrompt
    
    // Simple batch prompt creation (in production, this would be more sophisticated)
    const batchUserPrompt = `
请对以下病历进行多维度质控分析：

患者病历数据：
${this.formatPatientData(firstTask.context)}

需要执行的质控规则：
${tasks.map((task, index) => `
${index + 1}. 规则名称：${task.rule.name}
   规则类型：${task.rule.category}
   检查要点：${task.rule.description}
`).join('\n')}

请严格按照JSON格式返回分析结果，包含每个规则的检查结果。
`
    
    return {
      systemMessage: firstPrompt.systemMessage,
      userPrompt: batchUserPrompt,
      parameters: {
        temperature: 0.05,
        maxTokens: Math.min(6000, tasks.length * 1500),
        responseFormat: 'json'
      }
    }
  }

  private formatPatientData(context: unknown): string {
    return context.documents?.map((doc: unknown, index: number) => 
      `文书${index + 1}（${doc.type}）：\n${doc.content.substring(0, 500)}...`
    ).join('\n\n') || '无文书数据'
  }

  private parseBatchResponse(response: string, tasks: QCTask[]): unknown {
    try {
      const parsed = JSON.parse(response)
      
      // If response contains ruleResults array, return as is
      if (parsed.ruleResults && Array.isArray(parsed.ruleResults)) {
        return parsed
      }
      
      // Otherwise, treat as single result and replicate for all tasks
      return {
        ruleResults: tasks.map(() => parsed)
      }
    } catch (error) {
      // If parsing fails, create default results
      return {
        ruleResults: tasks.map(task => ({
          ruleId: task.rule.id,
          isCompliant: null,
          score: 0,
          findings: [{
            type: 'parsing_error',
            severity: 'critical',
            description: '无法解析LLM响应',
            recommendation: '请检查提示模板配置'
          }],
          confidence: 0
        }))
      }
    }
  }

  private createErrorResult(task: QCTask, error: unknown): QCExecutionResult {
    return {
      taskId: task.id,
      ruleId: task.rule.id,
      result: {
        ruleId: task.rule.id,
        ruleName: task.rule.name,
        ruleCode: task.rule.rule_code,
        isCompliant: null,
        score: 0,
        findings: [{
          type: 'execution_error',
          severity: 'critical',
          description: `质控规则执行失败: ${error.message}`,
          recommendation: '请检查规则配置或联系技术支持',
          scoreDeduction: 0
        }],
        confidence: 0,
        executionTime: Date.now() - task.startTime,
        error: error.message
      },
      executionTime: Date.now() - task.startTime,
      status: 'error'
    }
  }

  getExecutionMetrics() {
    return this.executionMonitor.getMetrics()
  }

  getPerformanceMetrics() {
    return this.executionMonitor.getPerformanceMetrics()
  }
}

// Export singleton instance and classes
export const qcExecutionOrchestrator = new QCExecutionOrchestrator()
export { MockLLMService, SimpleExecutionMonitor, ResultValidator }
