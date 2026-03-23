<template>
  <div class="qc-notification-demo-panel">
    <a-card
      title="医生端质控通知中心"
      class="notification-panel"
    >
      <template #extra>
        <a-space>
          <a-badge
            :count="unreadCount"
            :offset="[10, 0]"
          >
            <BellOutlined />
          </a-badge>
          <a-tooltip title="自动刷新">
            <a-switch
              v-model:checked="autoRefresh"
              size="small"
              @change="handleAutoRefreshChange"
            />
          </a-tooltip>
          <a-tooltip title="模拟新通知">
            <a-button
              type="primary"
              size="small"
              :icon="h(PlusOutlined)"
              @click="handleSimulateNotification"
            >
              模拟通知
            </a-button>
          </a-tooltip>
        </a-space>
      </template>

      <!-- 通知筛选和操作栏 -->
      <div class="notification-controls">
        <a-row
          :gutter="16"
          align="middle"
        >
          <a-col :span="6">
            <a-select
              v-model:value="filterType"
              placeholder="通知类型"
              style="width: 100%"
              allow-clear
              @change="handleFilterChange"
            >
              <a-select-option value="all">
                全部类型
              </a-select-option>
              <a-select-option value="error">
                错误
              </a-select-option>
              <a-select-option value="warning">
                警告
              </a-select-option>
              <a-select-option value="info">
                信息
              </a-select-option>
              <a-select-option value="success">
                成功
              </a-select-option>
            </a-select>
          </a-col>
          <a-col :span="6">
            <a-select
              v-model:value="filterSeverity"
              placeholder="严重程度"
              style="width: 100%"
              allow-clear
              @change="handleFilterChange"
            >
              <a-select-option value="all">
                全部程度
              </a-select-option>
              <a-select-option value="critical">
                紧急
              </a-select-option>
              <a-select-option value="high">
                高
              </a-select-option>
              <a-select-option value="medium">
                中
              </a-select-option>
              <a-select-option value="low">
                低
              </a-select-option>
            </a-select>
          </a-col>
          <a-col :span="6">
            <a-select
              v-model:value="filterStatus"
              placeholder="阅读状态"
              style="width: 100%"
              allow-clear
              @change="handleFilterChange"
            >
              <a-select-option value="all">
                全部状态
              </a-select-option>
              <a-select-option value="unread">
                未读
              </a-select-option>
              <a-select-option value="read">
                已读
              </a-select-option>
            </a-select>
          </a-col>
          <a-col :span="6">
            <a-space>
              <a-tooltip title="标记全部已读">
                <a-button
                  size="small"
                  :icon="h(CheckOutlined)"
                  :disabled="unreadCount === 0"
                  @click="handleMarkAllAsRead"
                >
                  全部已读
                </a-button>
              </a-tooltip>
              <a-tooltip title="清空通知">
                <a-button
                  size="small"
                  danger
                  :icon="h(DeleteOutlined)"
                  :disabled="notifications.length === 0"
                  @click="handleClearNotifications"
                >
                  清空
                </a-button>
              </a-tooltip>
            </a-space>
          </a-col>
        </a-row>
      </div>

      <!-- 通知统计 -->
      <div
        v-if="notifications.length > 0"
        class="notification-stats"
      >
        <a-row :gutter="16">
          <a-col :span="6">
            <a-statistic
              title="总通知"
              :value="notifications.length"
            />
          </a-col>
          <a-col :span="6">
            <a-statistic
              title="未读"
              :value="unreadCount"
              :value-style="{ color: '#cf1322' }"
            />
          </a-col>
          <a-col :span="6">
            <a-statistic
              title="紧急"
              :value="criticalCount"
              :value-style="{ color: '#ff4d4f' }"
            />
          </a-col>
          <a-col :span="6">
            <a-statistic
              title="今日"
              :value="todayCount"
              :value-style="{ color: '#1890ff' }"
            />
          </a-col>
        </a-row>
      </div>

      <!-- 通知列表 -->
      <div class="notifications-section">
        <div
          v-if="filteredNotifications.length === 0"
          class="empty-notifications"
        >
          <a-empty :description="notifications.length === 0 ? '暂无通知' : '没有符合条件的通知'">
            <a-button
              v-if="notifications.length === 0"
              type="primary"
              @click="handleSimulateNotification"
            >
              模拟通知
            </a-button>
          </a-empty>
        </div>

        <div
          v-else
          class="notifications-list"
        >
          <transition-group
            name="notification"
            tag="div"
          >
            <div
              v-for="notification in paginatedNotifications"
              :key="notification.id"
              class="notification-item"
              :class="{
                unread: !notification.isRead,
                active: activeNotification?.id === notification.id,
                critical: notification.severity === 'critical',
                [`notification-${notification.type}`]: true
              }"
              @click="handleNotificationClick(notification)"
            >
              <!-- 紧急通知闪烁效果 -->
              <div
                v-if="notification.severity === 'critical'"
                class="critical-indicator"
              />

              <div class="notification-header">
                <div class="notification-type">
                  <a-tag :color="getNotificationColor(notification.type)">
                    <component :is="getNotificationIcon(notification.type)" />
                    {{ getNotificationTypeText(notification.type) }}
                  </a-tag>
                  <a-tag
                    v-if="notification.severity"
                    :color="getSeverityColor(notification.severity)"
                  >
                    {{ getSeverityText(notification.severity) }}
                  </a-tag>
                  <a-tag
                    v-if="!notification.isRead"
                    color="red"
                    size="small"
                  >
                    NEW
                  </a-tag>
                </div>
                <div class="notification-actions">
                  <a-space size="small">
                    <a-tooltip title="查看详情">
                      <a-button
                        size="small"
                        type="text"
                        :icon="h(EyeOutlined)"
                        @click.stop="handleViewDetails(notification)"
                      />
                    </a-tooltip>
                    <a-tooltip :title="notification.isRead ? '标记未读' : '标记已读'">
                      <a-button
                        size="small"
                        type="text"
                        :icon="h(notification.isRead ? MailOutlined : CheckOutlined)"
                        @click.stop="handleToggleRead(notification)"
                      />
                    </a-tooltip>
                    <a-tooltip title="删除通知">
                      <a-button
                        size="small"
                        type="text"
                        danger
                        :icon="h(DeleteOutlined)"
                        @click.stop="handleDeleteNotification(notification)"
                      />
                    </a-tooltip>
                  </a-space>
                </div>
                <div class="notification-time">
                  <a-tooltip :title="formatFullTime(notification.timestamp)">
                    {{ formatRelativeTime(notification.timestamp) }}
                  </a-tooltip>
                </div>
              </div>

              <div class="notification-content">
                <h5 class="notification-title">
                  {{ notification.title }}
                </h5>
                <p class="notification-message">
                  {{ notification.message }}
                </p>

                <!-- 质控结果预览 -->
                <div
                  v-if="notification.qcResult"
                  class="qc-preview"
                >
                  <a-row :gutter="8">
                    <a-col :span="8">
                      <a-statistic
                        title="评分"
                        :value="notification.qcResult.overallScore"
                        suffix="分"
                        :value-style="{
                          color: getScoreColor(notification.qcResult.overallScore),
                          fontSize: '14px'
                        }"
                      />
                    </a-col>
                    <a-col :span="8">
                      <a-statistic
                        title="问题"
                        :value="notification.qcResult.issues?.length || 0"
                        suffix="个"
                        :value-style="{ color: '#cf1322', fontSize: '14px' }"
                      />
                    </a-col>
                    <a-col :span="8">
                      <a-statistic
                        title="建议"
                        :value="notification.qcResult.suggestions?.length || 0"
                        suffix="条"
                        :value-style="{ color: '#1890ff', fontSize: '14px' }"
                      />
                    </a-col>
                  </a-row>
                </div>

                <!-- 病历信息 -->
                <div
                  v-if="notification.recordInfo"
                  class="record-info"
                >
                  <a-tag color="blue">
                    {{ notification.recordInfo.patientName }}
                  </a-tag>
                  <a-tag color="green">
                    {{ notification.recordInfo.department }}
                  </a-tag>
                  <a-tag>{{ notification.recordInfo.recordNumber }}</a-tag>
                </div>
              </div>

              <div class="notification-footer">
                <a-space>
                  <a-button
                    size="small"
                    type="primary"
                    :icon="h(EyeOutlined)"
                    @click.stop="handleViewDetails(notification)"
                  >
                    查看详情
                  </a-button>
                  <a-button
                    v-if="notification.canAppeal"
                    size="small"
                    type="default"
                    :icon="h(FormOutlined)"
                    @click.stop="handleAppeal(notification)"
                  >
                    申诉
                  </a-button>
                  <a-button
                    v-if="!notification.isRead"
                    size="small"
                    :icon="h(CheckOutlined)"
                    @click.stop="handleMarkAsRead(notification)"
                  >
                    标记已读
                  </a-button>
                  <a-button
                    size="small"
                    type="text"
                    danger
                    :icon="h(DeleteOutlined)"
                    @click.stop="handleIgnoreNotification(notification)"
                  >
                    忽略
                  </a-button>
                </a-space>
              </div>
            </div>
          </transition-group>

          <!-- 分页 -->
          <div
            v-if="filteredNotifications.length > pageSize"
            class="notification-pagination"
          >
            <a-pagination
              v-model:current="currentPage"
              v-model:page-size="pageSize"
              :total="filteredNotifications.length"
              :show-size-changer="true"
              :show-quick-jumper="true"
              :show-total="showNotificationTotal"
              size="small"
              @change="handlePageChange"
              @show-size-change="handlePageSizeChange"
            />
          </div>
        </div>
      </div>
      
      <!-- 活动通知详情 -->
      <div
        v-if="activeNotification"
        class="active-notification"
      >
        <a-divider>通知详情</a-divider>
        <div class="notification-details">
          <h4>{{ activeNotification.title }}</h4>
          <p>{{ activeNotification.message }}</p>
          
          <!-- 质控结果摘要 -->
          <div class="qc-summary">
            <a-descriptions
              title="质控结果"
              :column="2"
              bordered
              size="small"
            >
              <a-descriptions-item label="总体评分">
                <span :style="{ color: getScoreColor(activeNotification.qcResult.overallScore) }">
                  {{ activeNotification.qcResult.overallScore }}分
                </span>
              </a-descriptions-item>
              <a-descriptions-item label="等级">
                {{ activeNotification.qcResult.overallGrade }}
              </a-descriptions-item>
              <a-descriptions-item label="问题数量">
                {{ activeNotification.qcResult.issues.length }}个
              </a-descriptions-item>
              <a-descriptions-item label="建议数量">
                {{ activeNotification.qcResult.suggestions.length }}条
              </a-descriptions-item>
            </a-descriptions>
          </div>
          
          <!-- 主要问题 -->
          <div
            v-if="activeNotification.qcResult.issues.length > 0"
            class="main-issues"
          >
            <h5>主要问题</h5>
            <a-list 
              :data-source="activeNotification.qcResult.issues.slice(0, 3)" 
              size="small"
            >
              <template #renderItem="{ item }">
                <a-list-item>
                  <a-list-item-meta>
                    <template #title>
                      <a-space>
                        <a-tag :color="getSeverityColor(item.severity)">
                          {{ getSeverityText(item.severity) }}
                        </a-tag>
                        {{ item.ruleName }}
                      </a-space>
                    </template>
                    <template #description>
                      {{ item.description }}
                    </template>
                  </a-list-item-meta>
                </a-list-item>
              </template>
            </a-list>
          </div>
        </div>
      </div>
      
      <!-- 操作按钮 -->
      <div class="panel-actions">
        <a-space>
          <a-button @click="handleSimulateNotification">
            <PlusOutlined />
            模拟新通知
          </a-button>
          <a-button
            :disabled="unreadCount === 0"
            @click="handleMarkAllAsRead"
          >
            <CheckOutlined />
            全部已读
          </a-button>
          <a-button
            :disabled="notifications.length === 0"
            @click="handleClearAll"
          >
            <DeleteOutlined />
            清空通知
          </a-button>
        </a-space>
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, h } from 'vue'
import { message } from 'ant-design-vue'
import {
  BellOutlined,
  PlusOutlined,
  CheckOutlined,
  DeleteOutlined,
  WarningOutlined,
  ExclamationCircleOutlined,
  InfoCircleOutlined,
  CheckCircleOutlined,
  EyeOutlined,
  FormOutlined,
  MailOutlined
} from '@ant-design/icons-vue'
import type { QCNotification } from '@/types/quality-control'

