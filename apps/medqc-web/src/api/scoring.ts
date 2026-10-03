/**
 * 评分标准与计分 API（V3.6 P2-S 评分标准与计分服务合同第 3、4 节）
 *
 * 读取需登录；写操作需 admin/qc_manager。只有草稿可编辑，启用中的标准须复制为新草稿。
 * 错误解析沿用 ruleSetVersions.ts：409 带业务 code，校验失败 422 带逐条 problems，
 * 数据库故障为脱敏 503。
 */

import { isAxiosError } from 'axios'
import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'

export type ScoringScene = 'running' | 'final' | 'outpatient'
export type ScoringStandardStatus = 'draft' | 'active' | 'archived'
/** 启用时原默认标准的处理：archive 归档；undefault 只取消默认标记。 */
export type ScoringReplaceMode = 'archive' | 'undefault'

/** 409 / 422 业务 code（scoring_standard_service）。 */
export type ScoringErrorCode =
  | 'version_conflict'
  | 'not_draft'
  | 'not_active'
  | 'already_default'
  | 'name_exists'
  | 'conflict'
  | 'invalid'
  | 'items_validation_failed'
  | 'standard_validation_failed'
  | 'scene_without_rule_set'
  | 'rule_set_scene_mismatch'
  | 'rule_set_version_mismatch'
  | 'excel_validation_failed'

/** 档位：区间左闭右开，最高档右闭；按分数降序、首尾相接覆盖 [0, base_score]。 */
export interface ScoringGradeBand {
  name: string
  min_score: number
  max_score: number
}

export interface ScoringRuleSetOption {
  rule_set_key: string
  rule_set_name: string
}

export interface ScoringSceneCatalogEntry {
  scene: ScoringScene
  /** 为空表示该场景暂无可评分的规则集（如门急诊）。 */
  rule_sets: ScoringRuleSetOption[]
}

export interface ScoringStandardItem {
  id: string
  name: string
  scene: ScoringScene
  rule_set_key: string
  status: ScoringStandardStatus
  is_default: boolean
  base_score: number | null
  grade_bands: ScoringGradeBand[]
  veto_grade: string
  version_seq: number
  created_by: string | null
  created_at: string | null
  updated_by: string | null
  updated_at: string | null
  activated_by: string | null
  activated_at: string | null
}

/** 项目组；max_deduction 为 null 表示不封顶。 */
export interface ScoringGroup {
  group_name: string
  max_deduction: number | null
  sort_order: number
}

export interface ScoringItem {
  group_name: string
  rule_id: string
  deduction: number
  is_veto: boolean
  enabled: boolean
  department_scope_mode: 'all' | 'selected'
  department_refs: Array<{ institute_id: string; department_name: string }>
}

export interface ScoringStandardDetail extends ScoringStandardItem {
  groups: ScoringGroup[]
  items: ScoringItem[]
  group_count: number
  item_count: number
  rule_document_types: Record<string, string[]>
}

export interface ScoringStandardList {
  items: ScoringStandardItem[]
  scenes: ScoringSceneCatalogEntry[]
}

export interface ScoringSceneList {
  items: ScoringSceneCatalogEntry[]
}

export interface ScoringStandardCreatePayload {
  name: string
  scene: ScoringScene
  /** 缺省时场景只有一个可用规则集才自动选定。 */
  rule_set_key?: string | null
  base_score: number
  grade_bands: ScoringGradeBand[]
  veto_grade: string
}

/** 未传的字段保持不变；场景与规则集创建后不可改。 */
export interface ScoringStandardUpdatePayload {
  version_seq: number
  name?: string
  base_score?: number
  grade_bands?: ScoringGradeBand[]
  veto_grade?: string
}

/** 写入项目组：max_deduction 为 null 表示不封顶。 */
export interface ScoringGroupWrite {
  group_name: string
  max_deduction: number | null
  sort_order: number
}

export interface ScoringItemsSavePayload {
  version_seq: number
  groups: ScoringGroupWrite[]
  items: ScoringItem[]
}

export interface ScoringActivatePayload {
  version_seq: number
  replace_mode: ScoringReplaceMode
}

export interface ScoringDeleteResult {
  id: string
  deleted: boolean
}

