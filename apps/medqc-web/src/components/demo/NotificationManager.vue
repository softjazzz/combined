<template>
  <div class="notification-manager">
    <!-- 顶部操作栏 -->
    <div class="manager-header">
      <a-space
        direction="vertical"
        :size="12"
        style="width: 100%"
      >
        <!-- 筛选器 -->
        <a-space
          wrap
          :size="8"
        >
          <a-select
            v-model:value="filters.type"
            placeholder="类型"
            style="width: 100px"
            size="small"
            allow-clear
          >
            <a-select-option value="">
              全部
            </a-select-option>
            <a-select-option value="error">
              <CloseCircleOutlined style="color: #ff4d4f" />
              错误
            </a-select-option>
            <a-select-option value="warning">
              <WarningOutlined style="color: #faad14" />
              警告
            </a-select-option>
            <a-select-option value="info">
              <InfoCircleOutlined style="color: #2b6cf6" />
              信息
            </a-select-option>
          </a-select>

          <a-select
            v-model:value="filters.severity"
            placeholder="严重程度"
            style="width: 100px"
            size="small"
            allow-clear
          >
            <a-select-option value="">
              全部
            </a-select-option>
            <a-select-option value="critical">
              严重
            </a-select-option>
            <a-select-option value="high">
              较重
            </a-select-option>
            <a-select-option value="medium">
              中等
            </a-select-option>
            <a-select-option value="low">
              轻微
            </a-select-option>
          </a-select>

          <a-select
            v-model:value="filters.status"
            placeholder="状态"
            style="width: 100px"
            size="small"
            allow-clear
          >
            <a-select-option value="">
              全部
            </a-select-option>
            <a-select-option value="pending">
              待处理
            </a-select-option>
            <a-select-option value="confirmed">
              已确认
            </a-select-option>
            <a-select-option value="ignored">
              已忽略
            </a-select-option>
          </a-select>

          <a-button
            size="small"
            :icon="h(ReloadOutlined)"
            @click="handleRefresh"
          >
            刷新
          </a-button>
        </a-space>

        <!-- 批量操作提示 -->
        <a-alert
          v-if="selectedIds.length > 0"
          type="info"
          :message="`已选择 ${selectedIds.length} 项`"
          closable
          @close="selectedIds = []"
        >
          <template #action>
            <a-space :size="8">
              <a-button
                size="small"
                @click="handleBatchMarkRead"
              >
                标记已读
              </a-button>
              <a-button
                size="small"
                @click="handleBatchIgnore"
              >
                批量忽略
              </a-button>
              <a-button
                size="small"
                danger
                @click="handleBatchDelete"
              >
                批量删除
              </a-button>
            </a-space>
          </template>
        </a-alert>
      </a-space>
    </div>

    <!-- 通知列表 -->
    <a-list
      :data-source="filteredNotifications"
      :pagination="pagination"
      size="small"
      class="notification-list"
    >
      <template #header>
        <div class="list-header">
          <a-statistic
            title="未读通知"
            :value="demoStore.unreadNotificationsCount"
            :value-style="{ color: '#2b6cf6', fontSize: '20px' }"
          >
            <template #prefix>
              <BellOutlined />
            </template>
          </a-statistic>
        </div>
      </template>

      <template #renderItem="{ item }">
        <a-list-item
          :class="['notification-item', { 'unread': !item.isRead }]"
          @click="handleView(item)"
        >
          <template #actions>
            <a-dropdown>
              <a-button
                type="text"
                size="small"
                :icon="h(MoreOutlined)"
              />
              <template #overlay>
                <a-menu @click="(info: MenuInfo) => handleAction(String(info.key), item)">
                  <a-menu-item key="view">
                    <EyeOutlined />
                    查看详情
                  </a-menu-item>
                  <a-menu-item key="confirm">
                    <CheckOutlined />
                    确认
                  </a-menu-item>
                  <a-menu-item key="appeal">
                    <FileTextOutlined />
                    申诉
                  </a-menu-item>
                  <a-menu-divider />
                  <a-menu-item key="ignore">
                    <EyeInvisibleOutlined />
                    忽略
                  </a-menu-item>
                  <a-menu-item
                    key="delete"
                    danger
                  >
                    <DeleteOutlined />
                    删除
                  </a-menu-item>
                </a-menu>
              </template>
            </a-dropdown>
          </template>

          <a-list-item-meta>
            <template #avatar>
              <a-checkbox
                :checked="selectedIds.includes(item.id)"
                @change="handleSelectChange($event, item.id)"
                @click.stop
              />
              <a-badge
                :dot="!item.isRead"
                :offset="[-5, 5]"
              >
                <a-avatar :style="{ backgroundColor: getTypeColor(item.type) }">
                  <template #icon>
                    <component :is="getTypeIcon(item.type)" />
                  </template>
                </a-avatar>
              </a-badge>
            </template>

            <template #title>
              <a-space>
                <span :class="{ 'font-bold': !item.isRead }">{{ item.title }}</span>
                <a-tag
                  :color="getSeverityColor(item.severity)"
                  size="small"
                >
                  {{ getSeverityLabel(item.severity) }}
                </a-tag>
              </a-space>
            </template>

            <template #description>
              <a-space
                direction="vertical"
                :size="4"
                style="width: 100%"
              >
                <div class="notification-meta">
                  <UserOutlined />
                  {{ item.recordInfo?.patientName || '未知患者' }}
                  <a-divider type="vertical" />
                  <ClockCircleOutlined />
                  {{ formatTime(item.timestamp) }}
                </div>
                <div class="notification-content">
                  {{ item.message }}
                </div>
              </a-space>
            </template>
          </a-list-item-meta>
        </a-list-item>
      </template>
    </a-list>

    <!-- 空状态 -->
    <a-empty
      v-if="filteredNotifications.length === 0"
      description="暂无通知"
      :image="Empty.PRESENTED_IMAGE_SIMPLE"
    >
      <a-button
        type="primary"
        @click="handleSimulate"
      >
        模拟生成通知
      </a-button>
    </a-empty>
  </div>
