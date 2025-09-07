<template>
  <div class="realtime-qc-alert">
    <!-- 浮动预警通知 -->
    <Transition name="alert-slide">
      <div
        v-if="showAlert && currentAlert"
        class="alert-notification"
        :class="`alert-${currentAlert.severity}`"
      >
        <div class="alert-content">
          <div class="alert-icon">
            <i :class="getAlertIcon(currentAlert.severity)"></i>
          </div>
          <div class="alert-text">
            <div class="alert-title">{{ getAlertTitle(currentAlert.severity) }}</div>
            <div class="alert-message">{{ currentAlert.message }}</div>
            <div class="alert-location" v-if="currentAlert.location">
              位置: {{ currentAlert.location }}
            </div>
          </div>
        </div>
        
        <div class="alert-actions">
          <button
            v-if="currentAlert.suggestion"
            @click="showSuggestion"
            class="btn-suggestion"
          >
            <i class="fas fa-lightbulb mr-1"></i>
            建议
          </button>
          <button
            @click="dismissAlert"
            class="btn-dismiss"
          >
            <i class="fas fa-times"></i>
          </button>
        </div>
      </div>
    </Transition>

    <!-- 预警历史面板 -->
    <div v-if="showHistory" class="alert-history-panel">
      <div class="history-header">
        <h3 class="history-title">
          <i class="fas fa-history mr-2"></i>
          预警历史
        </h3>
        <div class="history-controls">
          <select v-model="historyFilter" class="filter-select">
            <option value="all">全部</option>
            <option value="critical">严重</option>
            <option value="error">错误</option>
            <option value="warning">警告</option>
            <option value="info">信息</option>
          </select>
          <button
            @click="clearHistory"
            class="btn-clear"
          >
            <i class="fas fa-trash mr-1"></i>
            清空
          </button>
          <button
            @click="closeHistory"
            class="btn-close"
          >
            <i class="fas fa-times"></i>
          </button>
        </div>
      </div>

      <div class="history-content">
        <div v-if="filteredHistory.length === 0" class="no-history">
          <i class="fas fa-inbox text-gray-400 text-4xl mb-3"></i>
          <p class="text-gray-600">暂无预警历史</p>
        </div>

        <div v-else class="history-list">
          <div
            v-for="(alert, index) in filteredHistory"
            :key="index"
            class="history-item"
            :class="`history-${alert.severity}`"
          >
            <div class="history-icon">
              <i :class="getAlertIcon(alert.severity)"></i>
            </div>
            <div class="history-content">
              <div class="history-message">{{ alert.message }}</div>
              <div class="history-meta">
                <span class="history-type">{{ alert.type }}</span>
                <span class="history-time">{{ formatTime(alert.timestamp) }}</span>
                <span v-if="alert.location" class="history-location">{{ alert.location }}</span>
              </div>
              <div v-if="alert.suggestion" class="history-suggestion">
                <i class="fas fa-lightbulb text-yellow-500 mr-1"></i>
                {{ alert.suggestion }}
              </div>
            </div>
            <div class="history-actions">
              <button
                @click="replayAlert(alert)"
                class="btn-replay"
                title="重新显示"
              >
                <i class="fas fa-redo"></i>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 预警设置面板 -->
    <div v-if="showSettings" class="alert-settings-panel">
      <div class="settings-header">
        <h3 class="settings-title">
          <i class="fas fa-cog mr-2"></i>
          预警设置
        </h3>
        <button
          @click="closeSettings"
          class="btn-close"
        >
          <i class="fas fa-times"></i>
        </button>
      </div>

      <div class="settings-content">
        <div class="setting-group">
          <label class="setting-label">预警级别</label>
          <div class="setting-options">
            <label class="option-item">
              <input
                type="checkbox"
                v-model="alertSettings.enableCritical"
                class="option-checkbox"
              />
              <span class="option-text">严重问题</span>
            </label>
            <label class="option-item">
              <input
                type="checkbox"
                v-model="alertSettings.enableError"
                class="option-checkbox"
              />
              <span class="option-text">错误</span>
            </label>
            <label class="option-item">
              <input
                type="checkbox"
                v-model="alertSettings.enableWarning"
                class="option-checkbox"
              />
              <span class="option-text">警告</span>
            </label>
            <label class="option-item">
              <input
                type="checkbox"
                v-model="alertSettings.enableInfo"
                class="option-checkbox"
              />
              <span class="option-text">信息</span>
            </label>
          </div>
        </div>

        <div class="setting-group">
          <label class="setting-label">显示时间</label>
          <select v-model="alertSettings.displayDuration" class="setting-select">
            <option :value="3000">3秒</option>
            <option :value="5000">5秒</option>
            <option :value="10000">10秒</option>
            <option :value="0">手动关闭</option>
          </select>
        </div>

        <div class="setting-group">
          <label class="setting-label">声音提醒</label>
          <div class="setting-options">
            <label class="option-item">
              <input
                type="checkbox"
                v-model="alertSettings.enableSound"
                class="option-checkbox"
              />
              <span class="option-text">启用声音提醒</span>
            </label>
          </div>
        </div>

        <div class="setting-group">
          <label class="setting-label">位置</label>
          <select v-model="alertSettings.position" class="setting-select">
            <option value="top-right">右上角</option>
            <option value="top-left">左上角</option>
            <option value="bottom-right">右下角</option>
            <option value="bottom-left">左下角</option>
          </select>
        </div>

        <div class="settings-actions">
          <button
            @click="saveSettings"
            class="btn-save"
          >
            <i class="fas fa-save mr-2"></i>
            保存设置
          </button>
          <button
            @click="resetSettings"
            class="btn-reset"
          >
            <i class="fas fa-undo mr-2"></i>
            重置
          </button>
        </div>
      </div>
    </div>

    <!-- 控制按钮 -->
    <div class="alert-controls">
      <button
        @click="toggleHistory"
        class="control-btn"
        :class="{ active: showHistory }"
        title="预警历史"
      >
        <i class="fas fa-history"></i>
        <span class="control-badge" v-if="alertHistory.length > 0">
          {{ alertHistory.length }}
        </span>
      </button>
      <button
        @click="toggleSettings"
        class="control-btn"
        :class="{ active: showSettings }"
        title="预警设置"
      >
        <i class="fas fa-cog"></i>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRealTimeQC } from '@/composables/useRealTimeQC'
