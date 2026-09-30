import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'
import type {
  CustomRuleBatchJob,
  CustomRuleBatchJobQuery,
  CustomRuleBatchResult,
  CustomRuleDraft,
  CustomRuleDraftBasicInfo,
  CustomRuleDraftBasicInfoInput,
  CustomRuleDraftBatchPublishItem,
  CustomRuleDraftPayload,
  CustomRuleDocumentOption,
  CustomRuleDraftCondition,
  FixedTestValidationInput,
  FixedTestValidationProof,
  FixedTestValidationState,
  VisualConditionFieldOperator,
  VisualConditionFieldOption,
  VisualConditionOption,
  VisualConditionOptions,
  VisualConditionTree,
  CustomRuleBatchJobExport,
  CustomRulePublishResult,
  CustomRuleSingleTestResult,
  CustomRuleWorkspaceFilters,
  CustomRuleWorkspaceBatchJobCreatePayload,
  CustomRuleWorkspaceRecord,
  CustomRuleWorkspaceRecordQuery,
  CustomRuleWorkspaceTestRecord,
  WorkspaceDraftStatus,
} from '@/types/custom-rule-workspace'
import type { CustomQcPromptGenerationResult } from '@/types/custom-qc'

type ServiceResult<T> = {
  success: boolean
  data?: T
  message?: string
}

export type DraftBasicInfoMutationResult =
  | { success: true; data: CustomRuleDraftBasicInfo; resultUnknown: false; conflict: false }
  | { success: false; message: string; resultUnknown: boolean; conflict: boolean }

const DRAFT_BASIC_INFO_URL = '/api/v1/custom-qc/workspace/draft-basic-info'
const DRAFT_CONDITION_URL = '/api/v1/custom-qc/workspace/draft-condition'

export type DraftConditionMutationResult =
  | { success: true; data: CustomRuleDraftCondition; resultUnknown: false; conflict: false }
  | { success: false; message: string; resultUnknown: boolean; conflict: boolean }

export type FixedTestValidationMutationResult =
  | { success: true; data: FixedTestValidationState; resultUnknown: false; conflict: false }
  | { success: false; message: string; resultUnknown: boolean; conflict: boolean }

export type ValidatedDraftPublishResult =
  | { success: true; data: CustomRulePublishResult; resultUnknown: false; conflict: false }
  | { success: false; message: string; resultUnknown: boolean; conflict: boolean }

export type DraftBatchPublishResult =
  | { success: true; data: CustomRulePublishResult[]; resultUnknown: false; conflict: false }
  | { success: false; message: string; resultUnknown: boolean; conflict: boolean }

export type DraftDeleteResult =
  | { success: true; resultUnknown: false; conflict: false }
  | { success: false; message: string; resultUnknown: boolean; conflict: boolean }

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function normalizeDraftBasicInfo(value: unknown): CustomRuleDraftBasicInfo | null {
  if (!isRecord(value)) return null
  const required = ['id', 'rule_code', 'updated_at', 'name', 'category', 'rule_type', 'document_type']
  if (value.status !== 'draft' || required.some((key) => typeof value[key] !== 'string' || !String(value[key]).trim())) {
    return null
  }
  if (Number.isNaN(Date.parse(String(value.updated_at)))) return null
  return value as unknown as CustomRuleDraftBasicInfo
}

function nonBlankText(value: unknown): value is string {
  return typeof value === 'string' && Boolean(value.trim()) && value === value.trim()
}

function normalizeSimpleOptions(value: unknown): VisualConditionOption[] | null {
  if (!Array.isArray(value) || value.length === 0) return null
  const options = value.filter((item): item is VisualConditionOption =>
    isRecord(item) && nonBlankText(item.value) && nonBlankText(item.label),
  )
  return options.length === value.length && new Set(options.map((item) => item.value)).size === options.length
    ? options
    : null
}

