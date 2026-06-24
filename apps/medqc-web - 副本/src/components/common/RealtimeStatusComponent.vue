<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { getRealtimeService } from '@/lib/realtime/realtime-service'
import {
  WifiOutlined,
  DisconnectOutlined,
  LoadingOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons-vue'

// 连接状态
const isConnected = ref(false)
const isConnecting = ref(false)
const connectionAttempts = ref(0)

// 实时服务实例
const realtimeService = getRealtimeService()

// 检查连接状态
const checkConnectionStatus = () => {
  isConnected.value = Boolean(realtimeService.isConnected)
}

// 手动重连
const handleReconnect = async () => {
  try {
    isConnecting.value = true
    connectionAttempts.value++
    await realtimeService.reconnect()
    isConnected.value = true
  } catch (error) {
    console.error('重连失败:', error)
  } finally {
    isConnecting.value = false
  }
}

// 获取状态文本
const getStatusText = () => {
  if (isConnecting.value) {
    return '连接中...'
  }
  if (isConnected.value) {
    return '实时连接正常'
  }
  return '连接已断开'
}

// 获取状态颜色
const getStatusColor = () => {
  if (isConnecting.value) {
    return '#faad14'
  }
  if (isConnected.value) {
    return '#52c41a'
  }
  return '#ff4d4f'
}

// 获取状态图标
const getStatusIcon = () => {
  if (isConnecting.value) {
    return LoadingOutlined
  }
  if (isConnected.value) {
    return CheckCircleOutlined
  }
  return DisconnectOutlined
}

// 定时检查连接状态
let statusCheckInterval: NodeJS.Timeout | null = null

onMounted(() => {
  checkConnectionStatus()

  // 每5秒检查一次连接状态
  statusCheckInterval = setInterval(checkConnectionStatus, 5000)
})

onUnmounted(() => {
  if (statusCheckInterval) {
    clearInterval(statusCheckInterval)
  }
})
</script>

<template>
  <div class="realtime-status">
    <a-tooltip :title="getStatusText()">
      <div
        class="status-indicator"
        :class="{
          connected: isConnected,
          connecting: isConnecting,
          disconnected: !isConnected && !isConnecting,
        }"
        @click="!isConnected && !isConnecting ? handleReconnect() : null"
      >
        <component
          :is="getStatusIcon()"
          :style="{ color: getStatusColor() }"
          :spin="isConnecting"
        />
        <span class="status-text">
          {{ getStatusText() }}
        </span>
      </div>
    </a-tooltip>
  </div>
</template>

<style scoped>
.realtime-status {
  @apply inline-flex items-center;
}

.status-indicator {
  @apply flex items-center space-x-1 px-2 py-1 rounded-md text-xs;
  transition: all 0.2s;
  cursor: default;
}

.status-indicator.connected {
  @apply bg-green-50 text-green-700;
}

.status-indicator.connecting {
  @apply bg-yellow-50 text-yellow-700;
}

.status-indicator.disconnected {
  @apply bg-red-50 text-red-700 hover:bg-red-100 cursor-pointer;
}

.status-text {
  @apply font-medium;
}

/* 动画效果 */
.status-indicator.connected::before {
  content: '';
  @apply w-2 h-2 bg-green-500 rounded-full mr-1;
  animation: pulse 2s infinite;
}

.status-indicator.connecting::before {
  content: '';
  @apply w-2 h-2 bg-yellow-500 rounded-full mr-1;
  animation: pulse 1s infinite;
}

.status-indicator.disconnected::before {
  content: '';
  @apply w-2 h-2 bg-red-500 rounded-full mr-1;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}
</style>