export interface ScoringDeduction {
  rule_id: string
  group_name: string
  deduction: number
  is_veto: boolean
}

export interface ScoringGroupDeduction {
  group_name: string
  raw_deduction: number
  applied_deduction: number
  max_deduction: number | null
}

/** Canonical 结果的完整只读引用；缺失时前端不得用当前页面上下文补齐。 */
export interface CaseScoreResultRef {
  envelope_id: string
  root_job_id: string
  institute_id: string
  patient_id: string
  visit_id: string
  rule_set_key: string
  rule_set_version: string
}

/** 本次计分所用默认标准的精确 CAS 引用。 */
export interface CaseScoreStandardRef {
  standard_id: string
  version_seq: number
  updated_at: string
}

export interface CaseScoreScored {
  status: 'scored'
  scene: ScoringScene
  standard_id: string | null
  standard_name: string | null
  standard_updated_at: string | null
  rule_set_key: string | null
  rule_set_version: string | null
  job_id: string | null
  /** 历史响应可能没有引用；缺失不影响只读分数展示。 */
  result_ref?: CaseScoreResultRef | null
  /** 历史响应可能没有引用；只有完整引用可用于展示可信标准版本。 */
  standard_ref?: CaseScoreStandardRef | null
  score: number
  /** 分数落不进任何档位时为 null（显示未知）。 */
  grade: string | null
  veto_hit: boolean
  base_score: number
  deductions: ScoringDeduction[]
  group_deductions: ScoringGroupDeduction[]
  /** 结果中出现、但标准未配置扣分的确定问题。 */
  unscored_rule_ids: string[]
}

export interface CaseScoreNoStandard {
  status: 'no_standard'
  scene: ScoringScene
}

export interface CaseScoreNoResult {
  status: 'no_result'
  scene: ScoringScene
  result_state: string
  standard_id: string | null
}

export type CaseScore = CaseScoreScored | CaseScoreNoStandard | CaseScoreNoResult

export interface CaseScoreQuery {
  institute_id: string
  patient_id: string
  visit_id: string
  scene: ScoringScene
  standard_id?: string
}

export interface ScoringApiResult<T> {
  success: boolean
  data?: T
  message?: string
  /** HTTP 状态码；网络异常时为 undefined。 */
  status?: number
  /** 409/422 结构化错误的业务 code。 */
  code?: string
  /** 422 校验失败的逐条原因。 */
  problems?: string[]
}

export interface ScoringExcelProblem {
  sheet: string
  row: number
  field: string
  code: string
  message: string
}

export interface ScoringImportResult {
  success: boolean
  data?: ScoringStandardDetail
  message: string
  status?: number
  code?: string
  problems: ScoringExcelProblem[]
  /** 断网、超时、5xx 或异常成功响应都无法证明服务端未写入。 */
  resultUnknown: boolean
}

interface ErrorDetail {
  code?: string
  message?: string
  problems?: string[]
}