function normalizeVisualConditionOptions(value: unknown): VisualConditionOptions | null {
  if (!isRecord(value) || value.schema_version !== 'visual-condition-v1'
    || !Array.isArray(value.fields) || !Array.isArray(value.group_operators)
    || !isRecord(value.limits) || !isRecord(value.timeliness) || !isRecord(value.result_semantics)) return null
  const documents = normalizeSimpleOptions(value.document_types)
  const startFields = normalizeSimpleOptions(value.timeliness.start_fields)
  const endFields = normalizeSimpleOptions(value.timeliness.end_fields)
  const timeOperators = normalizeSimpleOptions(value.timeliness.operators)
  const units = normalizeSimpleOptions(value.timeliness.units)
  if (!documents || !startFields || !endFields || !timeOperators || !units) return null
  if (!value.group_operators.every((item) => item === 'all' || item === 'any')
    || new Set(value.group_operators).size !== value.group_operators.length
    || !Number.isInteger(value.limits.max_groups) || Number(value.limits.max_groups) < 1
    || !Number.isInteger(value.limits.max_conditions_per_group) || Number(value.limits.max_conditions_per_group) < 1
    || !Array.isArray(value.timeliness.allowed_pairs)) return null
  if (value.result_semantics.true !== 'non_compliant'
    || value.result_semantics.false !== 'compliant'
    || value.result_semantics.unknown !== 'data_gap') return null
  const allowedTimeOperators = new Set(['lt', 'lte', 'gt', 'gte'])
  const allowedUnits = new Set(['minutes', 'hours', 'days'])
  if (!timeOperators.every((item) => allowedTimeOperators.has(item.value))
    || !units.every((item) => allowedUnits.has(item.value))) return null
  const startKeys = new Set(startFields.map((item) => item.value))
  const endKeys = new Set(endFields.map((item) => item.value))
  if (!value.timeliness.allowed_pairs.every((pair) => isRecord(pair)
    && nonBlankText(pair.start_fact) && nonBlankText(pair.end_fact)
    && startKeys.has(pair.start_fact) && endKeys.has(pair.end_fact))) return null
  const fields = value.fields.filter((field): field is VisualConditionFieldOption => {
    if (!isRecord(field) || !nonBlankText(field.key) || !nonBlankText(field.label)
      || !['string', 'number', 'datetime', 'boolean'].includes(String(field.value_type))
      || !['record', 'document'].includes(String(field.kind)) || !Array.isArray(field.operators)
      || field.operators.length === 0) return false
    const operators = field.operators as unknown[]
    return operators.every((operator): operator is VisualConditionFieldOperator =>
      isRecord(operator) && nonBlankText(operator.value) && nonBlankText(operator.label)
      && typeof operator.value_required === 'boolean'
      && (operator.value_options === undefined || normalizeSimpleOptions(operator.value_options) !== null),
    ) && new Set((field.operators as VisualConditionFieldOperator[]).map((item) => item.value)).size === field.operators.length
  })
  if (fields.length !== value.fields.length || fields.length === 0
    || new Set(fields.map((item) => item.key)).size !== fields.length) return null
  return value as unknown as VisualConditionOptions
}

function normalizeVisualConditionTree(value: unknown): VisualConditionTree | null {
  if (!isRecord(value) || value.schema_version !== 'visual-condition-v1'
    || !['all', 'any'].includes(String(value.root_operator)) || !Array.isArray(value.groups)
    || value.groups.length === 0) return null
  const groupIds = new Set<string>()
  const conditionIds = new Set<string>()
  if (!value.groups.every((group) => {
    if (!isRecord(group) || !nonBlankText(group.id) || groupIds.has(group.id)
      || !['all', 'any'].includes(String(group.operator)) || !Array.isArray(group.conditions)
      || group.conditions.length === 0) return false
    groupIds.add(group.id)
    return group.conditions.every((condition) => {
      if (!isRecord(condition) || !nonBlankText(condition.id) || conditionIds.has(condition.id)) return false
      conditionIds.add(condition.id)
      if (condition.kind === 'field') {
        const validValue = condition.value === undefined || typeof condition.value === 'string'
          || typeof condition.value === 'number' || typeof condition.value === 'boolean'
          || (Array.isArray(condition.value) && condition.value.length > 0
            && condition.value.every((item) => nonBlankText(item)))
        return nonBlankText(condition.fact_key) && nonBlankText(condition.operator) && validValue
      }
      if (condition.kind === 'document_presence') {
        return nonBlankText(condition.document_type) && ['exists', 'not_exists'].includes(String(condition.operator))
      }
      return condition.kind === 'timeliness'
        && nonBlankText(condition.start_fact) && nonBlankText(condition.end_fact)
        && ['lt', 'lte', 'gt', 'gte'].includes(String(condition.operator))
        && isRecord(condition.threshold) && Number.isInteger(condition.threshold.value)
        && Number(condition.threshold.value) >= 1
        && ['minutes', 'hours', 'days'].includes(String(condition.threshold.unit))
    })
  })) return null
  return value as unknown as VisualConditionTree
}

