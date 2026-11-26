import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import * as vueRouter from 'vue-router'
import { ApiService } from '@/services/apiService'
import { useAuthStore } from '@/stores/auth'
import { normalizeNotification } from '@/views/workstation-v4/normalize'
import type { NotificationVM } from '@/views/workstation-v4/types'
import { parseQcTaskTime, QC_TASK_TIME_ZONE } from '@/views/workstation-v4/utils/qcTaskTime'
import { notificationLocation } from './notificationNavigation'

interface MessagePage {
  items: unknown[]
  total: number
  unread_count: number
}

export const MESSAGE_CENTER_UNREAD_EVENT = 'medqc:notifications-unread-updated'

const sharedMessageCenterUnreadCount = ref<number | null>(null)
let sharedMessageCenterUnreadVersion = 0

function normalizeUnreadCount(value: unknown): number | null {
  if (value === null || value === undefined) return null
  const num = Number(value)
  return Number.isInteger(num) && num >= 0 ? num : null
}

export function useSharedMessageCenterUnreadCount() {
  return sharedMessageCenterUnreadCount
}

export function getSharedMessageCenterUnreadVersion() {
  return sharedMessageCenterUnreadVersion
}

export function syncSharedMessageCenterUnreadCount(
  count: number | null,
  options: { emitEvent?: boolean } = {},
) {
  const normalized = normalizeUnreadCount(count)
  sharedMessageCenterUnreadVersion += 1
  sharedMessageCenterUnreadCount.value = normalized
  if (
    options.emitEvent !== false &&
    typeof window !== 'undefined' &&
    typeof window.dispatchEvent === 'function' &&
    typeof CustomEvent === 'function'
  ) {
    window.dispatchEvent(
      new CustomEvent(MESSAGE_CENTER_UNREAD_EVENT, {
        detail: { unreadCount: normalized },
      }),
    )
  }
}

export const MESSAGE_TYPE_LABELS: Record<string, string> = {
  qc_result_ready: '质控结果',
  remediation: '整改反馈',
  defect_urge: '整改催办',
  appeal_result: '申诉反馈',
  case_communication: '病历沟通',
  account_registration: '账号注册审核',
  task_assign: '任务派发',
  drg_alert: 'DRG 提醒',
  system: '系统通知',
  general: '其他消息',
}

export function isAccountRegistrationNotification(
  item: Pick<NotificationVM, 'type' | 'interaction_target'>,
) {
  return (
    item.type === 'account_registration' ||
    item.type === 'account_registration_result' ||
    item.interaction_target?.kind === 'account_registration' ||
    item.interaction_target?.kind === 'account_registration_result'
  )
}

