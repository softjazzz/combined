import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'
import type {
  SichuanBatchJobDebugSnapshot,
  SichuanBatchJobResultTrace,
  SichuanBatchJob,
  SichuanBatchJobExport,
  SichuanBatchJobQuery,
  Luxian0609ReviewReport,
} from '@/views/workstation-v4/semantic-rules/types'
import type { SingleRecordQcResultPayload } from '@/views/workstation-v4/customer-sample-validation/single-record-result-model'

type ServiceResult<T> = {
  success: boolean
  data?: T
  message?: string
}

const WORKSPACE_QUERY_TIMEOUT_MS = 60000

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

export async function createSichuanWorkspaceBatchJob(payload: {
  rule_ids?: string[]
  rule_set_key?: string
  execution_strategy?: string
  quality_profile?: string
  bucket_strategy?: string
  batch_output_mode?: string
  enable_selective_refine?: boolean
  refine_confidence_threshold?: number
  max_refine_candidates?: number
  scope: 'all' | 'running' | 'final'
  department?: string
  doctor?: string
  date_field: 'admission' | 'discharge'
  start_date?: string
  end_date?: string
  keyword?: string
  record_ids?: string[]
}) {
  return requestEnvelope<SichuanBatchJob>(
    {
      method: 'POST',
      url: '/api/v1/qc/sichuan/workspace/batch-jobs',
      data: payload,
    },
    '创建四川规则批量任务失败',
  )
}

export async function listSichuanWorkspaceBatchJobs(params: SichuanBatchJobQuery) {
  return requestEnvelope<{
    items: SichuanBatchJob[]
    total: number
    page: number
    page_size: number
  }>(
    {
      method: 'GET',
      url: '/api/v1/qc/sichuan/workspace/batch-jobs',
      params,
      timeout: WORKSPACE_QUERY_TIMEOUT_MS,
    },
    '获取四川规则批量任务失败',
  )
}

export async function getSichuanWorkspaceBatchJob(jobId: string) {
  return requestEnvelope<SichuanBatchJob>(
    {
      method: 'GET',
      url: `/api/v1/qc/sichuan/workspace/batch-jobs/${encodeURIComponent(jobId)}`,
      timeout: WORKSPACE_QUERY_TIMEOUT_MS,
    },
    '获取四川规则批量任务详情失败',
  )
}

/** 单病历结果页唯一允许使用的结果读取接口。 */
export async function getLatestLuxian0609RecordResult(recordId: string) {
  return requestEnvelope<SingleRecordQcResultPayload>(
    {
      method: 'GET',
      url: `/api/v1/qc/sichuan/workspace/records/${encodeURIComponent(recordId)}/latest-result`,
      timeout: WORKSPACE_QUERY_TIMEOUT_MS,
    },
    '获取该病历最近一次质控结果失败',
  )
}

export async function cancelSichuanWorkspaceBatchJob(jobId: string) {
  return requestEnvelope<SichuanBatchJob>(
    {
      method: 'POST',
      url: `/api/v1/qc/sichuan/workspace/batch-jobs/${encodeURIComponent(jobId)}/cancel`,
    },
    '停止四川规则批量任务失败',
  )
}

export async function retrySichuanWorkspaceBatchJob(jobId: string) {
  return requestEnvelope<SichuanBatchJob>(
    {
      method: 'POST',
      url: `/api/v1/qc/sichuan/workspace/batch-jobs/${encodeURIComponent(jobId)}/retry`,
    },
    '重试四川规则批量任务失败',
  )
}

export async function reviewSichuanWorkspaceBatchJob(jobId: string) {
  return requestEnvelope<{
    job: SichuanBatchJob
    review_report: Luxian0609ReviewReport
  }>(
    {
      method: 'POST',
      url: `/api/v1/qc/sichuan/workspace/batch-jobs/${encodeURIComponent(jobId)}/review`,
      timeout: WORKSPACE_QUERY_TIMEOUT_MS,
    },
    '复核泸县0609任务结果失败',
  )
}

export async function getSichuanWorkspaceBatchJobDebugSnapshot(
  jobId: string,
  params?: {
    rule_job_id?: string
    item_limit?: number
  },
) {
  return requestEnvelope<SichuanBatchJobDebugSnapshot>(
    {
      method: 'GET',
      url: `/api/v1/qc/sichuan/workspace/batch-jobs/${encodeURIComponent(jobId)}/debug`,
      params,
      timeout: WORKSPACE_QUERY_TIMEOUT_MS,
    },
    '获取四川规则批量任务调试快照失败',
  )
}

export async function getSichuanWorkspaceBatchJobResultTrace(
  jobId: string,
  params: {
    record_id?: string
    visit_id?: string
    rule_id?: string
    item_index?: number
  },
) {
  return requestEnvelope<SichuanBatchJobResultTrace>(
    {
      method: 'GET',
      url: `/api/v1/qc/sichuan/workspace/batch-jobs/${encodeURIComponent(jobId)}/trace`,
      params,
      timeout: WORKSPACE_QUERY_TIMEOUT_MS,
    },
    '获取质控诊断追踪失败',
  )
}

export async function exportSichuanWorkspaceBatchJob({
  job_id,
  format = 'xlsx',
}: SichuanBatchJobExport) {
  try {
    const response = await ApiService.requestRaw<Blob>({
      method: 'GET',
      url: `/api/v1/qc/sichuan/workspace/batch-jobs/${encodeURIComponent(job_id)}/export`,
      params: { format },
      responseType: 'blob',
    })
    return { success: true, data: response.data }
  } catch (error) {
    return {
      success: false,
      message: toErrorMessage(error, '导出四川规则批量任务失败'),
    }
  }
}

export async function evaluateSichuanRuleForVisit(payload: {
  rule_id: string
  institute_id: string
  patient_id: string
  visit_id: string
  source_schema?: string
  bundle_schema?: string
  force_refresh_bundle?: boolean
  model?: string
}) {
  return requestEnvelope<Record<string, unknown>>(
    {
      method: 'POST',
      url: '/api/v1/qc/sichuan/evaluate-rule-for-visit',
      data: payload,
      timeout: WORKSPACE_QUERY_TIMEOUT_MS,
    },
    '深度复核失败',
  )
}