// Props
const props = defineProps<{
  notifications: QCNotification[]
  activeNotification: QCNotification | null
}>()

// Emits
const emit = defineEmits<{
  notificationAction: [action: string, notification?: QCNotification]
}>()

// 响应式数据
const autoRefresh = ref(false)
const filterType = ref<string>('all')
const filterSeverity = ref<string>('all')
const filterStatus = ref<string>('all')
const currentPage = ref(1)
const pageSize = ref(10)
const refreshTimer = ref<NodeJS.Timeout | null>(null)

// 计算属性
const unreadCount = computed(() =>
  props.notifications.filter(n => !n.isRead).length
)

const criticalCount = computed(() => {
  return props.notifications.filter(n => n.severity === 'critical').length
})

const todayCount = computed(() => {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return props.notifications.filter(n => {
    const notificationDate = new Date(n.timestamp)
    notificationDate.setHours(0, 0, 0, 0)
    return notificationDate.getTime() === today.getTime()
  }).length
})

const filteredNotifications = computed(() => {
  let filtered = [...props.notifications]

  // 类型筛选
  if (filterType.value && filterType.value !== 'all') {
    filtered = filtered.filter(n => n.type === filterType.value)
  }

  // 严重程度筛选
  if (filterSeverity.value && filterSeverity.value !== 'all') {
    filtered = filtered.filter(n => n.severity === filterSeverity.value)
  }

  // 状态筛选
  if (filterStatus.value && filterStatus.value !== 'all') {
    if (filterStatus.value === 'unread') {
      filtered = filtered.filter(n => !n.isRead)
    } else if (filterStatus.value === 'read') {
      filtered = filtered.filter(n => n.isRead)
    }
  }

  // 按时间排序（最新的在前）
  return filtered.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
})

