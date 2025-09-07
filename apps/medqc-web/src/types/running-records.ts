// 运行病历相关类型定义

// 查询条件类型
export interface QueryConditions {
  timeRange: string
  customTimeRange?: [string, string]
  scoringStandard: string
  searchType: string
  searchValue: string
}

// 筛选条件类型
export interface FilterConditions {
  defectStatus?: string[]
  auditStatus?: string[]
  department?: string[]
  doctor?: string[]
  priority?: string[]
  [key: string]
}

// 快捷筛选模板类型
export interface FilterTemplate {
  id: string
  name: string
  conditions: FilterConditions
  createTime: string
  updateTime: string
}

// 缺陷记录类型
export interface DefectRecord {
  id: string
  registrationNo: string
  serialNo: string
  caseNo: string
  patientName: string
  department: string
  doctor: string
  defectType: string
  defectDescription: string
  defectStatus: 'pending' | 'urged' | 'rectified' | 'appealed'
  priority: 'high' | 'medium' | 'low'
  createTime: string
  updateTime: string
  score: number
  scoringStandard: string
}

// 病历记录类型
export interface MedicalRecord {
  id: string
  registrationNo: string
  serialNo: string
  caseNo: string
  patientName: string
  department: string
  doctor: string
  auditStatus: 'pending' | 'reviewing' | 'passed' | 'questioned'
  score: number
  scoringStandard: string
  defectCount: number
  createTime: string
  updateTime: string
  isUrgent: boolean
}

// 病历详情类型
export interface MedicalRecordDetail {
  basicInfo: {
    registrationNo: string
    serialNo: string
    caseNo: string
    patientName: string
    department: string
    doctor: string
    score: number
    scoringStandard: string
  }
  defects: DefectRecord[]
  documents: DocumentSection[]
  operationHistory: OperationRecord[]
}

// 文档章节类型
export interface DocumentSection {
  id: string
  name: string
  type: string
  content: string
  defects: DefectRecord[]
}

// 操作记录类型
export interface OperationRecord {
  id: string
  type: 'urge' | 'rectify' | 'audit' | 'comment'
  operator: string
  operateTime: string
  description: string
  result?: string
}

// 批量操作结果类型
export interface BatchOperationResult {
  total: number
  success: number
  failed: number
  failedItems: Array<{
    id: string
    reason: string
  }>
}

// 导出参数类型
export interface ExportParams {
  type: 'defects' | 'records' | 'qc-details'
  conditions: QueryConditions & FilterConditions
  maxCount: number
}

// 分页参数类型
export interface PaginationParams {
  current: number
  pageSize: number
  total: number
}

// API响应类型
export interface ApiResponse<T> {
  code: number
  message: string
  data: T
  success: boolean
}

// 列表响应类型
export interface ListResponse<T> {
  list: T[]
  pagination: PaginationParams
}
