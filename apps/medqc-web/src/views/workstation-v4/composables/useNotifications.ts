import { computed, ref, type Ref } from 'vue'
import { message } from 'ant-design-vue'
import { ApiService } from '@/services/apiService'
import { normalizeNotification } from '../normalize'
import type { NotificationOverviewItem, NotificationVM, PatientRecord } from '../types'

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
  openSessionRecord: (id: string) => void,
  assistPanelVisible: Ref<boolean>,
  assistTab: Ref<string>,
  frontpageTab: Ref<string>,
) {
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
    if (!ApiService.isAuthenticated()) {
      notificationOverviewItems.value = []
      return
    }

    overviewLoading.value = true
    try {
      const now = new Date()
      const dateKey = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
      const res = await ApiService.get<NotificationOverviewResponse>(
        '/api/v1/notifications/overview',
        {
          date: dateKey,
        },
      )
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
      if (!isAuthError(err)) {
        console.error('加载当天问题概览失败:', err)
      }
      notificationOverviewItems.value = buildLocalOverview(assistNotifications.value)
    } finally {
      overviewLoading.value = false
    }
  }

  async function fetchAssistNotifications() {
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
      if (!res.success) {
        assistNotifications.value = []
        notificationUnreadCount.value = 0
        return
      }

      const payload = extractListPayload(res.data)
      const items = Array.isArray(payload?.items) ? payload.items : []
      assistNotifications.value = items
        .map((item, index) => normalizeNotification(item, index))
        .filter((item) => !isBatchSummaryType(item.type))
      notificationUnreadCount.value = assistNotifications.value.filter(
        (item) => !item.is_read,
      ).length
      await fetchAssistNotificationOverview()
    } catch (err) {
      if (!isAuthError(err)) {
        console.error('加载消息概览失败:', err)
      }
      assistNotifications.value = []
      notificationUnreadCount.value = 0
      notificationOverviewItems.value = []
    } finally {
      notificationLoading.value = false
    }
  }

  async function markAssistNotificationRead(notif: NotificationVM) {
    if (!notif.id || notif.is_read || !ApiService.isAuthenticated()) return

    try {
      const res = await ApiService.put(`/api/v1/notifications/${notif.id}/read`)
      if (!res.success) return
      notif.is_read = true
      notificationUnreadCount.value = Math.max(0, notificationUnreadCount.value - 1)
    } catch (err) {
      if (!isAuthError(err)) {
        console.error('标记消息已读失败:', err)
        message.error('标记已读失败')
      }
    }
  }

  async function markAllAssistNotificationsRead() {
    if (!ApiService.isAuthenticated()) return

    try {
      const res = await ApiService.put('/api/v1/notifications/read-all')
      if (!res.success) return
      await fetchAssistNotifications()
      message.success('已全部标记为已读')
    } catch (err) {
      if (!isAuthError(err)) {
        console.error('全部已读失败:', err)
        message.error('全部已读失败')
      }
    }
  }

  async function handleAssistNotificationClick(notif: NotificationVM) {
    await markAssistNotificationRead(notif)
    const targetRecordId = notif.record_id
    if (!targetRecordId) {
      assistTab.value = 'form'
      frontpageTab.value = 'fields'
      message.info('该消息未绑定病历，已切换到质控页')
      return
    }

    const record = allRecords.value.find(
      (item) => item.id === targetRecordId || item.visitId === targetRecordId,
    )
    if (!record) {
      message.warning(`未找到病历：${targetRecordId}`)
      return
    }

    openSessionRecord(record.id)
    assistPanelVisible.value = true
    assistTab.value = 'form'
    frontpageTab.value = 'fields'
  }

  async function handleAssistOverviewClick(item: NotificationOverviewItem) {
    if (item.source_notification_ids.length > 0) {
      for (const notifId of item.source_notification_ids) {
        const target = assistNotifications.value.find((notif) => notif.id === notifId)
        if (!target) continue
        if (!target.is_read) {
          await markAssistNotificationRead(target)
        }
      }
    }

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

    await fetchAssistNotificationOverview()
  }

  function formatRelativeTime(iso: string) {
    if (!iso) return ''
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return ''
    const now = new Date()
    const diff = Math.floor((now.getTime() - d.getTime()) / 1000)
    if (diff < 60) return '刚刚'
    if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
    if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
    return `${Math.floor(diff / 86400)} 天前`
  }

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
