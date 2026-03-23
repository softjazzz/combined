// @ts-nocheck
// 杩愯鐥呭巻鐩稿叧绫诲瀷瀹氫箟

// 鏌ヨ鏉′欢绫诲瀷
export interface QueryConditions {
  timeRange: string
  customTimeRange?: [string, string]
  scoringStandard: string
  searchType: string
  searchValue: string
}

// 绛涢€夋潯浠剁被鍨?
export interface FilterConditions {
  defectStatus?: string[]
  auditStatus?: string[]
  department?: string[]
  doctor?: string[]
  priority?: string[]
  [key: string]
}

// 蹇嵎绛涢€夋ā鏉跨被鍨?
export interface FilterTemplate {
  id: string
  name: string
  conditions: FilterConditions
  createTime: string
  updateTime: string
}

// 缂洪櫡璁板綍绫诲瀷
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

// 鐥呭巻璁板綍绫诲瀷
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

// 鐥呭巻璇︽儏绫诲瀷
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

// 鏂囨。绔犺妭绫诲瀷
export interface DocumentSection {
  id: string
  name: string
  type: string
  content: string
  defects: DefectRecord[]
}

// 鎿嶄綔璁板綍绫诲瀷
export interface OperationRecord {
  id: string
  type: 'urge' | 'rectify' | 'audit' | 'comment'
  operator: string
  operateTime: string
  description: string
  result?: string
}

// 鎵归噺鎿嶄綔缁撴灉绫诲瀷
export interface BatchOperationResult {
  total: number
  success: number
  failed: number
  failedItems: Array<{
    id: string
    reason: string
  }>
}

// 瀵煎嚭鍙傛暟绫诲瀷
export interface ExportParams {
  type: 'defects' | 'records' | 'qc-details'
  conditions: QueryConditions & FilterConditions
  maxCount: number
}

// 鍒嗛〉鍙傛暟绫诲瀷
export interface PaginationParams {
  current: number
  pageSize: number
  total: number
}

// API鍝嶅簲绫诲瀷
export interface ApiResponse<T> {
  code: number
  message: string
  data: T
  success: boolean
}

// 鍒楄〃鍝嶅簲绫诲瀷
export interface ListResponse<T> {
  list: T[]
  pagination: PaginationParams
}