import type { QCIssue, QCAlertLevel } from '@/composables/useRealTimeQC'
import { message } from 'ant-design-vue'

// 预警设置接口
interface AlertSettings {
  enableCritical: boolean
  enableError: boolean
  enableWarning: boolean
  enableInfo: boolean
  displayDuration: number
  enableSound: boolean
  position: 'top-right' | 'top-left' | 'bottom-right' | 'bottom-left'
}

// 扩展的预警接口
interface ExtendedQCIssue extends QCIssue {
  timestamp: string
  id: string
}

// 使用实时质控组合式函数
const { alertQueue } = useRealTimeQC()

// 组件状态
const showAlert = ref(false)
const showHistory = ref(false)
const showSettings = ref(false)
const currentAlert = ref<ExtendedQCIssue | null>(null)
const alertHistory = ref<ExtendedQCIssue[]>([])
const historyFilter = ref<string>('all')

// 预警设置
const alertSettings = ref<AlertSettings>({
  enableCritical: true,
  enableError: true,
  enableWarning: true,
  enableInfo: false,
  displayDuration: 5000,
  enableSound: true,
  position: 'top-right'
})

// 定时器
let alertTimer: NodeJS.Timeout | null = null

// 计算属性
const filteredHistory = computed(() => {
  if (historyFilter.value === 'all') {
    return alertHistory.value
  }
  return alertHistory.value.filter(alert => alert.severity === historyFilter.value)
})

// 监听预警队列变化
watch(alertQueue, (newQueue) => {
  if (newQueue.length > 0) {
    const latestAlert = newQueue[0]
    showNewAlert(latestAlert)
  }
}, { deep: true })

