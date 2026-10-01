/**
 * 规则集版本 API（V3.6 P1-E1 规则集版本发布合同第 6 节）
 *
 * 读取需登录；写操作需 admin/qc_manager。质控点上线/暂停/下线只写草稿，发布后形成新版本；
 * 已建任务继续使用冻结版本。错误解析沿用 manualDefectReviews.ts：409 带业务 code，
 * 发布校验失败为 422 且带逐条 problems。
 */

import { isAxiosError } from 'axios'
import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'

/** 规则在版本中的状态：deleted 仅保留在冻结版本和差异中，不参与当前管理列表。 */
export type RuleSetEntryState = 'active' | 'paused' | 'offline' | 'deleted'
/** 版本来源：内置、已发布、已下线。 */
export type RuleSetVersionSource = 'builtin' | 'published' | 'retired'
export type RuleSetVersionStatus = RuleSetVersionSource | 'draft'

/** 409 业务 code（合同第 6 节）。 */
export type RuleSetVersionConflictCode =
  | 'draft_exists'
  | 'version_conflict'
  | 'version_exists'
  | 'unsupported_rule_set'
  | 'current_version'
  | 'builtin_version'
  | 'already_retired'
  | 'draft_changed'

export interface RuleSetVersionExcelIssue {
  sheet: string
  row: number | null
  field: string | null
  code: string
  message: string
}

/** 写接口只接受 rule_id 与 state。 */
export interface RuleSetEntry {
  rule_id: string
  state: RuleSetEntryState
  /** 历史版本可缺失；发布新版本前必须显式配置。 */
  department_scope_mode?: 'all' | 'selected' | null
  department_refs?: Array<{ institute_id: string; department_name: string }> | null
  doctor_visible?: boolean | null
  /** null/缺省为未知，空数组明确非核心制度。 */
  core_system_ids?: string[] | null
}

/**
 * 响应中的规则条目，附带后端只读派生字段（不入库、不参与摘要，写接口不接受）：
 * executable 是否可设为 active；qc_point/source_document 取自规则主表，无权威元数据时为 null。
 */
export interface RuleSetEntryView extends RuleSetEntry {
  executable: boolean
  qc_point: string | null
  source_document: string | null
  /** 编码规则目录的权威分类；非编码规则可为 null。 */
  category?: string | null
  category_name?: string | null
}

export interface RuleSetVersionItem {
  id: string | null
  rule_set_key: string
  /** 草稿为 null。 */
  version: string | null
  status: RuleSetVersionStatus
  /** 草稿为 null。 */
  source: RuleSetVersionSource | null
  base_version: string | null
  content_digest: string | null
  note: string | null
  /** 内置版本为 null。 */
  version_seq: number | null
  created_by: string | null
  created_at: string | null
  published_by: string | null
  published_at: string | null
  retired_by: string | null
  retired_at: string | null
  is_current: boolean
  active_count: number
  paused_count: number
  offline_count: number
  deleted_count: number
}

export interface RuleSetResolution {
  rule_set_key: string
  version: string
  source: RuleSetVersionSource
  active_rule_ids: string[]
  paused_rule_ids: string[]
  excluded_rule_ids: string[]
  deleted_rule_ids?: string[]
  content_digest: string
}

export interface RuleSetVersionDetail extends RuleSetVersionItem {
  entries: RuleSetEntryView[]
  resolution: RuleSetResolution
}

export interface RuleSetDraft extends RuleSetVersionItem {
  status: 'draft'
  version_seq: number
  base_version: string
  entries: RuleSetEntryView[]
}

export interface RuleSetVersionList {
  rule_set_key: string
  /** 本批只有 LX0609 可建草稿与发布；其余规则集只有内置版本。 */
  versionable: boolean
  builtin_version: string
  current_version: string
  items: RuleSetVersionItem[]
  draft: RuleSetDraft | null
}

export interface RuleSetDraftCreatePayload {
  base_version?: string | null
  entries?: RuleSetEntry[] | null
  note?: string | null
}

export interface RuleSetDraftUpdatePayload {
  version_seq: number
  entries?: RuleSetEntry[] | null
  note?: string | null
}

export interface RuleSetDraftPublishPayload {
  version: string
  note?: string | null
  version_seq?: number | null
}

export interface RuleSetDraftDeleteResult {
  rule_set_key: string
  deleted: boolean
}

export interface RuleSetVersionApiResult<T> {
  success: boolean
  data?: T
  message?: string
  /** HTTP 状态码；网络异常时为 undefined。 */
  status?: number
  /** 409/422 结构化错误的业务 code。 */
  code?: string
  /** 422 发布校验失败的逐条原因。 */
  problems?: string[]
  /** Excel 合同校验的逐表、行、字段问题。 */
  issues?: RuleSetVersionExcelIssue[]
}

export interface RuleSetDraftImportApiResult extends RuleSetVersionApiResult<RuleSetDraft> {
  resultUnknown: boolean
}

