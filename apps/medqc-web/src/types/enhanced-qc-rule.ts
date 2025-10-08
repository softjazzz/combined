// Enhanced QC Rule Type Definitions for LLM Integration
// This file defines the comprehensive type system for the LLM-integrated quality control rules

// Basic enums and types
export type DocumentType = 
  | 'admission_record'
  | 'progress_note' 
  | 'surgery_record'
  | 'discharge_record'
  | 'consultation_record'
  | 'nursing_record'
  | 'examination_report'
  | 'laboratory_report'

export type RuleImplementationType = 
  | 'semantic_llm'      // Requires LLM semantic analysis
  | 'logical_program'   // Programmatic structural checks
  | 'hybrid_analysis'   // Combination of both approaches

export type AlertLevel = 'critical' | 'major' | 'minor'

export type RuleCategory = 
  | 'completeness'      // Rules 6-7: Document completeness validation
  | 'duplication'       // Rule 8: Duplication detection
  | 'consistency'       // Rule 9: Consistency validation
  | 'multi_source'      // Rule 10: Multi-source consistency
  | 'authenticity'      // Rule 12: Authenticity validation
  | 'treatment_analysis' // Rule 13: Treatment analysis
  | 'diagnosis'         // Rule 14: Diagnosis validation
  | 'specialty_logic'   // Rule 15: Specialty-specific logic
  | 'writing_alerts'    // Rule 16: Writing alerts and warnings

// Core rule configuration interfaces
export interface ScoringConfig {
  default_deduction: number
  max_deduction: number
  weight_factor: number
  custom_scoring_rules?: CustomScoringRule[]
}

export interface CustomScoringRule {
  condition: string
  deduction: number
  description: string
}

export interface QualityLogicConfig {
  check_type: 'content_analysis' | 'format_validation' | 'time_constraint' | 'cross_reference'
  logic_expression: string
  validation_criteria: ValidationCriteria[]
  llm_prompt_template?: string
  expected_patterns?: string[]
  exclusion_patterns?: string[]
}

export interface ValidationCriteria {
  field: string
  operator: 'exists' | 'equals' | 'contains' | 'matches' | 'greater_than' | 'less_than'
  value?: string | number
  description: string
}

export interface RuleTemplateConfig {
  template_id: string
  template_name: string
  default_parameters: Record<string, unknown>
  customizable_fields: string[]
}

export interface AuditConfig {
  track_changes: boolean
  approval_required: boolean
  change_reason_required: boolean
  audit_retention_days: number
}

export interface DepartmentOverride {
  department_id: string
  department_name: string
  override_config: Partial<EnhancedQCRule>
  effective_date: string
  created_by: string
}

// Main Enhanced QC Rule interface
export interface EnhancedQCRule {
  id: string
  rule_code: string
  name: string
  description: string
  category: RuleCategory
  severity: 'critical' | 'major' | 'minor'
  
  // Document applicability
  applicable_documents: DocumentType[]
  
  // Implementation configuration
  rule_implementation: RuleImplementationType
  alert_level: AlertLevel
  
  // Scoring and evaluation
  scoring_config: ScoringConfig
  max_score: number
  weight: number
  
  // Quality control logic
  quality_logic: QualityLogicConfig
  
  // System integration
  core_system_related: boolean
  template_config?: RuleTemplateConfig
  audit_config: AuditConfig
  department_overrides: DepartmentOverride[]
  
  // Metadata
  version: string
  is_active: boolean
  created_at: string
  updated_at: string
  created_by: string
  updated_by: string
}

// LLM Integration interfaces
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

export interface GeneratedPrompt {
  systemMessage: string
  userPrompt: string
  parameters: {
    temperature: number
    maxTokens: number
    responseFormat: string
  }
  expectedOutputSchema?: any
}

// Medical data interfaces for QC context
export interface MedicalDocument {
  id: string
  type: DocumentType
  content: string
  timestamp: string
  author?: string
  status: string
  sections?: DocumentSection[]
}

export interface DocumentSection {
  name: string
  content: string
  required: boolean
  order: number
}

