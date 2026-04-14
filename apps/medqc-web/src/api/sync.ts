import { http } from '@/utils/http'

export type SyncSource = 'pg'
export type SyncTier = 'tier1' | 'tier2' | 'tier3' | 'all'

export interface PgConnectionConfig {
  remote_host?: string
  remote_port?: string
  remote_database?: string
  remote_username?: string
  remote_schema?: string
  sync_mode?: 'table' | 'procedure' | string
  remote_password_set?: boolean
  remote_password_display?: string
}

export interface SyncTableValidationItem {
  table: string
  source_table?: string
  source?: string
  enabled?: boolean
  mode?: 'table' | 'procedure' | string
  date_field?: string | null
  fallback_date_field?: string | null
  resolved_date_field?: string | null
  local_primary_keys?: string[]
  executable: boolean
  blockers: string[]
}

export interface PgSyncTableConfigItem {
  name: string
  label?: string
  source_table?: string
  date_field?: string | null
  fallback_date_field?: string | null
  enabled?: boolean
  procedure?: string
}

export interface PgSyncTableGroupItem {
  id: string
  label: string
  description?: string
  table_names: string[]
  table_count: number
}

export interface SyncStatusResponse {
  pg_sync: Record<string, any>
}

export interface SyncStatistics {
  PENDING: number
  PARTIAL: number
  SYNCED: number
  STALE: number
  FAILED: number
}

export interface SyncTriggerResponse {
  success: boolean
  error?: string
  message?: string
  [key: string]: any
}

export interface SyncConnectionStatus {
  all_connected: boolean
  connected_count: number
  total_sources: number
  pg_remote: Record<string, any>
  pg_local: Record<string, any>
}

export interface SyncPreflightResult {
  source: SyncSource
  tier: SyncTier | 'all'
  mode?: 'table' | 'procedure' | string
  remote_schema?: string
  executable: boolean
  blockers: string[]
  warnings: string[]
  estimated_impact: number
  risk_level: 'low' | 'medium' | 'high' | string
  matrix_scope?: {
    execution?: 'enabled' | 'all' | string
    full?: 'enabled' | 'all' | string
  }
  table_validations?: SyncTableValidationItem[]
  target_tables?: string[]
  execution_table_validations?: SyncTableValidationItem[]
  execution_target_tables?: string[]
  connections?: Record<string, any>
  state?: Record<string, any>
  statistics?: SyncStatistics
}

export interface SyncMappingItem {
  source_collection: string
  target_table: string
  key_fields: string[]
  tier: 'tier2' | 'tier3'
  enabled: boolean
}

export interface SyncMappingsResponse {
  items: SyncMappingItem[]
  total: number
}

export interface SyncRunLogItem {
  id: string
  source: 'pg'
  tier: SyncTier | 'all'
  status: 'success' | 'failed' | 'partial' | string
  started_at: string
  finished_at?: string
  duration_ms?: number
  total_records?: number
  error?: string
  operator?: {
    id?: string
    email?: string
    roles?: string[]
  }
}

export interface SyncRunsResponse {
  items: SyncRunLogItem[]
  total: number
  limit: number
}

export interface SyncTemplate {
  id:
    | 'hospital_standard'
    | 'single_department_focus'
    | 'multi_department_joint'
    | 'night_low_impact'
  name: string
  description: string
  risk_tip: string
  requires_departments: boolean
  allow_multi_departments: boolean
  defaults: Record<string, any>
}

export interface SyncPolicyConfig {
  scope?: 'running' | 'final' | 'frontpage' | 'coding' | 'settlement' | 'both' | string
  target_departments?: string[]
  start_date?: string
  end_date?: string
  schedule?: {
    mode?: 'interval' | 'cron' | string
    minutes?: number
  }
  night_window?: {
    start?: string
    end?: string
  }
  mirror_delay_base_minutes?: number
  policy_version?: string
  template_id?: string
  template_mapping_version?: string
  template_applied_at?: string
}

function unwrapSyncResponse<T = any>(raw: any): T {
  if (!raw || typeof raw !== 'object') {
    return raw as T
  }
  if (Object.prototype.hasOwnProperty.call(raw, 'success')) {
    if (raw.success === false) {
      return raw as T
    }
    if (Object.prototype.hasOwnProperty.call(raw, 'data')) {
      return raw.data as T
    }
  }
  return raw as T
}