const paginatedNotifications = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return filteredNotifications.value.slice(start, end)
})
const showNotificationTotal = (total: number, range: [number, number]) =>
  `第 ${range[0]}-${range[1]} 条，共 ${total} 条`

// 方法
const getNotificationColor = (type: string) => {
  const colors = {
    success: 'green',
    info: 'blue',
    warning: 'orange',
    error: 'red'
  }
  return colors[type as keyof typeof colors] || 'default'
}

const getNotificationIcon = (type: string) => {
  const icons = {
    success: 'CheckCircleOutlined',
    info: 'InfoCircleOutlined',
    warning: 'WarningOutlined',
    error: 'ExclamationCircleOutlined'
  }
  return icons[type as keyof typeof icons] || 'InfoCircleOutlined'
}

const getNotificationTypeText = (type: string) => {
  const texts = {
    success: '成功',
    info: '信息',
    warning: '警告',
    error: '错误'
  }
  return texts[type as keyof typeof texts] || type
}

const getSeverityColor = (severity: string) => {
  const colors = {
    low: 'green',
    medium: 'orange',
    high: 'red',
    critical: 'red'
  }
  return colors[severity as keyof typeof colors] || 'default'
}

const getSeverityText = (severity: string) => {
  const texts = {
    low: '轻微',
    medium: '中等',
    high: '严重',
    critical: '紧急'
  }
  return texts[severity as keyof typeof texts] || severity
}