interface ErrorDetail {
  code?: string
  message?: string
  problems?: string[]
  issues?: RuleSetVersionExcelIssue[]
}

/**
 * 读取结构化错误 detail（409 `{code, message}`、422 `{code, message, problems}`）。
 * 后端统一异常包装把 HTTPException.detail 放在 `error` 字段；直连 FastAPI 时位于 `detail`。
 */
function extractErrorDetail(error: unknown): ErrorDetail {
  if (!isAxiosError(error)) return {}
  const body: unknown = error.response?.data
  if (typeof body !== 'object' || body === null) return {}
  for (const key of ['detail', 'error'] as const) {
    const candidate: unknown = (body as Record<string, unknown>)[key]
    if (typeof candidate === 'object' && candidate !== null && !Array.isArray(candidate)) {
      const { code, message, problems, issues } = candidate as Record<string, unknown>
      if (typeof code === 'string' && code.trim()) {
        return {
          code,
          message: typeof message === 'string' && message.trim() ? message : undefined,
          problems: Array.isArray(problems)
            ? problems.filter(
                (item): item is string => typeof item === 'string' && item.trim() !== '',
              )
            : undefined,
          issues: Array.isArray(issues)
            ? issues.flatMap((item): RuleSetVersionExcelIssue[] => {
                if (typeof item !== 'object' || item === null) return []
                const raw = item as Record<string, unknown>
                if (
                  typeof raw.sheet !== 'string' ||
                  typeof raw.code !== 'string' ||
                  typeof raw.message !== 'string'
                )
                  return []
                return [
                  {
                    sheet: raw.sheet,
                    row: typeof raw.row === 'number' ? raw.row : null,
                    field: typeof raw.field === 'string' ? raw.field : null,
                    code: raw.code,
                    message: raw.message,
                  },
                ]
              })
            : undefined,
        }
      }
    }
  }
  return {}
}

async function request<T>(
  config: Parameters<typeof ApiService.requestRaw>[0],
  fallback: string,
): Promise<RuleSetVersionApiResult<T>> {
  try {
    const response = await ApiService.requestRaw<T>(config)
    const normalized = normalizeApiSuccess<T>(response.data)
    return {
      success: normalized.success,
      data: normalized.data,
      message: normalized.message,
      status: response.status,
    }
  } catch (error) {
    const detail = extractErrorDetail(error)
    return {
      success: false,
      message: detail.message || extractApiErrorMessageFromError(error, fallback),
      status: isAxiosError(error) ? error.response?.status : undefined,
      code: detail.code,
      problems: detail.problems,
      issues: detail.issues,
    }
  }
}

export function getMedicalCoreSystems() {
  return request<{
    items: Array<{ id: string; name: string }>
    source_url: string
    id_kind: string
  }>({ method: 'GET', url: '/api/v1/rule-set-versions/core-systems' }, '读取核心制度字典失败')
}

function keyPath(ruleSetKey: string): string {
  return `/api/v1/rule-set-versions/${encodeURIComponent(ruleSetKey)}`
}

/** 去掉只读派生字段，只保留写接口接受的 rule_id/state。 */
export function toWriteEntries(entries: readonly RuleSetEntry[]): RuleSetEntry[] {
  return entries.map(({ rule_id, state }) => ({ rule_id, state }))
}

/** 版本列表（含当前版本标记与草稿）。 */
export async function listRuleSetVersions(ruleSetKey: string) {
  return request<RuleSetVersionList>(
    {
      method: 'GET',
      url: '/api/v1/rule-set-versions',
      params: { rule_set_key: ruleSetKey },
    },
    '读取规则集版本失败',
  )
}

/** 版本详情（含 entries 与解析结果）。 */
export async function getRuleSetVersion(ruleSetKey: string, version: string) {
  return request<RuleSetVersionDetail>(
    {
      method: 'GET',
      url: `${keyPath(ruleSetKey)}/${encodeURIComponent(version)}`,
    },
    '读取规则集版本详情失败',
  )
}

/** 草稿详情；无草稿时 404。 */
export async function getRuleSetDraft(ruleSetKey: string) {
  return request<RuleSetDraft>(
    { method: 'GET', url: `${keyPath(ruleSetKey)}/draft` },
    '读取规则集草稿失败',
  )
}

/** 从基础版本创建草稿（缺省为当前版本）；已有草稿 409 draft_exists。 */
export async function createRuleSetDraft(
  ruleSetKey: string,
  payload: RuleSetDraftCreatePayload = {},
) {
  return request<RuleSetDraft>(
    {
      method: 'POST',
      url: `${keyPath(ruleSetKey)}/draft`,
      data: {
        ...payload,
        entries: payload.entries ? toWriteEntries(payload.entries) : payload.entries,
      },
    },
    '创建规则集草稿失败',
  )
}

