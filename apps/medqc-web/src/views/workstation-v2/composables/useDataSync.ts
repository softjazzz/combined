import { computed, reactive } from 'vue'
import { message } from 'ant-design-vue'

import { useAuthStore } from '@/stores/auth'
import {
  syncApi,
  type MongoConnectionConfig,
  type PgConnectionConfig,
  type SyncConnectionStatus,
  type SyncMappingItem,
  type SyncPreflightResult,
  type SyncRunLogItem as SyncRunHistoryItem,
  type SyncSource,
  type SyncStatistics,
  type SyncTier,
} from '@/api/sync'

export interface SyncRuntimeLogItem {
  timestamp: string
  level: 'info' | 'success' | 'warn' | 'error'
  message: string
}

export interface SyncOverviewStats {
  connectedCount: number
  totalSources: number
  lastSyncTime: string | null
  pendingRecords: number
  failedRecords: number
}

export interface MongoConnectionForm {
  mongo_uri: string
  mongo_database: string
  read_preference: MongoConnectionConfig['read_preference']
  connect_timeout_ms: number
}

export interface PgConnectionForm {
  remote_host: string
  remote_port: number
  remote_database: string
  remote_username: string
  remote_password: string
  remote_password_set: boolean
}

export interface SyncPolicyForm {
  enabled: boolean
  discharge_stable_days: number
  lookback_minutes: number
  rescan_recent_days: number
  tier1_interval_minutes: number
  tier2_interval_minutes: number
  tier3_cron: string
  max_batch_size: number
  inter_request_delay_ms: number
  night_window_start: string
  night_window_end: string
}

function nowTimestamp(): string {
  return new Date().toLocaleTimeString('zh-CN', { hour12: false })
}

function parseTimestamp(value?: string | null): number {
  if (!value) {
    return 0
  }
  const parsed = Date.parse(value)
  return Number.isNaN(parsed) ? 0 : parsed
}

function pickLastSyncTime(
  mongoSyncState: Record<string, any>,
  pgSyncState: Record<string, any>,
): string | null {
  const candidates = [
    mongoSyncState.tier3_last_run,
    mongoSyncState.tier2_last_run,
    mongoSyncState.tier1_last_run,
    mongoSyncState.last_sync_time,
    pgSyncState.last_sync_time,
  ].filter(Boolean) as string[]

  if (candidates.length === 0) {
    return null
  }

  let latest = candidates[0]
  for (const candidate of candidates.slice(1)) {
    if (parseTimestamp(candidate) > parseTimestamp(latest)) {
      latest = candidate
    }
  }
  return latest
}

function createInitialState() {
  return {
    activeTab: 'mongo' as 'mongo' | 'pg_remote' | 'pg_local',
    selectedTier: 'all' as SyncTier,

    stats: {
      connectedCount: 0,
      totalSources: 3,
      lastSyncTime: null,
      pendingRecords: 0,
      failedRecords: 0,
    } as SyncOverviewStats,

    mongoConnectionForm: {
      mongo_uri: '',
      mongo_database: 'his_emr',
      read_preference: 'secondaryPreferred',
      connect_timeout_ms: 5000,
    } as MongoConnectionForm,

    pgConnectionForm: {
      remote_host: '',
      remote_port: 5432,
      remote_database: '',
      remote_username: '',
      remote_password: '',
      remote_password_set: false,
    } as PgConnectionForm,

    policyForm: {
      enabled: false,
      discharge_stable_days: 3,
      lookback_minutes: 10,
      rescan_recent_days: 7,
      tier1_interval_minutes: 30,
      tier2_interval_minutes: 120,
      tier3_cron: '0 2 * * *',
      max_batch_size: 100,
      inter_request_delay_ms: 200,
      night_window_start: '22:00',
      night_window_end: '06:00',
    } as SyncPolicyForm,

    mongoConfigRaw: {} as MongoConnectionConfig,
    pgConfigRaw: {} as PgConnectionConfig,
    mongoSyncState: {} as Record<string, any>,
    pgSyncState: {} as Record<string, any>,
    mongoStats: { PENDING: 0, PARTIAL: 0, SYNCED: 0, STALE: 0, FAILED: 0 } as SyncStatistics,
    connectionStatus: null as SyncConnectionStatus | null,
    preflightResult: null as SyncPreflightResult | null,
    mappings: [] as SyncMappingItem[],
    runHistory: [] as SyncRunHistoryItem[],
    runHistoryTotal: 0,
    runHistorySourceFilter: 'all' as 'all' | SyncSource,
    runHistoryTierFilter: 'all' as SyncTier | 'all',

    isInitializing: false,
    isLoadingStatus: false,
    isTestingAll: false,
    isTestingActive: false,
    isSavingMongoConnection: false,
    isSavingPgConnection: false,
    isSavingPolicy: false,
    isPreflighting: false,
    isSyncing: false,
    mappingsLoading: false,
    runsLoading: false,

    currentRunLog: [] as SyncRuntimeLogItem[],
  }
}