const getScoreColor = (score: number) => {
  if (score >= 90) return '#52c41a'
  if (score >= 80) return '#faad14'
  if (score >= 60) return '#fa8c16'
  return '#f5222d'
}

const formatRelativeTime = (timestamp: Date) => {
  const now = new Date()
  const diff = now.getTime() - new Date(timestamp).getTime()
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (days > 0) return `${days}天前`
  if (hours > 0) return `${hours}小时前`
  if (minutes > 0) return `${minutes}分钟前`
  return '刚刚'
}

const formatFullTime = (timestamp: Date) => {
  return new Date(timestamp).toLocaleString('zh-CN')
}

// 事件处理方法
const handleAutoRefreshChange = (checked: boolean) => {
  if (checked) {
    refreshTimer.value = setInterval(() => {
      // 模拟新通知
      if (Math.random() > 0.7) {
        handleSimulateNotification()
      }
    }, 10000) // 每10秒检查一次
    message.success('已开启自动刷新')
  } else {
    if (refreshTimer.value) {
      clearInterval(refreshTimer.value)
      refreshTimer.value = null
    }
    message.info('已关闭自动刷新')
  }
}

const handleFilterChange = () => {
  currentPage.value = 1 // 重置到第一页
}

const handlePageChange = (page: number) => {
  currentPage.value = page
}

