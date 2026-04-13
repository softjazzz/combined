import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'
import type {
  CustomRuleBatchJob,
  CustomRuleBatchJobQuery,
  CustomRuleBatchResult,
  CustomRuleDraft,
  CustomRuleDraftPayload,
  CustomRuleBatchJobExport,
  CustomRulePublishResult,
  CustomRuleSingleTestResult,
  CustomRuleWorkspaceFilters,
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

export async function createWorkspaceBatchJob(payload: {
  draft_id: string
  scope: 'all' | 'running' | 'final'
  department?: string
  doctor?: string
  date_field: 'admission' | 'discharge'
  start_date?: string
  end_date?: string
  keyword?: string
  record_ids?: string[]
  temperature?: number
  top_p?: number
  max_tokens?: number
}) {
  return requestEnvelope<CustomRuleBatchJob>(
    {
      method: 'POST',
      url: '/api/v1/custom-qc/workspace/batch-jobs',
      data: payload,
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
