import { computed, reactive } from 'vue'
import { message } from 'ant-design-vue'

import { useAuthStore } from '@/stores/auth'
import { canManageSystemConfig } from '@/utils/systemConfigAccess'
import {
  syncApi,
  type PgConnectionConfig,
  type PgSyncTableGroupItem,
  type PgSyncTableConfigItem,
  type SyncConnectionStatus,
  type SyncMappingItem,
  type SyncPolicyConfig,
  type SyncPreflightResult,
  type SyncRunLogItem as SyncRunHistoryItem,
  type SyncSource,
  type SyncStatistics,
  type SyncTemplate,
  type SyncTier,
} from '@/api/sync'

const DEFAULT_PG_TABLE_GROUP_ID = 'sample_full_domain'

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

export interface PgConnectionForm {
  remote_host: string
  remote_port: number
  remote_database: string
  remote_username: string
  remote_schema: string
  default_institute_id: string
  sync_mode: 'table' | 'procedure'
  remote_password: string
  remote_password_set: boolean
}

export interface PgSyncTableFormItem {
  name: string
  label?: string
  source_table: string
  date_field: string
  fallback_date_field: string
  enabled: boolean
  procedure?: string
}

export interface SyncPolicyForm {
  scope: 'running' | 'final' | 'frontpage' | 'coding' | 'settlement' | 'both'
  start_date: string
  end_date: string
  schedule_mode: 'interval' | 'cron'
  schedule_minutes: number
  mirror_delay_base_minutes: number
  policy_version: string
  enabled: boolean
  target_departments: string[]
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

type SyncLoadSection = 'connection' | 'policy' | 'history'

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

function pickLastSyncTime(pgSyncState: Record<string, any>): string | null {
  const candidates = [pgSyncState.last_sync_time].filter(Boolean) as string[]

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
    activeTab: 'pg_remote' as 'pg_remote' | 'pg_local',
    selectedTier: 'all' as SyncTier,

    stats: {
      connectedCount: 0,
      totalSources: 2,
      lastSyncTime: null,
      pendingRecords: 0,
      failedRecords: 0,
    } as SyncOverviewStats,

    pgConnectionForm: {
      remote_host: '',
      remote_port: 5432,
      remote_database: '',
      remote_username: '',
      remote_schema: 'public',
      default_institute_id: '',
      sync_mode: 'table',
      remote_password: '',
      remote_password_set: false,
    } as PgConnectionForm,

    pgSyncTables: [] as PgSyncTableFormItem[],
    pgTableGroups: [] as PgSyncTableGroupItem[],
    selectedTableGroups: [DEFAULT_PG_TABLE_GROUP_ID] as string[],

    policyForm: {
      scope: 'both',
      start_date: '',
      end_date: '',
      schedule_mode: 'interval',
      schedule_minutes: 30,
      mirror_delay_base_minutes: 30,
      policy_version: '',
      enabled: false,
      target_departments: ['*'],
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

    pgConfigRaw: {} as PgConnectionConfig,
    pgSyncState: {} as Record<string, any>,
    pgStats: { PENDING: 0, PARTIAL: 0, SYNCED: 0, STALE: 0, FAILED: 0 } as SyncStatistics,
    connectionStatus: null as SyncConnectionStatus | null,
    preflightResult: null as SyncPreflightResult | null,
    preflightRequestKey: '',
    mappings: [] as SyncMappingItem[],
    runHistory: [] as SyncRunHistoryItem[],
    runHistoryTotal: 0,
    runHistorySourceFilter: 'all' as 'all' | SyncSource,
    runHistoryTierFilter: 'all' as SyncTier | 'all',

    isInitializing: false,
    isLoadingStatus: false,
    isTestingAll: false,
    isTestingActive: false,
    isSavingPgConnection: false,
    isLoadingPgTables: false,
    isSavingPgTables: false,
    isSavingPolicy: false,
    isPreflighting: false,
    isSyncing: false,
    mappingsLoading: false,
    runsLoading: false,
    templatesLoading: false,
    templateApplying: false,
    departmentsLoading: false,

    syncTemplates: [] as SyncTemplate[],
    selectedTemplateId: 'hospital_standard' as SyncTemplate['id'],
    selectedTemplateDepartments: [] as string[],
    showAdvancedPolicy: false,
    availableDepartments: [] as string[],
    loadErrors: {
      connection: null as string | null,
      policy: null as string | null,
      history: null as string | null,
    },

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

function toErrorMessage(error: any): string {
  return (
    error?.response?.data?.detail || error?.response?.data?.error || error?.message || '未知错误'
  )
}

function patchSyncPolicy(payload: SyncPolicyConfig) {
  const departments =
    Array.isArray(payload.target_departments) && payload.target_departments.length > 0
      ? payload.target_departments
      : ['*']
  const schedule = payload.schedule || {}
  const nightWindow = payload.night_window || {}

  const scope = String(payload.scope || 'both').toLowerCase()
  const normalizedScope: SyncPolicyForm['scope'] = [
    'running',
    'final',
    'frontpage',
    'coding',
    'settlement',
    'both',
  ].includes(scope)
    ? (scope as SyncPolicyForm['scope'])
    : 'both'

  globalSyncState.policyForm.scope = normalizedScope
  globalSyncState.policyForm.target_departments = departments
  globalSyncState.policyForm.start_date = String(payload.start_date || '')
  globalSyncState.policyForm.end_date = String(payload.end_date || '')
  globalSyncState.policyForm.schedule_mode =
    String(schedule.mode || '').toLowerCase() === 'cron' ? 'cron' : 'interval'
  globalSyncState.policyForm.schedule_minutes = Number(schedule.minutes || 30)
  globalSyncState.policyForm.night_window_start = String(nightWindow.start || '22:00')
  globalSyncState.policyForm.night_window_end = String(nightWindow.end || '06:00')
  globalSyncState.policyForm.mirror_delay_base_minutes = Number(
    payload.mirror_delay_base_minutes || 30,
  )
  globalSyncState.policyForm.policy_version = String(payload.policy_version || '')
}

function patchPgForms(payload: PgConnectionConfig) {
  globalSyncState.pgConfigRaw = payload
  globalSyncState.pgConnectionForm.remote_host = payload.remote_host || ''
  globalSyncState.pgConnectionForm.remote_port = Number(payload.remote_port || 5432)
  globalSyncState.pgConnectionForm.remote_database = payload.remote_database || ''
  globalSyncState.pgConnectionForm.remote_username = payload.remote_username || ''
  globalSyncState.pgConnectionForm.remote_schema = payload.remote_schema || 'public'
  globalSyncState.pgConnectionForm.default_institute_id = payload.default_institute_id || ''
  globalSyncState.pgConnectionForm.sync_mode =
    payload.sync_mode === 'procedure' ? 'procedure' : 'table'
  globalSyncState.pgConnectionForm.remote_password = ''
  globalSyncState.pgConnectionForm.remote_password_set = Boolean(payload.remote_password_set)
}

function normalizePgSyncTable(item: PgSyncTableConfigItem): PgSyncTableFormItem {
  return {
    name: item.name,
    label: item.label,
    source_table: item.source_table || '',
    date_field: item.date_field || '',
    fallback_date_field: item.fallback_date_field || '',
    enabled: Boolean(item.enabled),
    procedure: item.procedure,
  }
}

function normalizeSelectedTableGroups(
  selected: string[],
  groups: PgSyncTableGroupItem[],
): string[] {
  const validIds = new Set(groups.map((item) => String(item.id || '').trim()).filter(Boolean))
  const cleaned = [
    ...new Set((selected || []).map((item) => String(item || '').trim()).filter(Boolean)),
  ]
  const kept = cleaned.filter((id) => validIds.has(id))
  if (kept.length > 0) {
    return kept
  }
  if (validIds.has(DEFAULT_PG_TABLE_GROUP_ID)) {
    return [DEFAULT_PG_TABLE_GROUP_ID]
  }
  return Array.from(validIds).slice(0, 1)
}

function recomputeOverview() {
  const pending = Number(globalSyncState.pgStats.PENDING || 0)
  const partial = Number(globalSyncState.pgStats.PARTIAL || 0)
  const failed = Number(globalSyncState.pgStats.FAILED || 0)

  let connectedCount = 0
  if (globalSyncState.connectionStatus) {
    connectedCount = Number(globalSyncState.connectionStatus.connected_count || 0)
  } else {
    connectedCount += globalSyncState.pgSyncState.remote_connected ? 1 : 0
    connectedCount += globalSyncState.pgSyncState.local_connected ? 1 : 0
  }

  globalSyncState.stats.connectedCount = connectedCount
  globalSyncState.stats.totalSources = 2
  globalSyncState.stats.lastSyncTime = pickLastSyncTime(globalSyncState.pgSyncState)
  globalSyncState.stats.pendingRecords = pending + partial
  globalSyncState.stats.failedRecords = failed
}

async function loadPgConfig() {
  const payload = await syncApi.getPgConfig()
  patchPgForms(payload)
}

async function loadSyncPolicy() {
  const payload = await syncApi.getSyncPolicy()
  patchSyncPolicy(payload)
}

async function loadPgSyncTables() {
  globalSyncState.isLoadingPgTables = true
  try {
    const resp = await syncApi.getPgSyncTables()
    globalSyncState.pgSyncTables = Array.isArray(resp.items)
      ? resp.items.map(normalizePgSyncTable)
      : []
    return globalSyncState.pgSyncTables
  } catch (error) {
    console.error('加载 PG 表配置失败:', error)
    globalSyncState.pgSyncTables = []
    throw error
  } finally {
    globalSyncState.isLoadingPgTables = false
  }
}

async function loadPgSyncTableGroups() {
  try {
    const resp = await syncApi.getPgSyncTableGroups()
    globalSyncState.pgTableGroups = Array.isArray(resp.items) ? resp.items : []
    globalSyncState.selectedTableGroups = normalizeSelectedTableGroups(
      globalSyncState.selectedTableGroups,
      globalSyncState.pgTableGroups,
    )
    return globalSyncState.pgTableGroups
  } catch (error: any) {
    console.error('加载 PG 表分组失败:', error)
    const detail =
      error?.response?.data?.detail || error?.response?.data?.error || error?.message || '未知错误'
    message.warning(`加载 PG 表分组失败：${detail}`)
    globalSyncState.pgTableGroups = []
    return []
  }
}

async function loadStatusAndStats() {
  globalSyncState.isLoadingStatus = true
  try {
    const [statusResp, statsResp] = await Promise.all([
      syncApi.getStatus(),
      syncApi.getStatistics(),
    ])
    globalSyncState.pgSyncState = statusResp.pg_sync || {}
    globalSyncState.pgStats = statsResp
    globalSyncState.isSyncing = Boolean(globalSyncState.pgSyncState.is_running)
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

async function loadTemplates() {
  globalSyncState.templatesLoading = true
  try {
    const resp = await syncApi.getTemplates()
    globalSyncState.syncTemplates = Array.isArray(resp.items) ? resp.items : []
    if (
      !globalSyncState.syncTemplates.some((item) => item.id === globalSyncState.selectedTemplateId)
    ) {
      globalSyncState.selectedTemplateId = 'hospital_standard'
    }
  } catch (error) {
    console.error('加载同步模板失败:', error)
    globalSyncState.syncTemplates = []
  } finally {
    globalSyncState.templatesLoading = false
  }
}

async function loadDepartments() {
  globalSyncState.departmentsLoading = true
  try {
    globalSyncState.availableDepartments = await syncApi.getDepartments()
  } catch (error) {
    console.error('加载科室列表失败:', error)
    const detail =
      (error as any)?.response?.data?.detail ||
      (error as any)?.response?.data?.error ||
      (error as any)?.message ||
      '未知错误'
    message.warning(`加载科室列表失败：${detail}`)
    globalSyncState.availableDepartments = []
  } finally {
    globalSyncState.departmentsLoading = false
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

async function savePgConnection() {
  globalSyncState.isSavingPgConnection = true
  try {
    const defaultInstituteId = globalSyncState.pgConnectionForm.default_institute_id.trim()
    if (!defaultInstituteId || defaultInstituteId.toUpperCase() === 'LOCAL-HOSPITAL') {
      throw new Error('请填写本院长期稳定的机构标识，不能使用系统占位值')
    }
    const payload = {
      remote_host: globalSyncState.pgConnectionForm.remote_host,
      remote_port: Number(globalSyncState.pgConnectionForm.remote_port),
      remote_database: globalSyncState.pgConnectionForm.remote_database,
      remote_username: globalSyncState.pgConnectionForm.remote_username,
      remote_schema: globalSyncState.pgConnectionForm.remote_schema || 'public',
      default_institute_id: defaultInstituteId,
      sync_mode: globalSyncState.pgConnectionForm.sync_mode,
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

async function savePgSyncTables() {
  globalSyncState.isSavingPgTables = true
  try {
    const resp = await syncApi.updatePgSyncTables({
      items: globalSyncState.pgSyncTables.map((item) => ({
        name: item.name,
        source_table: item.source_table || undefined,
        date_field: item.date_field || undefined,
        fallback_date_field: item.fallback_date_field || undefined,
        enabled: Boolean(item.enabled),
      })),
    })
    globalSyncState.pgSyncTables = Array.isArray(resp.items)
      ? resp.items.map(normalizePgSyncTable)
      : []
    pushLog('success', 'PG 表同步配置已保存')
    return globalSyncState.pgSyncTables
  } catch (error: any) {
    const errMsg = error?.response?.data?.detail || error?.message || '未知错误'
    pushLog('error', `保存 PG 表同步配置失败：${errMsg}`)
    throw error
  } finally {
    globalSyncState.isSavingPgTables = false
  }
}

async function savePolicy() {
  globalSyncState.isSavingPolicy = true
  try {
    const departments = Array.isArray(globalSyncState.policyForm.target_departments)
      ? [
          ...new Set(
            globalSyncState.policyForm.target_departments
              .map((item) => String(item || '').trim())
              .filter(Boolean),
          ),
        ]
      : []
    const safeDepartments =
      departments.length === 0 || departments.includes('*') ? ['*'] : departments

    const saved = await syncApi.updateSyncPolicy({
      scope: globalSyncState.policyForm.scope,
      target_departments: safeDepartments,
      start_date:
        globalSyncState.policyForm.scope === 'running'
          ? undefined
          : globalSyncState.policyForm.start_date || undefined,
      end_date:
        globalSyncState.policyForm.scope === 'running'
          ? undefined
          : globalSyncState.policyForm.end_date || undefined,
      schedule: {
        mode: globalSyncState.policyForm.schedule_mode,
        minutes: Number(globalSyncState.policyForm.schedule_minutes || 30),
      },
      night_window: {
        start: globalSyncState.policyForm.night_window_start,
        end: globalSyncState.policyForm.night_window_end,
      },
      mirror_delay_base_minutes: Number(globalSyncState.policyForm.mirror_delay_base_minutes || 30),
    })
    patchSyncPolicy(saved)
    pushLog('success', '同步策略已保存')
  } catch (error: any) {
    const errMsg = error?.response?.data?.detail || error?.message || '未知错误'
    pushLog('error', `保存同步策略失败：${errMsg}`)
    throw error
  } finally {
    globalSyncState.isSavingPolicy = false
  }
}

async function applyTemplate() {
  globalSyncState.templateApplying = true
  try {
    const resp = await syncApi.applyTemplate({
      template_id: globalSyncState.selectedTemplateId,
      departments:
        globalSyncState.selectedTemplateDepartments.length > 0
          ? globalSyncState.selectedTemplateDepartments
          : undefined,
    })
    pushLog('success', `模板已应用：${resp.template_id}`)
    await Promise.all([loadSyncPolicy(), loadStatusAndStats()])
    try {
      await runPreflight('pg')
    } catch {
      // 模板应用后预检失败仅记录日志，不中断主流程
    }
    return resp
  } catch (error: any) {
    const errMsg = error?.response?.data?.detail || error?.message || '未知错误'
    pushLog('error', `模板应用失败：${errMsg}`)
    throw error
  } finally {
    globalSyncState.templateApplying = false
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
      const stillRunning = Boolean(globalSyncState.pgSyncState.is_running)
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

function resolveTargetDepartments(): string[] | undefined {
  const cleaned = [
    ...new Set(
      (globalSyncState.policyForm.target_departments || [])
        .map((item) => String(item || '').trim())
        .filter(Boolean),
    ),
  ]
  if (cleaned.length === 0 || (cleaned.length === 1 && cleaned[0] === '*')) {
    return ['*']
  }
  if (cleaned.includes('*')) {
    return cleaned.filter((item) => item !== '*')
  }
  return cleaned
}

function resolveTableGroups(): string[] | undefined {
  const groups = normalizeSelectedTableGroups(
    globalSyncState.selectedTableGroups,
    globalSyncState.pgTableGroups,
  )
  globalSyncState.selectedTableGroups = groups
  return groups.length > 0 ? groups : undefined
}

function sortStrings(values?: string[]): string[] | undefined {
  const cleaned = [
    ...new Set((values || []).map((item) => String(item || '').trim()).filter(Boolean)),
  ].sort()
  return cleaned.length > 0 ? cleaned : undefined
}

function buildSyncScopePayload(
  source: SyncSource = 'pg',
  options: { normalizeGroups?: boolean } = {},
) {
  const targetDepartments = source === 'pg' ? resolveTargetDepartments() : undefined
  let tableGroups: string[] | undefined
  if (source === 'pg') {
    if (options.normalizeGroups !== false) {
      tableGroups = resolveTableGroups()
    } else {
      const groups = normalizeSelectedTableGroups(
        globalSyncState.selectedTableGroups,
        globalSyncState.pgTableGroups,
      )
      tableGroups = groups.length > 0 ? groups : undefined
    }
  }
  return {
    source,
    tier: globalSyncState.selectedTier,
    scene: source === 'pg' ? globalSyncState.policyForm.scope : undefined,
    date_window:
      source === 'pg' && globalSyncState.policyForm.scope !== 'running'
        ? {
            start: globalSyncState.policyForm.start_date || undefined,
            end: globalSyncState.policyForm.end_date || undefined,
          }
        : undefined,
    target_departments: targetDepartments,
    policy_version:
      source === 'pg' ? globalSyncState.policyForm.policy_version || undefined : undefined,
    table_groups: tableGroups,
  }
}

function buildPreflightRequestKey(payload = buildSyncScopePayload('pg')): string {
  return JSON.stringify({
    source: payload.source,
    tier: payload.tier,
    scene: payload.scene || '',
    date_window: {
      start: payload.date_window?.start || '',
      end: payload.date_window?.end || '',
    },
    target_departments: sortStrings(payload.target_departments) || [],
    policy_version: payload.policy_version || '',
    table_groups: sortStrings(payload.table_groups) || [],
  })
}

async function runPreflight(source: SyncSource = 'pg') {
  globalSyncState.isPreflighting = true
  try {
    const payload = buildSyncScopePayload(source)
    const result = await syncApi.preflight(payload)
    globalSyncState.preflightResult = result
    globalSyncState.preflightRequestKey = buildPreflightRequestKey(payload)
    if (result.executable) {
      pushLog('success', `预检通过：预计涉及 ${result.estimated_impact} 份病历`)
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

async function executeSync(source: SyncSource = 'pg') {
  const candidateCount = Math.max(
    0,
    Number(globalSyncState.preflightResult?.estimated_impact || 0),
  )
  globalSyncState.isSyncing = true
  globalSyncState.pgSyncState = {
    ...globalSyncState.pgSyncState,
    is_running: true,
    last_sync_status: 'running',
    total_records_synced: 0,
    progress: {
      status: 'running',
      stage: 'initializing',
      tables_total: 0,
      tables_done: 0,
      rows_pulled_total: 0,
      rows_upserted_total: 0,
      eligible_visit_count: candidateCount,
      visit_progress: {
        total: candidateCount,
        completed: 0,
        remaining: candidateCount,
        missing_mr: 0,
        detail_only: 0,
      },
    },
  }
  pushLog('info', '同步任务已提交，正在轮询执行进度')
  startPolling()
  try {
    const payload = buildSyncScopePayload(source)
    const result = await syncApi.triggerSync({
      ...payload,
      preflight_fingerprint: globalSyncState.preflightResult?.preflight_fingerprint,
    })
    if (result.success || result.status === 'partial') {
      const warnings = Array.isArray(result.warnings) ? result.warnings.filter(Boolean) : []
      if (result.idempotent_reused) {
        pushLog('info', '检测到重复触发，已返回已有同步结果')
      }
      if (result.status === 'partial') {
        pushLog('warn', warnings[0] || '同步部分完成：部分病历缺少 mr 主记录，病历池暂不可见')
      } else {
        pushLog('info', '同步任务已启动，进入状态轮询')
      }
      await loadStatusAndStats()
      if (globalSyncState.isSyncing) {
        startPolling()
      } else {
        stopPolling()
      }
    } else {
      pushLog('warn', result.error || '同步任务未启动')
      globalSyncState.isSyncing = false
      stopPolling()
    }
    return result
  } catch (error: any) {
    const errMsg = error?.response?.data?.detail || error?.message || '未知错误'
    const isTimeout =
      error?.code === 'ECONNABORTED' ||
      String(error?.message || '')
        .toLowerCase()
        .includes('timeout')
    if (isTimeout) {
      pushLog('warn', '同步请求超过前端等待时间，已转入状态轮询。请勿重复点击执行。')
      try {
        await loadStatusAndStats()
        startPolling()
      } catch (pollError) {
        console.error('同步超时后加载状态失败:', pollError)
      }
      return {
        success: true,
        status: 'timeout_polling',
        message: '同步请求仍可能在后端执行，已转入状态轮询。',
      }
    }
    pushLog('error', `执行同步失败：${errMsg}`)
    globalSyncState.isSyncing = false
    stopPolling()
    throw error
  }
}

function clearLogs() {
  globalSyncState.currentRunLog = []
}

async function initialize() {
  globalSyncState.isInitializing = true
  globalSyncState.loadErrors.connection = null
  globalSyncState.loadErrors.policy = null
  globalSyncState.loadErrors.history = null
  try {
    const tasks: Array<{
      section: SyncLoadSection
      label: string
      run: () => Promise<unknown>
    }> = [
      {
        section: 'connection',
        label: '连接配置',
        run: () =>
          Promise.all([
            loadPgConfig(),
            loadPgSyncTables(),
            loadPgSyncTableGroups(),
            loadDepartments(),
            loadStatusAndStats(),
          ]),
      },
      {
        section: 'policy',
        label: '策略模板',
        run: () => Promise.all([loadSyncPolicy(), loadTemplates()]),
      },
      {
        section: 'history',
        label: '运行历史',
        run: () => loadRunHistory(),
      },
    ]

    const results = await Promise.allSettled(tasks.map((item) => item.run()))
    let failedCount = 0

    results.forEach((result, index) => {
      const task = tasks[index]
      if (!task) {
        return
      }
      if (result.status === 'fulfilled') {
        globalSyncState.loadErrors[task.section] = null
        return
      }
      failedCount += 1
      const detail = toErrorMessage(result.reason)
      const errorText = `${task.label}加载失败：${detail}`
      if (!globalSyncState.loadErrors[task.section]) {
        globalSyncState.loadErrors[task.section] = errorText
      }
      pushLog('warn', errorText)
    })

    if (failedCount === 0) {
      pushLog('info', '数据同步控制台已加载')
    } else {
      message.warning(
        `数据同步配置部分加载失败（${failedCount}/${tasks.length}），可继续操作已就绪模块`,
      )
      pushLog('warn', '控制台已降级加载，可继续使用已就绪功能')
    }
  } catch (error: any) {
    const errMsg = toErrorMessage(error)
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
  const isAdmin = computed(() => canManageSystemConfig(authStore.userRoles))
  const isReadonly = computed(() => !isAdmin.value)
  const hasPreflightPass = computed(
    () =>
      Boolean(globalSyncState.preflightResult?.executable) &&
      globalSyncState.preflightRequestKey ===
        buildPreflightRequestKey(buildSyncScopePayload('pg', { normalizeGroups: false })),
  )

  return {
    state: globalSyncState,
    isAdmin,
    isReadonly,
    hasPreflightPass,
    initialize,
    loadStatusAndStats,
    testAllConnections,
    testActiveConnection,
    savePgConnection,
    loadPgSyncTables,
    loadPgSyncTableGroups,
    savePgSyncTables,
    savePolicy,
    runPreflight,
    executeSync,
    clearLogs,
    loadMappings,
    loadRunHistory: refreshRunHistory,
    applyTemplate,
    loadSyncPolicy,
    loadTemplates,
    loadDepartments,
    resetState,
  }
}