</template>

<script setup lang="ts">
import { h, ref, computed } from 'vue'
import { message, Empty } from 'ant-design-vue'
import type { CheckboxChangeEvent } from 'ant-design-vue/es/checkbox/interface'
import type { MenuInfo } from 'ant-design-vue/es/menu/src/interface'
import { useQCDemoStore } from '@/stores/qcDemo'
import type { QCNotification } from '@/types/quality-control'
import {
  BellOutlined,
  ReloadOutlined,
  MoreOutlined,
  EyeOutlined,
  CheckOutlined,
  FileTextOutlined,
  EyeInvisibleOutlined,
  DeleteOutlined,
  UserOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  WarningOutlined,
  InfoCircleOutlined,
  CheckCircleOutlined
} from '@ant-design/icons-vue'
import dayjs from 'dayjs'

const demoStore = useQCDemoStore()
const demoStoreActions = demoStore as unknown as {
  batchMarkRead?: (ids: string[]) => void
  batchIgnore?: (ids: string[]) => void
  batchDelete?: (ids: string[]) => void
}

// 筛选器
const filters = ref({
  type: '',
  severity: '',
  status: ''
})

// 选中的通知ID
const selectedIds = ref<string[]>([])

// 计算属性
const filteredNotifications = computed(() => {
  let notifications = demoStore.notifications

  // 按类型筛选
  if (filters.value.type) {
    notifications = notifications.filter(n => n.type === filters.value.type)
  }

  // 按严重程度筛选
  if (filters.value.severity) {
    notifications = notifications.filter(n => n.severity === filters.value.severity)
  }

  // 按状态筛选
  if (filters.value.status) {
    notifications = notifications.filter(n => n.status === filters.value.status)
  }

  return notifications
})

// 分页配置
const pagination = {
  pageSize: 10,
  showSizeChanger: true,
  showTotal: (total: number) => `共 ${total} 条`
}

// 工具函数
const getTypeColor = (type: string) => {
  const colors = {
    error: '#ff4d4f',
    warning: '#faad14',
    info: '#2b6cf6',
    success: '#52c41a'
  }
  return colors[type as keyof typeof colors] || '#2b6cf6'
}

const getTypeIcon = (type: string) => {
  const icons = {
    error: CloseCircleOutlined,
    warning: WarningOutlined,
    info: InfoCircleOutlined,
    success: CheckCircleOutlined
  }
  return icons[type as keyof typeof icons] || InfoCircleOutlined
}

const getSeverityColor = (severity: string) => {
  const colors = {
    critical: 'red',
    high: 'orange',
    medium: 'gold',
    low: 'blue'
  }
  return colors[severity as keyof typeof colors] || 'default'
}

const getSeverityLabel = (severity: string) => {
  const labels = {
    critical: '严重',
    high: '较重',
    medium: '中等',
    low: '轻微'
  }
  return labels[severity as keyof typeof labels] || severity
}

const formatTime = (timestamp: Date | string) => {
  return dayjs(timestamp).format('YYYY-MM-DD HH:mm:ss')
}

// 事件处理
const handleSelectChange = (e: CheckboxChangeEvent, id: string) => {
  if (e.target.checked) {
    selectedIds.value.push(id)
  } else {
    selectedIds.value = selectedIds.value.filter(selectedId => selectedId !== id)
  }
}

const handleBatchMarkRead = () => {
  demoStoreActions.batchMarkRead?.(selectedIds.value)
  message.success(`已标记 ${selectedIds.value.length} 条通知为已读`)
  selectedIds.value = []
}

const handleBatchIgnore = () => {
  demoStoreActions.batchIgnore?.(selectedIds.value)
  message.success(`已忽略 ${selectedIds.value.length} 条通知`)
  selectedIds.value = []
}

const handleBatchDelete = () => {
  demoStoreActions.batchDelete?.(selectedIds.value)
  message.success(`已删除 ${selectedIds.value.length} 条通知`)
  selectedIds.value = []
}

const handleView = (notification: QCNotification) => {
  demoStore.handleNotificationAction('view', notification)
}

const handleAction = (key: string, notification: QCNotification) => {
  demoStore.handleNotificationAction(key, notification)
}

const handleRefresh = () => {
  message.success('列表已刷新')
}

const handleSimulate = () => {
  demoStore.handleNotificationAction('simulate')
}
</script>

<style scoped lang="less">
.notification-manager {
  .manager-header {
    margin-bottom: 16px;
  }

  .notification-list {
    max-height: 600px;
    overflow-y: auto;

    .notification-item {
      cursor: pointer;
      transition: background-color 0.3s;

      &:hover {
        background-color: #f5f5f5;
      }

      &.unread {
        background-color: #e6f7ff;
      }

      .font-bold {
        font-weight: 600;
      }

      .notification-meta {
        color: #8c8c8c;
        font-size: 12px;
      }

      .notification-content {
        color: #595959;
        font-size: 13px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }
  }

  .list-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
}
</style>
