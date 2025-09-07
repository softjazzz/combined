// LLM-Integrated QC Services Index
// This file exports all the LLM-integrated quality control services

// Core Services
export { llmIntegratedRulesService, LLMIntegratedRulesService } from './llm-integrated-rules-service'
export { dynamicPromptGenerator, DynamicPromptGenerator } from './dynamic-prompt-generator'
export { qcExecutionOrchestrator, QCExecutionOrchestrator, MockLLMService, SimpleExecutionMonitor, ResultValidator } from './qc-execution-orchestrator'
export { integratedQCEngine, IntegratedQCEngine } from './integrated-qc-engine'
export { intelligentQCCache, IntelligentQCCache, LRUCache, CacheKeyGenerator, ConfigurationCacheImpl } from './intelligent-cache'

// Demo and Testing
export { llmQCDemoService, LLMQCDemoService } from './llm-qc-demo'

// Type exports for convenience
export type {
  EnhancedQCRule,
  CreateEnhancedRuleRequest,
  EnhancedRuleFilter,
  QCExecutionContext,
  ComprehensiveQCResult,
  QCRuleResult,
  QCFinding,
  MedicalDocument,
  MedicalOrder,
  LabReport,
  MedicalTimeline,
  BatchUpdateRequest,
  BatchUpdateResult,
  ImportResult,
  RuleExportConfig,
  RuleImportConfig
} from '@/types/enhanced-qc-rule'

export type {
  LLMExecutionConfig,
  GeneratedPrompt,
  QCExecutionPlan,
  QCExecutionBatch,
  QCExecutionResult,
  QCTask,
  RuleTestResult,
  ExecutionMetrics,
  PerformanceMetrics,
  CacheEntry,
  CacheStats,
  ConfigurationCache,
  LLMService,
  PromptTemplate,
  CompiledPromptTemplate,
  ValidationResult
} from '@/types/llm-integration'