function normalizeDraftCondition(value: unknown): CustomRuleDraftCondition | null {
  if (!isRecord(value) || value.status !== 'draft' || !nonBlankText(value.id)
    || !nonBlankText(value.rule_code) || !nonBlankText(value.updated_at)
    || Number.isNaN(Date.parse(value.updated_at))) return null
  const visualCondition = value.visual_condition === null ? null : normalizeVisualConditionTree(value.visual_condition)
  return value.visual_condition === null || visualCondition
    ? { ...value, visual_condition: visualCondition } as CustomRuleDraftCondition
    : null
}

function normalizeRecordRef(value: unknown) {
  if (!isRecord(value) || !nonBlankText(value.institute_id)
    || !nonBlankText(value.patient_id) || !nonBlankText(value.visit_id)) return null
  return {
    institute_id: value.institute_id,
    patient_id: value.patient_id,
    visit_id: value.visit_id,
  }
}

function normalizeValidationProof(value: unknown): FixedTestValidationProof | null {
  if (!isRecord(value) || value.schema_version !== 'fixed_test_records_v1'
    || !nonBlankText(value.validation_id) || !nonBlankText(value.draft_id)
    || !nonBlankText(value.validated_revision) || !nonBlankText(value.proof_revision)
    || !nonBlankText(value.created_at) || Number.isNaN(Date.parse(value.created_at))) return null
  const countKeys = [
    'item_count', 'success_count', 'failed_count', 'issue_records', 'compliant_records',
    'unknown_count', 'technical_error_count',
  ]
  if (countKeys.some((key) => !Number.isInteger(value[key]) || Number(value[key]) < 0)
    || !Array.isArray(value.selected_items) || !Array.isArray(value.results)
    || !Array.isArray(value.failures)) return null
  const selectedItems = value.selected_items.map((item) => {
    if (!isRecord(item) || !nonBlankText(item.item_id) || !nonBlankText(item.item_updated_at)) return null
    const recordRef = normalizeRecordRef(item.record_ref)
    return recordRef ? { item_id: item.item_id, item_updated_at: item.item_updated_at, record_ref: recordRef } : null
  })
  const allowedStatuses = new Set([
    'compliant', 'non_compliant', 'ai_suggested_compliant', 'ai_suggested_non_compliant',
    'data_gap', 'not_applicable', 'not_executed', 'technical_error', 'uncertain',
  ])
  const results = value.results.map((item) => {
    if (!isRecord(item) || !nonBlankText(item.item_id) || !nonBlankText(item.item_updated_at)
      || !allowedStatuses.has(String(item.status)) || !Number.isInteger(item.issue_count)
      || Number(item.issue_count) < 0 || !isRecord(item.finding)
      || typeof item.finding.description !== 'string' || item.finding.description.length > 300
      || typeof item.finding.evidence !== 'string' || item.finding.evidence.length > 300
      || !Array.isArray(item.condition_trace) || item.condition_trace.length > 20
      || !item.condition_trace.every((trace) => typeof trace === 'string' && trace.length <= 300)) return null
    const recordRef = normalizeRecordRef(item.record_ref)
    return recordRef ? {
      item_id: item.item_id, item_updated_at: item.item_updated_at, record_ref: recordRef,
      status: item.status, issue_count: item.issue_count,
      finding: { description: item.finding.description, evidence: item.finding.evidence },
      condition_trace: item.condition_trace,
    } : null
  })
  const failures = value.failures.map((item) => isRecord(item) && nonBlankText(item.item_id)
    && nonBlankText(item.code) && nonBlankText(item.message)
    ? { item_id: item.item_id, code: item.code, message: item.message }
    : null)
  if (selectedItems.some((item) => item === null) || results.some((item) => item === null)
    || failures.some((item) => item === null) || selectedItems.length !== value.item_count
    || results.length + failures.length !== value.item_count) return null
  return {
    ...value,
    selected_items: selectedItems,
    results,
    failures,
  } as FixedTestValidationProof
}

