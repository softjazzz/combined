/**
 * 测试病历模块类型定义
 * 对应 PRD 中的测试病历管理核心数据结构
 */

// 病历复杂度
export type RecordComplexity = 'simple' | 'medium' | 'complex' | 'very_complex'

// 病历状态
export type RecordStatus = 'draft' | 'ready' | 'verified' | 'archived'

// 质控等级
export type ExpectedGrade = 'A' | 'B' | 'C'

// 列表记录
export interface TestMedicalRecordSummary {
  id: string
  recordCode: string
  name: string
  type: string
  department: string
  diseaseCategory: string
  complexity: RecordComplexity
  createdAt: string
  updatedAt: string
  createdBy: string
  status: RecordStatus
  relatedRuleCount: number
  passRate: number
  tags: string[]
}

// 病历详情内容
export interface TestMedicalRecordDetail extends TestMedicalRecordSummary {
  description?: string
  expectedGrade?: ExpectedGrade
  expectedScoreRange?: [number, number]
  expectedDefectTypes?: string[]
  expectedDefectCount?: number
  checkpoints?: Array<{
    id: string
    title: string
    description: string
    priority: 'high' | 'medium' | 'low'
  }>
  content: string
}

// 查询条件
export interface RecordSearchConditions {
  keyword?: string
  keywordType?: 'id' | 'name' | 'creator'
  recordType?: string[]
  departments?: string[]
  diseaseCategories?: string[]
  complexity?: RecordComplexity[]
  status?: RecordStatus[]
  tags?: string[]
  createdTimeRange?: [string, string]
  passRateGreaterThan?: number
  passRateLessThan?: number
}

// 批量操作
export interface BatchActionPayload {
  action: 'delete' | 'export' | 'duplicate' | 'updateStatus' | 'associateRules'
  recordIds: string[]
  targetStatus?: RecordStatus
  targetRuleIds?: string[]
}

// 分页
export interface PaginationState {
  current: number
  pageSize: number
  total: number
}

// 列表响应
export interface RecordListResponse {
  items: TestMedicalRecordSummary[]
  pagination: PaginationState
}

// API 标准响应
export interface ApiResponse<T> {
  success: boolean
  message?: string
  data: T
}

// 快速筛选模板
export interface FilterTemplate {
  id: string
  name: string
  conditions: RecordSearchConditions
  createdAt: string
  updatedAt: string
}

// 快速过滤标签
export interface QuickFilterTag {
  key: string
  label: string
  conditions: Partial<RecordSearchConditions>
}
