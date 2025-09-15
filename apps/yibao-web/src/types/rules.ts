// 规则相关类型定义

export type RuleSeverity = 'info' | 'warn' | 'block'

export type RuleType =
  | 'drug_age'
  | 'drug_gender'
  | 'visit_type'
  | 'drug_hospital_level'
  | 'drug_insurance_type'
  | 'hospital_level'
  | 'duration'
  | 'surgery_pricing'

export type RuleCategory = 
  | 'batch_1' 
  | 'batch_2' 
  | 'batch_3' 
  | 'batch_4' 
  | 'batch_5'

export type ActionType = 'intercept' | 'warn' | 'notify'

export interface Rule {
  id: number
  code: string
  name: string
  description?: string
  rule_type: RuleType
  category_id: RuleCategory
  severity: RuleSeverity
  enabled: boolean
  version: number
  priority?: number
  metadata?: Record<string, any>
  created_at: string
  updated_at: string
  
  // 统计字段
  trigger_count?: number
  condition_count?: number
  action_count?: number
  hit_count?: number
}

export interface RuleTrigger {
  id: number
  rule_id: number
  event_type: string
  priority: number
  description?: string
}

export interface RuleCondition {
  id: number
  rule_id: number
  priority: number
  expression_json: ConditionExpression
}

export interface RuleAction {
  id: number
  rule_id: number
  action_type: ActionType
  message_template: string
}

// 条件表达式类型
export interface ConditionExpression {
  all?: ConditionExpression[]
  any?: ConditionExpression[]
  fact?: string
  op?: ConditionOperator
  value?: any
}

export type ConditionOperator = 
  | '==' 
  | '!=' 
  | '>' 
  | '>=' 
  | '<' 
  | '<=' 
  | 'in' 
  | 'not_in'

// 规则统计信息
export interface RuleStatistics {
  total: number
  enabled: number
  disabled: number
  bySeverity: {
    info: number
    warn: number
    block: number
  }
  byType: Record<RuleType, number>
  byCategory: Record<RuleCategory, number>
}

// 规则创建/更新请求
export interface CreateRuleRequest {
  rule: Omit<Rule, 'id' | 'created_at' | 'updated_at'>
  conditions: Omit<RuleCondition, 'id' | 'rule_id'>[]
  actions: Omit<RuleAction, 'id' | 'rule_id'>[]
  triggers: Omit<RuleTrigger, 'id' | 'rule_id'>[]
}

export interface UpdateRuleRequest extends CreateRuleRequest {
  rule: Omit<Rule, 'created_at' | 'updated_at'>
}

// 规则查询参数
export interface RuleQueryParams {
  page?: number
  pageSize?: number
  keyword?: string
  enabled?: boolean
  severity?: RuleSeverity
  rule_type?: RuleType
  category_id?: RuleCategory
  updated_after?: string
  updated_before?: string
  sort_by?: 'created_at' | 'updated_at' | 'name' | 'code'
  sort_order?: 'asc' | 'desc'
}

// 规则查询响应
export interface RuleQueryResponse {
  data: Rule[]
  total: number
  page: number
  pageSize: number
}

// 规则验证结果
export interface RuleValidationResult {
  valid: boolean
  errors: string[]
  warnings: string[]
}

// 规则测试请求
export interface RuleTestRequest {
  rule_id: number
  test_data: {
    patient: {
      age: number
      gender: string
      [key: string]: any
    }
    visit: {
      type: string
      [key: string]: any
    }
    order: {
      drug_code?: string
      service_code?: string
      [key: string]: any
    }
  }
}

// 规则测试结果
export interface RuleTestResult {
  rule_id: number
  matched: boolean
  severity: RuleSeverity
  action_type: ActionType
  message: string
  execution_time: number
  details: {
    conditions_matched: boolean[]
    triggered_actions: RuleAction[]
  }
}

// 规则执行日志
export interface RuleExecutionLog {
  id: number
  rule_id: number
  visit_id: string
  patient_id?: string
  matched: boolean
  severity: RuleSeverity
  action_type: ActionType
  message: string
  context_data: Record<string, any>
  execution_time: number
  created_at: string
}

// 规则版本历史
export interface RuleVersion {
  id: number
  rule_id: number
  version: number
  changes: string
  created_by: string
  created_at: string
  rule_data: Rule
  conditions_data: RuleCondition[]
  actions_data: RuleAction[]
  triggers_data: RuleTrigger[]
}

// 规则导入/导出
export interface RuleExportData {
  rules: Rule[]
  conditions: RuleCondition[]
  actions: RuleAction[]
  triggers: RuleTrigger[]
  metadata: {
    export_time: string
    export_by: string
    version: string
  }
}

export interface RuleImportResult {
  success: number
  failed: number
  errors: string[]
  imported_rules: Rule[]
}

// 规则模板
export interface RuleTemplate {
  id: string
  name: string
  description: string
  rule_type: RuleType
  category_id: RuleCategory
  template_data: {
    rule: Partial<Rule>
    conditions: Partial<RuleCondition>[]
    actions: Partial<RuleAction>[]
    triggers: Partial<RuleTrigger>[]
  }
}

// 规则配置选项
export interface RuleConfigOptions {
  severities: Array<{ label: string; value: RuleSeverity; description: string }>
  types: Array<{ label: string; value: RuleType; description: string }>
  categories: Array<{ label: string; value: RuleCategory; description: string }>
  actionTypes: Array<{ label: string; value: ActionType; description: string }>
  operators: Array<{ label: string; value: ConditionOperator; description: string }>
  eventTypes: Array<{ label: string; value: string; description: string }>
}

// API 响应包装类型
export interface ApiResponse<T = any> {
  success: boolean
  data?: T
  message?: string
  error?: string
}

// 分页响应类型
export interface PaginatedResponse<T = any> {
  data: T[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}