function normalizeValidationState(value: unknown, draftId: string): FixedTestValidationState | null {
  if (!isRecord(value) || value.draft_id !== draftId || !nonBlankText(value.draft_updated_at)
    || typeof value.publish_ready !== 'boolean' || !['draft', 'published'].includes(String(value.draft_status))
    || (value.published_rule_id !== null && !nonBlankText(value.published_rule_id))) return null
  const reasons = new Set(['not_tested', 'draft_changed', 'validation_incomplete', 'draft_not_executable'])
  if (value.unavailable_reason !== null && !reasons.has(String(value.unavailable_reason))) return null
  const validation = value.validation === null ? null : normalizeValidationProof(value.validation)
  if (value.validation !== null && (!validation || validation.draft_id !== draftId)) return null
  if (value.publish_ready && (!validation || value.unavailable_reason !== null || value.draft_status !== 'draft')) return null
  return { ...value, validation } as FixedTestValidationState
}

function errorStatus(error: unknown): number | undefined {
  if (!isRecord(error) || !isRecord(error.response)) return undefined
  return typeof error.response.status === 'number' ? error.response.status : undefined
}

async function mutateDraftBasicInfo(
  method: 'POST' | 'PATCH',
  url: string,
  data: Record<string, unknown>,
): Promise<DraftBasicInfoMutationResult> {
  try {
    const response = await ApiService.requestRaw({ method, url, data })
    const normalized = normalizeApiSuccess<unknown>(response.data)
    const draft = normalized.success ? normalizeDraftBasicInfo(normalized.data) : null
    if (!draft) {
      return {
        success: false,
        message: '服务端未返回可确认的草稿回执，请刷新草稿列表核对，勿盲目重试',
        resultUnknown: true,
        conflict: false,
      }
    }
    return { success: true, data: draft, resultUnknown: false, conflict: false }
  } catch (error) {
    const status = errorStatus(error)
    const conflict = status === 409
    const confirmedRejection = status === 401 || status === 403 || status === 404 || status === 409 || status === 422
    return {
      success: false,
      message: confirmedRejection
        ? toErrorMessage(error, conflict ? '草稿已变更，请重新读取后再修改' : '草稿保存被拒绝')
        : '草稿保存结果无法确认，请刷新草稿列表核对，勿盲目重试',
      resultUnknown: !confirmedRejection,
      conflict,
    }
  }
}

export async function getDraftBasicInfoOptions(): Promise<ServiceResult<{ documents: CustomRuleDocumentOption[] }>> {
  const result = await requestEnvelope<unknown>(
    { method: 'GET', url: `${DRAFT_BASIC_INFO_URL}/options` },
    '获取质控文书选项失败',
  )
  if (!result.success) return { success: false, message: result.message }
  if (!isRecord(result.data) || !Array.isArray(result.data.documents)) {
    return { success: false, message: '质控文书选项回执格式异常' }
  }
  const documents = result.data.documents.filter((item): item is CustomRuleDocumentOption =>
    isRecord(item)
    && typeof item.value === 'string'
    && Boolean(item.value.trim())
    && item.value === item.value.trim()
    && typeof item.label === 'string'
    && Boolean(item.label.trim()),
  )
  const distinctValues = new Set(documents.map((item) => item.value.trim()))
  if (documents.length !== result.data.documents.length || documents.length === 0 || distinctValues.size !== documents.length) {
    return { success: false, message: '质控文书选项回执格式异常' }
  }
  return { success: true, data: { documents } }
}

export async function getDraftBasicInfo(draftId: string): Promise<ServiceResult<CustomRuleDraftBasicInfo>> {
  const result = await requestEnvelope<unknown>(
    { method: 'GET', url: `${DRAFT_BASIC_INFO_URL}/${encodeURIComponent(draftId)}` },
    '读取草稿基础信息失败',
  )
  if (!result.success) return { success: false, message: result.message }
  const data = normalizeDraftBasicInfo(result.data)
  return data && data.id === draftId
    ? { success: true, data }
    : { success: false, message: '草稿基础信息回执格式异常' }
}

