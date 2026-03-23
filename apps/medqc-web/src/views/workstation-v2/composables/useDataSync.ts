import { reactive } from 'vue'

// ---- 类型定义 ----

/** 后端 DTO（原样映射 API 返回） */
export interface DryRunResultDTO {
  estimatedImpact: number
  riskLevel: string
  warnings: string[]
}

/** 前端视图模型（在 adapter 中做类型收窄） */
export interface DryRunResultVM {
  estimatedImpact: number
  riskLevel: 'low' | 'medium' | 'high'
  warnings: string[]
}

/** 结构化运行日志条目 */
export interface SyncLogItem {
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

// ---- DTO → VM Adapter ----

function adaptDryRunResult(dto: DryRunResultDTO): DryRunResultVM {
  const validLevels = ['low', 'medium', 'high'] as const
  const level = validLevels.includes(dto.riskLevel as typeof validLevels[number])
    ? (dto.riskLevel as DryRunResultVM['riskLevel'])
    : 'medium'
  return {
    estimatedImpact: dto.estimatedImpact,
    riskLevel: level,
    warnings: dto.warnings ?? [],
  }
}

// ---- 辅助：生成日志时间戳 ----

function nowTimestamp(): string {
  return new Date().toLocaleTimeString('en-US', { hour12: false })
}

// ---- 初始状态快照（用于 reset） ----

function createInitialState() {
  return {
    stats: {
      connectedCount: 2,
      totalSources: 3,
      lastSyncTime: '2026-03-23 09:30:00',
      pendingRecords: 12050,
      failedRecords: 3,
    } as SyncOverviewStats,

    activeTab: 'mongo' as 'mongo' | 'pg_remote' | 'pg_local',

    isRunPanelExpanded: false,
    currentRunLog: [] as SyncLogItem[],
    isSyncing: false,

    dryRunResults: null as DryRunResultVM | null,
  }
}

// ---- 全局单例状态 ----

const globalSyncState = reactive(createInitialState())

// ---- Composable ----

export function useDataSync() {
  /** 试运行 */
  const triggerDryRun = async () => {
    globalSyncState.isSyncing = true
    try {
      // TODO: 替换为真实 API 调用
      await new Promise((resolve) => setTimeout(resolve, 800))
      const mockDTO: DryRunResultDTO = {
        estimatedImpact: 12050,
        riskLevel: 'medium',
        warnings: ['存在 3 个类型不匹配警告', '建议开启增量更新选项'],
      }
      globalSyncState.dryRunResults = adaptDryRunResult(mockDTO)
    } catch (err) {
      globalSyncState.currentRunLog.push({
        timestamp: nowTimestamp(),
        level: 'error',
        message: `试运行失败: ${err instanceof Error ? err.message : String(err)}`,
      })
    } finally {
      globalSyncState.isSyncing = false
    }
  }

  /** 正式执行同步 */
  const executeSync = async () => {
    if (!globalSyncState.dryRunResults) {
      return false
    }
    globalSyncState.isSyncing = true
    globalSyncState.currentRunLog.push({
      timestamp: nowTimestamp(),
      level: 'info',
      message: '正在启动全量同步队列...',
    })
    try {
      // TODO: 替换为真实 API 调用
      await new Promise((resolve) => setTimeout(resolve, 1500))
      globalSyncState.currentRunLog.push({
        timestamp: nowTimestamp(),
        level: 'success',
        message: '同步完成 (耗时 1.5s)',
      })
      globalSyncState.stats.pendingRecords = 0
      globalSyncState.stats.lastSyncTime = new Date().toLocaleString()
      globalSyncState.dryRunResults = null
      return true
    } catch (err) {
      globalSyncState.currentRunLog.push({
        timestamp: nowTimestamp(),
        level: 'error',
        message: `同步执行失败: ${err instanceof Error ? err.message : String(err)}`,
      })
      return false
    } finally {
      globalSyncState.isSyncing = false
    }
  }

  /** 重置全局状态（登出/页面卸载时调用） */
  const resetState = () => {
    Object.assign(globalSyncState, createInitialState())
  }

  return {
    state: globalSyncState,
    triggerDryRun,
    executeSync,
    resetState,
  }
}