/** 修改草稿（version_seq CAS）；冲突 409 version_conflict。 */
export async function updateRuleSetDraft(ruleSetKey: string, payload: RuleSetDraftUpdatePayload) {
  return request<RuleSetDraft>(
    {
      method: 'PUT',
      url: `${keyPath(ruleSetKey)}/draft`,
      data: {
        ...payload,
        entries: payload.entries ? toWriteEntries(payload.entries) : payload.entries,
      },
    },
    '保存规则集草稿失败',
  )
}

/** 放弃草稿（version_seq CAS）。 */
export async function deleteRuleSetDraft(ruleSetKey: string, versionSeq: number) {
  return request<RuleSetDraftDeleteResult>(
    {
      method: 'DELETE',
      url: `${keyPath(ruleSetKey)}/draft`,
      params: { version_seq: versionSeq },
    },
    '放弃规则集草稿失败',
  )
}

/** 发布草稿为新版本；校验失败 422 带 problems，版本号重复 409 version_exists。 */
export async function publishRuleSetDraft(ruleSetKey: string, payload: RuleSetDraftPublishPayload) {
  return request<RuleSetVersionDetail>(
    {
      method: 'POST',
      url: `${keyPath(ruleSetKey)}/draft/publish`,
      data: payload,
    },
    '发布规则集版本失败',
  )
}

/** 下线已发布版本；不能下线当前版本（current_version）或内置版本（builtin_version）。 */
export async function retireRuleSetVersion(ruleSetKey: string, version: string) {
  return request<RuleSetVersionDetail>(
    {
      method: 'POST',
      url: `${keyPath(ruleSetKey)}/${encodeURIComponent(version)}/retire`,
    },
    '下线规则集版本失败',
  )
}

async function download(url: string, fallback: string): Promise<RuleSetVersionApiResult<Blob>> {
  try {
    const response = await ApiService.requestRaw<Blob>({ method: 'GET', url, responseType: 'blob' })
    if (!(response.data instanceof Blob))
      return { success: false, status: response.status, message: fallback }
    return { success: true, data: response.data, status: response.status }
  } catch (error) {
    return {
      success: false,
      status: isAxiosError(error) ? error.response?.status : undefined,
      message: extractApiErrorMessageFromError(error, fallback),
    }
  }
}

/** 导出冻结的内置/已发布/已下线版本。 */
export function exportRuleSetVersion(ruleSetKey: string, version: string) {
  return download(
    `${keyPath(ruleSetKey)}/${encodeURIComponent(version)}/export`,
    '导出规则集版本失败',
  )
}

/** 导出当前草稿，文件携带 version_seq 供再次导入时做 CAS。 */
export function exportRuleSetDraft(ruleSetKey: string) {
  return download(`${keyPath(ruleSetKey)}/draft/export`, '导出规则集草稿失败')
}

/** 导入只能创建或 CAS 更新草稿，不发布版本。 */
export async function importRuleSetDraft(ruleSetKey: string, file: File) {
  const form = new FormData()
  form.append('file', file)
  const result = await request<unknown>(
    {
      method: 'POST',
      url: `${keyPath(ruleSetKey)}/draft/import`,
      data: form,
      timeout: 120_000,
    },
    '导入规则集草稿失败',
  )
  if (!result.success) {
    const knownNotWritten = [401, 403, 409, 413, 422].includes(result.status ?? 0)
    return { ...result, resultUnknown: !knownNotWritten } as RuleSetDraftImportApiResult
  }
  const data = normalizeImportedDraft(result.data, ruleSetKey)
  if (!data) {
    return {
      success: false,
      status: result.status,
      message: '服务端返回的草稿回执不完整，请刷新列表核对后再决定是否重试',
      resultUnknown: true,
    }
  }
  return { ...result, data, resultUnknown: false } as RuleSetDraftImportApiResult
}

function normalizeImportedDraft(value: unknown, ruleSetKey: string): RuleSetDraft | null {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return null
  const item = value as Record<string, unknown>
  if (
    item.rule_set_key !== ruleSetKey ||
    item.status !== 'draft' ||
    !Number.isInteger(item.version_seq) ||
    Number(item.version_seq) < 1 ||
    typeof item.base_version !== 'string' ||
    !item.base_version.trim() ||
    !Array.isArray(item.entries)
  )
    return null
  const seen = new Set<string>()
  for (const raw of item.entries) {
    if (typeof raw !== 'object' || raw === null || Array.isArray(raw)) return null
    const entry = raw as Record<string, unknown>
    if (
      typeof entry.rule_id !== 'string' ||
      !entry.rule_id.trim() ||
      !['active', 'paused', 'offline', 'deleted'].includes(String(entry.state)) ||
      typeof entry.executable !== 'boolean' ||
      seen.has(entry.rule_id)
    )
      return null
    seen.add(entry.rule_id)
  }
  return item as unknown as RuleSetDraft
}