const handlePageSizeChange = (current: number, size: number) => {
  currentPage.value = 1
  pageSize.value = size
}

const handleViewDetails = (notification: QCNotification) => {
  emit('notificationAction', 'view', notification)
}

const handleToggleRead = (notification: QCNotification) => {
  emit('notificationAction', notification.isRead ? 'mark-unread' : 'mark-read', notification)
}

const handleDeleteNotification = (notification: QCNotification) => {
  emit('notificationAction', 'delete', notification)
}

const handleIgnoreNotification = (notification: QCNotification) => {
  emit('notificationAction', 'ignore', notification)
}

const handleMarkAllAsRead = () => {
  emit('notificationAction', 'mark-all-read', {} as QCNotification)
  message.success('已标记全部通知为已读')
}

const handleClearNotifications = () => {
  emit('notificationAction', 'clear-all', {} as QCNotification)
  message.success('已清空所有通知')
}

const handleClearAll = () => {
  handleClearNotifications()
}

const handleNotificationClick = (notification: QCNotification) => {
  emit('notificationAction', 'select', notification)
}

const handleAppeal = (notification: QCNotification) => {
  emit('notificationAction', 'appeal', notification)
  message.info('开始申诉流程')
}

const handleMarkAsRead = (notification: QCNotification) => {
  emit('notificationAction', 'markRead', notification)
  message.success('已标记为已读')
}

const handleSimulateNotification = () => {
  emit('notificationAction', 'simulate', {} as QCNotification)
  message.info('模拟新通知')
}

// 生命周期钩子
onMounted(() => {
  // 组件挂载时的初始化
  console.log('通知面板已挂载')
})

onUnmounted(() => {
  // 清理定时器
  if (refreshTimer.value) {
    clearInterval(refreshTimer.value)
  }
})
</script>

