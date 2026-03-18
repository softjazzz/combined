import { ref, computed, type Ref } from 'vue'
import { message } from 'ant-design-vue'
import { ApiService } from '@/services/apiService'
import type { PatientRecord } from '../types'

export function useNotifications(
  allRecords: Ref<PatientRecord[]>,
  openSessionRecord: (id: string) => void,
  assistPanelVisible: Ref<boolean>,
  assistTab: Ref<string>,
  frontpageTab: Ref<string>,
) {
  const assistNotifications = ref<any[]>([])
  const notificationUnreadCount = ref(0)
  const notificationLoading = ref(false)
  const notificationReadFilter = ref<'all' | 'unread' | 'read'>('unread')

  const filteredAssistNotifications = computed(() => {
    if (notificationReadFilter.value === 'all') return assistNotifications.value
    const expectRead = notificationReadFilter.value === 'read'
    return assistNotifications.value.filter(item => !!item.is_read === expectRead)
  })

  function isAuthError(err: any) {
    const status = err?.response?.status
    return status === 401 || status === 403
  }

  async function fetchAssistNotifications() {
    if (!ApiService.isAuthenticated()) {
      assistNotifications.value = []
      notificationUnreadCount.value = 0
      return
    }

    notificationLoading.value = true
    try {
      const res = await ApiService.get('/api/v1/notifications', {
        page_size: 30,
      })
      if (!res.success) {
        assistNotifications.value = []
        notificationUnreadCount.value = 0
        return
      }
      const data = res.data?.data || {}
      assistNotifications.value = Array.isArray(data.items) ? data.items : []
      notificationUnreadCount.value = Number(data.unread_count || 0)
    } catch (err) {
      if (!isAuthError(err)) {
        console.error('加载消息概览失败:', err)
      }
      assistNotifications.value = []
      notificationUnreadCount.value = 0
    } finally {
      notificationLoading.value = false
    }
  }

  async function markAssistNotificationRead(notif: any) {
    if (!notif?.id || notif.is_read) return
    if (!ApiService.isAuthenticated()) return

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

  async function handleAssistNotificationClick(notif: any) {
    await markAssistNotificationRead(notif)
    const targetRecordId = notif?.record_id
    if (!targetRecordId) {
      assistTab.value = 'form'
      frontpageTab.value = 'fields'
      message.info('该消息未绑定病历，已切换到质控页')
      return
    }

    const record = allRecords.value.find(item => item.id === targetRecordId)
    if (!record) {
      message.warning(`未找到病历：${targetRecordId}`)
      return
    }

    openSessionRecord(record.id)
    assistPanelVisible.value = true
    assistTab.value = 'form'
    frontpageTab.value = 'fields'
  }

  function formatRelativeTime(iso: string) {
    if (!iso) return ''
    const d = new Date(iso)
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
    filteredAssistNotifications,
    fetchAssistNotifications,
    markAssistNotificationRead,
    markAllAssistNotificationsRead,
    handleAssistNotificationClick,
    formatRelativeTime,
  }
}
