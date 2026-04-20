import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'
import type {
  ManualSamplePoolItemsResult,
  ManualSamplePoolListResult,
  ManualSamplePoolRecordsResult,
} from '@/views/workstation-v4/customer-sample-validation/types'

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
  formData.append('source_sheet', payload.source_sheet || 'Sheet2')
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
    pool_id: string
    matched: number
    ambiguous: number
    unmatched: number
    eligible_visits: number
    total_rows_pulled: number
    total_rows_upserted: number
    sync_group_ids: string[]
    missing_group_ids: string[]
    synced_tables: Array<{
      table_name: string
      source_table: string
      rows_pulled: number
      rows_upserted: number
    }>
  }>(
    {
      method: 'POST',
      url: `/api/v1/qc/sample-pools/${encodeURIComponent(poolId)}/sync-records`,
      data: payload || {},
    },
    '同步样本病历失败',
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
    sample_item_ids?: string[]
    record_ids?: string[]
  },
) {
  return requestEnvelope<{
    pool_id: string
    job_id: string
    sample_item_count: number
    selected_record_count: number
    record_count: number
    rule_count: number
    record_ids: string[]
    rule_ids: string[]
  }>(
    {
      method: 'POST',
      url: `/api/v1/qc/sample-pools/${encodeURIComponent(poolId)}/run`,
      data: payload || {},
    },
    '创建客户样本内涵验证任务失败',
  )
}
