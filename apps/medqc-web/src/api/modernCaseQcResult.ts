import { ApiService } from '@/services/apiService'

/**
 * 统一病历质控快照的来源标识。
 * 结算质控（settlement_qc）与结算生成质控（settlement_generate_qc）是两个独立来源，
 * 请求与响应都必须按原值一一对应，不得合并或互相回退。
 */
export type ModernCaseQcSourceKey =
  | 'frontpage_formal_qc'
  | 'coding_qc'
  | 'settlement_qc'
  | 'settlement_generate_qc'

export const MODERN_CASE_QC_SOURCE_KEYS: readonly ModernCaseQcSourceKey[] = [
  'frontpage_formal_qc',
  'coding_qc',
  'settlement_qc',
  'settlement_generate_qc',
]

const MODERN_CASE_QC_SNAPSHOT_URL = '/api/v1/workstation/case-qc/snapshot'

/** 未显式传 page 时使用的分页默认值：offset 0 / limit 20。 */
export const MODERN_CASE_QC_DEFAULT_OFFSET = 0
export const MODERN_CASE_QC_DEFAULT_DEFECTS_LIMIT = 20
export const MODERN_CASE_QC_MAX_DEFECTS_LIMIT = 50

/**
 * 缺陷分组分页入参。
 * 两个 offset 互相独立（活跃缺陷与本次结果缺陷是两组不同的集合），limit 对两组同时生效。
 * 未传 page 时按默认值 0/0/20 发起请求，分页信封字段同样必须回传。
 */
export interface ModernCaseQcSnapshotPage {
  active_defects_offset?: number
  current_result_defects_offset?: number
  defects_limit?: number
}

/** 请求四维：机构、患者、就诊三坐标 + 来源标识。 */
export interface ModernCaseQcIdentity {
  institute_id: string
  patient_id: string
  visit_id: string
  source_key: ModernCaseQcSourceKey
}

/** 缺陷条目：字段由规则执行器判定，前端只搬运，不重写业务状态与缺陷语义。 */
export interface ModernCaseQcDefect {
  id?: string
  rule_name?: string
  description?: string
  severity?: string
  category?: string
  suggestion?: string
  evidence?: unknown
  location?: string
  status?: string
  [key: string]: unknown
}

export interface ModernCaseQcResultRecord {
  id?: string
  result_id?: string
  status?: string
  created_at?: string
  updated_at?: string
  [key: string]: unknown
}

export interface ModernCaseQcNotification {
  id?: string
  title?: string
  content?: string
  created_at?: string
  [key: string]: unknown
}

export interface ModernCaseQcSnapshot {
  identity_status: 'verified'
  source_key: ModernCaseQcSourceKey
  institute_id: string
  patient_id: string
  visit_id: string
  latest_qc_result: ModernCaseQcResultRecord | null
  recent_results: ModernCaseQcResultRecord[]
  active_defects: ModernCaseQcDefect[]
  current_result_defects: ModernCaseQcDefect[]
  latest_notification: ModernCaseQcNotification | null
  /** 分页信封：两组缺陷各自声明是否还有下一页，以及下一页游标（无下一页为 null）。 */
  active_defects_has_more: boolean
  current_result_defects_has_more: boolean
  active_defects_next_offset: number | null
  current_result_defects_next_offset: number | null
}

export type ModernCaseQcSnapshotErrorCode =
  | 'invalid_identity'
  | 'invalid_page'
  | 'unsupported_source_key'
  | 'unexpected_status'
  | 'malformed_envelope'
  | 'identity_unverified'
  | 'identity_mismatch'
  | 'malformed_payload'

/**
 * 快照读取的失败语义。
 * 传输层错误（网络超时、409/503 等）不在此包装，直接向上抛出原始异常。
 */
export class ModernCaseQcSnapshotError extends Error {
  readonly code: ModernCaseQcSnapshotErrorCode
  /** 仅承载失败定位信息（字段名、来源标识），不携带患者三坐标。 */
  readonly details?: unknown

