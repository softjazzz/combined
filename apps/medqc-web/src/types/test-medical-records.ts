/**
 * 测试病历管理类型定义（V3.6 P1-E3 合同第 2 节）
 * 后端：/api/v1/qc/sample-pools/test-records，固定池 customer-created-test-records-v1。
 */

/** 条目状态由后端依据 include_in_batch_1 / exclude_reason 推导，前端只搬运。 */
export type TestRecordState = 'active' | 'removed' | 'superseded' | 'unknown'

/** created：页面新建；derived：由派生可编辑副本生成。 */
export type TestRecordOrigin = 'created' | 'derived'

export interface TestRecordItem {
  id: string
  institute_id: string
  patient_id: string
  visit_id: string
  case_title: string
  patient_name: string
  department: string
  mr_no: string
  /** 旧条目未记录文书数时为 null，页面显示“未知”。 */
  document_count: number | null
  rule_ids: string[]
  rule_count: number
  latest_job_id: string
  bundle_status: string
  origin: TestRecordOrigin
  /** CDM 只读取得的人口学字段；缺失为 null，不推断、不默认。 */
  sex: string | null
  age: number | null
  admission_time: string | null
  /** 编辑派生时被替换的旧条目 ID。 */
  source_item_id: string
  state: TestRecordState
  removed: boolean
  superseded_by: string | null
  created_at: string | null
  /** CAS 令牌：原样回传给写接口。 */
  updated_at: string
}

export interface TestRecordListQuery {
  include_removed?: boolean
  q?: string
  page: number
  page_size: number
}

export interface TestRecordListResult {
  items: TestRecordItem[]
  total: number
  page: number
  page_size: number
}

export type RuleSetEntryState = 'active' | 'paused' | 'offline'

/** 当前规则集版本详情中的单条规则；qc_point/source_document 缺失时为 null，不猜名称。 */
export interface RuleSetRuleOption {
  rule_id: string
  state: RuleSetEntryState
  qc_point: string | null
  source_document: string | null
  executable?: boolean
}

export interface CurrentRuleSetCatalog {
  rule_set_key: string
  version: string
  entries: RuleSetRuleOption[]
}

/** 编辑抽屉中的文书草稿。 */
export interface TestRecordDocumentDraft {
  key: string
  document_type: string
  title: string
  record_time?: string
  submit_time?: string
  content: string
  doctor_name?: string
  doctor_code?: string
  enabled: boolean
}

export interface TestRecordImportValidationIssue {
  sheet: string
  row: number
  field: string
  message: string
}

export interface TestRecordImportRowResult {
  case_key: string
  case_row: number
  document_rows: number[]
  status: 'created' | 'unknown'
  message: string
  item_id?: string
  institute_id?: string
  patient_id?: string
  visit_id?: string
  bundle_status?: string
}

export interface TestRecordImportResult {
  total: number
  created: number
  unknown: number
  results: TestRecordImportRowResult[]
}

export interface TestRecordImportResponse {
  success: boolean
  data?: TestRecordImportResult
  message: string
  validationErrors: TestRecordImportValidationIssue[]
  /** 请求没有得到服务端确认，可能已经写入，页面必须阻止用户盲目重试。 */
  resultUnknown: boolean
}
