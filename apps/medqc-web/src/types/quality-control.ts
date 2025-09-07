// 质控点相关类型定义

export interface QualityControlPoint {
  id: string
  name: string
  source: string
  category: string
  type: string
  coreSystem?: string
  document: string
  onlineDate?: string
  lastOperator?: string
  enabled?: boolean
  status: 'online' | 'offline' | 'draft'
  lastOperationDate?: string
  managementSystem?: string
  coreSystemCategory?: string
  infoCategory?: string
  significance?: string
  errorExample?: string
  createTime?: string
  updateTime?: string
}

export interface QualityControlPointForm {
  name: string
  category: string
  type: string
  document: string
  coreSystemCategory?: string
  infoCategory?: string
  managementSystem?: string
  source?: string
  significance?: string
  errorExample?: string
}

export interface QualityControlRule {
  id: string
  pointId: string
  conditions: QualityControlCondition[]
  logicOperator: 'AND' | 'OR'
  createTime: string
  updateTime: string
}

export interface QualityControlCondition {
  id: string
  type: 'normal' | 'time' | 'group'
  field: string
  operator: string
  value: string | number
  timeUnit?: 'hour' | 'day' | 'month' | 'year'
  constraints?: QualityControlConstraint[]
}

export interface QualityControlConstraint {
  id: string
  field: string
  operator: string
  value: string | number
}

export interface QualityControlTestCase {
  id: string
  name: string
  description?: string
  medicalRecordId: string
  expectedResult: boolean
  actualResult?: boolean
  testStatus: 'pending' | 'passed' | 'failed'
  createTime: string
  updateTime?: string
}

export interface QualityControlSearchParams {
  keyword?: string
  searchType?: 'id' | 'name'
  category?: string
  type?: string
  status?: string
  enabled?: boolean
  page?: number
  pageSize?: number
}

export interface QualityControlBatchOperation {
  action: 'enable' | 'disable' | 'online' | 'offline' | 'delete'
  pointIds: string[]
}

// API 响应类型
export interface QualityControlPointListResponse {
  data: QualityControlPoint[]
  total: number
  page: number
  pageSize: number
}

export interface QualityControlPointDetailResponse {
  data: QualityControlPoint
}

// 表格列配置类型
export interface TableColumn {
  title: string
  dataIndex: string
  key: string
  width?: number
  sorter?: boolean
  fixed?: 'left' | 'right'
}

// 分页配置类型
export interface PaginationConfig {
  current: number
  pageSize: number
  total: number
  showSizeChanger: boolean
  showQuickJumper: boolean
  showTotal: (total: number, range: [number, number]) => string
  pageSizeOptions: string[]
}