  constructor(
    code: ModernCaseQcSnapshotErrorCode,
    message: string,
    options?: { details?: unknown },
  ) {
    super(message)
    this.name = 'ModernCaseQcSnapshotError'
    this.code = code
    this.details = options?.details
  }
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isModernCaseQcSourceKey(value: unknown): value is ModernCaseQcSourceKey {
  return (
    typeof value === 'string' && (MODERN_CASE_QC_SOURCE_KEYS as readonly string[]).includes(value)
  )
}

/** 任一维度为空、缺失或含非规范前后空格时本地拒绝，不发起请求。 */
function normalizeIdentityValue(value: unknown, field: string): string {
  if (typeof value !== 'string') {
    throw new ModernCaseQcSnapshotError('invalid_identity', `${field} 必须是字符串`, {
      details: { field },
    })
  }
  if (value === '') {
    throw new ModernCaseQcSnapshotError('invalid_identity', `${field} 不能为空`, {
      details: { field },
    })
  }
  if (value !== value.trim()) {
    throw new ModernCaseQcSnapshotError('invalid_identity', `${field} 含非规范前后空格`, {
      details: { field },
    })
  }
  if (value.trim() === '') {
    throw new ModernCaseQcSnapshotError('invalid_identity', `${field} 不能为空白`, {
      details: { field },
    })
  }
  return value
}

function normalizeSourceKey(value: unknown): ModernCaseQcSourceKey {
  const normalized = normalizeIdentityValue(value, 'source_key')
  if (!isModernCaseQcSourceKey(normalized)) {
    throw new ModernCaseQcSnapshotError(
      'unsupported_source_key',
      `不支持的 source_key：${normalized}`,
      { details: { field: 'source_key' } },
    )
  }
  return normalized
}

/** 归一化后的分页入参：两组 offset 各自独立，limit 对两组同时生效。 */
interface ModernCaseQcPageRequest {
  active_defects_offset: number
  current_result_defects_offset: number
  defects_limit: number
}

/** offset 必须是非负安全整数，避免超过 JS 安全整数后被静默截断。 */
function normalizeOffset(value: unknown, field: string): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) {
    throw new ModernCaseQcSnapshotError('invalid_page', `${field} 必须是非负安全整数`, {
      details: { field },
    })
  }
  return value
}

/** 分页入参本地校验：非法值一律拒绝且不发起请求，缺省回落到 offset 0 / limit 20。 */
function normalizePage(page: unknown): ModernCaseQcPageRequest {
  if (page === undefined) {
    return {
      active_defects_offset: MODERN_CASE_QC_DEFAULT_OFFSET,
      current_result_defects_offset: MODERN_CASE_QC_DEFAULT_OFFSET,
      defects_limit: MODERN_CASE_QC_DEFAULT_DEFECTS_LIMIT,
    }
  }
  if (!isPlainObject(page)) {
    throw new ModernCaseQcSnapshotError('invalid_page', 'page 必须是对象', {
      details: { field: 'page' },
    })
  }

  let defectsLimit = MODERN_CASE_QC_DEFAULT_DEFECTS_LIMIT
  if (page.defects_limit !== undefined) {
    if (
      typeof page.defects_limit !== 'number' ||
      !Number.isSafeInteger(page.defects_limit) ||
      page.defects_limit < 1 ||
      page.defects_limit > MODERN_CASE_QC_MAX_DEFECTS_LIMIT
    ) {
      throw new ModernCaseQcSnapshotError(
        'invalid_page',
        `defects_limit 必须是 1 到 ${MODERN_CASE_QC_MAX_DEFECTS_LIMIT} 之间的整数`,
        { details: { field: 'defects_limit' } },
      )
    }
    defectsLimit = page.defects_limit
  }

  return {
    active_defects_offset:
      page.active_defects_offset === undefined
        ? MODERN_CASE_QC_DEFAULT_OFFSET
        : normalizeOffset(page.active_defects_offset, 'active_defects_offset'),
    current_result_defects_offset:
      page.current_result_defects_offset === undefined
        ? MODERN_CASE_QC_DEFAULT_OFFSET
        : normalizeOffset(page.current_result_defects_offset, 'current_result_defects_offset'),
    defects_limit: defectsLimit,
  }
}

/**
 * 单组缺陷的分页信封校验：两个字段必填，且必须与本页内容自洽。
 * has_more=false 必须配 next_offset=null；has_more=true 必须本页非空，
 * 且 next_offset 严格等于本次请求 offset + 本页条数。
 */
