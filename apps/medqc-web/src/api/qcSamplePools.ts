import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'
import type { SamplePoolItemsResponse, SamplePoolListResponse } from '@/types/qc-sample-pool'

type ServiceResult<T> = {
  success: boolean
  data?: T
  message?: string
}

const SAMPLE_POOLS_URL = '/api/v1/qc/sample-pools'

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
      message: extractApiErrorMessageFromError(error, fallbackMessage),
    }
  }
}

export async function listSamplePools(params?: { q?: string; page?: number; page_size?: number }) {
  const query = new URLSearchParams()
  if (params?.q) query.append('q', params.q)
  if (params?.page) query.append('page', String(params.page))
  if (params?.page_size) query.append('page_size', String(params.page_size))
  const url = `${SAMPLE_POOLS_URL}${query.toString() ? `?${query.toString()}` : ''}`
  return requestEnvelope<SamplePoolListResponse>({ method: 'GET', url }, '获取客户样本池失败')
}

export async function listSamplePoolItems(
  poolId: string,
  params?: {
    coverage_type?: string
    match_status?: string
    include_in_batch_1?: boolean
    q?: string
    page?: number
    page_size?: number
  },
) {
  const query = new URLSearchParams()
  if (params?.coverage_type) query.append('coverage_type', params.coverage_type)
  if (params?.match_status) query.append('match_status', params.match_status)
  if (typeof params?.include_in_batch_1 === 'boolean') {
    query.append('include_in_batch_1', String(params.include_in_batch_1))
  }
  if (params?.q) query.append('q', params.q)
  if (params?.page) query.append('page', String(params.page))
  if (params?.page_size) query.append('page_size', String(params.page_size))
  const url = `${SAMPLE_POOLS_URL}/${poolId}/items${query.toString() ? `?${query.toString()}` : ''}`
  return requestEnvelope<SamplePoolItemsResponse>({ method: 'GET', url }, '获取客户样本明细失败')
}
