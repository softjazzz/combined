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
}

export type ModernCaseQcSnapshotErrorCode =
  | 'invalid_identity'
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

/** 数组字段必须是数组且元素为对象，缺失或畸形一律失败关闭，不补空数组。 */
function requireObjectArray(
  data: Record<string, unknown>,
  field: string,
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
  const activeDefects = requireObjectArray(data, 'active_defects')
  const currentResultDefects = requireObjectArray(data, 'current_result_defects')
  const latestNotification = requireObjectOrNull<ModernCaseQcNotification>(
    data,
    'latest_notification',
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
  }
}

/**
 * 读取单病历统一质控快照。
 * 传输层异常（网络、409、503 等）原样抛出；业务不变量不满足时抛
 * {@link ModernCaseQcSnapshotError}，绝不返回“看起来正常”的空快照。
 */
export async function getModernCaseQcSnapshot(
  identity: ModernCaseQcIdentity,
): Promise<ModernCaseQcSnapshot> {
  const request: ModernCaseQcIdentity = {
    institute_id: normalizeIdentityValue(identity?.institute_id, 'institute_id'),
    patient_id: normalizeIdentityValue(identity?.patient_id, 'patient_id'),
    visit_id: normalizeIdentityValue(identity?.visit_id, 'visit_id'),
    source_key: normalizeSourceKey(identity?.source_key),
  }

  const response = await ApiService.requestRaw<unknown>({
    method: 'GET',
    url: MODERN_CASE_QC_SNAPSHOT_URL,
    params: {
      institute_id: request.institute_id,
      patient_id: request.patient_id,
      visit_id: request.visit_id,
      source_key: request.source_key,
    },
  })

  if (response?.status !== 200) {
    throw new ModernCaseQcSnapshotError(
      'unexpected_status',
      `快照接口返回非 200 状态：${String(response?.status)}`,
      { details: { status: response?.status ?? null } },
    )
  }

  return validateSnapshotPayload(response.data, request)
}