export function createDraftBasicInfo(payload: CustomRuleDraftBasicInfoInput) {
  return mutateDraftBasicInfo('POST', DRAFT_BASIC_INFO_URL, { ...payload })
}

export async function updateDraftBasicInfo(
  draftId: string,
  payload: CustomRuleDraftBasicInfoInput & { expected_updated_at: string },
) {
  const result = await mutateDraftBasicInfo('PATCH', `${DRAFT_BASIC_INFO_URL}/${encodeURIComponent(draftId)}`, { ...payload })
  if (result.success === false || result.data.id === draftId) return result
  return {
    success: false as const,
    message: '服务端返回了其他草稿，更新结果无法确认，请刷新核对，勿盲目重试',
    resultUnknown: true,
    conflict: false,
  }
}

export async function getDraftConditionOptions(): Promise<ServiceResult<VisualConditionOptions>> {
  const result = await requestEnvelope<unknown>(
    { method: 'GET', url: `${DRAFT_CONDITION_URL}/options` },
    '读取条件目录失败',
  )
  if (!result.success) return { success: false, message: result.message }
  const data = normalizeVisualConditionOptions(result.data)
  return data ? { success: true, data } : { success: false, message: '条件目录回执格式异常' }
}

export async function getDraftCondition(draftId: string): Promise<ServiceResult<CustomRuleDraftCondition>> {
  const result = await requestEnvelope<unknown>(
    { method: 'GET', url: `${DRAFT_CONDITION_URL}/${encodeURIComponent(draftId)}` },
    '读取条件配置失败',
  )
  if (!result.success) return { success: false, message: result.message }
  const data = normalizeDraftCondition(result.data)
  return data && data.id === draftId
    ? { success: true, data }
    : { success: false, message: '条件配置回执格式异常' }
}

export async function updateDraftCondition(
  draftId: string,
  payload: { expected_updated_at: string; visual_condition: VisualConditionTree },
): Promise<DraftConditionMutationResult> {
  try {
    const response = await ApiService.requestRaw({
      method: 'PATCH', url: `${DRAFT_CONDITION_URL}/${encodeURIComponent(draftId)}`, data: payload,
    })
    const normalized = normalizeApiSuccess<unknown>(response.data)
    const data = normalized.success ? normalizeDraftCondition(normalized.data) : null
    if (!data || data.id !== draftId || data.visual_condition === null) {
      return { success: false, message: '条件保存结果无法确认，请重新读取草稿核对，勿盲目重试', resultUnknown: true, conflict: false }
    }
    return { success: true, data, resultUnknown: false, conflict: false }
  } catch (error) {
    const status = errorStatus(error)
    const conflict = status === 409
    const confirmedRejection = status === 401 || status === 403 || status === 404 || status === 409 || status === 422
    return {
      success: false,
      message: confirmedRejection
        ? toErrorMessage(error, conflict ? '草稿已变更，请重新读取条件后再修改' : '条件保存被拒绝')
        : '条件保存结果无法确认，请重新读取草稿核对，勿盲目重试',
      resultUnknown: !confirmedRejection,
      conflict,
    }
  }
}

function toErrorMessage(error: unknown, fallback: string): string {
  return extractApiErrorMessageFromError(error, fallback)
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
      message: normalized.message,
    }
  } catch (error) {
    return {
      success: false,
      message: toErrorMessage(error, fallbackMessage),
    }
  }
}

export async function listWorkspaceDrafts(params: {
  status?: WorkspaceDraftStatus
  q?: string
  page?: number
  page_size?: number
}) {
  return requestEnvelope<{
    items: CustomRuleDraft[]
    total: number
    page: number
    page_size: number
  }>(
    {
      method: 'GET',
      url: '/api/v1/custom-qc/workspace/drafts',
      params,
    },
    '获取草稿列表失败',
  )
}

export async function createWorkspaceDraft(payload: CustomRuleDraftPayload) {
  return requestEnvelope<CustomRuleDraft>(
    {
      method: 'POST',
      url: '/api/v1/custom-qc/workspace/drafts',
      data: payload,
    },
    '创建草稿失败',
  )
}