function extractExcelProblems(error: unknown): ScoringExcelProblem[] {
  if (!isAxiosError(error)) return []
  const body: unknown = error.response?.data
  if (typeof body !== 'object' || body === null) return []
  const container = body as Record<string, unknown>
  const detail = (typeof container.detail === 'object' && container.detail !== null
    ? container.detail
    : container.error) as Record<string, unknown> | undefined
  if (!detail || !Array.isArray(detail.problems)) return []
  return detail.problems.flatMap((problem): ScoringExcelProblem[] => {
    if (typeof problem !== 'object' || problem === null) return []
    const value = problem as Record<string, unknown>
    if (typeof value.sheet !== 'string' || typeof value.row !== 'number'
      || typeof value.field !== 'string' || typeof value.code !== 'string'
      || typeof value.message !== 'string') return []
    return [{
      sheet: value.sheet,
      row: value.row,
      field: value.field,
      code: value.code,
      message: value.message,
    }]
  })
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
      const { code, message, problems } = candidate as Record<string, unknown>
      if (typeof code === 'string' && code.trim()) {
        return {
          code,
          message: typeof message === 'string' && message.trim() ? message : undefined,
          problems: Array.isArray(problems)
            ? problems.filter((item): item is string => typeof item === 'string' && item.trim() !== '')
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
): Promise<ScoringApiResult<T>> {
  try {
    const response = await ApiService.requestRaw<T>(config)
    const normalized = normalizeApiSuccess<T>(response.data)
    return { success: normalized.success, data: normalized.data, message: normalized.message, status: response.status }
  } catch (error) {
    const detail = extractErrorDetail(error)
    return {
      success: false,
      message: detail.message || extractApiErrorMessageFromError(error, fallback),
      status: isAxiosError(error) ? error.response?.status : undefined,
      code: detail.code,
      problems: detail.problems,
    }
  }
}

const BASE = '/api/v1/scoring'

export interface SpecialReportDefaultBinding {
  purpose: 'special_report'
  execution_scene: 'final'
  version_seq: number
  standard_id: string | null
  standard_version_seq: number | null
  status: 'no_standard' | 'configured' | 'unavailable'
  standard: ScoringStandardItem | null
}

export interface SpecialReportDefaultWrite {
  version_seq: number
  standard_id: string | null
  standard_version_seq?: number | null
}

function validSpecialBinding(value: unknown): value is SpecialReportDefaultBinding {
  if (!value || typeof value !== 'object') return false
  const row = value as Record<string, unknown>
  if (row.purpose !== 'special_report' || row.execution_scene !== 'final'
    || !Number.isSafeInteger(row.version_seq) || Number(row.version_seq) < 0
    || !['no_standard', 'configured', 'unavailable'].includes(String(row.status))) return false
  if (row.status === 'no_standard') return row.standard_id === null && row.standard_version_seq === null && row.standard === null
  if (typeof row.standard_id !== 'string' || !row.standard_id
    || !Number.isSafeInteger(row.standard_version_seq) || Number(row.standard_version_seq) < 1) return false
  if (row.status === 'unavailable') return row.standard === null
  if (!row.standard || typeof row.standard !== 'object') return false
  const standard = row.standard as Record<string, unknown>
  return standard.id === row.standard_id && standard.scene === 'final' && standard.status === 'active'
    && standard.version_seq === row.standard_version_seq && typeof standard.name === 'string'
}

async function specialBindingRequest(config: Parameters<typeof ApiService.requestRaw>[0], fallback: string) {
  const result = await request<unknown>(config, fallback)
  if (!result.success) return result as ScoringApiResult<SpecialReportDefaultBinding>
  if (!validSpecialBinding(result.data)) return { success: false, status: result.status, message: '专用默认标准回执不完整，请刷新核对' }
  return { ...result, data: result.data }
}

export function getSpecialReportDefault() {
  return specialBindingRequest({
    method: 'GET', url: `${BASE}/defaults/special-report`, params: { scene: 'final' },
  }, '读取特殊病历报表默认标准失败')
}

export function setSpecialReportDefault(payload: SpecialReportDefaultWrite) {
  return specialBindingRequest({
    method: 'PUT', url: `${BASE}/defaults/special-report`, params: { scene: 'final' },
    data: {
      version_seq: payload.version_seq,
      standard_id: payload.standard_id,
      ...(payload.standard_version_seq !== undefined
        ? { standard_version_seq: payload.standard_version_seq } : {}),
    },
  }, '保存特殊病历报表默认标准失败')
}

function standardPath(id: string): string {
  return `${BASE}/standards/${encodeURIComponent(id)}`
}

function isImportedDraft(value: unknown): value is ScoringStandardDetail {
  if (typeof value !== 'object' || value === null) return false
  const data = value as Record<string, unknown>
  const groups = data.groups
  const items = data.items
  return typeof data.id === 'string' && Boolean(data.id.trim())
    && typeof data.name === 'string' && Boolean(data.name.trim())
    && (data.scene === 'running' || data.scene === 'final' || data.scene === 'outpatient')
    && typeof data.rule_set_key === 'string' && Boolean(data.rule_set_key.trim())
    && data.status === 'draft'
    && data.is_default === false
    && data.version_seq === 1
    && Array.isArray(data.grade_bands)
    && Array.isArray(groups)
    && Array.isArray(items)
    && data.group_count === groups.length
    && data.item_count === items.length
}

/** 只发送写接口接受的字段，去掉多余属性。 */
export function toWriteBands(bands: readonly ScoringGradeBand[]): ScoringGradeBand[] {
  return bands.map(({ name, min_score, max_score }) => ({ name, min_score, max_score }))
}

export function toWriteGroups(groups: readonly ScoringGroupWrite[]): ScoringGroupWrite[] {
  return groups.map(({ group_name, max_deduction, sort_order }) => ({ group_name, max_deduction, sort_order }))
}

export function toWriteItems(items: readonly ScoringItem[]): ScoringItem[] {
  return items.map(({ group_name, rule_id, deduction, is_veto, enabled, department_scope_mode, department_refs }) => {
    if (department_scope_mode !== 'all' && department_scope_mode !== 'selected') {
      throw new TypeError('科室适用模式无效')
    }
    if (!Array.isArray(department_refs)) throw new TypeError('科室引用必须是数组')
    const normalizedRefs = department_refs.map((ref) => {
      if (typeof ref?.institute_id !== 'string' || typeof ref?.department_name !== 'string') {
        throw new TypeError('科室引用格式无效')
      }
      const normalized = {
        institute_id: ref.institute_id.trim(),
        department_name: ref.department_name.trim(),
      }
      if (!normalized.institute_id || !normalized.department_name) throw new TypeError('科室引用不能为空')
      return normalized
    })
    return {
      group_name, rule_id, deduction, is_veto, enabled,
      department_scope_mode,
      department_refs: normalizedRefs,
    }
  })
}

/** 场景与可用规则集。 */
export async function listScoringScenes() {
  return request<ScoringSceneList>({ method: 'GET', url: `${BASE}/scenes` }, '读取评分场景失败')
}

/** 标准列表（不含条目），附场景目录。 */
export async function listScoringStandards(filters: { scene?: ScoringScene; status?: ScoringStandardStatus } = {}) {
  const params: Record<string, string> = {}
  if (filters.scene) params.scene = filters.scene
  if (filters.status) params.status = filters.status
  return request<ScoringStandardList>({ method: 'GET', url: `${BASE}/standards`, params }, '读取评分标准失败')
}

/** 标准详情（含项目组与条目）。 */
export async function getScoringStandard(id: string) {
  return request<ScoringStandardDetail>({ method: 'GET', url: standardPath(id) }, '读取评分标准详情失败')
}

/** 新建草稿。 */
export async function createScoringStandard(payload: ScoringStandardCreatePayload) {
  return request<ScoringStandardDetail>({
    method: 'POST',
    url: `${BASE}/standards`,
    data: { ...payload, grade_bands: toWriteBands(payload.grade_bands) },
  }, '新建评分标准失败')
}

/** 修改草稿基本信息（version_seq CAS）。 */
export async function updateScoringStandard(id: string, payload: ScoringStandardUpdatePayload) {
  return request<ScoringStandardDetail>({
    method: 'PUT',
    url: standardPath(id),
    data: payload.grade_bands ? { ...payload, grade_bands: toWriteBands(payload.grade_bands) } : payload,
  }, '保存评分标准失败')
}

/** 项目组与条目整表保存（version_seq CAS）。 */
export async function saveScoringItems(id: string, payload: ScoringItemsSavePayload) {
  return request<ScoringStandardDetail>({
    method: 'PUT',
    url: `${standardPath(id)}/items`,
    data: {
      version_seq: payload.version_seq,
      groups: toWriteGroups(payload.groups),
      items: toWriteItems(payload.items),
    },
  }, '保存评分条目失败')
}

/** 复制为新草稿。 */
export async function copyScoringStandard(id: string, name: string) {
  return request<ScoringStandardDetail>({
    method: 'POST',
    url: `${standardPath(id)}/copy`,
    data: { name },
  }, '复制评分标准失败')
}

/** 启用并设为场景默认；原默认标准按 replace_mode 归档或只取消默认。 */
export async function activateScoringStandard(id: string, payload: ScoringActivatePayload) {
  return request<ScoringStandardDetail>({
    method: 'POST',
    url: `${standardPath(id)}/activate`,
    data: payload,
  }, '启用评分标准失败')
}

/** 将已启用但非默认的标准直接设为场景默认。 */
export async function setDefaultScoringStandard(id: string, payload: ScoringActivatePayload) {
  return request<ScoringStandardDetail>({
    method: 'POST',
    url: `${standardPath(id)}/set-default`,
    data: payload,
  }, '设置默认评分标准失败')
}

/** 归档启用中的标准（同时取消默认）。 */
export async function archiveScoringStandard(id: string, versionSeq: number) {
  return request<ScoringStandardDetail>({
    method: 'POST',
    url: `${standardPath(id)}/archive`,
    data: { version_seq: versionSeq },
  }, '归档评分标准失败')
}

/** 删除草稿。 */
export async function deleteScoringStandard(id: string, versionSeq: number) {
  return request<ScoringDeleteResult>({
    method: 'DELETE',
    url: standardPath(id),
    params: { version_seq: versionSeq },
  }, '删除评分标准草稿失败')
}

/** 导出一个评分标准的固定版本 Excel，不包含病例数据。 */
export async function exportScoringStandard(id: string): Promise<ScoringApiResult<Blob>> {
  try {
    const response = await ApiService.requestRaw<Blob>({
      method: 'GET',
      url: `${standardPath(id)}/export`,
      responseType: 'blob',
      timeout: 60000,
    })
    if (!(response.data instanceof Blob) || response.data.size === 0) {
      return { success: false, message: '导出的评分标准文件无效', status: response.status }
    }
    return { success: true, data: response.data, status: response.status }
  } catch (error) {
    return {
      success: false,
      message: extractApiErrorMessageFromError(error, '导出评分标准失败'),
      status: isAxiosError(error) ? error.response?.status : undefined,
    }
  }
}

/** 导入固定模板；服务端成功时始终创建新草稿。 */
export async function importScoringStandard(file: File): Promise<ScoringImportResult> {
  if (!file.name.toLowerCase().endsWith('.xlsx')) {
    return { success: false, message: '仅支持 .xlsx 评分标准文件', problems: [], resultUnknown: false }
  }
  if (file.size > 2 * 1024 * 1024) {
    return { success: false, message: '文件不能超过 2 MiB', problems: [], resultUnknown: false }
  }
  const form = new FormData()
  form.append('file', file)
  try {
    const response = await ApiService.requestRaw<ScoringStandardDetail>({
      method: 'POST',
      url: `${BASE}/standards/import`,
      data: form,
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 15 * 60 * 1000,
    })
    const normalized = normalizeApiSuccess<ScoringStandardDetail>(response.data)
    const data = normalized.data
    if (!normalized.success || !isImportedDraft(data)) {
      return {
        success: false,
        message: '服务端成功响应无法确认新草稿，可能已写入。请先刷新列表核对，不要盲目重试',
        problems: [],
        resultUnknown: true,
        status: response.status,
      }
    }
    return {
      success: true,
      data,
      message: normalized.message || '评分标准已导入为草稿',
      problems: [],
      resultUnknown: false,
      status: response.status,
    }
  } catch (error) {
    const status = isAxiosError(error) ? error.response?.status : undefined
    const rejectedBeforeWrite = status === 401 || status === 403 || status === 409 || status === 413 || status === 422
    return {
      success: false,
      message: rejectedBeforeWrite
        ? extractApiErrorMessageFromError(error, '导入评分标准失败')
        : '导入请求未获得可确认的服务端结果，可能已写入。请勿盲目重试，先刷新列表按标准名称核对',
      status,
      code: extractErrorDetail(error).code,
      problems: extractExcelProblems(error),
      resultUnknown: !rejectedBeforeWrite,
    }
  }
}

/** 单病历按最新 ready 结果与本次选择或场景默认标准计分（不落库）。 */
export async function getCaseScore(query: CaseScoreQuery) {
  return request<CaseScore>({
    method: 'GET',
    url: `${BASE}/case`,
    params: {
      institute_id: query.institute_id,
      patient_id: query.patient_id,
      visit_id: query.visit_id,
      scene: query.scene,
      ...(query.standard_id !== undefined ? { standard_id: query.standard_id } : {}),
    },
  }, '读取病历得分失败')
}
