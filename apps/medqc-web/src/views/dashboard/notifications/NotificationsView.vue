<template>
  <div class="notifications-page p-6 bg-gray-50 min-h-screen">
    <!-- 页面标题 -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-800">
          通知与整改
        </h1>
        <p class="text-gray-500 text-sm mt-1">
          质控消息推送、整改跟踪与问题闭环
        </p>
      </div>
      <a-button
        :disabled="unreadCount === 0"
        @click="markAllRead"
      >
        <CheckOutlined /> 全部已读 ({{ unreadCount }})
      </a-button>
    </div>

    <!-- 标签页 -->
    <a-tabs
      v-model:active-key="activeTab"
      @change="handleTabChange"
    >
      <!-- Tab 1: 消息通知 -->
      <a-tab-pane key="notifications">
        <template #tab>
          <a-badge
            :count="unreadCount"
            :offset="[10, -2]"
          >
            <span><BellOutlined /> 消息通知</span>
          </a-badge>
        </template>

        <!-- 筛选 -->
        <div class="flex gap-3 mb-4">
          <a-select
            v-model:value="notifType"
            placeholder="消息类型"
            style="width: 160px"
            allow-clear
            @change="fetchNotifications"
          >
            <a-select-option value="qc_result">
              质控结果
            </a-select-option>
            <a-select-option value="urge">
              催办提醒
            </a-select-option>
            <a-select-option value="rectification">
              整改通知
            </a-select-option>
            <a-select-option value="appeal">
              临床申诉
            </a-select-option>
            <a-select-option value="system">
              系统通知
            </a-select-option>
          </a-select>
          <a-select
            v-model:value="readFilter"
            placeholder="阅读状态"
            style="width: 120px"
            allow-clear
            @change="fetchNotifications"
          >
            <a-select-option value="false">
              未读
            </a-select-option>
            <a-select-option value="true">
              已读
            </a-select-option>
          </a-select>
        </div>

        <!-- 消息列表 -->
        <div class="space-y-3">
          <div
            v-for="notif in notifications"
            :key="notif.id"
            :class="[
              'bg-white rounded-xl border p-4 cursor-pointer transition-all',
              notif.is_read
                ? 'border-gray-100 opacity-70'
                : 'border-blue-100 shadow-sm hover:shadow-md',
            ]"
            @click="handleNotifClick(notif)"
          >
            <div class="flex items-start gap-3">
              <span
                :class="[
                  'w-8 h-8 rounded-lg flex items-center justify-center text-white flex-shrink-0 mt-0.5',
                  notifIconBg(notif.type),
                ]"
              >
                <component :is="notifIcon(notif.type)" />
              </span>
              <div class="flex-1 min-w-0">
                <div class="flex items-center justify-between">
                  <span class="font-medium text-gray-800">{{ notif.title }}</span>
                  <div class="flex items-center gap-2">
                    <a-tag
                      v-if="!notif.is_read"
                      color="blue"
                      size="small"
                    >
                      未读
                    </a-tag>
                    <span class="text-xs text-gray-400">{{ formatTime(notif.created_at) }}</span>
                  </div>
                </div>
                <p class="text-sm text-gray-500 mt-1">
                  {{ notif.content }}
                </p>
              </div>
            </div>
          </div>

          <div
            v-if="!notifications.length"
            class="text-center py-12 text-gray-400"
          >
            <BellOutlined class="text-4xl mb-3" />
            <p>暂无通知消息</p>
          </div>
        </div>
      </a-tab-pane>

      <!-- Tab 2: 整改跟踪 -->
      <a-tab-pane key="rectifications">
        <template #tab>
          <a-badge
            :count="rectStats.pending + rectStats.overdue"
            :offset="[10, -2]"
          >
            <span><ToolOutlined /> 整改跟踪</span>
          </a-badge>
        </template>

        <!-- 统计卡片 -->
        <div class="grid grid-cols-4 gap-4 mb-5">
          <div
            v-for="st in rectStatusList"
            :key="st.key"
            :class="[
              'bg-white rounded-xl border p-4 cursor-pointer transition-all text-center',
              rectStatusFilter === st.key
                ? 'border-blue-500 shadow-md'
                : 'border-gray-100 hover:border-blue-200',
            ]"
            @click="rectStatusFilter = rectStatusFilter === st.key ? '' : st.key"
          >
            <div
              class="text-2xl font-bold"
              :class="st.color"
            >
              {{ rectStats[st.key] || 0 }}
            </div>
            <div class="text-xs text-gray-500 mt-1">
              {{ st.label }}
            </div>
          </div>
        </div>

        <!-- 整改列表 -->
        <div class="space-y-3">
          <div
            v-for="rect in filteredRectifications"
            :key="rect.id"
            class="bg-white rounded-xl border border-gray-100 p-4 hover:shadow-sm transition-all"
          >
            <div class="flex items-center justify-between mb-2">
              <div class="flex items-center gap-2">
                <span class="font-medium text-gray-800">{{ rect.patient_name }}</span>
                <a-tag size="small">
                  {{ rect.department }}
                </a-tag>
                <span class="text-xs text-gray-400">{{ rect.record_id }}</span>
              </div>
              <a-tag
                :color="rectStatusColor(rect.status)"
                size="small"
              >
                {{ rectStatusLabel(rect.status) }}
              </a-tag>
            </div>
            <p class="text-sm text-gray-600 mb-3">
              {{ rect.defect_description }}
            </p>
            <div class="flex items-center justify-between">
              <div class="text-xs text-gray-400">
                责任人: {{ rect.assigned_to }} · 截止: {{ formatDate(rect.deadline) }}
              </div>
              <div class="flex gap-2">
                <template v-if="rect.status === 'submitted'">
                  <a-button
                    type="primary"
                    size="small"
                    @click="approveRect(rect.id)"
                  >
                    审核通过
                  </a-button>
                  <a-button
                    size="small"
                    danger
                    @click="rejectRect(rect.id)"
                  >
                    退回
                  </a-button>
                </template>
                <template v-if="rect.status === 'pending' || rect.status === 'overdue'">
                  <a-button
                    type="primary"
                    size="small"
                    ghost
                    @click="submitRect(rect.id)"
                  >
                    提交整改
                  </a-button>
                </template>
                <template v-if="rect.status === 'approved'">
                  <a-tag color="success">
                    <CheckCircleOutlined /> 已闭环
                  </a-tag>
                </template>
              </div>
            </div>
          </div>

          <div
            v-if="!filteredRectifications.length"
            class="text-center py-12 text-gray-400"
          >
            <ToolOutlined class="text-4xl mb-3" />
            <p>暂无整改任务</p>
          </div>
        </div>
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  BellOutlined,
  CheckOutlined,
  ToolOutlined,
  AlertOutlined,
  SendOutlined,
  FileTextOutlined,
  ExclamationCircleOutlined,
  SettingOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons-vue'