export async function updateWorkspaceDraft(
  draftId: string,
  payload: Partial<CustomRuleDraftPayload> & {
    prompt_template?: string
    examples?: Array<{ title: string; content: string }>
    check_logic?: Record<string, unknown>
  },
) {
  return requestEnvelope<CustomRuleDraft>(
    {
      method: 'PUT',
      url: `/api/v1/custom-qc/workspace/drafts/${encodeURIComponent(draftId)}`,
      data: payload,
    },
    '更新草稿失败',
  )
}

export async function deleteWorkspaceDraft(draftId: string) {
  return requestEnvelope<{ id: string }>(
    {
      method: 'DELETE',
      url: `/api/v1/custom-qc/workspace/drafts/${encodeURIComponent(draftId)}`,
    },
    '删除草稿失败',
  )
}

/** 按草稿版本 CAS 删除；只能删除本人未上线草稿。 */
export async function deleteWorkspaceDraftChecked(
  draftId: string,
  expectedUpdatedAt: string,
): Promise<DraftDeleteResult> {
  try {
    const response = await ApiService.requestRaw({
      method: 'DELETE',
      url: `/api/v1/custom-qc/workspace/drafts/${encodeURIComponent(draftId)}`,
      params: { expected_updated_at: expectedUpdatedAt },
    })
    const normalized = normalizeApiSuccess<unknown>(response.data)
    if (!normalized.success || !isRecord(normalized.data) || normalized.data.id !== draftId) {
      return {
        success: false, resultUnknown: true, conflict: false,
        message: '删除结果无法确认，请刷新列表核对，勿盲目重试',
      }
    }
    return { success: true, resultUnknown: false, conflict: false }
  } catch (error) {
    const status = errorStatus(error)
    const conflict = status === 409
    const confirmedRejection = [401, 403, 404, 409, 422].includes(status || 0)
    return {
      success: false,
      message: confirmedRejection
        ? toErrorMessage(error, conflict ? '草稿已变化或已上线，请刷新后重试' : '删除被拒绝')
        : '删除结果无法确认，请刷新列表核对，勿盲目重试',
      resultUnknown: !confirmedRejection,
      conflict,
    }
  }
}

/** 批量上线：服务端全批校验后同一事务发布，任一失败整批不发布。 */
export async function publishWorkspaceDraftsBatch(
  items: CustomRuleDraftBatchPublishItem[],
): Promise<DraftBatchPublishResult> {
  try {
    const response = await ApiService.requestRaw({
      method: 'POST',
      url: '/api/v1/custom-qc/workspace/drafts/publish-batch',
      data: { items },
    })
    const normalized = normalizeApiSuccess<unknown>(response.data)
    const value = normalized.data
    const expected = new Set(items.map((item) => item.draft_id))
    const published = normalized.success && isRecord(value) && Array.isArray(value.items)
      ? value.items
      : null
    const valid = published !== null && published.length === expected.size
      && published.every((item) => isRecord(item) && typeof item.draft_id === 'string'
        && expected.has(item.draft_id) && nonBlankText(item.rule_code)
        && nonBlankText(item.published_rule_id) && item.status === 'published')
      && new Set(published.map((item) => (item as Record<string, unknown>).draft_id)).size === expected.size
    if (!valid) {
      return {
        success: false, resultUnknown: true, conflict: false,
        message: '批量上线结果无法确认，请刷新列表核对，勿盲目重试',
      }
    }
    return {
      success: true, data: published as unknown as CustomRulePublishResult[], resultUnknown: false, conflict: false,
    }
  } catch (error) {
    const status = errorStatus(error)
    const conflict = status === 409
    const confirmedRejection = [401, 403, 404, 409, 422].includes(status || 0)
    return {
      success: false,
      message: confirmedRejection
        ? toErrorMessage(error, conflict ? '所选草稿或测试证明已变化，整批未上线，请刷新后重试' : '批量上线被拒绝，整批未上线')
        : '批量上线结果无法确认，请刷新列表核对，勿盲目重试',
      resultUnknown: !confirmedRejection,
      conflict,
    }
  }
}

export async function generateWorkspaceDraftPrompt(draftId: string) {
  return requestEnvelope<{ draft: CustomRuleDraft; prompt_result: CustomQcPromptGenerationResult }>(
    {
      method: 'POST',
      url: `/api/v1/custom-qc/workspace/drafts/${encodeURIComponent(draftId)}/generate-prompt`,
    },
    '生成 Prompt 失败',
  )
}

