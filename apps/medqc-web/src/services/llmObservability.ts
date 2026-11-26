import type {
  LlmObservabilityOverview,
  LlmObservabilityQuery,
  LlmObservabilityRange,
  LlmObservabilityRecordPage,
  LlmRecordCallAttempts,
  LlmRecordCallsQuery,
} from '@/types/llmObservability'
import { authFetch } from '@/utils/auth-fetch'

export interface LlmObservabilityRecordsResponse extends LlmObservabilityRecordPage {
  range?: LlmObservabilityRange
}

export interface LlmObservabilityRequestOptions {
  signal?: AbortSignal
}

const UNAVAILABLE_MESSAGE = '模型性能数据暂不可用'

function buildSearchParams(query: Record<string, string | number | undefined>): string {
  const params = new URLSearchParams()
  Object.entries(query).forEach(([key, value]) => {
    if (value === undefined || value === '') return
    params.set(key, String(value))
  })
  const serialized = params.toString()
  return serialized ? `?${serialized}` : ''
}

async function readJson<T>(url: string, options?: LlmObservabilityRequestOptions): Promise<T> {
  let response: Response
  try {
    response = await authFetch(
      url,
      options?.signal ? { method: 'GET', signal: options.signal } : { method: 'GET' },
    )
  } catch (error) {
    if (options?.signal?.aborted || (error instanceof Error && error.name === 'AbortError')) {
      throw error
    }
    throw new Error(UNAVAILABLE_MESSAGE)
  }

  if (!response.ok) {
    throw new Error(UNAVAILABLE_MESSAGE)
  }

  try {
    const payload = (await response.json()) as unknown
    if (!payload || typeof payload !== 'object' || !('data' in payload)) {
      throw new Error(UNAVAILABLE_MESSAGE)
    }
    const envelope = payload as { success?: boolean; data?: unknown }
    if (envelope.success !== true || envelope.data === undefined || envelope.data === null) {
      throw new Error(UNAVAILABLE_MESSAGE)
    }
    return envelope.data as T
  } catch {
    throw new Error(UNAVAILABLE_MESSAGE)
  }
}

export function getLlmObservabilityOverview(
  query: LlmObservabilityQuery = {},
  options?: LlmObservabilityRequestOptions,
): Promise<LlmObservabilityOverview> {
  const search = buildSearchParams({ ...query })
  return readJson<LlmObservabilityOverview>(
    `/api/v1/system/llm-observability/overview${search}`,
    options,
  )
}

export function getLlmObservabilityRecords(
  query: LlmObservabilityQuery = {},
  options?: LlmObservabilityRequestOptions,
): Promise<LlmObservabilityRecordsResponse> {
  const search = buildSearchParams({ ...query })
  return readJson<LlmObservabilityRecordsResponse>(
    `/api/v1/system/llm-observability/records${search}`,
    options,
  )
}

export function getLlmRecordCallAttempts(
  recordKeyHash: string,
  query: LlmRecordCallsQuery = {},
  options?: LlmObservabilityRequestOptions,
): Promise<LlmRecordCallAttempts> {
  const search = buildSearchParams({ ...query })
  return readJson<LlmRecordCallAttempts>(
    `/api/v1/system/llm-observability/records/${encodeURIComponent(recordKeyHash)}/calls${search}`,
    options,
  )
}
