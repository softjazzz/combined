<script setup lang="ts">
import { computed } from 'vue'
import { message, notification } from 'ant-design-vue'
import { useNotificationStore } from '../../stores/notification'
import { 
  BellOutlined, 
  CheckCircleOutlined, 
  ExclamationCircleOutlined, 
  InfoCircleOutlined, 
  CloseCircleOutlined,
  CloseOutlined
} from '@ant-design/icons-vue'

// 使用通知store
const notificationStore = useNotificationStore()

// 计算属性
const notifications = computed(() => notificationStore.notifications)
const unreadCount = computed(() => notificationStore.unreadCount)
const hasNotifications = computed(() => notificationStore.hasNotifications)

// 获取通知图标
const getNotificationIcon = (type: string) => {
  const iconMap = {
    'success': CheckCircleOutlined,
    'error': CloseCircleOutlined,
    'warning': ExclamationCircleOutlined,
    'info': InfoCircleOutlined
  }
  return iconMap[type as keyof typeof iconMap] || InfoCircleOutlined
}

// 获取通知颜色
const getNotificationColor = (type: string) => {
  const colorMap = {
    'success': '#52c41a',
    'error': '#ff4d4f',
    'warning': '#faad14',
    'info': '#1890ff'
  }
  return colorMap[type as keyof typeof colorMap] || '#1890ff'
}

// 处理通知点击
const handleNotificationClick = (notificationItem: { id: string }) => {
  notificationStore.markAsRead(notificationItem.id)
}

// 关闭通知
const handleCloseNotification = (notificationItem: { id: string }) => {
  notificationStore.removeNotification(notificationItem.id)
}

// 清空所有通知
const handleClearAll = () => {
  notificationStore.clearAll()
}

// 标记所有为已读
const handleMarkAllRead = () => {
  notificationStore.markAllAsRead()
}

// 格式化时间
const formatTime = (timestamp: string) => {
  const date = new Date(timestamp)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  
  if (diff < 60000) { // 1分钟内
    return '刚刚'
  } else if (diff < 3600000) { // 1小时内
    return `${Math.floor(diff / 60000)}分钟前`
  } else if (diff < 86400000) { // 1天内
    return `${Math.floor(diff / 3600000)}小时前`
  } else {
    return date.toLocaleDateString()
  }
}
</script>

<template>
  <div class="notification-center">
    <!-- 通知触发按钮 -->
    <a-dropdown 
      :trigger="['click']" 
      placement="bottomRight"
      :overlay-style="{ width: '400px', maxHeight: '500px' }"
    >
      <a-button 
        type="text" 
        shape="circle" 
        size="large"
        class="notification-trigger"
        :class="{ 'has-notifications': hasNotifications }"
      >
        <template #icon>
          <a-badge
            :count="unreadCount"
            :offset="[0, 0]"
          >
            <BellOutlined />
          </a-badge>
        </template>
      </a-button>
      
      <template #overlay>
        <div class="notification-dropdown">
          <!-- 头部 -->
          <div class="notification-header">
            <div class="flex items-center justify-between">
              <h3 class="text-base font-semibold text-gray-900">
                通知中心
              </h3>
              <div class="flex items-center space-x-2">
                <a-button 
                  v-if="unreadCount > 0"
                  type="link" 
                  size="small"
                  class="text-xs"
                  @click="handleMarkAllRead"
                >
                  全部已读
                </a-button>
                <a-button 
                  v-if="hasNotifications"
                  type="link" 
                  size="small"
                  class="text-xs text-red-500"
                  @click="handleClearAll"
                >
                  清空全部
                </a-button>
              </div>
            </div>
          </div>
          
          <!-- 通知列表 -->
          <div class="notification-list">
            <div 
              v-if="!hasNotifications" 
              class="notification-empty"
            >
              <div class="text-center py-8">
                <BellOutlined class="text-4xl text-gray-300 mb-2" />
                <p class="text-gray-500">
                  暂无通知
                </p>
              </div>
            </div>
            
            <div 
              v-else
              class="max-h-96 overflow-y-auto"
            >
              <div
                v-for="item in notifications"
                :key="item.id"
                class="notification-item"
                :class="{ 'unread': !item.read }"
                @click="handleNotificationClick(item)"
              >
                <div class="notification-content">
                  <div class="notification-icon">
                    <component 
                      :is="getNotificationIcon(item.type)"
                      :style="{ color: getNotificationColor(item.type) }"
                    />
                  </div>
                  
                  <div class="notification-body">
                    <div class="notification-title">
                      {{ item.title }}
                    </div>
                    <div 
                      v-if="item.message" 
                      class="notification-message"
                    >
                      {{ item.message }}
                    </div>
                    <div class="notification-time">
                      {{ formatTime(item.timestamp) }}
                    </div>
                  </div>
                  
                  <div class="notification-actions">
                    <a-button
                      type="text"
                      size="small"
                      shape="circle"
                      class="text-gray-400 hover:text-gray-600"
                      @click.stop="handleCloseNotification(item)"
                    >
                      <template #icon>
                        <CloseOutlined />
                      </template>
                    </a-button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
    </a-dropdown>
  </div>
</template>

<style scoped>
.notification-center {
  position: relative;
}

.notification-trigger {
  @apply text-gray-600 hover:text-gray-900 hover:bg-gray-100;
  transition: all 0.2s;
}

.notification-trigger.has-notifications {
  @apply text-blue-600;
}

.notification-dropdown {
  @apply bg-white rounded-lg shadow-lg border border-gray-200;
  min-width: 400px;
  max-width: 500px;
}

.notification-header {
  @apply px-4 py-3 border-b border-gray-100;
}

.notification-list {
  @apply max-h-96 overflow-y-auto;
}

.notification-empty {
  @apply p-4;
}

.notification-item {
  @apply px-4 py-3 border-b border-gray-50 hover:bg-gray-50 cursor-pointer;
  transition: background-color 0.2s;
}

.notification-item.unread {
  @apply bg-blue-50 border-l-4 border-l-blue-500;
}

.notification-item:last-child {
  @apply border-b-0;
}

.notification-content {
  @apply flex items-start space-x-3;
}

.notification-icon {
  @apply flex-shrink-0 mt-1;
}

.notification-body {
  @apply flex-1 min-w-0;
}

.notification-title {
  @apply text-sm font-medium text-gray-900 line-clamp-1;
}

.notification-message {
  @apply text-xs text-gray-600 mt-1 line-clamp-2;
}

.notification-time {
  @apply text-xs text-gray-400 mt-1;
}

.notification-actions {
  @apply flex-shrink-0;
}

/* 滚动条样式 */
.notification-list::-webkit-scrollbar {
  width: 4px;
}

.notification-list::-webkit-scrollbar-track {
  background: #f1f1f1;
}

.notification-list::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 2px;
}

.notification-list::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}

/* 文本截断 */
.line-clamp-1 {
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style> 
