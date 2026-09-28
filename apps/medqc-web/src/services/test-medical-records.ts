/**
 * 测试病历管理服务（V3.6 P1-E3）：全部走真实接口，不含 mock 数据。
 * - 列表 / 关联质控点 / 移除：/api/v1/qc/sample-pools/test-records
 * - 编辑：复用 POST /test-records 派生新副本，并以 supersedes_item_id 标记旧条目被替换
 * - 运行：复用 POST /{pool_id}/run（固定池 + 三坐标）
 * - 规则元数据：当前规则集版本详情 /api/v1/rule-set-versions
 */
import { ApiService } from '@/services/apiService'
import {
  createManualTestMedicalRecord,
  getEditableMedicalRecordDocuments,
  runManualSamplePool,
  type ManualSamplePoolRunPayload,
} from '@/services/manual-case-sample-service'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'
import type {
  CurrentRuleSetCatalog,
  RuleSetEntryState,
  RuleSetRuleOption,
  TestRecordDocumentDraft,
  TestRecordItem,
  TestRecordListQuery,
  TestRecordListResult,
  TestRecordImportResponse,
  TestRecordImportResult,
  TestRecordImportValidationIssue,
} from '@/types/test-medical-records'
import type { ManualTestRecordCreateRequest } from '@/views/workstation-v4/customer-sample-validation/types'

export const CUSTOMER_TEST_POOL_ID = 'customer-created-test-records-v1'
/** 测试病历按泸县0609客户规则集验证，与新建测试病历页一致。 */
export const TEST_RECORD_RULE_SET_KEY = 'luxian_0609_qc_v1'
const TEST_RECORDS_URL = '/api/v1/qc/sample-pools/test-records'
const RUN_TIMEOUT_MS = 90000
const IMPORT_TIMEOUT_MS = 15 * 60 * 1000
export const TEST_RECORD_IMPORT_MAX_BYTES = 5 * 1024 * 1024
export const TEST_RECORD_IMPORT_MAX_CASES = 20

export type ServiceResult<T> = {
  success: boolean
  data?: T
  message?: string
}

async function requestEnvelope<T>(
  config: Parameters<typeof ApiService.requestRaw>[0],
  fallbackMessage: string,
): Promise<ServiceResult<T>> {
  try {
    const response = await ApiService.requestRaw<T>(config)
    const normalized = normalizeApiSuccess<T>(response.data)
    return {
      success: normalized.success,
      data: normalized.data,
      message: normalized.success ? normalized.message : normalized.message || fallbackMessage,
    }
  } catch (error) {
    return { success: false, message: extractApiErrorMessageFromError(error, fallbackMessage) }
  }
}

export function listTestRecords(query: TestRecordListQuery) {
  return requestEnvelope<TestRecordListResult>(
    {
      method: 'GET',
      url: TEST_RECORDS_URL,
      params: {
        page: query.page,
        page_size: query.page_size,
        ...(query.include_removed ? { include_removed: true } : {}),
        ...(query.q?.trim() ? { q: query.q.trim() } : {}),
      },
    },
    '获取测试病历失败',
  )
}

export function updateTestRecordRules(item: Pick<TestRecordItem, 'id' | 'updated_at'>, ruleIds: string[]) {
  return requestEnvelope<TestRecordItem>(
    {
      method: 'PUT',
      url: `${TEST_RECORDS_URL}/${encodeURIComponent(item.id)}/rules`,
      data: { rule_ids: ruleIds, updated_at: item.updated_at },
    },
    '更新关联质控点失败',
  )
}