import { ApiService } from '@/services/apiService'

// ============= 状态 =============
const activeTab = ref('notifications')
const notifications = ref<any[]>([])
const unreadCount = ref(0)
const notifType = ref<string | undefined>(undefined)
const readFilter = ref<'false' | 'true' | undefined>(undefined)

const rectifications = ref<any[]>([])
const rectStats = ref<Record<string, number>>({
  pending: 0,
  overdue: 0,
  submitted: 0,
  approved: 0,
  total: 0,
})
const rectStatusFilter = ref('')

// ============= 整改状态列表 =============
const rectStatusList = [
  { key: 'pending', label: '待整改', color: 'text-orange-600' },
  { key: 'overdue', label: '已超期', color: 'text-red-600' },
  { key: 'submitted', label: '待审核', color: 'text-blue-600' },
  { key: 'approved', label: '已闭环', color: 'text-green-600' },
]

// ============= 计算属性 =============
const filteredRectifications = computed(() => {
  if (!rectStatusFilter.value) return rectifications.value
  return rectifications.value.filter((r) => r.status === rectStatusFilter.value)
})

// ============= 方法 =============
const fetchNotifications = async () => {
  try {
    const params: any = {}
    if (notifType.value) params.type = notifType.value
    if (readFilter.value !== undefined) params.is_read = readFilter.value === 'true'
    const res = await ApiService.get('/api/v1/notifications', params)
    if (!res.success) return
    const data = (
      res.data as
        | { data?: { items?: Array<Record<string, unknown>>; unread_count?: number } }
        | undefined
    )?.data
    if (data) {
      notifications.value = data.items || []
      unreadCount.value = data.unread_count || 0
    }
  } catch (err) {
    console.error('获取通知失败:', err)
  }
}