<style scoped lang="less">
.qc-notification-demo-panel {
  .notification-panel {
    // 通知控制栏
    .notification-controls {
      margin-bottom: 16px;
      padding: 16px;
      background: #ffffff;
      border-radius: 12px;
      box-shadow: 0 1px 6px rgba(15, 23, 42, 0.06);
    }

    // 通知统计
    .notification-stats {
      margin-bottom: 16px;
      padding: 16px;
      background: linear-gradient(135deg, var(--primary-color-light) 0%, var(--primary-color) 100%);
      border-radius: 12px;
      box-shadow: 0 6px 18px rgba(14, 110, 209, 0.18);

      :deep(.ant-statistic-title) {
        color: rgba(255, 255, 255, 0.8);
      }

      :deep(.ant-statistic-content) {
        color: white;
      }
    }

    .notifications-section {
      margin-bottom: 24px;

      .empty-notifications {
        text-align: center;
        padding: 40px 0;
      }

      .notifications-list {
        .notification-item {
          position: relative;
          border: 1px solid #eef1f5;
          border-radius: 12px;
          padding: 16px;
          margin-bottom: 12px;
          cursor: pointer;
          transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          overflow: hidden;

          // 紧急通知闪烁指示器
          .critical-indicator {
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background: #ff4d4f;
            animation: pulse 2s infinite;
          }

          &:hover {
            border-color: var(--primary-color);
            box-shadow: 0 6px 18px rgba(24, 144, 255, 0.15);
            transform: translateY(-2px);
          }

          &.unread {
            border-left: 4px solid #1890ff;
            background: linear-gradient(135deg, #f0f6ff 0%, #f5fbff 100%);
          }

          &.active {
            border-color: #1890ff;
            background: #e6f7ff;
            box-shadow: 0 0 0 2px rgba(24, 144, 255, 0.2);
          }

          &.critical {
            border-left: 4px solid #ff4d4f;
            background: linear-gradient(135deg, #fff5f0 0%, #fff9f5 100%);

            &::before {
              content: '';
              position: absolute;
              top: 0;
              right: 0;
              width: 0;
              height: 0;
              border-left: 20px solid transparent;
              border-top: 20px solid #ff4d4f;
            }

            &::after {
              content: '!';
              position: absolute;
              top: 2px;
              right: 6px;
              color: white;
              font-weight: bold;
              font-size: 12px;
            }
          }

          .notification-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 12px;

            .notification-type {
              display: flex;
              gap: 8px;
              flex-wrap: wrap;
            }

            .notification-actions {
              display: flex;
              gap: 4px;
            }

            .notification-time {
              font-size: 12px;
              color: #666;
              white-space: nowrap;
            }
          }

          .notification-content {
            margin-bottom: 12px;

            .notification-title {
              font-weight: 600;
              margin: 0 0 8px 0;
              color: #333;
              font-size: 16px;
            }

            .notification-message {
              margin: 0 0 12px 0;
              color: #666;
              font-size: 14px;
              line-height: 1.5;
            }

            .qc-preview {
              margin: 12px 0;
              padding: 12px;
              background: #fafafa;
              border-radius: 6px;
              border: 1px solid #f0f0f0;
            }

            .record-info {
              margin-top: 8px;
              display: flex;
              gap: 8px;
              flex-wrap: wrap;
            }
          }

          .notification-footer {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-top: 12px;
            border-top: 1px solid #f0f0f0;
          }
        }

        .notification-pagination {
          margin-top: 24px;
          text-align: center;

          :deep(.ant-pagination) {
            display: inline-flex;
          }
        }
      }
    }

    .active-notification {
      .notification-details {
        h4 {
          font-weight: 600;
          margin-bottom: 8px;
          color: #333;
        }

        .qc-summary {
          margin: 16px 0;
        }

        .main-issues {
          margin-top: 16px;
          
          h5 {
            font-weight: 600;
            margin-bottom: 8px;
            color: #333;
          }
        }
      }
    }
    
    .panel-actions {
      text-align: center;
      padding-top: 16px;
      border-top: 1px solid #f0f0f0;
    }
  }
}

// 通知列表动画
.notification-enter-active,
.notification-leave-active {
  transition: all 0.5s ease;
}

.notification-enter-from {
  opacity: 0;
  transform: translateX(-30px);
}

.notification-leave-to {
  opacity: 0;
  transform: translateX(30px);
}

.notification-move {
  transition: transform 0.5s ease;
}

// 关键帧动画
@keyframes pulse {
  0% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
  100% {
    opacity: 1;
  }
}

@keyframes slideInRight {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

// 响应式设计
@media (max-width: 768px) {
  .qc-notification-demo-panel {
    .notification-controls {
      .ant-row {
        flex-direction: column;
        gap: 8px;
      }
    }

    .notification-stats {
      .ant-row {
        .ant-col {
          margin-bottom: 8px;
        }
      }
    }

    .notifications-list {
      .notification-item {
        .notification-header {
          flex-direction: column;
          align-items: flex-start;
          gap: 8px;
        }

        .notification-footer {
          flex-direction: column;
          gap: 8px;
          align-items: stretch;
        }
      }
    }
  }
}
</style>