export function removeTestRecord(item: Pick<TestRecordItem, 'id' | 'updated_at'>) {
  return requestEnvelope<TestRecordItem>(
    {
      method: 'DELETE',
      url: `${TEST_RECORDS_URL}/${encodeURIComponent(item.id)}`,
      params: { updated_at: item.updated_at },
    },
    '移除测试病历失败',
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function validationIssuesFromError(error: unknown): TestRecordImportValidationIssue[] {
  if (!error || typeof error !== 'object') return []
  const response = (error as { response?: { data?: unknown } }).response
  const body = response?.data
  if (!isRecord(body)) return []
  const detail = isRecord(body.detail) ? body.detail : isRecord(body.error) ? body.error : null
  if (!detail) return []
  const errors = detail.errors
  if (!Array.isArray(errors)) return []
  return errors
    .map((item): TestRecordImportValidationIssue | null => {
      if (!item || typeof item !== 'object') return null
      const row = item as Record<string, unknown>
      if (
        typeof row.sheet !== 'string' ||
        typeof row.row !== 'number' ||
        typeof row.field !== 'string' ||
        typeof row.message !== 'string'
      ) {
        return null
      }
      return { sheet: row.sheet, row: row.row, field: row.field, message: row.message }
    })
    .filter((item): item is TestRecordImportValidationIssue => Boolean(item))
}

function isImportCount(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0
}

function normalizeImportResult(value: unknown): TestRecordImportResult | null {
  if (!isRecord(value)
    || !isImportCount(value.total)
    || value.total < 1
    || !isImportCount(value.created)
    || !isImportCount(value.unknown)
    || value.total > TEST_RECORD_IMPORT_MAX_CASES
    || !Array.isArray(value.results)
    || value.results.length !== value.total
    || value.created + value.unknown !== value.total) {
    return null
  }
  const results = value.results.map((raw): TestRecordImportResult['results'][number] | null => {
    if (!isRecord(raw)
      || typeof raw.case_key !== 'string'
      || !raw.case_key.trim()
      || !isImportCount(raw.case_row)
      || raw.case_row < 2
      || !Array.isArray(raw.document_rows)
      || raw.document_rows.length === 0
      || !raw.document_rows.every((row) => isImportCount(row) && row >= 2)
      || (raw.status !== 'created' && raw.status !== 'unknown')
      || typeof raw.message !== 'string'
      || !raw.message.trim()) {
      return null
    }
    const optionalKeys = ['item_id', 'institute_id', 'patient_id', 'visit_id', 'bundle_status'] as const
    if (optionalKeys.some((key) => raw[key] !== undefined && typeof raw[key] !== 'string')) return null
    if (raw.status === 'created'
      && ['item_id', 'institute_id', 'patient_id', 'visit_id'].some((key) => {
        const text = raw[key]
        return typeof text !== 'string' || !text.trim()
      })) {
      return null
    }
    return {
      case_key: raw.case_key,
      case_row: raw.case_row,
      document_rows: raw.document_rows as number[],
      status: raw.status,
      message: raw.message,
      ...(typeof raw.item_id === 'string' ? { item_id: raw.item_id } : {}),
      ...(typeof raw.institute_id === 'string' ? { institute_id: raw.institute_id } : {}),
      ...(typeof raw.patient_id === 'string' ? { patient_id: raw.patient_id } : {}),
      ...(typeof raw.visit_id === 'string' ? { visit_id: raw.visit_id } : {}),
      ...(typeof raw.bundle_status === 'string' ? { bundle_status: raw.bundle_status } : {}),
    }
  })
  if (results.some((item) => item === null)) return null
  const normalized = results as TestRecordImportResult['results']
  if (new Set(normalized.map((item) => item.case_key)).size !== normalized.length
    || new Set(normalized.map((item) => item.case_row)).size !== normalized.length) {
    return null
  }
  if (normalized.filter((item) => item.status === 'created').length !== value.created
    || normalized.filter((item) => item.status === 'unknown').length !== value.unknown) {
    return null
  }
  return { total: value.total, created: value.created, unknown: value.unknown, results: normalized }
}

export async function downloadTestRecordImportTemplate(): Promise<ServiceResult<Blob>> {
  try {
    const response = await ApiService.requestRaw<Blob>({
      method: 'GET',
      url: `${TEST_RECORDS_URL}/import-template`,
      responseType: 'blob',
      timeout: 60000,
    })
    if (!(response.data instanceof Blob) || response.data.size === 0) {
      return { success: false, message: '下载的测试病历导入模板无效' }
    }
    return { success: true, data: response.data }
  } catch (error) {
    return {
      success: false,
      message: extractApiErrorMessageFromError(error, '下载测试病历导入模板失败'),
    }
  }
}

export async function importTestRecords(file: File): Promise<TestRecordImportResponse> {
  if (!file.name.toLowerCase().endsWith('.xlsx')) {
    return {
      success: false,
      message: '仅支持 .xlsx 测试病历模板',
      validationErrors: [],
      resultUnknown: false,
    }
  }
  if (file.size > TEST_RECORD_IMPORT_MAX_BYTES) {
    return {
      success: false,
      message: '文件不能超过 5 MiB',
      validationErrors: [],
      resultUnknown: false,
    }
  }
  const form = new FormData()
  form.append('file', file)
  try {
    const response = await ApiService.requestRaw<TestRecordImportResult>({
      method: 'POST',
      url: `${TEST_RECORDS_URL}/import`,
      data: form,
      timeout: IMPORT_TIMEOUT_MS,
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    const normalized = normalizeApiSuccess<TestRecordImportResult>(response.data)
    if (!normalized.success) {
      return {
        success: false,
        message: '服务端未返回可确认的逐病例结果。请先刷新列表核对，不要盲目重试',
        validationErrors: [],
        resultUnknown: true,
      }
    }
    const data = normalizeImportResult(normalized.data)
    if (!data) {
      return {
        success: false,
        message: '服务端返回的逐病例结果格式异常，状态无法确认。请先刷新列表核对，不要盲目重试',
        validationErrors: [],
        resultUnknown: true,
      }
    }
    return {
      success: true,
      data,
      message: normalized.message || '测试病历导入已完成',
      validationErrors: [],
      resultUnknown: false,
    }
  } catch (error) {
    const validationErrors = validationIssuesFromError(error)
    const response = error && typeof error === 'object'
      ? (error as { response?: { status?: number } }).response
      : undefined
    const status = response?.status
    const rejectedBeforeWrite = status === 401 || status === 403 || status === 422
    const resultUnknown = !rejectedBeforeWrite
    return {
      success: false,
      message: resultUnknown
        ? '导入请求未获得可确认的服务端结果，可能已写入。请勿盲目重试，先刷新列表核对'
        : extractApiErrorMessageFromError(error, '导入测试病历失败'),
      validationErrors,
      resultUnknown,
    }
  }
}

const ENTRY_STATES: RuleSetEntryState[] = ['active', 'paused', 'offline']

function normalizeRuleEntries(value: unknown): RuleSetRuleOption[] {
  if (!Array.isArray(value)) return []
  return value
    .map((raw): RuleSetRuleOption | null => {
      if (!raw || typeof raw !== 'object') return null
      const row = raw as Record<string, unknown>
      const ruleId = typeof row.rule_id === 'string' ? row.rule_id.trim() : ''
      const state = ENTRY_STATES.find((item) => item === row.state)
      if (!ruleId || !state) return null
      return {
        rule_id: ruleId,
        state,
        qc_point: typeof row.qc_point === 'string' && row.qc_point.trim() ? row.qc_point : null,
        source_document:
          typeof row.source_document === 'string' && row.source_document.trim()
            ? row.source_document
            : null,
        ...(typeof row.executable === 'boolean' ? { executable: row.executable } : {}),
      }
    })
    .filter((item): item is RuleSetRuleOption => Boolean(item))
}

/** 读取当前规则集版本的规则全集（与后端关联校验的集合一致）。 */
export async function getCurrentRuleSetCatalog(): Promise<ServiceResult<CurrentRuleSetCatalog>> {
  const listResult = await requestEnvelope<{ current_version?: string }>(
    { method: 'GET', url: '/api/v1/rule-set-versions', params: { rule_set_key: TEST_RECORD_RULE_SET_KEY } },
    '读取当前规则集版本失败',
  )
  const version = String(listResult.data?.current_version || '').trim()
  if (!listResult.success || !version) {
    return { success: false, message: listResult.message || '读取当前规则集版本失败' }
  }
  const detailResult = await requestEnvelope<{ entries?: unknown }>(
    {
      method: 'GET',
      url: `/api/v1/rule-set-versions/${encodeURIComponent(TEST_RECORD_RULE_SET_KEY)}/${encodeURIComponent(version)}`,
    },
    '读取当前规则集版本详情失败',
  )
  if (!detailResult.success || !detailResult.data) {
    return { success: false, message: detailResult.message }
  }
  return {
    success: true,
    data: {
      rule_set_key: TEST_RECORD_RULE_SET_KEY,
      version,
      entries: normalizeRuleEntries(detailResult.data.entries),
    },
  }
}

/** 仅有效条目且三坐标完整时可运行；身份不明时失败关闭。 */
export function isRunnableTestRecord(item: TestRecordItem): boolean {
  return (
    item.state === 'active' &&
    Boolean(item.institute_id.trim() && item.patient_id.trim() && item.visit_id.trim())
  )
}

/** 多条病历的默认运行规则：各自关联质控点的并集（保持首次出现顺序）。 */
export function unionTestRecordRuleIds(items: TestRecordItem[]): string[] {
  const result: string[] = []
  items.forEach((item) => {
    item.rule_ids.forEach((ruleId) => {
      if (!result.includes(ruleId)) result.push(ruleId)
    })
  })
  return result
}

export function buildTestRecordRunPayload(
  items: TestRecordItem[],
  ruleIds: string[],
): ManualSamplePoolRunPayload {
  if (!items.length) throw new Error('请至少选择一条测试病历')
  if (items.some((item) => !isRunnableTestRecord(item))) {
    throw new Error('所选病历存在已移除、已被替换或三坐标不完整的条目')
  }
  const selectedRuleIds = Array.from(new Set(ruleIds.map((id) => id.trim()).filter(Boolean)))
  if (!selectedRuleIds.length) throw new Error('请先选择要运行的质控点')
  return {
    sample_item_ids: items.map((item) => item.id),
    record_refs: items.map((item) => ({
      institute_id: item.institute_id,
      patient_id: item.patient_id,
      visit_id: item.visit_id,
    })),
    selected_rule_ids: selectedRuleIds,
    validation_mode: 'customer',
    rule_set_key: TEST_RECORD_RULE_SET_KEY,
    max_parallel_records: Math.min(items.length, 4),
  }
}

export function runTestRecords(items: TestRecordItem[], ruleIds: string[]) {
  return runManualSamplePool(CUSTOMER_TEST_POOL_ID, buildTestRecordRunPayload(items, ruleIds), {
    timeout: RUN_TIMEOUT_MS,
  })
}

/** 读取测试病历现有文书（只读接口），作为编辑草稿。 */
export async function loadTestRecordDocuments(
  item: TestRecordItem,
): Promise<ServiceResult<TestRecordDocumentDraft[]>> {
  const result = await getEditableMedicalRecordDocuments(item.visit_id, {
    institute_id: item.institute_id,
    patient_id: item.patient_id,
    visit_id: item.visit_id,
  })
  if (!result.success || !result.data) return { success: false, message: result.message }
  return {
    success: true,
    data: result.data.documents.map((document, index) => ({
      key: document.key || `document-${index + 1}`,
      document_type: document.document_type,
      title: document.title,
      record_time: document.record_time || undefined,
      submit_time: document.submit_time || undefined,
      content: document.content || '',
      doctor_name: document.doctor_name,
      doctor_code: document.doctor_code,
      enabled: document.enabled !== false,
    })),
  }
}

/**
 * 病历时间按墙上时间原样传递（后端只取前 19 位、不处理时区），
 * 不做 toISOString 转换，避免整体偏移 8 小时。
 */
export function normalizeWallClock(value?: string | null): string | undefined {
  const text = String(value || '').trim()
  const matched = text.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?/)
  if (!matched) return undefined
  const [, year, month, day, hour = '00', minute = '00', second = '00'] = matched
  const pad = (part: string) => part.padStart(2, '0')
  return `${year}-${pad(month)}-${pad(day)}T${pad(hour)}:${minute}:${second}`
}

export interface TestRecordEditBasics {
  caseTitle: string
  sex: string
  age: number | null
  admissionTime: string
}

/** 编辑抽屉的必填人口学字段：源病历缺失时必须由用户填写，不使用默认值。 */
export function findMissingEditBasics(basics: TestRecordEditBasics): string[] {
  const missing: string[] = []
  if (!basics.sex.trim()) missing.push('性别')
  if (basics.age === null || !Number.isInteger(basics.age) || basics.age < 0 || basics.age > 120) {
    missing.push('年龄')
  }
  if (!normalizeWallClock(basics.admissionTime)) missing.push('入院时间')
  return missing
}

/**
 * 编辑 = 派生可编辑副本：新建病历并指向旧条目；旧条目由后端在同一事务内标记为被替换。
 * 不原地修改 CDM 文书，保留已发布 Bundle 与历史结果。
 */
export function buildTestRecordEditPayload(
  item: TestRecordItem,
  basics: TestRecordEditBasics,
  documents: TestRecordDocumentDraft[],
): ManualTestRecordCreateRequest {
  const enabledDocuments = documents
    .filter((document) => document.enabled && document.content.trim())
    .map((document) => ({
      document_type: document.document_type,
      title: document.title,
      record_time: normalizeWallClock(document.record_time),
      submit_time: normalizeWallClock(document.submit_time),
      content: document.content,
      doctor_name: document.doctor_name,
      doctor_code: document.doctor_code,
      enabled: true,
    }))
  const missing = findMissingEditBasics(basics)
  if (missing.length) throw new Error(`请填写${missing.join('、')}`)
  const admissionTime = normalizeWallClock(basics.admissionTime) as string
  if (!enabledDocuments.length) throw new Error('至少保留一份有正文的文书')
  return {
    case_title: basics.caseTitle.trim() || item.case_title || `${item.patient_name}测试病历`,
    basic_info: {
      patient_name: item.patient_name || '测试患者',
      sex: basics.sex.trim(),
      age: basics.age as number,
      mr_no: undefined,
      department: item.department || '未说明科室',
      admission_time: admissionTime,
    },
    documents: enabledDocuments,
    selected_rule_ids: [...item.rule_ids],
    manual_issue_text: `测试病历编辑副本：替换 ${item.case_title || item.visit_id}。`,
    template_key: 'customer_source_editable_copy',
    source: {
      type: 'customer_source_editable_copy',
      source_pool_id: CUSTOMER_TEST_POOL_ID,
      source_item_ids: [item.id],
      source_visit_id: item.visit_id,
      source_mr_no: item.mr_no,
      source_patient_name: item.patient_name,
      source_department: item.department,
      created_from: 'test_record_management',
      supersedes_item_id: item.id,
      supersedes_updated_at: item.updated_at,
    },
  }
}

export function saveTestRecordEdit(payload: ManualTestRecordCreateRequest) {
  return createManualTestMedicalRecord(payload)
}

export const TEST_RECORD_STATE_LABELS: Record<TestRecordItem['state'], string> = {
  active: '有效',
  removed: '已移除',
  superseded: '已被替换',
  unknown: '未知',
}