const globalSyncState = reactive(createInitialState())
let pollingTimer: ReturnType<typeof setInterval> | null = null

function pushLog(level: SyncRuntimeLogItem['level'], text: string) {
  globalSyncState.currentRunLog.unshift({
    timestamp: nowTimestamp(),
    level,
    message: text,
  })
}

function patchMongoForms(payload: MongoConnectionConfig) {
  globalSyncState.mongoConfigRaw = payload
  globalSyncState.mongoConnectionForm.mongo_uri = ''
  globalSyncState.mongoConnectionForm.mongo_database = payload.mongo_database || 'his_emr'
  globalSyncState.mongoConnectionForm.read_preference =
    payload.read_preference || 'secondaryPreferred'
  globalSyncState.mongoConnectionForm.connect_timeout_ms = payload.connect_timeout_ms || 5000

  globalSyncState.policyForm.enabled = payload.enabled ?? false
  globalSyncState.policyForm.discharge_stable_days = payload.discharge_stable_days ?? 3
  globalSyncState.policyForm.lookback_minutes = payload.lookback_minutes ?? 10
  globalSyncState.policyForm.rescan_recent_days = payload.rescan_recent_days ?? 7
  globalSyncState.policyForm.tier1_interval_minutes = payload.tier1_interval_minutes ?? 30
  globalSyncState.policyForm.tier2_interval_minutes = payload.tier2_interval_minutes ?? 120
  globalSyncState.policyForm.tier3_cron = payload.tier3_cron || '0 2 * * *'
  globalSyncState.policyForm.max_batch_size = payload.max_batch_size ?? 100
  globalSyncState.policyForm.inter_request_delay_ms = payload.inter_request_delay_ms ?? 200
  globalSyncState.policyForm.night_window_start = payload.night_window_start || '22:00'
  globalSyncState.policyForm.night_window_end = payload.night_window_end || '06:00'
}

function patchPgForms(payload: PgConnectionConfig) {
  globalSyncState.pgConfigRaw = payload
  globalSyncState.pgConnectionForm.remote_host = payload.remote_host || ''
  globalSyncState.pgConnectionForm.remote_port = Number(payload.remote_port || 5432)
  globalSyncState.pgConnectionForm.remote_database = payload.remote_database || ''
  globalSyncState.pgConnectionForm.remote_username = payload.remote_username || ''
  globalSyncState.pgConnectionForm.remote_password = ''
  globalSyncState.pgConnectionForm.remote_password_set = Boolean(payload.remote_password_set)
}

