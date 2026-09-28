import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'
import type {
  CustomRuleBatchJob,
  CustomRuleBatchJobQuery,
  CustomRuleBatchResult,
  CustomRuleDraft,
  CustomRuleDraftBasicInfo,
  CustomRuleDraftBasicInfoInput,
  CustomRuleDraftPayload,
  CustomRuleDocumentOption,
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
    last_test_summary?: Record<string, unknown> | null
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
