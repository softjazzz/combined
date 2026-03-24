export type RuleTypeValue =
  | 'all'
  | 'main_diagnosis'
  | 'other_diagnosis'
  | 'main_procedure'
  | 'other_procedure'

export type RuleStatus = 'published' | 'draft' | 'disabled'
export type RuleRiskLevel = 'high' | 'medium' | 'low'

export interface RuleListItem {
  id: string
  name: string
  ruleType: string
  status: RuleStatus
  riskLevel: RuleRiskLevel
  conditionSummary: string
  hitCount7d: number
  hitRate7d?: number
  updatedAt: string
  updatedBy: string
  conflictFlag?: boolean
  falsePositiveHighFlag?: boolean
}

export interface RuleConditionLeaf {
  field: string
  comparator: string
  value: string | number | boolean | string[]
}

export interface RuleConditionGroup {
  operator: 'AND' | 'OR'
  children: Array<RuleConditionGroup | RuleConditionLeaf>
}

export interface RuleDetail {
  id: string
  name: string
  description?: string
  ruleType: string
  status: RuleStatus
  riskLevel: RuleRiskLevel
  conditionTree: RuleConditionGroup
  suggestionText?: string
  updatedAt?: string
  updatedBy?: string
}

export interface RuleChangeLogItem {
  id: string
  time: string
  operator: string
  action: 'save_draft' | 'publish' | 'disable' | 'rollback'
  ruleCount?: number
  impactCount?: number
  version?: string
  result?: 'success' | 'failed'
  rollbackable?: boolean
}
