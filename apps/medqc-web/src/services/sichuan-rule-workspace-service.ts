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
  /** 失败时的 HTTP 状态码，供轮询区分确定性失败与临时失败 */
  status?: number
  /** 任务详情 409 时后端附带的任务状态（X-Batch-Job-Status），旧后端没有 */
  jobStatus?: string
}

type ErrorResponseLike = {
  response?: { status?: unknown; headers?: Record<string, unknown> }
} | null

function toErrorStatus(error: unknown): number | undefined {
  const status = (error as ErrorResponseLike)?.response?.status
  return typeof status === 'number' ? status : undefined
}

function toErrorJobStatus(error: unknown): string | undefined {
  const value = (error as ErrorResponseLike)?.response?.headers?.['x-batch-job-status']
  return typeof value === 'string' && value.trim() ? value.trim().toLowerCase() : undefined
}

const WORKSPACE_QUERY_TIMEOUT_MS = 60000
// 整改草稿要等一次模型生成，单独放宽超时，避免误报为请求失败。
const WORKSPACE_DRAFT_TIMEOUT_MS = 120000

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
      status: toErrorStatus(error),
      jobStatus: toErrorJobStatus(error),
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
  sync_scope?: 'all' | 'today_inpatient'
  department?: string
  doctor?: string
  date_field: 'visit' | 'admission' | 'discharge'
  start_date?: string
  end_date?: string
  keyword?: string
  record_ids?: string[]
  record_refs?: Array<{
    institute_id: string
    patient_id: string
    visit_id: string
  }>
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

/** 结果页病历标识：按客户安全引用 record_ref 回查住院号、科室等，不含患者姓名。 */
export type BatchJobRecordIdentity = {
  record_ref: string
  sequence: number
  inpatient_no: string
  department: string
  doctor: string
  admission_date: string
  discharge_date: string
}

export async function getSichuanWorkspaceBatchJobRecordIdentities(jobId: string) {
  return requestEnvelope<{ items: BatchJobRecordIdentity[] }>(
    {
      method: 'GET',
      url: `/api/v1/qc/sichuan/workspace/batch-jobs/${encodeURIComponent(jobId)}/record-identities`,
      timeout: WORKSPACE_QUERY_TIMEOUT_MS,
    },
    '获取病历标识失败',
  )
}

/** 单病历结果页唯一允许使用的三坐标结果读取接口。 */
export async function getLatestLuxian0609RecordResult(record: {
  instituteId: string
  patientId: string
  visitId: string
}) {
  return requestEnvelope<SingleRecordQcResultPayload>(
    {
      method: 'GET',
      url: `/api/v1/qc/sichuan/workspace/records/${encodeURIComponent(record.visitId)}/latest-result`,
      params: {
        institute_id: record.instituteId,
        patient_id: record.patientId,
      },
      timeout: WORKSPACE_QUERY_TIMEOUT_MS,
    },
    '获取该病历最近一次质控结果失败',
  )
}

export interface QcRemediationDraftResult {
  available: boolean
  rule_id: string
  draft?: string
  reason?: string
}

/**
 * 按需生成单条规则的整改草稿。
 * 只读取该病历已保存的质控结果，不写入结果、不改变质控结论与权威建议。
 */
export async function requestLuxian0609RemediationDraft(
  record: { instituteId: string; patientId: string; visitId: string },
  ruleId: string,
) {
  return requestEnvelope<QcRemediationDraftResult>(
    {
      method: 'POST',
      url: `/api/v1/qc/sichuan/workspace/records/${encodeURIComponent(record.visitId)}/latest-result/remediation-draft`,
      params: {
        institute_id: record.instituteId,
        patient_id: record.patientId,
      },
      data: { rule_id: ruleId },
      timeout: WORKSPACE_DRAFT_TIMEOUT_MS,
    },
    '生成整改草稿失败',
  )
}

export async function exportLatestLuxian0609RecordResult(record: {
  instituteId: string
  patientId: string
  visitId: string
}) {
  try {
    const response = await ApiService.requestRaw<Blob>({
      method: 'GET',
      url: `/api/v1/qc/sichuan/workspace/records/${encodeURIComponent(record.visitId)}/latest-result/export`,
      params: {
        institute_id: record.instituteId,
        patient_id: record.patientId,
      },
      responseType: 'blob',
      timeout: WORKSPACE_QUERY_TIMEOUT_MS,
    })
    return { success: true, data: response.data }
  } catch (error) {
    return {
      success: false,
      message: toErrorMessage(error, '导出单病历质控结果失败'),
    }
  }
}

export async function exportFilteredLuxian0609RecordResults(payload: {
  scope: 'all' | 'running' | 'final'
  department?: string
  doctor?: string
  date_field: 'visit' | 'admission' | 'discharge'
  start_date?: string
  end_date?: string
  keyword?: string
  record_refs?: Array<{
    institute_id: string
    patient_id: string
    visit_id: string
  }>
}) {
  try {
    const response = await ApiService.requestRaw<Blob>({
      method: 'POST',
      url: '/api/v1/qc/sichuan/workspace/records/export',
      data: payload,
      responseType: 'blob',
      timeout: WORKSPACE_QUERY_TIMEOUT_MS,
    })
    return { success: true, data: response.data }
  } catch (error) {
    return {
      success: false,
      message: toErrorMessage(error, '导出当前筛选质控结果失败'),
    }
  }
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
