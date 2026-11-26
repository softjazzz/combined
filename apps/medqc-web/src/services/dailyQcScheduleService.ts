import { apiClient } from '@/services/apiService'

export interface DailyQcDefinition {
  name: string
  enabled: boolean
  time_of_day: string
  timezone: string
  institute_id: string
  scope: 'running' | 'final'
  department: string
  date_field: 'admission' | 'discharge'
  lookback_days: number
  end_offset_days: number
  rule_set_key: string
  rule_ids: string[]
  max_records: number
}
export interface DailyQcPlan extends DailyQcDefinition {
  id: string
  revision: number
  next_run_at: string
  last_status: string | null
  last_job_id: string | null
}
export interface DailyQcRun {
  id: string
  local_date: string
  state: string
  scheduled_for: string
  job_id: string | null
  reason: string | null
  attempts: number
}
export interface DailyQcOptions {
  institutes: string[]
  departments: string[]
  rule_sets: Array<{ key: string; name: string; scope: string; description?: string }>
}
export interface DailyQcList {
  items: DailyQcPlan[]
  scheduler_enabled: boolean
  local_process_active: boolean
}

export interface DailyQcRequestOptions {
  signal?: AbortSignal
}

const root = '/api/v1/qc/daily-schedules'
export const dailyQcScheduleService = {
  async list(requestOptions?: DailyQcRequestOptions): Promise<DailyQcList> {
    const response = requestOptions?.signal
      ? await apiClient.get(root, { signal: requestOptions.signal })
      : await apiClient.get(root)
    return response.data.data
  },
  async options(
    instituteId = '',
    scope = 'final',
    requestOptions?: DailyQcRequestOptions,
  ): Promise<DailyQcOptions> {
    const config = {
      params: { institute_id: instituteId || undefined, scope },
      ...(requestOptions?.signal ? { signal: requestOptions.signal } : {}),
    }
    return (await apiClient.get(`${root}/options`, config)).data.data
  },
  async save(
    definition: DailyQcDefinition,
    current?: DailyQcPlan,
    requestOptions?: DailyQcRequestOptions,
  ): Promise<DailyQcPlan> {
    const config = requestOptions?.signal ? { signal: requestOptions.signal } : undefined
    if (current) {
      const response = config
        ? await apiClient.put(`${root}/${current.id}`, { revision: current.revision, definition }, config)
        : await apiClient.put(`${root}/${current.id}`, { revision: current.revision, definition })
      return response.data.data
    }
    const response = config
      ? await apiClient.post(root, definition, config)
      : await apiClient.post(root, definition)
    return response.data.data
  },
  async remove(
    id: string,
    requestOptions?: DailyQcRequestOptions,
  ): Promise<{ id: string; deleted: boolean }> {
    const response = requestOptions?.signal
      ? await apiClient.delete(`${root}/${id}`, { signal: requestOptions.signal })
      : await apiClient.delete(`${root}/${id}`)
    return response.data.data
  },
  async history(id: string, requestOptions?: DailyQcRequestOptions): Promise<DailyQcRun[]> {
    const response = requestOptions?.signal
      ? await apiClient.get(`${root}/${id}/runs`, { signal: requestOptions.signal })
      : await apiClient.get(`${root}/${id}/runs`)
    return response.data.data.items
  },
}
