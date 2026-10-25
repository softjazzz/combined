import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { useRouter } from 'vue-router'
import { ApiService } from '@/services/apiService'
import { useAuthStore } from '@/stores/auth'
import { normalizeNotification } from '@/views/workstation-v4/normalize'
import type { NotificationVM } from '@/views/workstation-v4/types'
import { notificationLocation } from './notificationNavigation'

interface MessagePage {
  items: unknown[]
  total: number
  unread_count: number
}

export const MESSAGE_TYPE_LABELS: Record<string, string> = {
  qc_result_ready: '质控结果',
  remediation: '整改反馈',
  defect_urge: '整改催办',
  appeal_result: '申诉反馈',
  task_assign: '任务派发',
  drg_alert: 'DRG 提醒',
  system: '系统通知',
  general: '其他消息',
}

export function messageTypeLabel(item: NotificationVM) {
  if (item.type?.endsWith('_batch_summary')) return '批量摘要'
  return MESSAGE_TYPE_LABELS[item.type || ''] || '其他消息'
}

export function messageActionLabel(item: NotificationVM) {
  switch (item.interaction_target?.kind) {
    case 'qc_result_ready':
      return '查看质控结果'
    case 'rectification':
      return '查看整改'
    case 'modern_appeal':
      return '查看申诉'
    case 'account_registration':
      return '查看账号申请'
    case 'account_registration_result':
      return '查看开通结果'
    case 'case_communication':
      return '查看病历沟通'
    default:
      return ''
  }
}

export function messageTime(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? '时间未知'
    : new Intl.DateTimeFormat('zh-CN', {
        timeZone: 'Asia/Shanghai',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      }).format(date)
}

export function useMessageCenter() {
  const router = useRouter()
  const auth = useAuthStore()
  const items = ref<NotificationVM[]>([])
  const total = ref(0)
  const unread = ref<number | null>(null)
  const page = ref(1)
  const pageSize = 20
  const status = ref<'unread' | 'all' | 'read'>('unread')
  const type = ref('')
  const loading = ref(false)
  const error = ref('')
  const busy = ref('')
  const selectedId = ref('')
  const mobileReading = ref(false)
  let sequence = 0
  let identity = 0
  const selected = computed(() => items.value.find((item) => item.id === selectedId.value))

  async function load() {
    const token = ++sequence
    loading.value = true
    error.value = ''
    try {
      const result = await ApiService.get<MessagePage>('/api/v1/notifications', {
        page: page.value,
        page_size: pageSize,
        type: type.value || undefined,
        is_read: status.value === 'all' ? undefined : status.value === 'read',
      })
      if (token !== sequence) return
      const data = result.data
      if (
        !result.success ||
        !data ||
        !Array.isArray(data.items) ||
        !Number.isInteger(data.total) ||
        data.total < 0 ||
        !Number.isInteger(data.unread_count) ||
        data.unread_count < 0
      ) {
        throw new Error(result.message || '消息读取失败，请重试')
      }
      const rows = data.items.map((item, index) => {
        const raw = item as Record<string, unknown> | null
        if (!raw || typeof raw.id !== 'string' || !raw.id || raw.id.length > 36)
          throw new Error('消息身份不完整，请刷新核对')
        return normalizeNotification(raw, index)
      })
      if (!rows.length && page.value > 1) {
        const lastPage = Math.max(1, Math.ceil(data.total / pageSize))
        if (lastPage < page.value) {
          page.value = lastPage
          await load()
          return
        }
        throw new Error('消息分页信息不一致，请刷新核对')
      }
      items.value = rows
      total.value = data.total
      unread.value = data.unread_count
      if (!rows.some((row) => row.id === selectedId.value)) {
        selectedId.value = rows[0]?.id || ''
        mobileReading.value = false
      }
    } catch (cause) {
      if (token === sequence)
        error.value = cause instanceof Error ? cause.message : '消息读取失败，请重试'
    } finally {
      if (token === sequence) loading.value = false
    }
  }

  function select(item: NotificationVM) {
    selectedId.value = item.id
    mobileReading.value = true
  }

  async function markRead(item: NotificationVM) {
    if (busy.value || loading.value || error.value) return false
    if (item.is_read) return true
    const owner = identity
    busy.value = item.id
    try {
      const result = await ApiService.put(
        `/api/v1/notifications/${encodeURIComponent(item.id)}/read`,
      )
      if (owner !== identity) return false
      if (!result.success) throw new Error('已读回执保存失败，请重试')
      await load()
      return owner === identity
    } catch (cause) {
      if (owner === identity)
        message.error(cause instanceof Error ? cause.message : '已读回执保存失败，请重试')
      return false
    } finally {
      if (owner === identity) busy.value = ''
    }
  }

  async function open(item: NotificationVM) {
    if (!item.interaction_target || !(await markRead(item))) return
    await router.push(notificationLocation(item.interaction_target))
  }

  async function markAllRead() {
    if (busy.value || loading.value || error.value || !unread.value) return
    const owner = identity
    busy.value = '*'
    try {
      const result = await ApiService.put('/api/v1/notifications/read-all')
      if (owner !== identity) return
      if (!result.success) throw new Error('全部已读回执保存失败，请重试')
      await load()
    } catch (cause) {
      if (owner === identity)
        message.error(cause instanceof Error ? cause.message : '全部已读回执保存失败，请重试')
    } finally {
      if (owner === identity) busy.value = ''
    }
  }

  watch([status, type], () => {
    page.value = 1
    items.value = []
    total.value = 0
    selectedId.value = ''
    mobileReading.value = false
    void load()
  })
  watch(
    () => [auth.user?.id, auth.userRoles],
    () => {
      ++identity
      ++sequence
      items.value = []
      total.value = 0
      unread.value = null
      selectedId.value = ''
      mobileReading.value = false
      busy.value = ''
      page.value = 1
      if (ApiService.isAuthenticated()) void load()
      else loading.value = false
    },
    { deep: true, immediate: true },
  )
  onBeforeUnmount(() => {
    ++sequence
    ++identity
  })

  return {
    items,
    total,
    unread,
    page,
    pageSize,
    status,
    type,
    loading,
    error,
    busy,
    selected,
    mobileReading,
    load,
    select,
    markRead,
    markAllRead,
    open,
  }
}