export function messageTypeLabel(item: NotificationVM) {
  if (isAccountRegistrationNotification(item)) return MESSAGE_TYPE_LABELS.account_registration
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

export function messageTime(value: string, _type?: string) {
  void _type
  const date = parseQcTaskTime(value)
  return !date || Number.isNaN(date.getTime())
    ? '时间未知'
    : new Intl.DateTimeFormat('zh-CN', {
        timeZone: QC_TASK_TIME_ZONE,
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      }).format(date)
}

type MessageStatusFilter = 'unread' | 'all' | 'read'
const VALID_MESSAGE_STATUSES = new Set<MessageStatusFilter>(['unread', 'all', 'read'])

function readSingleQuery(query: Record<string, unknown> | undefined, key: string): string {
  const raw = query?.[key]
  const value = Array.isArray(raw) ? raw[0] : raw
  return typeof value === 'string' ? value.trim() : ''
}

function parseStatusQuery(query: Record<string, unknown> | undefined): MessageStatusFilter {
  const value = readSingleQuery(query, 'status')
  return VALID_MESSAGE_STATUSES.has(value as MessageStatusFilter)
    ? (value as MessageStatusFilter)
    : 'unread'
}

function parseTypeQuery(query: Record<string, unknown> | undefined): string {
  return readSingleQuery(query, 'type')
}

function parsePageQuery(query: Record<string, unknown> | undefined): number {
  const raw = readSingleQuery(query, 'page')
  const parsed = Number(raw)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 1
}

function safeUseRoute() {
  try {
    return typeof vueRouter.useRoute === 'function' ? vueRouter.useRoute() : undefined
  } catch {
    return undefined
  }
}

export function useMessageCenter() {
  const router = vueRouter.useRouter()
  const route = safeUseRoute()
  const auth = useAuthStore()
  const items = ref<NotificationVM[]>([])
  const total = ref(0)
  const unread = ref<number | null>(null)
  const page = ref(parsePageQuery(route?.query as Record<string, unknown> | undefined))
  const pageSize = 20
  const status = ref<MessageStatusFilter>(
    parseStatusQuery(route?.query as Record<string, unknown> | undefined),
  )
  const type = ref(parseTypeQuery(route?.query as Record<string, unknown> | undefined))
  const loading = ref(false)
  const error = ref('')
  const busy = ref('')
  const selectedId = ref('')
  const mobileReading = ref(false)
  let sequence = 0
  let identity = 0
  let pendingRouteSyncKey: string | null = null
  let suppressFilterWatchKey: string | null = null
  let authInitialized = false
  let disposed = false
  const selected = computed(() => items.value.find((item) => item.id === selectedId.value))
  const hasActiveFilter = computed(() => {
    const normalizedType = type.value.trim()
    return Boolean(normalizedType && normalizedType !== 'all')
  })

  function queryStateKey(
    nextStatus: MessageStatusFilter,
    nextType: string,
    nextPage: number,
  ): string {
    return `${nextStatus}|${nextType}|${nextPage}`
  }

  function syncQueryToUrl() {
    if (disposed || !route || typeof router?.replace !== 'function') return
    const currentQuery = (route.query || {}) as Record<string, unknown>
    const nextStatus = status.value === 'unread' ? undefined : status.value
    const nextType = type.value || undefined
    const nextPage = page.value > 1 ? String(page.value) : undefined
    const curStatus = readSingleQuery(currentQuery, 'status') || undefined
    const curType = readSingleQuery(currentQuery, 'type') || undefined
    const curPage = readSingleQuery(currentQuery, 'page') || undefined
    if (curStatus === nextStatus && curType === nextType && curPage === nextPage) {
      pendingRouteSyncKey = null
      return
    }
    const desiredKey = queryStateKey(status.value, type.value, page.value)
    if (pendingRouteSyncKey === desiredKey) return
    pendingRouteSyncKey = desiredKey
    const nextQuery = { ...route.query }
    if (nextStatus) nextQuery.status = nextStatus
    else delete nextQuery.status
    if (nextType) nextQuery.type = nextType
    else delete nextQuery.type
    if (nextPage) nextQuery.page = nextPage
    else delete nextQuery.page
    void Promise.resolve(router.replace({ path: route.path, query: nextQuery }))
      .catch(() => {})
      .finally(() => {
        if (pendingRouteSyncKey === desiredKey) pendingRouteSyncKey = null
      })
  }

  async function load() {
    syncQueryToUrl()
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
      syncSharedMessageCenterUnreadCount(data.unread_count)
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

  function setStatus(nextStatus: MessageStatusFilter) {
    if (busy.value || status.value === nextStatus) return
    status.value = nextStatus
  }

  function resetFilters() {
    if (busy.value || !hasActiveFilter.value) return
    type.value = ''
  }

  function select(item: NotificationVM) {
    selectedId.value = item.id
    mobileReading.value = true
  }

  async function markRead(item: NotificationVM, options: { awaitReload?: boolean } = {}) {
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
      if (options.awaitReload === false) {
        void load().catch(() => {})
      } else {
        await load().catch(() => {})
      }
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
    if (!item.interaction_target || !(await markRead(item, { awaitReload: false }))) return
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
    const filterKey = `${status.value}|${type.value}`
    if (suppressFilterWatchKey === filterKey) {
      suppressFilterWatchKey = null
      return
    }
    suppressFilterWatchKey = null
    page.value = 1
    items.value = []
    total.value = 0
    selectedId.value = ''
    mobileReading.value = false
    void load()
  })
  watch(
    () => [route?.query?.status, route?.query?.type, route?.query?.page],
    () => {
      if (!route) return
      const query = route.query as Record<string, unknown>
      const nextStatus = parseStatusQuery(query)
      const nextType = parseTypeQuery(query)
      const nextPage = parsePageQuery(query)
      const incomingKey = queryStateKey(nextStatus, nextType, nextPage)
      if (pendingRouteSyncKey) {
        if (incomingKey === pendingRouteSyncKey) {
          pendingRouteSyncKey = null
        }
        return
      }
      if (nextStatus === status.value && nextType === type.value && nextPage === page.value) return
      if (nextStatus !== status.value || nextType !== type.value) {
        suppressFilterWatchKey = `${nextStatus}|${nextType}`
      }
      status.value = nextStatus
      type.value = nextType
      page.value = nextPage
      selectedId.value = ''
      mobileReading.value = false
      void load()
    },
  )
  const authSignature = computed(() => {
    const userId = String(auth.user?.id || '')
    const roles = Array.isArray(auth.userRoles)
      ? [...auth.userRoles].map((role) => String(role)).sort().join(',')
      : ''
    return `${userId}::${roles}`
  })
  watch(
    authSignature,
    () => {
      ++identity
      ++sequence
      items.value = []
      total.value = 0
      unread.value = null
      selectedId.value = ''
      mobileReading.value = false
      busy.value = ''
      if (!authInitialized) {
        authInitialized = true
      } else {
        page.value = 1
      }
      if (ApiService.isAuthenticated()) void load()
      else loading.value = false
    },
    { immediate: true },
  )
  onBeforeUnmount(() => {
    disposed = true
    pendingRouteSyncKey = null
    suppressFilterWatchKey = null
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
    hasActiveFilter,
    loading,
    error,
    busy,
    selected,
    mobileReading,
    load,
    setStatus,
    resetFilters,
    select,
    markRead,
    markAllRead,
    open,
  }
}