function recomputeOverview() {
  const pending = Number(globalSyncState.mongoStats.PENDING || 0)
  const partial = Number(globalSyncState.mongoStats.PARTIAL || 0)
  const failed = Number(globalSyncState.mongoStats.FAILED || 0)

  let connectedCount = 0
  if (globalSyncState.connectionStatus) {
    connectedCount = Number(globalSyncState.connectionStatus.connected_count || 0)
  } else {
    connectedCount += globalSyncState.mongoSyncState.connected ? 1 : 0
    connectedCount += globalSyncState.pgSyncState.remote_connected ? 1 : 0
    connectedCount += globalSyncState.pgSyncState.local_connected ? 1 : 0
  }

  globalSyncState.stats.connectedCount = connectedCount
  globalSyncState.stats.totalSources = 3
  globalSyncState.stats.lastSyncTime = pickLastSyncTime(
    globalSyncState.mongoSyncState,
    globalSyncState.pgSyncState,
  )
  globalSyncState.stats.pendingRecords = pending + partial
  globalSyncState.stats.failedRecords = failed
}

async function loadMongoConfig() {
  const payload = await syncApi.getMongoConfig()
  patchMongoForms(payload)
}

async function loadPgConfig() {
  const payload = await syncApi.getPgConfig()
  patchPgForms(payload)
}

async function loadStatusAndStats() {
  globalSyncState.isLoadingStatus = true
  try {
    const [statusResp, statsResp] = await Promise.all([
      syncApi.getStatus(),
      syncApi.getStatistics(),
    ])
    globalSyncState.mongoSyncState = statusResp.mongo_sync || {}
    globalSyncState.pgSyncState = statusResp.pg_sync || {}
    globalSyncState.mongoStats = statsResp
    globalSyncState.isSyncing = Boolean(
      globalSyncState.mongoSyncState.is_running || globalSyncState.pgSyncState.is_running,
    )
    recomputeOverview()
  } finally {
    globalSyncState.isLoadingStatus = false
  }
}

async function loadMappings() {
  globalSyncState.mappingsLoading = true
  try {
    const resp = await syncApi.getMappings()
    globalSyncState.mappings = Array.isArray(resp.items) ? resp.items : []
  } catch (error) {
    console.error('加载字段映射失败:', error)
  } finally {
    globalSyncState.mappingsLoading = false
  }
}

async function loadRunHistory() {
  globalSyncState.runsLoading = true
  try {
    const source =
      globalSyncState.runHistorySourceFilter === 'all'
        ? undefined
        : globalSyncState.runHistorySourceFilter
    const tier =
      globalSyncState.runHistoryTierFilter === 'all'
        ? undefined
        : globalSyncState.runHistoryTierFilter
    const resp = await syncApi.getRuns({
      source,
      tier,
      limit: 50,
    })
    globalSyncState.runHistory = Array.isArray(resp.items) ? resp.items : []
    globalSyncState.runHistoryTotal = Number(resp.total || 0)
  } catch (error) {
    console.error('加载同步历史失败:', error)
    globalSyncState.runHistory = []
    globalSyncState.runHistoryTotal = 0
  } finally {
    globalSyncState.runsLoading = false
  }
}

async function testAllConnections() {
  globalSyncState.isTestingAll = true
  try {
    const result = await syncApi.testAllConnections()
    globalSyncState.connectionStatus = result
    recomputeOverview()
    pushLog('info', `全连接测试完成：${result.connected_count}/${result.total_sources} 可用`)
    return result
  } catch (error: any) {
    const errMsg = error?.response?.data?.detail || error?.message || '未知错误'
    pushLog('error', `全连接测试失败：${errMsg}`)
    throw error
  } finally {
    globalSyncState.isTestingAll = false
  }
}