const fetchRectifications = async () => {
  try {
    const res = await ApiService.get('/api/v1/notifications/rectifications')
    if (!res.success) return
    const data = (
      res.data as
        | { data?: { items?: Array<Record<string, unknown>>; stats?: Record<string, number> } }
        | undefined
    )?.data
    if (data) {
      rectifications.value = data.items || []
      rectStats.value = data.stats || {}
    }
  } catch (err) {
    console.error('获取整改失败:', err)
  }
}

const handleTabChange = (key: string) => {
  if (key === 'rectifications') fetchRectifications()
  else fetchNotifications()
}

const markAllRead = async () => {
  try {
    const res = await ApiService.put('/api/v1/notifications/read-all')
    if (!res.success) throw new Error(String(res.error || 'mark all read failed'))
    message.success('已全部标为已读')
    await fetchNotifications()
  } catch (err) {
    message.error('操作失败')
  }
}

const handleNotifClick = async (notif: any) => {
  if (!notif.is_read) {
    try {
      const res = await ApiService.put(`/api/v1/notifications/${notif.id}/read`)
      if (!res.success) return
      notif.is_read = true
      unreadCount.value = Math.max(0, unreadCount.value - 1)
    } catch (err) {
      /* ignore */
    }
  }
}

const submitRect = async (id: string) => {
  try {
    const res = await ApiService.put(`/api/v1/notifications/rectifications/${id}/submit`, {
      note: '已完成整改',
    })
    if (!res.success) throw new Error(String(res.error || 'submit rectification failed'))
    message.success('整改已提交')
    await fetchRectifications()
  } catch (err) {
    message.error('提交失败')
  }
}

const approveRect = async (id: string) => {
  try {
    const res = await ApiService.put(`/api/v1/notifications/rectifications/${id}/approve`)
    if (!res.success) throw new Error(String(res.error || 'approve rectification failed'))
    message.success('审核通过，问题已闭环')
    await fetchRectifications()
  } catch (err) {
    message.error('审核失败')
  }
}

const rejectRect = async (id: string) => {
  try {
    const res = await ApiService.put(`/api/v1/notifications/rectifications/${id}/reject`, {
      reason: '整改不充分',
    })
    if (!res.success) throw new Error(String(res.error || 'reject rectification failed'))
    message.warning('已退回整改')
    await fetchRectifications()
  } catch (err) {
    message.error('退回失败')
  }
}

// ============= 辅助 =============
const notifIcon = (type: string) =>
  ({
    qc_result: FileTextOutlined,
    urge: SendOutlined,
    rectification: ToolOutlined,
    appeal: ExclamationCircleOutlined,
    system: SettingOutlined,
  })[type] || BellOutlined

const notifIconBg = (type: string) =>
  ({
    qc_result: 'bg-blue-500',
    urge: 'bg-orange-500',
    rectification: 'bg-green-500',
    appeal: 'bg-red-500',
    system: 'bg-gray-500',
  })[type] || 'bg-gray-400'

const rectStatusColor = (status: string) =>
  ({
    pending: 'orange',
    overdue: 'red',
    submitted: 'blue',
    approved: 'green',
  })[status] || 'default'

const rectStatusLabel = (status: string) =>
  ({
    pending: '待整改',
    overdue: '已超期',
    submitted: '待审核',
    approved: '已闭环',
  })[status] || status

const formatTime = (iso: string) => {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const diff = (now.getTime() - d.getTime()) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  return `${Math.floor(diff / 86400)} 天前`
}

const formatDate = (iso: string) => {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('zh-CN')
}

// ============= 初始化 =============
onMounted(() => {
  fetchNotifications()
  fetchRectifications()
})
</script>
