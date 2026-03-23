import { http } from '@/utils/http'

export type SyncSource = 'mongo' | 'pg'
export type SyncTier = 'tier1' | 'tier2' | 'tier3' | 'all'

export interface MongoConnectionConfig {
  mongo_uri?: string
  mongo_uri_display?: string
  mongo_database?: string
  read_preference?: 'primary' | 'primaryPreferred' | 'secondary' | 'secondaryPreferred' | 'nearest'
  connect_timeout_ms?: number
  discharge_stable_days?: number
  lookback_minutes?: number
  rescan_recent_days?: number
  tier1_interval_minutes?: number
  tier2_interval_minutes?: number
  tier3_cron?: string
  max_batch_size?: number
  inter_request_delay_ms?: number
  night_window_start?: string
  night_window_end?: string
  enabled?: boolean
}

export interface PgConnectionConfig {
  remote_host?: string
  remote_port?: string
  remote_database?: string
  remote_username?: string
  remote_password_set?: boolean
  remote_password_display?: string
}

export interface SyncStatusResponse {
  pg_sync: Record<string, any>
  mongo_sync: Record<string, any>
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
  mongo: Record<string, any>
  pg_remote: Record<string, any>
  pg_local: Record<string, any>
}

export interface SyncPreflightResult {
  source: SyncSource
  tier: SyncTier | 'all'
  executable: boolean
  blockers: string[]
  warnings: string[]
  estimated_impact: number
  risk_level: 'low' | 'medium' | 'high' | string
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
  source: SyncSource
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

export const syncApi = {
  async getStatus(): Promise<SyncStatusResponse> {
    const response = await http.get('/api/v1/sync/status')
    return response.data
  },

  async getStatistics(): Promise<SyncStatistics> {
    const response = await http.get('/api/v1/sync/statistics')
    return response.data
  },

  async getMongoConfig(): Promise<MongoConnectionConfig> {
    const response = await http.get('/api/v1/sync/config/mongo')
    return response.data
  },

  async updateMongoConfig(payload: Partial<MongoConnectionConfig>): Promise<{ success: boolean; config: MongoConnectionConfig }> {
    const response = await http.put('/api/v1/sync/config/mongo', payload)
    return response.data
  },

  async getPgConfig(): Promise<PgConnectionConfig> {
    const response = await http.get('/api/v1/sync/config/pg')
    return response.data
  },

  async updatePgConfig(payload: {
    remote_host: string
    remote_port: number
    remote_database: string
    remote_username: string
    remote_password?: string
  }): Promise<{ success: boolean; config: PgConnectionConfig; connection: Record<string, any> }> {
    const response = await http.put('/api/v1/sync/config/pg', payload)
    return response.data
  },

  async testMongoConnection(): Promise<Record<string, any>> {
    const response = await http.post('/api/v1/sync/test-connection/mongo')
    return response.data
  },

  async testPgRemoteConnection(): Promise<Record<string, any>> {
    const response = await http.post('/api/v1/sync/test-connection/pg-remote')
    return response.data
  },

  async testPgLocalConnection(): Promise<Record<string, any>> {
    const response = await http.post('/api/v1/sync/test-connection/pg-local')
    return response.data
  },

  async testAllConnections(): Promise<SyncConnectionStatus> {
    const response = await http.post('/api/v1/sync/test-connection/all')
    return response.data
  },

  async preflight(payload: {
    source: SyncSource
    tier?: SyncTier
    tables?: string[]
  }): Promise<SyncPreflightResult> {
    const response = await http.post('/api/v1/sync/preflight', payload)
    return response.data
  },

  async triggerSync(payload: {
    source: SyncSource
    tier?: SyncTier
    sync_date?: string
    tables?: string[]
  }): Promise<SyncTriggerResponse> {
    const response = await http.post('/api/v1/sync/trigger', payload)
    return response.data
  },

  async getMappings(): Promise<SyncMappingsResponse> {
    const response = await http.get('/api/v1/sync/mappings')
    return response.data
  },

  async getRuns(params?: {
    source?: SyncSource
    tier?: SyncTier | 'all'
    limit?: number
  }): Promise<SyncRunsResponse> {
    const response = await http.get('/api/v1/sync/runs', { params })
    return response.data
  },
}