export const syncApi = {
  async getStatus(): Promise<SyncStatusResponse> {
    const response = await http.get('/api/v1/sync/status')
    return unwrapSyncResponse<SyncStatusResponse>(response.data)
  },

  async getStatistics(): Promise<SyncStatistics> {
    const response = await http.get('/api/v1/sync/statistics')
    return unwrapSyncResponse<SyncStatistics>(response.data)
  },

  async getPgConfig(): Promise<PgConnectionConfig> {
    const response = await http.get('/api/v1/sync/config/pg')
    return unwrapSyncResponse<PgConnectionConfig>(response.data)
  },

  async updatePgConfig(payload: {
    remote_host: string
    remote_port: number
    remote_database: string
    remote_username: string
    remote_schema?: string
    sync_mode?: 'table' | 'procedure'
    remote_password?: string
  }): Promise<{ config: PgConnectionConfig; connection: Record<string, any> }> {
    const response = await http.put('/api/v1/sync/config/pg', payload)
    return unwrapSyncResponse<{ config: PgConnectionConfig; connection: Record<string, any> }>(
      response.data,
    )
  },

  async getSyncPolicy(): Promise<SyncPolicyConfig> {
    const response = await http.get('/api/v1/sync/config/policy')
    return unwrapSyncResponse<SyncPolicyConfig>(response.data)
  },

  async updateSyncPolicy(payload: {
    scope?: SyncPolicyConfig['scope']
    target_departments?: string[]
    start_date?: string
    end_date?: string
    schedule?: SyncPolicyConfig['schedule']
    night_window?: SyncPolicyConfig['night_window']
    mirror_delay_base_minutes?: number
    keep_policy_version?: boolean
  }): Promise<SyncPolicyConfig> {
    const response = await http.put('/api/v1/sync/config/policy', payload)
    return unwrapSyncResponse<SyncPolicyConfig>(response.data)
  },

  async getPgSyncTables(): Promise<{ items: PgSyncTableConfigItem[]; total: number }> {
    const response = await http.get('/api/v1/sync/config/pg/tables')
    return unwrapSyncResponse<{ items: PgSyncTableConfigItem[]; total: number }>(response.data)
  },

  async getPgSyncTableGroups(): Promise<{ items: PgSyncTableGroupItem[]; total: number }> {
    const response = await http.get('/api/v1/sync/config/pg/table-groups')
    return unwrapSyncResponse<{ items: PgSyncTableGroupItem[]; total: number }>(response.data)
  },

  async updatePgSyncTables(payload: {
    items: Array<{
      name: string
      source_table?: string
      date_field?: string
      fallback_date_field?: string
      enabled?: boolean
    }>
  }): Promise<{ items: PgSyncTableConfigItem[]; total: number }> {
    const response = await http.put('/api/v1/sync/config/pg/tables', payload)
    return unwrapSyncResponse<{ items: PgSyncTableConfigItem[]; total: number }>(response.data)
  },

  async testPgRemoteConnection(): Promise<Record<string, any>> {
    const response = await http.post('/api/v1/sync/test-connection/pg-remote')
    return unwrapSyncResponse<Record<string, any>>(response.data)
  },

  async testPgLocalConnection(): Promise<Record<string, any>> {
    const response = await http.post('/api/v1/sync/test-connection/pg-local')
    return unwrapSyncResponse<Record<string, any>>(response.data)
  },

  async testAllConnections(): Promise<SyncConnectionStatus> {
    const response = await http.post('/api/v1/sync/test-connection/all')
    return unwrapSyncResponse<SyncConnectionStatus>(response.data)
  },

  async preflight(payload: {
    source: SyncSource
    tier?: SyncTier
    tables?: string[]
    scene?: SyncPolicyConfig['scope']
    date_window?: {
      start?: string
      end?: string
      start_date?: string
      end_date?: string
    }
    target_departments?: string[]
    policy_version?: string
    table_groups?: string[]
  }): Promise<SyncPreflightResult> {
    const response = await http.post('/api/v1/sync/preflight', payload)
    return unwrapSyncResponse<SyncPreflightResult>(response.data)
  },

  async triggerSync(payload: {
    source: SyncSource
    tier?: SyncTier
    sync_date?: string
    tables?: string[]
    scene?: SyncPolicyConfig['scope']
    date_window?: {
      start?: string
      end?: string
      start_date?: string
      end_date?: string
    }
    target_departments?: string[]
    policy_version?: string
    table_groups?: string[]
  }): Promise<SyncTriggerResponse> {
    const response = await http.post('/api/v1/sync/trigger', payload)
    return unwrapSyncResponse<SyncTriggerResponse>(response.data)
  },

  async getMappings(): Promise<SyncMappingsResponse> {
    const response = await http.get('/api/v1/sync/mappings')
    return unwrapSyncResponse<SyncMappingsResponse>(response.data)
  },

  async getRuns(params?: {
    source?: SyncSource
    tier?: SyncTier | 'all'
    limit?: number
  }): Promise<SyncRunsResponse> {
    const response = await http.get('/api/v1/sync/runs', { params })
    return unwrapSyncResponse<SyncRunsResponse>(response.data)
  },

  async getTemplates(): Promise<{ items: SyncTemplate[] }> {
    const response = await http.get('/api/v1/sync/templates')
    return unwrapSyncResponse<{ items: SyncTemplate[] }>(response.data)
  },

  async applyTemplate(payload: {
    template_id: SyncTemplate['id']
    departments?: string[]
  }): Promise<{ template_id: string; policy: SyncPolicyConfig }> {
    const response = await http.post('/api/v1/sync/templates/apply', payload)
    return unwrapSyncResponse<{ template_id: string; policy: SyncPolicyConfig }>(response.data)
  },

  async getDepartments(): Promise<string[]> {
    const response = await http.get('/api/v1/sync/departments')
    const payload = unwrapSyncResponse<{ items?: string[] }>(response.data)
    return Array.isArray(payload?.items) ? payload.items : []
  },
}
