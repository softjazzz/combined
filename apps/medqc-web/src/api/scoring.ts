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
  | 'name_exists'
  | 'conflict'
  | 'invalid'
  | 'items_validation_failed'
  | 'standard_validation_failed'
  | 'scene_without_rule_set'
  | 'rule_set_scene_mismatch'

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
}

export interface ScoringStandardDetail extends ScoringStandardItem {
  groups: ScoringGroup[]
  items: ScoringItem[]
  group_count: number
  item_count: number
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

export interface CaseScoreScored {
  status: 'scored'
  scene: ScoringScene
  standard_id: string | null
  standard_name: string | null
  standard_updated_at: string | null
  rule_set_key: string | null
  rule_set_version: string | null
  job_id: string | null
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

interface ErrorDetail {
  code?: string
  message?: string
  problems?: string[]
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

function standardPath(id: string): string {
  return `${BASE}/standards/${encodeURIComponent(id)}`
}

/** 只发送写接口接受的字段，去掉多余属性。 */
export function toWriteBands(bands: readonly ScoringGradeBand[]): ScoringGradeBand[] {
  return bands.map(({ name, min_score, max_score }) => ({ name, min_score, max_score }))
}

export function toWriteGroups(groups: readonly ScoringGroupWrite[]): ScoringGroupWrite[] {
  return groups.map(({ group_name, max_deduction, sort_order }) => ({ group_name, max_deduction, sort_order }))
}

export function toWriteItems(items: readonly ScoringItem[]): ScoringItem[] {
  return items.map(({ group_name, rule_id, deduction, is_veto, enabled }) => ({
    group_name, rule_id, deduction, is_veto, enabled,
  }))
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

/** 单病历按最新 ready 结果与场景默认标准计分（不落库）。 */
export async function getCaseScore(query: CaseScoreQuery) {
  return request<CaseScore>({
    method: 'GET',
    url: `${BASE}/case`,
    params: {
      institute_id: query.institute_id,
      patient_id: query.patient_id,
      visit_id: query.visit_id,
      scene: query.scene,
    },
  }, '读取病历得分失败')
}
