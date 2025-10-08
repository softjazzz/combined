// LLM Integration Type Definitions
// This file defines types specific to LLM integration and execution

import type { EnhancedQCRule, QCExecutionContext, QCRuleResult } from './enhanced-qc-rule'

// LLM Service Configuration
export interface LLMServiceConfig {
  provider: 'openai' | 'anthropic' | 'qwen' | 'custom'
  apiKey: string
  baseUrl?: string
  model: string
  defaultTemperature: number
  defaultMaxTokens: number
  timeout: number
  retryAttempts: number
}

// LLM Request and Response interfaces
export interface LLMRequest {
  systemMessage: string
  userPrompt: string
  temperature: number
  maxTokens: number
  responseFormat: 'text' | 'json'
  stream?: boolean
}

export interface LLMResponse {
  content: string
  usage: {
    promptTokens: number
    completionTokens: number
    totalTokens: number
  }
  model: string
  finishReason: string
  timestamp: string
}

// Prompt Template System
export interface PromptTemplate {
  name: string
  systemMessage: string
  userPromptTemplate: string
  outputSchema?: Record<string, unknown>
  variables: PromptVariable[]
  examples?: PromptExample[]
}

export interface PromptVariable {
  name: string
  type: 'string' | 'number' | 'boolean' | 'array' | 'object'
  required: boolean
  description: string
  defaultValue?: Record<string, unknown>
}

export interface PromptExample {
  input: Record<string, unknown>
  expectedOutput: Record<string, unknown>
  description: string
}

export interface CompiledPromptTemplate {
  ruleId: string
  template: GeneratedPrompt | null
  compiledAt: string
  isValid: boolean
  error?: string
}

export interface GeneratedPrompt {
  systemMessage: string
  userPrompt: string
  parameters: {
    temperature: number
    maxTokens: number
    responseFormat: string
  }
  expectedOutputSchema?: Record<string, unknown>
}

// Rule Context and Execution
export interface RuleContext {
  ruleInfo: {
    id: string
    name: string
    description: string
    category: string
    severity: string
  }
  applicableDocuments[]
  checkingCriteria: string
  scoringGuidelines: string
  departmentContext?: {
    hasOverrides: boolean
    specialRequirements?: string
  }
  auxiliaryData?: {
    orders?[]
    reports?[]
    timeline?: Record<string, unknown>
  }
}

export interface QCTask {
  id: string
  rule: EnhancedQCRule
  context: QCExecutionContext
  ruleContext: RuleContext
  generatedPrompt: Promise<GeneratedPrompt>
  startTime: number
  priority: number
}

export interface QCExecutionBatch {
  id: string
  type: 'single' | 'batch'
  canBatchProcess: boolean
  tasks: QCTask[]
  estimatedTokens: number
  priority: number
}

export interface QCExecutionPlan {
  totalRules: number
  totalBatches: number
  estimatedExecutionTime: number
  estimatedCost: number
  batches: QCExecutionBatch[]
}

export interface OptimizedExecutionPlan extends QCExecutionPlan {
  optimizationApplied: boolean
  skippedBatches?: number
  optimizationStrategy?: string[]
}

export interface QCExecutionResult {
  taskId: string
  ruleId: string
  result: QCRuleResult
  executionTime: number
  status: 'success' | 'error' | 'timeout'
}

// Performance and Optimization
export interface RuleAnalysis {
  rule: EnhancedQCRule
  llmConfig: LLMExecutionConfig
  complexity: string
  batchCompatibility: {
    canBatch: boolean
    batchGroup?: string
    incompatibilityReasons?: string[]
  }
  dependencies: string[]
  estimatedTokens: number
  priority: number
}

export interface LLMExecutionConfig {
  ruleId: string
  ruleCode: string
  llmCapability: string
  promptTemplate: string
  batchable: boolean
  complexity: 'low' | 'medium' | 'high' | 'very_high'
  llmParameters: {
    temperature: number
    maxTokens: number
    systemMessage: string
    responseFormat: string
  }
  executionConfig: {
    requiresSpecialtyKnowledge: boolean
    departmentSpecific: boolean
    multiModal: boolean
    priority: number
  }
}

// Caching System
export interface CacheEntry<T> {
  key: string
  value: T
  timestamp: number
  ttl: number
  metadata?: Record<string, unknown>
}

export interface CacheStats {
  hitRate: number
  missRate: number
  totalRequests: number
  cacheSize: number
  evictionCount: number
}

// Cost Control and Monitoring
export interface CostBreakdown {
  development: {
    [key: string]: number
    total: number
  }
  operational: {
    [key: string]: number
    total: number
  }
  perAnalysis: number
}

export interface ExecutionMetrics {
  totalExecutions: number
  successfulExecutions: number
  failedExecutions: number
  averageExecutionTime: number
  totalTokensUsed: number
  totalCost: number
  errorRate: number
}

