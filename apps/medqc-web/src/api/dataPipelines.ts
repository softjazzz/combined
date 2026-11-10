import { http } from '@/utils/http'

export type DataPipeline = 'legacy_pg' | 'independent_cdm'
export interface DataPipelineSettings {
  version: number
  default_pipeline: DataPipeline
  independent_enabled: boolean
}
export interface DataPipelineConfiguration {
  settings: DataPipelineSettings
  runtime: {
    control_configured: boolean
    control_profile: string
    clinical_read_source: 'business_cdm' | 'independent_cdm'
    cdm_url_configured: boolean
    cdm_configuration_valid?: boolean
    read_scope: string
    pdf_source: string
    automatic_extraction: boolean
    automatic_qc: boolean
  }
}
export interface IndependentCatalog {
  profile: string
  interfaces: string[]
  manual_only: boolean
  session: SyncCapabilities
}
export interface SyncCapabilities {
  permissions: ('read' | 'run' | 'schedule')[]
  timezone: string
  last_complete_date: string
  max_manual_days: number
  features: { schedule_drafts: boolean; schedule_controls: false; date_recovery_profiles: string[] }
}
export interface SyncUnit {
  unit_id?: string
  sequence?: number
  interface_name?: string
  source_date?: string
  phase?: string
  status?: string
  execution_attempts?: number
  error: { code?: string; location?: string; retry_policy?: string }
  result?: { counts?: Record<string, number>; selected?: number; written?: number }
}
export interface ScheduleDraftConfig {
  frequency: 'daily' | 'weekly'
  local_time: string
  window_days: number
  weekday?: number
  interfaces: string[]
}
export interface SyncSchedule {
  schedule_id: string
  version: number
  enabled: boolean
  next_fire_at: string | null
  config: Omit<ScheduleDraftConfig, 'interfaces'> & {
    timezone: string
    request: { profile: string; interfaces: string[]; mode: string; publish: boolean }
  }
}
export interface IndependentSyncJob {
  job_id: string
  status:
    | 'queued'
    | 'running'
    | 'recovery_required'
    | 'succeeded'
    | 'completed_with_source_limitations'
    | 'failed'
    | 'cancelled'
  counts: Record<string, number>
  created_at?: string
  updated_at?: string
  cancel_requested: boolean
  error?: { code?: string; location?: string }
  mode?: string
  published?: boolean
  units?: SyncUnit[]
  request?: { start_date?: string; end_date?: string; interfaces?: string[]; plan_version?: number }
}
export interface IndependentSyncRequest {
  operation_id: string
  start_date: string
  end_date: string
  interfaces: string[]
  mode: 'dry' | 'replay'
  publish: boolean
}
interface Envelope<T> {
  success: boolean
  data: T
}
function unwrap<T>(value: Envelope<T>): T {
  if (value.success !== true || value.data == null) throw new Error('数据链路接口未返回有效结果')
  return value.data
}
const base = '/api/v1/sync/pipelines'
export const dataPipelinesApi = {
  async configuration(): Promise<DataPipelineConfiguration> {
    return unwrap((await http.get<Envelope<DataPipelineConfiguration>>(base)).data)
  },
  async save(settings: DataPipelineSettings): Promise<DataPipelineConfiguration> {
    return unwrap((await http.put<Envelope<DataPipelineConfiguration>>(base, settings)).data)
  },
  async check(): Promise<IndependentCatalog> {
    return unwrap((await http.post<Envelope<IndependentCatalog>>(`${base}/independent/check`)).data)
  },
  async jobs(): Promise<IndependentSyncJob[]> {
    return unwrap(
      (await http.get<Envelope<{ jobs: IndependentSyncJob[] }>>(`${base}/independent/jobs`)).data,
    ).jobs
  },
  async submit(payload: IndependentSyncRequest): Promise<IndependentSyncJob> {
    return unwrap(
      (await http.post<Envelope<IndependentSyncJob>>(`${base}/independent/jobs`, payload)).data,
    )
  },
  async action(id: string, action: 'cancel' | 'retry'): Promise<IndependentSyncJob> {
    return unwrap(
      (
        await http.post<Envelope<IndependentSyncJob>>(
          `${base}/independent/jobs/${encodeURIComponent(id)}/${action}`,
        )
      ).data,
    )
  },
  async detail(id: string): Promise<IndependentSyncJob> {
    return unwrap((await http.get<Envelope<IndependentSyncJob>>(`${base}/independent/jobs/${encodeURIComponent(id)}`)).data)
  },
  async schedules(): Promise<SyncSchedule[]> {
    return unwrap((await http.get<Envelope<{ schedules: SyncSchedule[] }>>(`${base}/independent/schedules`)).data).schedules
  },
  async schedule(id: string): Promise<SyncSchedule> {
    return unwrap((await http.get<Envelope<SyncSchedule>>(`${base}/independent/schedules/${encodeURIComponent(id)}`)).data)
  },
  async saveDraft(id: string, payload: { version: number | null; config: ScheduleDraftConfig }): Promise<SyncSchedule> {
    return unwrap((await http.put<Envelope<SyncSchedule>>(`${base}/independent/schedule-drafts/${encodeURIComponent(id)}`, payload)).data)
  },
}
