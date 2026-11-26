import { computed, ref, watch, type Ref } from 'vue'
import { message } from 'ant-design-vue'
import { ApiService } from '@/services/apiService'
import { normalizeNotification, normalizeDoctorInteraction } from '../normalize'
import { useAuthStore } from '@/stores/auth'
import { parseQcTaskTime } from '../utils/qcTaskTime'
import { findRecordById, RECORD_RESELECTION_MESSAGE } from '../workstationNavigationController'
import type {
  DoctorInteractionTarget,
  NotificationOverviewItem,
  NotificationVM,
  PatientRecord,
} from '../types'

type NotificationPayload = {
  items?: unknown[]
  unread_count?: number
}

interface NotificationListResponse {
  data?: NotificationPayload
}

interface NotificationOverviewResponse {
  items?: unknown[]
  date?: string
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isAuthError(err: unknown): boolean {
  const status = (err as { response?: { status?: number } })?.response?.status
  return status === 401 || status === 403
}

function isBatchSummaryType(type: string | undefined): boolean {
  return String(type || '')
    .trim()
    .toLowerCase()
    .endsWith('_batch_summary')
}

function extractListPayload(payload: unknown): NotificationPayload | undefined {
  if (!isPlainObject(payload)) return undefined
  if (Array.isArray(payload.items)) return payload as NotificationPayload
  const nested = payload.data
  if (isPlainObject(nested)) return nested as NotificationPayload
  return undefined
}

function extractOverviewPayload(payload: unknown): NotificationOverviewResponse | undefined {
  if (!isPlainObject(payload)) return undefined
  if (Array.isArray(payload.items)) return payload as NotificationOverviewResponse
  const nested = payload.data
  if (isPlainObject(nested) && Array.isArray(nested.items)) {
    return nested as NotificationOverviewResponse
  }
  return undefined
}

export function useNotifications(
  allRecords: Ref<PatientRecord[]>,
  openRecord: (record: PatientRecord) => void,
  assistPanelVisible: Ref<boolean>,
  assistTab: Ref<string>,
  frontpageTab: Ref<string>,
  openInteraction?: (target: DoctorInteractionTarget) => Promise<unknown>,
) {
  const auth = useAuthStore()
  let generation = 0
  let overviewRequestSeq = 0
  let markingAllRead = false
  let handlingOverviewClick = false
  const assistNotifications = ref<NotificationVM[]>([])
  const notificationUnreadCount = ref(0)
  const notificationLoading = ref(false)
  const notificationReadFilter = ref<'all' | 'unread' | 'read'>('unread')
  const overviewLoading = ref(false)
  const overviewViewMode = ref<'overview' | 'detail'>('overview')
  const overviewTypeFilter = ref<'all' | string>('all')
  const overviewSeverityFilter = ref<'all' | string>('all')
  const overviewDepartmentFilter = ref<'all' | string>('all')
  const notificationOverviewItems = ref<NotificationOverviewItem[]>([])

  const filteredAssistNotifications = computed(() => {
    if (notificationReadFilter.value === 'all') return assistNotifications.value
    const expectRead = notificationReadFilter.value === 'read'
    return assistNotifications.value.filter((item) => item.is_read === expectRead)
  })

  const overviewDepartments = computed(() => {
    const set = new Set<string>()
    for (const item of notificationOverviewItems.value) {
      if (item.department) set.add(item.department)
    }
    return Array.from(set).sort()
  })

  const overviewTypes = computed(() => {
    const set = new Set<string>()
    for (const item of notificationOverviewItems.value) {
      if (item.type) set.add(item.type)
    }
    return Array.from(set).sort()
  })

  const overviewSeverities = computed(() => {
    const set = new Set<string>()
    for (const item of notificationOverviewItems.value) {
      if (item.severity) set.add(item.severity)
    }
    return Array.from(set).sort()
  })

  const filteredNotificationOverviewItems = computed(() => {
    return notificationOverviewItems.value.filter((item) => {
      const matchDepartment =
        overviewDepartmentFilter.value === 'all' ||
        item.department === overviewDepartmentFilter.value
      const matchType = overviewTypeFilter.value === 'all' || item.type === overviewTypeFilter.value
      const matchSeverity =
        overviewSeverityFilter.value === 'all' || item.severity === overviewSeverityFilter.value
      return matchDepartment && matchType && matchSeverity
    })
  })

  function normalizeOverviewItem(raw: unknown, index: number): NotificationOverviewItem {
    const item = (raw || {}) as Record<string, unknown>
    const sourceIdsRaw = item.source_notification_ids
    const sourceIds = Array.isArray(sourceIdsRaw)
      ? sourceIdsRaw.map((id) => String(id)).filter(Boolean)
      : []
    return {
      overview_id: String(item.overview_id || `overview-${index}`),
      type: String(item.type || 'general'),
      severity: String(item.severity || 'info'),
      department: String(item.department || '未分科室'),
      record_id: String(item.record_id || ''),
      title: String(item.title || '病案问题集中点'),
      summary: String(item.summary || '暂无描述'),
      occurrence_count: Number(item.occurrence_count || 0),
      unread_count: Number(item.unread_count || 0),
      latest_created_at: String(item.latest_created_at || ''),
      source_notification_ids: sourceIds,
      interaction_target: normalizeDoctorInteraction(item.interaction_target),
    }
  }

  function buildLocalOverview(items: NotificationVM[]): NotificationOverviewItem[] {
    const groups = new Map<string, NotificationOverviewItem>()
    for (const notif of items) {
      if (isBatchSummaryType(notif.type)) continue
      const type = notif.type || 'general'
      const severity = notif.level || 'info'
      const department = '未分科室'
      const recordId = notif.record_id || ''
      const key = `${type}|${severity}|${department}|${recordId}`
      const existing = groups.get(key)
      if (existing) {
        existing.occurrence_count += 1
        existing.unread_count += notif.is_read ? 0 : 1
        existing.source_notification_ids.push(notif.id)
        if (notif.created_at > existing.latest_created_at) {
          existing.latest_created_at = notif.created_at
          existing.summary = notif.content || existing.summary
        }
        continue
      }
      groups.set(key, {
        overview_id: key,
        type,
        severity,
        department,
        record_id: recordId,
        title: notif.title || '病案问题集中点',
        summary: notif.content || '暂无描述',
        occurrence_count: 1,
        unread_count: notif.is_read ? 0 : 1,
        latest_created_at: notif.created_at,
        source_notification_ids: notif.id ? [notif.id] : [],
        interaction_target: notif.interaction_target,
      })
    }
    return Array.from(groups.values()).sort(
      (a, b) =>
        b.unread_count - a.unread_count ||
        b.occurrence_count - a.occurrence_count ||
        (b.latest_created_at || '').localeCompare(a.latest_created_at || ''),
    )
  }

  async function fetchAssistNotificationOverview() {
    const token = generation
    const requestSeq = ++overviewRequestSeq
    if (!ApiService.isAuthenticated()) {
      notificationOverviewItems.value = []
      overviewLoading.value = false
      return
    }

    overviewLoading.value = true
    try {
      // 缺省日期由服务端按东八区（Asia/Shanghai）确定，避免客户端本地时区跨日偏移
      const res = await ApiService.get<NotificationOverviewResponse>(
        '/api/v1/notifications/overview',
      )
      if (token !== generation || requestSeq !== overviewRequestSeq) return
      if (!res.success) {
        notificationOverviewItems.value = buildLocalOverview(assistNotifications.value)
        return
      }
      const payload = extractOverviewPayload(res.data)
      const items = Array.isArray(payload?.items) ? payload.items : []
      notificationOverviewItems.value = items
        .map((item, index) => normalizeOverviewItem(item, index))
        .filter((item) => !isBatchSummaryType(item.type))
    } catch (err) {
      if (token !== generation || requestSeq !== overviewRequestSeq) return
      if (!isAuthError(err)) {
        console.error('加载当天问题概览失败:', err)
      }
      notificationOverviewItems.value = buildLocalOverview(assistNotifications.value)
    } finally {
      if (token === generation && requestSeq === overviewRequestSeq) overviewLoading.value = false
    }
  }

  async function fetchAssistNotifications() {
    const token = generation
    if (!ApiService.isAuthenticated()) {
      assistNotifications.value = []
      notificationUnreadCount.value = 0
      return
    }

    notificationLoading.value = true
    try {
      const res = await ApiService.get<NotificationListResponse>('/api/v1/notifications', {
        page_size: 30,
      })
      if (token !== generation) return
      if (!res.success) {
        message.error('消息读取失败，当前未读状态不可用，请刷新核对')
        return
      }

      const payload = extractListPayload(res.data)
      const items = Array.isArray(payload?.items) ? payload.items : []
      assistNotifications.value = items
        .map((item, index) => normalizeNotification(item, index))
        .filter((item) => !isBatchSummaryType(item.type))
      notificationUnreadCount.value =
        typeof payload?.unread_count === 'number'
          ? payload.unread_count
          : assistNotifications.value.filter((item) => !item.is_read).length
      await fetchAssistNotificationOverview()
    } catch (err) {
      if (token !== generation) return
      if (!isAuthError(err)) {
        console.error('加载消息概览失败:', err)
      }
      message.error('消息读取失败，保留上次已核实记录，请刷新核对')
    } finally {
      if (token === generation) notificationLoading.value = false
    }
  }

  async function markAssistNotificationRead(notif: NotificationVM) {
    const token = generation
    if (!notif.id || !ApiService.isAuthenticated()) return false
    if (notif.is_read) return true

    try {
      const res = await ApiService.put(`/api/v1/notifications/${notif.id}/read`)
      if (token !== generation) return false
      if (!res.success) {
        message.error('标记已读失败，请刷新核对')
        return false
      }
      notif.is_read = true
      notificationUnreadCount.value = Math.max(0, notificationUnreadCount.value - 1)
      return true
    } catch (err) {
      if (token !== generation) return false
      if (!isAuthError(err)) {
        console.error('标记消息已读失败:', err)
        message.error('标记已读失败')
      }
      return false
    }
  }

  async function markAllAssistNotificationsRead() {
    if (markingAllRead || !ApiService.isAuthenticated()) return
    const token = generation
    markingAllRead = true

    try {
      const res = await ApiService.put('/api/v1/notifications/read-all')
      if (token !== generation) return
      if (!res.success) return
      await fetchAssistNotifications()
      if (token !== generation) return
      message.success('已全部标记为已读')
    } catch (err) {
      if (token !== generation) return
      if (!isAuthError(err)) {
        console.error('全部已读失败:', err)
        message.error('全部已读失败')
      }
    } finally {
      if (token === generation) markingAllRead = false
    }
  }

  async function handleAssistNotificationClick(notif: NotificationVM) {
    const token = generation
    if (!(await markAssistNotificationRead(notif))) return
    if (token !== generation) return
    if (notif.interaction_target) {
      if (!openInteraction) {
        message.warning('当前入口不能打开该处理对象')
        return
      }
      await openInteraction(notif.interaction_target)
      return
    }
    if (notif.record_id?.startsWith('feedback:')) {
      message.error('消息处理对象未核实，请刷新核对')
      return
    }
    const targetRecordId = notif.record_id
    if (!targetRecordId) {
      assistTab.value = 'form'
      frontpageTab.value = 'fields'
      message.info('该消息未绑定病历，已切换到质控页')
      return
    }

    const record = findRecordById(allRecords.value, targetRecordId)
    if (!record) {
      message.warning(RECORD_RESELECTION_MESSAGE)
      return
    }

    openRecord(record)
    assistPanelVisible.value = true
    assistTab.value = 'form'
    frontpageTab.value = 'fields'
  }

  async function handleAssistOverviewClick(item: NotificationOverviewItem) {
    if (handlingOverviewClick) return
    const token = generation
    handlingOverviewClick = true
    try {
      if (item.interaction_target) {
        try {
          for (const id of item.source_notification_ids) {
            const response = await ApiService.put(
              `/api/v1/notifications/${encodeURIComponent(id)}/read`,
            )
            if (token !== generation) return
            if (!response.success) {
              message.error('消息状态未核实，请刷新核对')
              return
            }
          }
        } catch {
          if (token === generation) message.error('消息状态未核实，请刷新核对')
          return
        }
        if (!openInteraction) {
          message.warning('当前入口不能打开该处理对象')
          return
        }
        await openInteraction(item.interaction_target)
        return
      }
      if (item.source_notification_ids.length > 0) {
        for (const notifId of item.source_notification_ids) {
          if (token !== generation) return
          const target = assistNotifications.value.find((notif) => notif.id === notifId)
          if (!target) continue
          if (!target.is_read) {
            await markAssistNotificationRead(target)
          }
        }
      }
      if (token !== generation) return

      if (item.record_id) {
        const pseudoNotification: NotificationVM = {
          id: item.source_notification_ids[0] || item.overview_id,
          record_id: item.record_id,
          title: item.title,
          content: item.summary,
          message: item.summary,
          created_at: item.latest_created_at,
          is_read: item.unread_count <= 0,
          level: item.severity,
          type: item.type,
        }
        await handleAssistNotificationClick(pseudoNotification)
      } else {
        assistPanelVisible.value = true
        assistTab.value = 'form'
        frontpageTab.value = 'fields'
        message.info('该问题集中点未绑定具体病历，已进入质控页')
      }
      if (token !== generation) return

      await fetchAssistNotificationOverview()
    } finally {
      if (token === generation) handlingOverviewClick = false
    }
  }

  function formatRelativeTime(iso?: string | null, _type?: string) {
    void _type
    if (!iso) return ''
    const date = parseQcTaskTime(iso)
    if (!date || Number.isNaN(date.getTime())) return ''
    const now = new Date()
    const diff = Math.floor((now.getTime() - date.getTime()) / 1000)
    if (diff < 60) return '刚刚'
    if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
    if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
    return `${Math.floor(diff / 86400)} 天前`
  }

  watch(
    () => [auth.user?.id, auth.userRoles],
    () => {
      ++generation
      ++overviewRequestSeq
      markingAllRead = false
      handlingOverviewClick = false
      assistNotifications.value = []
      notificationOverviewItems.value = []
      notificationUnreadCount.value = 0
      notificationLoading.value = false
      overviewLoading.value = false
    },
    { deep: true },
  )

  return {
    assistNotifications,
    notificationUnreadCount,
    notificationLoading,
    notificationReadFilter,
    overviewLoading,
    overviewViewMode,
    overviewTypeFilter,
    overviewSeverityFilter,
    overviewDepartmentFilter,
    notificationOverviewItems,
    filteredNotificationOverviewItems,
    overviewDepartments,
    overviewTypes,
    overviewSeverities,
    filteredAssistNotifications,
    fetchAssistNotifications,
    fetchAssistNotificationOverview,
    markAssistNotificationRead,
    markAllAssistNotificationsRead,
    handleAssistNotificationClick,
    handleAssistOverviewClick,
    formatRelativeTime,
  }
}