async function testActiveConnection() {
  globalSyncState.isTestingActive = true
  try {
    if (globalSyncState.activeTab === 'mongo') {
      const result = await syncApi.testMongoConnection()
      pushLog(
        result.connected ? 'success' : 'warn',
        result.connected ? 'Mongo 连接成功' : `Mongo 连接失败：${result.error || '未知错误'}`,
      )
      return result
    }
    if (globalSyncState.activeTab === 'pg_remote') {
      const result = await syncApi.testPgRemoteConnection()
      pushLog(
        result.connected ? 'success' : 'warn',
        result.connected ? '远端 PG 连接成功' : `远端 PG 连接失败：${result.error || '未知错误'}`,
      )
      return result
    }
    const result = await syncApi.testPgLocalConnection()
    pushLog(
      result.connected ? 'success' : 'warn',
      result.connected ? '本地 PG 连接成功' : `本地 PG 连接失败：${result.error || '未知错误'}`,
    )
    return result
  } finally {
    globalSyncState.isTestingActive = false
  }
}

async function saveMongoConnection() {
  globalSyncState.isSavingMongoConnection = true
  try {
    const payload = {
      mongo_database: globalSyncState.mongoConnectionForm.mongo_database,
      read_preference: globalSyncState.mongoConnectionForm.read_preference,
      connect_timeout_ms: Number(globalSyncState.mongoConnectionForm.connect_timeout_ms),
      mongo_uri: globalSyncState.mongoConnectionForm.mongo_uri || undefined,
    }
    await syncApi.updateMongoConfig(payload)
    pushLog('success', 'Mongo 连接配置已保存')
    await loadMongoConfig()
    await loadStatusAndStats()
    return await syncApi.testMongoConnection()
  } catch (error: any) {
    const errMsg = error?.response?.data?.detail || error?.message || '未知错误'
    pushLog('error', `保存 Mongo 连接配置失败：${errMsg}`)
    throw error
  } finally {
    globalSyncState.isSavingMongoConnection = false
  }
}

async function savePgConnection() {
  globalSyncState.isSavingPgConnection = true
  try {
    const payload = {
      remote_host: globalSyncState.pgConnectionForm.remote_host,
      remote_port: Number(globalSyncState.pgConnectionForm.remote_port),
      remote_database: globalSyncState.pgConnectionForm.remote_database,
      remote_username: globalSyncState.pgConnectionForm.remote_username,
      remote_password: globalSyncState.pgConnectionForm.remote_password,
    }
    const resp = await syncApi.updatePgConfig(payload)
    patchPgForms(resp.config)
    pushLog('success', 'PG 连接配置已保存')
    return resp
  } catch (error: any) {
    const errMsg = error?.response?.data?.detail || error?.message || '未知错误'
    pushLog('error', `保存 PG 连接配置失败：${errMsg}`)
    throw error
  } finally {
    globalSyncState.isSavingPgConnection = false
  }
}

async function savePolicy() {
  globalSyncState.isSavingPolicy = true
  try {
    await syncApi.updateMongoConfig({
      enabled: globalSyncState.policyForm.enabled,
      discharge_stable_days: globalSyncState.policyForm.discharge_stable_days,
      lookback_minutes: globalSyncState.policyForm.lookback_minutes,
      rescan_recent_days: globalSyncState.policyForm.rescan_recent_days,
      tier1_interval_minutes: globalSyncState.policyForm.tier1_interval_minutes,
      tier2_interval_minutes: globalSyncState.policyForm.tier2_interval_minutes,
      tier3_cron: globalSyncState.policyForm.tier3_cron,
      max_batch_size: globalSyncState.policyForm.max_batch_size,
      inter_request_delay_ms: globalSyncState.policyForm.inter_request_delay_ms,
      night_window_start: globalSyncState.policyForm.night_window_start,
      night_window_end: globalSyncState.policyForm.night_window_end,
    })
    pushLog('success', '同步策略已保存')
    await loadMongoConfig()
  } catch (error: any) {
    const errMsg = error?.response?.data?.detail || error?.message || '未知错误'
    pushLog('error', `保存同步策略失败：${errMsg}`)
    throw error
  } finally {
    globalSyncState.isSavingPolicy = false
  }
}