export async function publishWorkspaceDraft(draftId: string) {
  return requestEnvelope<CustomRulePublishResult>(
    {
      method: 'POST',
      url: `/api/v1/custom-qc/workspace/drafts/${encodeURIComponent(draftId)}/publish`,
    },
    '发布规则失败',
  )
}

const validationUrl = (draftId: string) =>
  `/api/v1/custom-qc/workspace/drafts/${encodeURIComponent(draftId)}/test-validations`

export async function getFixedTestValidation(
  draftId: string,
): Promise<ServiceResult<FixedTestValidationState>> {
  const result = await requestEnvelope<unknown>(
    { method: 'GET', url: validationUrl(draftId) },
    '读取固定测试证明失败',
  )
  if (!result.success) return { success: false, message: result.message }
  const data = normalizeValidationState(result.data, draftId)
  return data
    ? { success: true, data }
    : { success: false, message: '固定测试证明回执格式异常' }
}

export async function runFixedTestValidation(
  draftId: string,
  payload: FixedTestValidationInput,
): Promise<FixedTestValidationMutationResult> {
  try {
    const response = await ApiService.requestRaw({
      method: 'POST', url: validationUrl(draftId), data: payload,
    })
    const normalized = normalizeApiSuccess<unknown>(response.data)
    const data = normalized.success ? normalizeValidationState(normalized.data, draftId) : null
    if (!data) {
      return {
        success: false, resultUnknown: true, conflict: false,
        message: '测试结果无法确认，请读取测试证明核对，勿盲目重试',
      }
    }
    return { success: true, data, resultUnknown: false, conflict: false }
  } catch (error) {
    const status = errorStatus(error)
    const conflict = status === 409
    const confirmedRejection = [401, 403, 404, 409, 422].includes(status || 0)
    return {
      success: false,
      message: confirmedRejection
        ? toErrorMessage(error, conflict ? '草稿或测试病例版本已变化，请刷新后重新选择' : '固定测试被拒绝')
        : '测试结果无法确认，请读取测试证明核对，勿盲目重试',
      resultUnknown: !confirmedRejection,
      conflict,
    }
  }
}

export async function publishValidatedWorkspaceDraft(
  draftId: string,
  payload: { expected_updated_at: string; validation_id: string },
): Promise<ValidatedDraftPublishResult> {
  try {
    const response = await ApiService.requestRaw({
      method: 'POST',
      url: `/api/v1/custom-qc/workspace/drafts/${encodeURIComponent(draftId)}/publish`,
      data: payload,
    })
    const normalized = normalizeApiSuccess<unknown>(response.data)
    const value = normalized.data
    const data = normalized.success && isRecord(value) && value.draft_id === draftId
      && nonBlankText(value.rule_code) && nonBlankText(value.published_rule_id)
      && value.status === 'published'
      ? value as unknown as CustomRulePublishResult
      : null
    if (!data) {
      return {
        success: false, resultUnknown: true, conflict: false,
        message: '发布结果无法确认，请重新读取草稿核对，勿盲目重试',
      }
    }
    return { success: true, data, resultUnknown: false, conflict: false }
  } catch (error) {
    const status = errorStatus(error)
    const conflict = status === 409
    const confirmedRejection = [401, 403, 404, 409, 422].includes(status || 0)
    return {
      success: false,
      message: confirmedRejection
        ? toErrorMessage(error, conflict ? '草稿或测试证明已变化，请重新读取后再发布' : '发布被拒绝')
        : '发布结果无法确认，请重新读取草稿核对，勿盲目重试',
      resultUnknown: !confirmedRejection,
      conflict,
    }
  }
}

export async function getWorkspaceRecordFilters(params: {
  scope: 'all' | 'running' | 'final'
  department?: string
}) {
  return requestEnvelope<CustomRuleWorkspaceFilters>(
    {
      method: 'GET',
      url: '/api/v1/custom-qc/workspace/filters',
      params,
    },
    '获取筛选项失败',
  )
}