function requireDefectGroupEnvelope(
  data: Record<string, unknown>,
  prefix: 'active_defects' | 'current_result_defects',
  requestOffset: number,
  pageSize: number,
): { has_more: boolean; next_offset: number | null } {
  const hasMoreField = `${prefix}_has_more`
  const nextOffsetField = `${prefix}_next_offset`
  for (const field of [hasMoreField, nextOffsetField]) {
    if (!(field in data)) {
      throw new ModernCaseQcSnapshotError('malformed_payload', `缺少字段 ${field}`, {
        details: { field },
      })
    }
  }

  const hasMore = data[hasMoreField]
  if (typeof hasMore !== 'boolean') {
    throw new ModernCaseQcSnapshotError('malformed_payload', `${hasMoreField} 必须是布尔值`, {
      details: { field: hasMoreField },
    })
  }

  const nextOffset = data[nextOffsetField]
  if (!hasMore) {
    if (nextOffset !== null) {
      throw new ModernCaseQcSnapshotError(
        'malformed_payload',
        `${hasMoreField} 为 false 时 ${nextOffsetField} 必须为 null`,
        { details: { field: nextOffsetField } },
      )
    }
    return { has_more: false, next_offset: null }
  }
  if (typeof nextOffset !== 'number' || !Number.isSafeInteger(nextOffset) || nextOffset < 0) {
    throw new ModernCaseQcSnapshotError(
      'malformed_payload',
      `${nextOffsetField} 必须是安全非负整数`,
      { details: { field: nextOffsetField } },
    )
  }
  if (pageSize === 0) {
    throw new ModernCaseQcSnapshotError('malformed_payload', `${hasMoreField} 为 true 但本页为空`, {
      details: { field: hasMoreField, offset: requestOffset },
    })
  }
  if (nextOffset !== requestOffset + pageSize) {
    throw new ModernCaseQcSnapshotError(
      'malformed_payload',
      `${nextOffsetField} 必须等于请求 offset 与本页条数之和`,
      {
        details: {
          field: nextOffsetField,
          offset: requestOffset,
          page_size: pageSize,
          received: nextOffset,
        },
      },
    )
  }
  return { has_more: true, next_offset: nextOffset }
}

/** 数组字段必须是数组且元素为对象，缺失或畸形一律失败关闭，不补空数组。 */
function requireObjectArray(
  data: Record<string, unknown>,
  field: string,
  maxLength?: number,
): Array<Record<string, unknown>> {
  const value = data[field]
  if (!Array.isArray(value)) {
    throw new ModernCaseQcSnapshotError('malformed_payload', `字段 ${field} 必须是数组`, {
      details: { field },
    })
  }
  if (!value.every((item) => isPlainObject(item))) {
    throw new ModernCaseQcSnapshotError(
      'malformed_payload',
      `字段 ${field} 的元素必须是对象`,
      { details: { field } },
    )
  }
  if (maxLength !== undefined && value.length > maxLength) {
    throw new ModernCaseQcSnapshotError(
      'malformed_payload',
      `字段 ${field} 返回 ${value.length} 条，超过请求上限 ${maxLength}`,
      { details: { field, received: value.length, limit: maxLength } },
    )
  }
  return value as Array<Record<string, unknown>>
}

/** 单值字段必须是对象或显式 null，缺失或畸形一律失败关闭。 */
function requireObjectOrNull<T>(data: Record<string, unknown>, field: string): T | null {
  if (!(field in data)) {
    throw new ModernCaseQcSnapshotError('malformed_payload', `缺少字段 ${field}`, {
      details: { field },
    })
  }
  const value = data[field]
  if (value === null) {
    return null
  }
  if (!isPlainObject(value)) {
    throw new ModernCaseQcSnapshotError(
      'malformed_payload',
      `字段 ${field} 必须是对象或 null`,
      { details: { field } },
    )
  }
  return value as T
}

function assertRequestedIdentity(
  data: Record<string, unknown>,
  request: ModernCaseQcIdentity,
): void {
  for (const field of ['institute_id', 'patient_id', 'visit_id'] as const) {
    const received = data[field]
    if (typeof received !== 'string' || received !== request[field]) {
      throw new ModernCaseQcSnapshotError('identity_mismatch', `响应 ${field} 与请求不一致`, {
        details: { field },
      })
    }
  }
  if (data.source_key !== request.source_key) {
    throw new ModernCaseQcSnapshotError('identity_mismatch', '响应 source_key 与请求不一致', {
      details: {
        field: 'source_key',
        expected_source_key: request.source_key,
        received_source_key: data.source_key ?? null,
      },
    })
  }
}