function stopPolling() {
  if (pollingTimer) {
    clearInterval(pollingTimer)
    pollingTimer = null
  }
}

function startPolling() {
  stopPolling()
  pollingTimer = setInterval(async () => {
    try {
      await loadStatusAndStats()
      const stillRunning = Boolean(
        globalSyncState.mongoSyncState.is_running || globalSyncState.pgSyncState.is_running,
      )
      if (!stillRunning) {
        stopPolling()
        await loadRunHistory()
        pushLog('success', '同步任务已结束')
      }
    } catch (error) {
      console.error('同步状态轮询失败:', error)
    }
  }, 2000)
}

async function runPreflight(source: SyncSource = 'mongo') {
  globalSyncState.isPreflighting = true
  try {
    const result = await syncApi.preflight({
      source,
      tier: globalSyncState.selectedTier,
    })
    globalSyncState.preflightResult = result
    if (result.executable) {
      pushLog('success', `预检通过：预计影响 ${result.estimated_impact} 条`)
    } else {
      pushLog('warn', `预检未通过：${result.blockers.join('；') || '存在阻断项'}`)
    }
    return result
  } catch (error: any) {
    const errMsg = error?.response?.data?.detail || error?.message || '未知错误'
    pushLog('error', `试运行预检失败：${errMsg}`)
    throw error
  } finally {
    globalSyncState.isPreflighting = false
  }
}

async function executeSync(source: SyncSource = 'mongo') {
  globalSyncState.isSyncing = true
  try {
    const result = await syncApi.triggerSync({
      source,
      tier: globalSyncState.selectedTier,
    })
    if (result.success) {
      pushLog('info', '同步任务已启动，进入状态轮询')
      await loadStatusAndStats()
      startPolling()
    } else {
      pushLog('warn', result.error || '同步任务未启动')
      globalSyncState.isSyncing = false
    }
    return result
  } catch (error: any) {
    const errMsg = error?.response?.data?.detail || error?.message || '未知错误'
    pushLog('error', `执行同步失败：${errMsg}`)
    globalSyncState.isSyncing = false
    throw error
  }
}

function clearLogs() {
  globalSyncState.currentRunLog = []
}

async function initialize() {
  globalSyncState.isInitializing = true
  try {
    await Promise.all([
      loadMongoConfig(),
      loadPgConfig(),
      loadStatusAndStats(),
      loadMappings(),
      loadRunHistory(),
    ])
    pushLog('info', '数据同步控制台已加载')
  } catch (error: any) {
    const errMsg = error?.response?.data?.detail || error?.message || '加载失败'
    message.error(`数据同步配置加载失败：${errMsg}`)
    pushLog('error', `控制台初始化失败：${errMsg}`)
  } finally {
    globalSyncState.isInitializing = false
  }
}

function resetState() {
  stopPolling()
  Object.assign(globalSyncState, createInitialState())
}

async function refreshRunHistory(filters?: {
  source?: 'all' | SyncSource
  tier?: SyncTier | 'all'
}) {
  if (filters?.source) {
    globalSyncState.runHistorySourceFilter = filters.source
  }
  if (filters?.tier) {
    globalSyncState.runHistoryTierFilter = filters.tier
  }
  await loadRunHistory()
}

export function useDataSync() {
  const authStore = useAuthStore()
  const isAdmin = computed(() => authStore.userRoles.includes('admin'))
  const isReadonly = computed(() => !isAdmin.value)
  const hasPreflightPass = computed(() => Boolean(globalSyncState.preflightResult?.executable))

  return {
    state: globalSyncState,
    isAdmin,
    isReadonly,
    hasPreflightPass,
    initialize,
    loadStatusAndStats,
    testAllConnections,
    testActiveConnection,
    saveMongoConnection,
    savePgConnection,
    savePolicy,
    runPreflight,
    executeSync,
    clearLogs,
    loadMappings,
    loadRunHistory: refreshRunHistory,
    resetState,
  }
}