// 方法
const showNewAlert = (alert: QCIssue) => {
  // 检查是否启用该级别的预警
  if (!isAlertEnabled(alert.severity)) {
    return
  }

  // 创建扩展的预警对象
  const extendedAlert: ExtendedQCIssue = {
    ...alert,
    timestamp: new Date().toISOString(),
    id: `alert_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  }

  // 添加到历史记录
  alertHistory.value.unshift(extendedAlert)
  
  // 保持历史记录大小
  if (alertHistory.value.length > 100) {
    alertHistory.value = alertHistory.value.slice(0, 100)
  }

  // 显示当前预警
  currentAlert.value = extendedAlert
  showAlert.value = true

  // 播放声音提醒
  if (alertSettings.value.enableSound) {
    playAlertSound(alert.severity)
  }

  // 设置自动关闭定时器
  if (alertSettings.value.displayDuration > 0) {
    if (alertTimer) {
      clearTimeout(alertTimer)
    }
    alertTimer = setTimeout(() => {
      dismissAlert()
    }, alertSettings.value.displayDuration)
  }
}

const isAlertEnabled = (severity: QCAlertLevel): boolean => {
  switch (severity) {
    case 'critical':
      return alertSettings.value.enableCritical
    case 'error':
      return alertSettings.value.enableError
    case 'warning':
      return alertSettings.value.enableWarning
    case 'info':
      return alertSettings.value.enableInfo
    default:
      return false
  }
}

const dismissAlert = () => {
  showAlert.value = false
  currentAlert.value = null
  
  if (alertTimer) {
    clearTimeout(alertTimer)
    alertTimer = null
  }
}

const showSuggestion = () => {
  if (currentAlert.value?.suggestion) {
    message.info(currentAlert.value.suggestion)
  }
}

const toggleHistory = () => {
  showHistory.value = !showHistory.value
  if (showHistory.value) {
    showSettings.value = false
  }
}

const toggleSettings = () => {
  showSettings.value = !showSettings.value
  if (showSettings.value) {
    showHistory.value = false
  }
}

const closeHistory = () => {
  showHistory.value = false
}

const closeSettings = () => {
  showSettings.value = false
}

const clearHistory = () => {
  alertHistory.value = []
  message.success('预警历史已清空')
}

const replayAlert = (alert: ExtendedQCIssue) => {
  currentAlert.value = alert
  showAlert.value = true
  
  if (alertSettings.value.displayDuration > 0) {
    if (alertTimer) {
      clearTimeout(alertTimer)
    }
    alertTimer = setTimeout(() => {
      dismissAlert()
    }, alertSettings.value.displayDuration)
  }
}

const saveSettings = () => {
  // 保存设置到本地存储
  localStorage.setItem('qc_alert_settings', JSON.stringify(alertSettings.value))
  message.success('预警设置已保存')
  closeSettings()
}

const resetSettings = () => {
  alertSettings.value = {
    enableCritical: true,
    enableError: true,
    enableWarning: true,
    enableInfo: false,
    displayDuration: 5000,
    enableSound: true,
    position: 'top-right'
  }
  message.success('预警设置已重置')
}

const loadSettings = () => {
  const saved = localStorage.getItem('qc_alert_settings')
  if (saved) {
    try {
      alertSettings.value = { ...alertSettings.value, ...JSON.parse(saved) }
    } catch (error) {
      console.error('加载预警设置失败:', error)
    }
  }
}

const playAlertSound = (severity: QCAlertLevel) => {
  // 创建音频上下文播放提示音
  try {
    const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)()
    const oscillator = audioContext.createOscillator()
    const gainNode = audioContext.createGain()
    
    oscillator.connect(gainNode)
    gainNode.connect(audioContext.destination)
    
    // 根据严重程度设置不同的音调
    const frequencies = {
      critical: 800,
      error: 600,
      warning: 400,
      info: 300
    }
    
    oscillator.frequency.setValueAtTime(frequencies[severity], audioContext.currentTime)
    oscillator.type = 'sine'
    
    gainNode.gain.setValueAtTime(0.1, audioContext.currentTime)
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3)
    
    oscillator.start(audioContext.currentTime)
    oscillator.stop(audioContext.currentTime + 0.3)
  } catch (error) {
    console.warn('播放预警声音失败:', error)
  }
}

// 工具函数
const getAlertIcon = (severity: QCAlertLevel): string => {
  const icons = {
    critical: 'fas fa-exclamation-circle',
    error: 'fas fa-exclamation-triangle',
    warning: 'fas fa-exclamation',
    info: 'fas fa-info-circle'
  }
  return icons[severity]
}

const getAlertTitle = (severity: QCAlertLevel): string => {
  const titles = {
    critical: '严重质控问题',
    error: '质控错误',
    warning: '质控警告',
    info: '质控信息'
  }
  return titles[severity]
}

const formatTime = (timestamp: string): string => {
  const date = new Date(timestamp)
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

// 生命周期
onMounted(() => {
  loadSettings()
  console.log('实时质控预警组件已加载')
})

onUnmounted(() => {
  if (alertTimer) {
    clearTimeout(alertTimer)
  }
})
</script>

<style scoped>
.realtime-qc-alert {
  @apply fixed inset-0 pointer-events-none z-50;
}

/* 浮动预警通知 */
.alert-notification {
  @apply fixed pointer-events-auto bg-white rounded-lg shadow-lg border-l-4 p-4 max-w-md;
  top: 20px;
  right: 20px;
  z-index: 1000;
}

.alert-critical {
  @apply border-red-500 bg-red-50;
}

.alert-error {
  @apply border-orange-500 bg-orange-50;
}

.alert-warning {
  @apply border-yellow-500 bg-yellow-50;
}

.alert-info {
  @apply border-blue-500 bg-blue-50;
}

.alert-content {
  @apply flex items-start space-x-3 mb-3;
}

.alert-icon {
  @apply text-xl mt-0.5;
}

.alert-critical .alert-icon {
  @apply text-red-500;
}

.alert-error .alert-icon {
  @apply text-orange-500;
}

.alert-warning .alert-icon {
  @apply text-yellow-500;
}

.alert-info .alert-icon {
  @apply text-blue-500;
}

.alert-text {
  @apply flex-1;
}

.alert-title {
  @apply font-semibold text-gray-800 mb-1;
}

.alert-message {
  @apply text-gray-700 text-sm mb-1;
}

.alert-location {
  @apply text-gray-500 text-xs;
}

.alert-actions {
  @apply flex items-center justify-end space-x-2;
}

.btn-suggestion {
  @apply px-3 py-1 text-xs bg-yellow-100 text-yellow-800 hover:bg-yellow-200 rounded transition-colors duration-200 flex items-center;
}

.btn-dismiss {
  @apply p-1 text-gray-400 hover:text-red-600 rounded transition-colors duration-200;
}

/* 预警历史面板 */
.alert-history-panel {
  @apply fixed pointer-events-auto bg-white rounded-lg shadow-xl border border-gray-200 max-w-md max-h-96 overflow-hidden;
  top: 80px;
  right: 20px;
  z-index: 999;
}

.history-header {
  @apply flex items-center justify-between p-4 bg-gray-50 border-b border-gray-200;
}

.history-title {
  @apply text-lg font-semibold text-gray-800 flex items-center;
}

.history-controls {
  @apply flex items-center space-x-2;
}

.filter-select {
  @apply px-2 py-1 text-xs border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-blue-500;
}

.btn-clear {
  @apply px-2 py-1 text-xs bg-red-100 text-red-700 hover:bg-red-200 rounded transition-colors duration-200 flex items-center;
}

.btn-close {
  @apply p-1 text-gray-400 hover:text-red-600 rounded transition-colors duration-200;
}

.history-content {
  @apply max-h-80 overflow-y-auto;
}

.no-history {
  @apply text-center py-12;
}

.history-list {
  @apply divide-y divide-gray-100;
}

.history-item {
  @apply flex items-start space-x-3 p-3 hover:bg-gray-50 transition-colors duration-200;
}

.history-critical {
  @apply bg-red-50;
}

.history-error {
  @apply bg-orange-50;
}

.history-warning {
  @apply bg-yellow-50;
}

.history-info {
  @apply bg-blue-50;
}

.history-icon {
  @apply text-sm mt-0.5;
}

.history-critical .history-icon {
  @apply text-red-500;
}

.history-error .history-icon {
  @apply text-orange-500;
}

.history-warning .history-icon {
  @apply text-yellow-500;
}

.history-info .history-icon {
  @apply text-blue-500;
}

.history-content {
  @apply flex-1;
}

.history-message {
  @apply text-sm text-gray-800 mb-1;
}

.history-meta {
  @apply flex items-center space-x-2 text-xs text-gray-500 mb-1;
}

.history-type {
  @apply px-1.5 py-0.5 bg-gray-100 text-gray-700 rounded;
}

.history-suggestion {
  @apply text-xs text-gray-600 mt-1 pl-4 border-l-2 border-yellow-300;
}

.history-actions {
  @apply flex items-center;
}

.btn-replay {
  @apply p-1 text-gray-400 hover:text-blue-600 rounded transition-colors duration-200;
}

/* 预警设置面板 */
.alert-settings-panel {
  @apply fixed pointer-events-auto bg-white rounded-lg shadow-xl border border-gray-200 w-80;
  top: 80px;
  right: 20px;
  z-index: 999;
}

.settings-header {
  @apply flex items-center justify-between p-4 bg-gray-50 border-b border-gray-200;
}

.settings-title {
  @apply text-lg font-semibold text-gray-800 flex items-center;
}

.settings-content {
  @apply p-4 space-y-4 max-h-80 overflow-y-auto;
}

.setting-group {
  @apply space-y-2;
}

.setting-label {
  @apply block text-sm font-medium text-gray-700;
}

.setting-options {
  @apply space-y-2;
}

.option-item {
  @apply flex items-center space-x-2 cursor-pointer;
}

.option-checkbox {
  @apply rounded border-gray-300 text-blue-600 focus:ring-blue-500;
}

.option-text {
  @apply text-sm text-gray-700;
}

.setting-select {
  @apply w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500;
}

.settings-actions {
  @apply flex items-center justify-end space-x-2 pt-4 border-t border-gray-200;
}

.btn-save {
  @apply px-3 py-2 bg-blue-600 text-white hover:bg-blue-700 rounded-lg transition-colors duration-200 flex items-center text-sm;
}

.btn-reset {
  @apply px-3 py-2 bg-gray-200 text-gray-700 hover:bg-gray-300 rounded-lg transition-colors duration-200 flex items-center text-sm;
}

/* 控制按钮 */
.alert-controls {
  @apply fixed pointer-events-auto flex flex-col space-y-2;
  bottom: 20px;
  right: 20px;
  z-index: 998;
}

.control-btn {
  @apply relative w-12 h-12 bg-white hover:bg-gray-50 border border-gray-200 rounded-full shadow-lg flex items-center justify-center text-gray-600 hover:text-blue-600 transition-all duration-200;
}

.control-btn.active {
  @apply bg-blue-50 text-blue-600 border-blue-200;
}

.control-badge {
  @apply absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center;
}

/* 动画效果 */
.alert-slide-enter-active,
.alert-slide-leave-active {
  transition: all 0.3s ease;
}

.alert-slide-enter-from {
  transform: translateX(100%);
  opacity: 0;
}

.alert-slide-leave-to {
  transform: translateX(100%);
  opacity: 0;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .alert-notification,
  .alert-history-panel,
  .alert-settings-panel {
    @apply left-4 right-4 max-w-none;
  }

  .alert-controls {
    @apply bottom-4 right-4;
  }

  .control-btn {
    @apply w-10 h-10;
  }
}

/* 位置变体 */
.alert-notification.position-top-left {
  top: 20px;
  left: 20px;
  right: auto;
}

.alert-notification.position-bottom-right {
  top: auto;
  bottom: 20px;
  right: 20px;
}

.alert-notification.position-bottom-left {
  top: auto;
  bottom: 20px;
  left: 20px;
  right: auto;
}
</style>
