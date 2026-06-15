import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'
import type {
  ManualSamplePoolItemsResult,
  ManualSamplePoolListResult,
  ManualSamplePoolRecordsResult,
  ManualSamplePoolRunResult,
  ManualSamplePoolSyncJob,
  ManualTestRecordCreateRequest,
  ManualTestRecordCreateResult,
  ManualSampleValidationRuleSetListResult,
  Sheet2ExactReviewAcceptancePackage,
} from '@/views/workstation-v4/customer-sample-validation/types'

type ServiceResult<T> = {
  success: boolean
  data?: T
  message?: string
  errorType?: 'timeout' | 'network' | 'server' | 'unknown'
}

function toErrorMessage(error: unknown, fallback: string): string {
  return extractApiErrorMessageFromError(error, fallback)
}

function classifyRequestError(error: unknown): ServiceResult<never>['errorType'] {
  if (error && typeof error === 'object') {
    const candidate = error as { code?: unknown; message?: unknown; response?: unknown }
    const code = String(candidate.code || '').toLowerCase()
    const message = String(candidate.message || '').toLowerCase()
    if (code === 'econnaborted' || message.includes('timeout')) {
      return 'timeout'
    }
    if (!candidate.response && (code === 'err_network' || message.includes('network'))) {
      return 'network'
    }
    if (candidate.response) {
      return 'server'
    }
  }
  return 'unknown'
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
      errorType: classifyRequestError(error),
    }
  }
}

export async function listManualSamplePools(params: {
  q?: string
  page?: number
  page_size?: number
}) {
  return requestEnvelope<ManualSamplePoolListResult>(
    {
      method: 'GET',
      url: '/api/v1/qc/sample-pools',
      params,
    },
    '获取客户样本池失败',
  )
}

export async function importManualSamplePoolByUpload(payload: {
  pool_name: string
  source_sheet?: string
  description?: string
  scene?: string
  file: File
}) {
  const formData = new FormData()
  formData.append('pool_name', payload.pool_name)
  if (payload.source_sheet) {
    formData.append('source_sheet', payload.source_sheet)
  }
  formData.append('description', payload.description || '')
  formData.append('scene', payload.scene || 'running')
  formData.append('file', payload.file)

  return requestEnvelope<{
    id: string
    name: string
    imported_rows: number
  }>(
    {
      method: 'POST',
      url: '/api/v1/qc/sample-pools/import-upload',
      data: formData,
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    },
    '导入客户样本模板失败',
  )
}

export async function createManualTestMedicalRecord(payload: ManualTestRecordCreateRequest) {
  return requestEnvelope<ManualTestRecordCreateResult>(
    {
      method: 'POST',
      url: '/api/v1/qc/sample-pools/test-records',
      data: payload,
    },
    '创建测试病历失败',
  )
}

export async function getManualSamplePoolItems(
  poolId: string,
  params: {
    coverage_type?: string
    match_status?: string
    include_in_batch_1?: boolean
    q?: string
    page?: number
    page_size?: number
  },
) {
  return requestEnvelope<ManualSamplePoolItemsResult>(
    {
      method: 'GET',
      url: `/api/v1/qc/sample-pools/${encodeURIComponent(poolId)}/items`,
      params,
    },
    '获取客户样本明细失败',
  )
}

export async function getManualSamplePoolRecords(
  poolId: string,
  params: {
    coverage_type?: string
    match_status?: string
    include_in_batch_1?: boolean
    q?: string
    page?: number
    page_size?: number
  },
) {
  return requestEnvelope<ManualSamplePoolRecordsResult>(
    {
      method: 'GET',
      url: `/api/v1/qc/sample-pools/${encodeURIComponent(poolId)}/records`,
      params,
    },
    '获取客户样本病历列表失败',
  )
}

export async function matchManualSamplePool(poolId: string) {
  return requestEnvelope<Record<string, unknown>>(
    {
      method: 'POST',
      url: `/api/v1/qc/sample-pools/${encodeURIComponent(poolId)}/match`,
    },
    '执行病历匹配失败',
  )
}

export async function syncManualSamplePoolRecords(
  poolId: string,
  payload?: {
    only_intrinsic?: boolean
    include_in_batch_1?: boolean
    table_groups?: string[]
  },
) {
  return requestEnvelope<{
    job_id: string
    pool_id: string
    status: string
    summary?: ManualSamplePoolSyncJob['summary']
  }>(
    {
      method: 'POST',
      url: `/api/v1/qc/sample-pools/${encodeURIComponent(poolId)}/sync-records`,
      data: payload || {},
    },
    '同步样本病历失败',
  )
}

export async function getLatestManualSamplePoolSyncJob(poolId: string) {
  return requestEnvelope<ManualSamplePoolSyncJob | null>(
    {
      method: 'GET',
      url: `/api/v1/qc/sample-pools/${encodeURIComponent(poolId)}/sync-jobs/latest`,
    },
    '获取样本同步任务失败',
  )
}

export async function getManualSamplePoolSyncJob(jobId: string) {
  return requestEnvelope<ManualSamplePoolSyncJob>(
    {
      method: 'GET',
      url: `/api/v1/qc/sample-pools/sync-jobs/${encodeURIComponent(jobId)}`,
    },
    '获取样本同步任务失败',
  )
}

export async function runManualSamplePool(
  poolId: string,
  payload?: {
    department?: string
    doctor?: string
    model_code?: string
    top_p?: number
    temperature?: number
    max_tokens?: number
    max_parallel_records?: number
    sample_item_ids?: string[]
    record_ids?: string[]
    validation_mode?: string
    rule_set_key?: string
  },
  options?: {
    timeout?: number
  },
) {
  return requestEnvelope<ManualSamplePoolRunResult>(
    {
      method: 'POST',
      url: `/api/v1/qc/sample-pools/${encodeURIComponent(poolId)}/run`,
      data: payload || {},
      timeout: options?.timeout,
    },
    '创建客户样本验证任务失败',
  )
}

export async function getSheet2ExactReviewAcceptancePackage() {
  return requestEnvelope<Sheet2ExactReviewAcceptancePackage>(
    {
      method: 'GET',
      url: '/api/v1/qc/sample-pools/sheet2-exact-review/acceptance-package',
    },
    '获取 Sheet2 精确复核验收包失败',
  )
}

export async function listManualSampleValidationRuleSets() {
  return requestEnvelope<ManualSampleValidationRuleSetListResult>(
    {
      method: 'GET',
      url: '/api/v1/qc/sample-pools/rule-sets',
    },
    '获取样本验证规则集失败',
  )
}

export async function exportLuxian0609EvaluationReport(format: 'md' | 'csv' | 'json' = 'md') {
  try {
    const response = await ApiService.requestRaw<Blob>({
      method: 'GET',
      url: '/api/v1/qc/sample-pools/reports/luxian-0609',
      params: { format },
      responseType: 'blob',
    })
    return {
      success: true,
      data: response.data,
    }
  } catch (error) {
    return {
      success: false,
      message: toErrorMessage(error, '导出泸县0609质控点评估报告失败'),
      errorType: classifyRequestError(error),
    }
  }
}