export interface PerformanceMetrics {
  cacheHitRate: number
  averageResponseTime: number
  throughput: number
  errorRate: number
  costPerExecution: number
}

// Error Handling and Recovery
export interface ExecutionError {
  type: 'timeout' | 'api_error' | 'parsing_error' | 'validation_error' | 'unknown'
  message: string
  details?: Record<string, unknown>
  timestamp: string
  ruleId?: string
  taskId?: string
}

export interface RecoveryStrategy {
  type: 'retry' | 'fallback' | 'skip' | 'manual_review'
  maxAttempts?: number
  backoffStrategy?: 'linear' | 'exponential'
  fallbackRule?: string
}

// Monitoring and Observability
export interface ExecutionMonitor {
  updateProgress(batchId: string, status: string): void
  recordError(batchId: string, error: unknown): void
  getMetrics(): ExecutionMetrics
  getPerformanceMetrics(): PerformanceMetrics
}

// Validation and Testing
export interface RuleTestResult {
  ruleId: string
  isSuccessful: boolean
  executionTime?: number
  result?: QCRuleResult
  error?: string
  testData: Record<string, unknown>
}

export interface ValidationResult {
  isValid: boolean
  errors: string[]
  warnings: string[]
  suggestions: string[]
}

// Batch Processing Optimization
export interface BatchProcessor {
  createOptimalBatches(rules: RuleAnalysis[]): QCExecutionBatch[]
  estimateBatchCost(batch: QCExecutionBatch): number
  optimizeBatchOrder(batches: QCExecutionBatch[]): QCExecutionBatch[]
}

export interface OptimizationStrategy {
  name: string
  description: string
  optimize(plan: QCExecutionPlan, budget?: number): Promise<OptimizedExecutionPlan>
}

// Result Processing and Validation
export interface ResultValidator { validate(result: unknown, rule: EnhancedQCRule): QCRuleResult
  validateBatch(results[], rules: EnhancedQCRule: unknown[]): QCRuleResult[]
}

export interface ResultProcessor { process(results: QCExecutionResult[], rules: EnhancedQCRule: unknown[]): Promise<unknown>
  consolidate(results: QCExecutionResult[]): Promise<unknown>
  postProcess(results: unknown): Promise<unknown>
}

// Configuration Management
export interface ConfigurationCache {
  get(key: string): unknown
  set(key: string, value: unknown, ttl?: number): void
  invalidate(key: string): void
  invalidateRule(ruleId: string): void
  clear(): void
}

export interface RealTimeSyncManager {
  notifyRuleUpdate(rule: EnhancedQCRule): void
  notifyRuleDelete(ruleId: string): void
  subscribeToUpdates(callback: (event: unknown) => void): void
  unsubscribe(callback: (event: unknown) => void): void
}

// Service Interfaces
export interface LLMService {
  analyze(prompt: string, options?: Partial<LLMRequest>): Promise<string>
  analyzeStructured(request: LLMRequest): Promise<LLMResponse>
  isHealthy(): Promise<boolean>
  getUsageStats(): Promise<unknown>
}

export interface PromptTemplateLibrary {
  getTemplate(templateType: string): PromptTemplate
  renderTemplate(template: PromptTemplate, context: unknown): string
  validateTemplate(template: PromptTemplate): ValidationResult
  registerTemplate(template: PromptTemplate): void
}

export interface DynamicPromptGenerator {
  generatePrompt(rule: EnhancedQCRule, context: QCExecutionContext): Promise<GeneratedPrompt>
  precompileTemplate(rule: EnhancedQCRule): Promise<CompiledPromptTemplate>
  validatePrompt(prompt: GeneratedPrompt): ValidationResult
}

// Integration Interfaces
export interface IntegratedQCEngine {
  executeQualityControl(
    patientData: unknown,
    departmentId?: string,
    ruleFilter?: Record<string, unknown>
  ): Promise<unknown>
  updateRuleConfiguration(ruleId: string, config: unknown): Promise<void>
  testRule(ruleId: string): Promise<RuleTestResult>
  getExecutionMetrics(): ExecutionMetrics
}

export interface QCExecutionOrchestrator {
  execute(executionPlan: QCExecutionPlan): Promise<QCExecutionResult[]>
  executeBatch(batch: QCExecutionBatch): Promise<QCExecutionResult[]>
  executeWithRecovery(batch: QCExecutionBatch): Promise<QCExecutionResult[]>
}

export interface QCPerformanceOptimizer { createExecutionPlan(
    rules: EnhancedQCRule[],
    context: QCExecutionContext
  ): Promise<QCExecutionPlan>
  optimizeForCost(plan: QCExecutionPlan, budget: number): Promise<OptimizedExecutionPlan>
  optimizeForSpeed(plan: QCExecutionPlan): Promise<OptimizedExecutionPlan>
}
