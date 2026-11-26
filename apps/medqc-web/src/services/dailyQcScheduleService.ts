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

const root = '/api/v1/qc/daily-schedules'
export const dailyQcScheduleService = {
  async list(): Promise<DailyQcList> {
    return (await apiClient.get(root)).data.data
  },
  async options(instituteId = '', scope = 'final'): Promise<DailyQcOptions> {
    return (await apiClient.get(`${root}/options`, { params: { institute_id: instituteId || undefined, scope } })).data.data
  },
  async save(definition: DailyQcDefinition, current?: DailyQcPlan): Promise<DailyQcPlan> {
    return current
      ? (await apiClient.put(`${root}/${current.id}`, { revision: current.revision, definition })).data.data
      : (await apiClient.post(root, definition)).data.data
  },
  async remove(id: string): Promise<{ id: string; deleted: boolean }> {
    return (await apiClient.delete(`${root}/${id}`)).data.data
  },
  async history(id: string): Promise<DailyQcRun[]> {
    return (await apiClient.get(`${root}/${id}/runs`)).data.data.items
  },
}