function validateSnapshotPayload(
  payload: unknown,
  request: ModernCaseQcIdentity,
  page: ModernCaseQcPageRequest,
): ModernCaseQcSnapshot {
  if (!isPlainObject(payload)) {
    throw new ModernCaseQcSnapshotError('malformed_envelope', '响应不是统一信封对象')
  }
  if (payload.success !== true) {
    throw new ModernCaseQcSnapshotError('malformed_envelope', '响应信封 success 不是 true', {
      details: { field: 'success' },
    })
  }
  if (!isPlainObject(payload.data)) {
    throw new ModernCaseQcSnapshotError('malformed_envelope', '响应信封缺少对象 data', {
      details: { field: 'data' },
    })
  }

  const data = payload.data

  if (data.identity_status !== 'verified') {
    throw new ModernCaseQcSnapshotError('identity_unverified', '响应未确认身份为 verified', {
      details: { field: 'identity_status' },
    })
  }

  assertRequestedIdentity(data, request)

  const latestQcResult = requireObjectOrNull<ModernCaseQcResultRecord>(data, 'latest_qc_result')
  const recentResults = requireObjectArray(data, 'recent_results')
  // 单组返回条数不得超过本次请求的 limit。
  const activeDefects = requireObjectArray(data, 'active_defects', page.defects_limit)
  const currentResultDefects = requireObjectArray(
    data,
    'current_result_defects',
    page.defects_limit,
  )
  const latestNotification = requireObjectOrNull<ModernCaseQcNotification>(
    data,
    'latest_notification',
  )

  const activeEnvelope = requireDefectGroupEnvelope(
    data,
    'active_defects',
    page.active_defects_offset,
    activeDefects.length,
  )
  const currentEnvelope = requireDefectGroupEnvelope(
    data,
    'current_result_defects',
    page.current_result_defects_offset,
    currentResultDefects.length,
  )

  return {
    identity_status: 'verified',
    source_key: request.source_key,
    institute_id: request.institute_id,
    patient_id: request.patient_id,
    visit_id: request.visit_id,
    latest_qc_result: latestQcResult,
    recent_results: recentResults as ModernCaseQcResultRecord[],
    active_defects: activeDefects as ModernCaseQcDefect[],
    current_result_defects: currentResultDefects as ModernCaseQcDefect[],
    latest_notification: latestNotification,
    active_defects_has_more: activeEnvelope.has_more,
    current_result_defects_has_more: currentEnvelope.has_more,
    active_defects_next_offset: activeEnvelope.next_offset,
    current_result_defects_next_offset: currentEnvelope.next_offset,
  }
}

/**
 * 读取单病历统一质控快照。
 * 传输层异常（网络、409、503 等）原样抛出；业务不变量不满足时抛
 * {@link ModernCaseQcSnapshotError}，绝不返回“看起来正常”的空快照。
 */
export async function getModernCaseQcSnapshot(
  identity: ModernCaseQcIdentity,
  page?: ModernCaseQcSnapshotPage,
): Promise<ModernCaseQcSnapshot> {
  const request: ModernCaseQcIdentity = {
    institute_id: normalizeIdentityValue(identity?.institute_id, 'institute_id'),
    patient_id: normalizeIdentityValue(identity?.patient_id, 'patient_id'),
    visit_id: normalizeIdentityValue(identity?.visit_id, 'visit_id'),
    source_key: normalizeSourceKey(identity?.source_key),
  }
  // 分页入参先本地校验：非法值不发请求。
  const requestedPage = normalizePage(page)

  const response = await ApiService.requestRaw<unknown>({
    method: 'GET',
    url: MODERN_CASE_QC_SNAPSHOT_URL,
    params: {
      institute_id: request.institute_id,
      patient_id: request.patient_id,
      visit_id: request.visit_id,
      source_key: request.source_key,
      active_defects_offset: requestedPage.active_defects_offset,
      current_result_defects_offset: requestedPage.current_result_defects_offset,
      defects_limit: requestedPage.defects_limit,
    },
  })

  if (response?.status !== 200) {
    throw new ModernCaseQcSnapshotError(
      'unexpected_status',
      `快照接口返回非 200 状态：${String(response?.status)}`,
      { details: { status: response?.status ?? null } },
    )
  }

  return validateSnapshotPayload(response.data, request, requestedPage)
}