export interface MedicalOrder {
  id: string
  type: string
  content: string
  timestamp: string
  status: string
  medicationName?: string
  dosage?: string
  frequency?: string
}

export interface LabReport {
  id: string
  type: string
  result: string
  timestamp: string
  abnormalFindings?: string[]
  normalRanges?: Record<string, string>
}

export interface MedicalTimeline {
  events: TimelineEvent[]
  admissionTime: string
  dischargeTime?: string
}

export interface TimelineEvent {
  timestamp: string
  type: string
  description: string
  documentId?: string
  significance: 'high' | 'medium' | 'low'
}

// QC execution context and results
export interface QCExecutionContext {
  patientId: string
  documents: MedicalDocument[]
  orders?: MedicalOrder[]
  reports?: LabReport[]
  timeline?: MedicalTimeline
  departmentId?: string
  executionId: string
  requestedRules?: string[]
}

export interface QCFinding {
  type: string
  severity: AlertLevel
  description: string
  location?: string
  evidence?: string
  recommendation: string
  scoreDeduction: number
  confidence?: number
}

export interface QCRuleResult {
  ruleId: string
  ruleName: string
  ruleCode: string
  isCompliant: boolean
  score: number
  findings: QCFinding[]
  confidence: number
  executionTime: number
  medicalReasoning?: string
  error?: string
}

export interface ComprehensiveQCResult {
  executionId: string
  patientId: string
  overallScore: number
  riskLevel: 'low' | 'medium' | 'high' | 'critical'
  ruleResults: QCRuleResult[]
  summary: string
  executionTime: number
  timestamp: string
  crossRuleAnalysis?: {
    correlatedIssues: string
    systemicProblems: string
    priorityRecommendations: string
  }
}

// Filter and query interfaces
export interface EnhancedRuleFilter {
  document_type?: DocumentType
  implementation_type?: RuleImplementationType
  alert_level?: AlertLevel
  core_system_only?: boolean
  department_id?: string
  search?: string
  ruleIds?: string[]
  category?: RuleCategory
}

export interface CreateEnhancedRuleRequest {
  rule_code: string
  name: string
  description: string
  applicable_documents: DocumentType[]
  rule_implementation: RuleImplementationType
  alert_level: AlertLevel
  scoring_config: ScoringConfig
  quality_logic: QualityLogicConfig
  core_system_related: boolean
  category: RuleCategory
  severity: 'critical' | 'major' | 'minor'
  max_score: number
  weight: number
  template_config?: RuleTemplateConfig
  is_active: boolean
}

// Batch operation interfaces
export interface BatchUpdateRequest {
  ruleIds: string[]
  updates: Partial<EnhancedQCRule>
  reason: string
}

export interface BatchUpdateResult {
  successCount: number
  errorCount: number
  errors: string[]
  updatedRules: string[]
}

// Import/Export interfaces
export interface RuleExportConfig {
  ruleIds: string[]
  includeAuditHistory: boolean
  includeTemplateConfig: boolean
  format: 'json' | 'csv' | 'excel'
}

export interface RuleImportConfig {
  data: any
  conflictResolution: 'skip' | 'overwrite' | 'merge'
  validateBeforeImport: boolean
  createBackup: boolean
}

export interface ImportResult {
  importedCount: number
  skippedCount: number
  errorCount: number
  errors: string[]
  warnings: string[]
}

// Template and configuration interfaces
export interface RuleTemplate {
  id: string
  templateName: string
  templateCategory: string
  description: string
  templateConfig: any
  applicableDepartments: string[]
  isDefault: boolean
  createdAt: string
  updatedAt: string
  createdBy: string
}

// Audit and versioning interfaces
export interface RuleAuditLog {
  id: string
  ruleId: string
  action: 'CREATE' | 'UPDATE' | 'DELETE' | 'BATCH_UPDATE' | 'IMPORT' | 'EXPORT'
  oldData?: any
  newData?: any
  changeReason?: string
  createdAt: string
  createdBy: string
}

export interface RuleVersion {
  id: string
  ruleId: string
  version: string
  ruleData: any
  changeSummary?: string
  createdAt: string
  createdBy: string
}
