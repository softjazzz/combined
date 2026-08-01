import { computed, watch, type Ref } from 'vue'
import type {
  ManualSamplePool,
  ManualSamplePoolRecord,
  ManualSamplePoolSyncJob,
  SyncPhase,
} from './types'

export interface CustomerSampleSyncPresentationDependencies {
  syncJobDetail: Ref<ManualSamplePoolSyncJob | undefined>
  dismissedSyncJobId: Ref<string>
  selectedPool: Ref<ManualSamplePool | undefined>
  records: Ref<ManualSamplePoolRecord[]>
  isRecordSyncedForValidation: (record: ManualSamplePoolRecord) => boolean
  isSyncJobRunning: (status?: string) => boolean
}

export function useCustomerSampleSyncPresentation(
  dependencies: CustomerSampleSyncPresentationDependencies,
) {
  const {
    syncJobDetail,
    dismissedSyncJobId,
    selectedPool,
    records,
    isRecordSyncedForValidation,
    isSyncJobRunning,
  } = dependencies
  let syncStatusAutoHideTimer: ReturnType<typeof setTimeout> | null = null

  const syncProgress = computed(() => syncJobDetail.value?.summary?.progress || {})
  const syncPhase = computed(() => String(syncProgress.value.phase || '') as SyncPhase | '')
  const syncPrimaryVisible = computed(
    () =>
      syncProgress.value.primary_visible === true ||
      ['primary_visible', 'detail_sync', 'bundle_refresh', 'completed'].includes(syncPhase.value),
  )
  const syncCustomerStepText = computed(() => {
    const status = String(syncJobDetail.value?.status || '').toLowerCase()
    if (status === 'completed') return '文书已就绪'
    if (status === 'failed') return '同步未完成，已保留现有病历'
    if (syncPrimaryVisible.value) return '病历已进入样本池，文书整理中'
    if (status === 'running') return '正在同步病历基本信息'
    return '等待同步开始'
  })
  const syncHospitalizationSummary = computed(() => {
    const hospitalization = syncJobDetail.value?.summary?.hospitalization_scope
    if (hospitalization?.scope) {
      const departments = hospitalization.scope.departments || []
      const departmentLabel = departments.length ? departments.join('、') : '全部科室'
      const modeLabel =
        hospitalization.scope.mode === 'active'
          ? '当前在院'
          : hospitalization.scope.mode === 'discharged'
            ? '期间出院'
            : '当前在院 + 期间出院'
      return {
        range: `${modeLabel} · ${departmentLabel}`,
        newCount: Number(hospitalization.new_count || 0),
        existingCount: Number(hospitalization.existing_count || 0),
        failedCount: Number(hospitalization.failed_count || 0),
      }
    }
    const legacy = syncJobDetail.value?.summary?.admission_filter
    if (!legacy?.filter) return null
    const departments = legacy.filter.departments || []
    const departmentLabel = departments.length ? departments.join('、') : '全部科室'
    return {
      range: `${legacy.filter.start_date || '—'} 至 ${legacy.filter.end_date || '—'} · ${departmentLabel}`,
      newCount: Number(legacy.new_count || 0),
      existingCount: Number(legacy.existing_count || 0),
      failedCount: Number(legacy.failed_count || 0),
    }
  })
  const syncRecordProgress = computed(() => {
    const summary = syncJobDetail.value?.summary || {}
    const rawProgress = syncProgress.value.record_progress || summary.record_progress || {}
    const total = Number(
      rawProgress.total ??
        syncProgress.value.eligible_visits ??
        summary.eligible_visits ??
        selectedPool.value?.matched_items ??
        0,
    )
    const fallbackCompleted = records.value.filter((record) =>
      isRecordSyncedForValidation(record),
    ).length
    const completed = Math.min(
      Math.max(0, Number(rawProgress.completed ?? fallbackCompleted ?? 0)),
      Math.max(total, 0),
    )
    const remaining = Math.max(0, Number(rawProgress.remaining ?? Math.max(total - completed, 0)))
    const missingMr = Math.max(0, Number(rawProgress.missing_mr ?? remaining))
    const ready =
      total > 0
        ? Math.min(
            Math.max(
              0,
              Number(
                selectedPool.value?.ready_items ??
                  records.value.filter((record) => record.bundle_status === 'ready').length,
              ),
            ),
            Math.max(total, 0),
          )
        : 0
    const readyHint =
      completed > ready
        ? '有病历已同步，文书仍在整理中。'
        : ready > 0
          ? '文书已可用于质控。'
          : '等待文书整理完成。'
    return {
      total,
      completed,
      remaining,
      missingMr,
      detailOnly: Math.max(0, Number(rawProgress.detail_only ?? 0)),
      ready,
      readyHint,
    }
  })
  const syncResolvedStats = computed(() => {
    const summary = syncJobDetail.value?.summary || {}
    const progress = syncProgress.value
    return {
      matched: Number(progress.matched ?? summary.matched ?? 0),
      ambiguous: Number(progress.ambiguous ?? summary.ambiguous ?? 0),
      unmatched: Number(progress.unmatched ?? summary.unmatched ?? 0),
    }
  })

  function customerFacingSyncError(errorMessage?: string | null): string {
    const rawMessage = String(errorMessage || '').trim()
    if (
      /connection to server|connection refused|timeout|timed out|econn|could not connect|server closed|网络|连接超时/i.test(
        rawMessage,
      )
    ) {
      return '暂时无法连接医院数据源，请确认数据服务可用后重试。'
    }
    if (/permission|denied|not authorized|权限/i.test(rawMessage)) {
      return '当前账号无权读取部分病历资料，请联系管理员检查数据访问权限。'
    }
    if (
      /relation .* does not exist|table .* not found|undefined table|缺少.*表/i.test(rawMessage)
    ) {
      return '医院数据源缺少本次同步所需的病历资料，请联系管理员检查数据配置。'
    }
    return '本次同步未完成，请稍后重试；如持续失败，请联系管理员查看同步日志。'
  }

  const syncResultNotice = computed(() => {
    const job = syncJobDetail.value
    if (!job) return null
    const normalizedStatus = String(job.status || '').toLowerCase()
    const summary = job.summary || {}
    const progress = syncProgress.value
    const totalCandidates = Number(progress.total_candidates ?? 0)
    const eligibleVisits = Number(progress.eligible_visits ?? summary.eligible_visits ?? 0)
    const rowsUpserted = Number(progress.total_rows_upserted ?? summary.total_rows_upserted ?? 0)
    if (normalizedStatus === 'failed') {
      return {
        title: '同步失败',
        description: customerFacingSyncError(job.error_message),
        className: 'border-rose-200 bg-rose-50 text-rose-700',
      }
    }
    if (normalizedStatus === 'completed' && totalCandidates === 0) {
      return {
        title: '没有找到可同步样本',
        description:
          '当前筛选条件下没有进入同步的样本病历，请检查是否被“仅内涵/仅首批”过滤，或先执行病历匹配。',
        className: 'border-amber-200 bg-amber-50 text-amber-800',
      }
    }
    if (normalizedStatus === 'completed' && eligibleVisits === 0) {
      return {
        title: '未匹配到可同步病历',
        description:
          '同步任务已结束，但没有找到对应病历。请检查住院号或就诊标识是否正确，并确认医院数据源配置可用。',
        className: 'border-amber-200 bg-amber-50 text-amber-800',
      }
    }
    if (normalizedStatus === 'completed' && rowsUpserted === 0) {
      return {
        title: '文书已就绪',
        description: '已完成病历核对，本次未发现需要更新的内容。',
        className: 'border-emerald-200 bg-emerald-50 text-emerald-700',
      }
    }
    return null
  })

  const showSyncStatusBar = computed(() => {
    const job = syncJobDetail.value
    if (!job) return false
    return String(job.id) !== dismissedSyncJobId.value
  })

  const syncStatusBar = computed(() => {
    const job = syncJobDetail.value
    const normalizedStatus = String(job?.status || '').toLowerCase()
    const progressSummary = `病历 ${syncRecordProgress.value.completed}/${syncRecordProgress.value.total} · 文书就绪 ${syncRecordProgress.value.ready} · 表 ${syncProgress.value.processed_tables ?? 0}/${syncProgress.value.total_tables ?? 0}`

    if (normalizedStatus === 'failed') {
      return {
        title: '同步失败',
        summary: customerFacingSyncError(job?.error_message),
        description: '',
        className: 'border-rose-200 bg-rose-50/70 text-rose-700',
        dotClassName: 'bg-rose-500',
        canRetry: true,
        canDismiss: true,
      }
    }
    if (normalizedStatus === 'completed') {
      const notice = syncResultNotice.value
      return {
        title: notice?.title || '文书已就绪',
        summary: notice?.description || progressSummary,
        description: notice ? progressSummary : '',
        className: notice
          ? 'border-amber-200 bg-amber-50/70 text-amber-800'
          : 'border-emerald-200 bg-emerald-50/60 text-emerald-700',
        dotClassName: notice ? 'bg-amber-500' : 'bg-emerald-500',
        canRetry: Boolean(notice),
        canDismiss: true,
      }
    }
    return {
      title: syncCustomerStepText.value,
      summary: progressSummary,
      description: syncPrimaryVisible.value
        ? '可先查看病历，文书将在后台继续整理。'
        : '正在准备病例基本信息。',
      className: 'border-blue-200 bg-blue-50/60 text-[#0057b8]',
      dotClassName: normalizedStatus === 'running' ? 'bg-blue-500 animate-pulse' : 'bg-amber-500',
      canRetry: false,
      canDismiss: false,
    }
  })

  watch(
    () => [String(syncJobDetail.value?.id || ''), String(syncJobDetail.value?.status || '')],
    ([jobId, status], [previousJobId]) => {
      if (syncStatusAutoHideTimer) {
        clearTimeout(syncStatusAutoHideTimer)
        syncStatusAutoHideTimer = null
      }
      if (!jobId) return
      if (jobId !== previousJobId || isSyncJobRunning(status)) {
        dismissedSyncJobId.value = ''
      }
      if (status.toLowerCase() === 'completed' && !syncResultNotice.value) {
        syncStatusAutoHideTimer = setTimeout(() => {
          if (String(syncJobDetail.value?.id || '') === jobId) {
            dismissedSyncJobId.value = jobId
          }
          syncStatusAutoHideTimer = null
        }, 6000)
      }
    },
  )

  function stopSyncStatusAutoHideTimer() {
    if (!syncStatusAutoHideTimer) return
    clearTimeout(syncStatusAutoHideTimer)
    syncStatusAutoHideTimer = null
  }

  return {
    syncProgress,
    syncCustomerStepText,
    syncHospitalizationSummary,
    syncRecordProgress,
    syncResolvedStats,
    customerFacingSyncError,
    syncResultNotice,
    showSyncStatusBar,
    syncStatusBar,
    stopSyncStatusAutoHideTimer,
  }
}