export async function getWorkspaceRecords(params: CustomRuleWorkspaceRecordQuery) {
  return requestEnvelope<{
    items: CustomRuleWorkspaceRecord[]
    total: number
    page: number
    page_size: number
  }>(
    {
      method: 'GET',
      url: '/api/v1/custom-qc/workspace/records',
      params,
    },
    '获取病历列表失败',
  )
}

export async function runWorkspaceSingleTest(payload: {
  draft_id: string
  records: CustomRuleWorkspaceTestRecord[]
  temperature?: number
  top_p?: number
  max_tokens?: number
}) {
  return requestEnvelope<CustomRuleSingleTestResult>(
    {
      method: 'POST',
      url: '/api/v1/custom-qc/workspace/test',
      data: payload,
    },
    '单病历测试失败',
  )
}

export async function runWorkspaceBatchTest(payload: {
  draft_id: string
  records: CustomRuleWorkspaceTestRecord[]
  temperature?: number
  top_p?: number
  max_tokens?: number
}) {
  return requestEnvelope<CustomRuleBatchResult>(
    {
      method: 'POST',
      url: '/api/v1/custom-qc/workspace/test/batch',
      data: payload,
    },
    '批量测试失败',
  )
}

export async function createWorkspaceBatchJob(payload: CustomRuleWorkspaceBatchJobCreatePayload) {
  const recordRefs = payload.record_refs?.length
    ? payload.record_refs.map((item) => ({
        institute_id: item.institute_id,
        patient_id: item.patient_id,
        visit_id: item.visit_id,
      }))
    : undefined
  const data: CustomRuleWorkspaceBatchJobCreatePayload = {
    draft_id: payload.draft_id,
    draft_ids: payload.draft_ids,
    execution_mode: payload.execution_mode,
    run_mode: payload.run_mode,
    scope: payload.scope,
    department: payload.department,
    doctor: payload.doctor,
    date_field: payload.date_field,
    start_date: payload.start_date,
    end_date: payload.end_date,
    keyword: payload.keyword,
    ...(recordRefs ? { record_refs: recordRefs } : {}),
    temperature: payload.temperature,
    top_p: payload.top_p,
    max_tokens: payload.max_tokens,
  }
  return requestEnvelope<CustomRuleBatchJob>(
    {
      method: 'POST',
      url: '/api/v1/custom-qc/workspace/batch-jobs',
      data,
    },
    '创建批量任务失败',
  )
}

export async function listWorkspaceBatchJobs(params: CustomRuleBatchJobQuery) {
  return requestEnvelope<{
    items: CustomRuleBatchJob[]
    total: number
    page: number
    page_size: number
  }>(
    {
      method: 'GET',
      url: '/api/v1/custom-qc/workspace/batch-jobs',
      params,
    },
    '获取批量任务失败',
  )
}

export async function getWorkspaceBatchJob(jobId: string) {
  return requestEnvelope<CustomRuleBatchJob>(
    {
      method: 'GET',
      url: `/api/v1/custom-qc/workspace/batch-jobs/${encodeURIComponent(jobId)}`,
    },
    '获取批量任务详情失败',
  )
}

export async function cancelWorkspaceBatchJob(jobId: string) {
  return requestEnvelope<CustomRuleBatchJob>(
    {
      method: 'POST',
      url: `/api/v1/custom-qc/workspace/batch-jobs/${encodeURIComponent(jobId)}/cancel`,
    },
    '停止批量任务失败',
  )
}

export async function retryWorkspaceBatchJob(jobId: string) {
  return requestEnvelope<CustomRuleBatchJob>(
    {
      method: 'POST',
      url: `/api/v1/custom-qc/workspace/batch-jobs/${encodeURIComponent(jobId)}/retry`,
    },
    '重试批量任务失败',
  )
}

export async function exportWorkspaceBatchJob({
  job_id,
  format = 'xlsx',
}: CustomRuleBatchJobExport) {
  try {
    const response = await ApiService.requestRaw<Blob>({
      method: 'GET',
      url: `/api/v1/custom-qc/workspace/batch-jobs/${encodeURIComponent(job_id)}/export`,
      params: { format },
      responseType: 'blob',
    })
    return { success: true, data: response.data }
  } catch (error) {
    return {
      success: false,
      message: toErrorMessage(error, '导出批量任务失败'),
    }
  }
}
