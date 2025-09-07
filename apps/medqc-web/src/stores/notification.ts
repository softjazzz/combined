/**
 * 通知系统状态管理
 * 管理全局通知消息的显示和状态
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Notification } from '../types'

export const useNotificationStore = defineStore('notification', () => {
  // 状态
  const notifications = ref<Notification[]>([])
  const maxNotifications = ref(5) // 最大显示通知数量
  const defaultDuration = ref(5000) // 默认显示时长

  // 计算属性
  const unreadCount = computed(() => 
    notifications.value.filter(n => !n.read).length
  )

  const hasNotifications = computed(() => 
    notifications.value.length > 0
  )

  const latestNotification = computed(() => 
    notifications.value[0] || null
  )

  // 添加通知
  const addNotification = (notification: Omit<Notification, 'id' | 'timestamp'>) => {
    const newNotification: Notification = {
      ...notification,
      id: `notification-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date().toISOString(),
      read: false
    }

    // 添加到数组开头
    notifications.value.unshift(newNotification)

    // 限制最大数量
    if (notifications.value.length > maxNotifications.value) {
      notifications.value = notifications.value.slice(0, maxNotifications.value)
    }

    // 自动移除（如果设置了duration）
    const duration = notification.duration ?? defaultDuration.value
    if (duration > 0) {
      setTimeout(() => {
        removeNotification(newNotification.id)
      }, duration)
    }

    return newNotification
  }

  // 移除通知
  const removeNotification = (id: string) => {
    const index = notifications.value.findIndex(n => n.id === id)
    if (index > -1) {
      notifications.value.splice(index, 1)
    }
  }

  // 标记为已读
  const markAsRead = (id: string) => {
    const notification = notifications.value.find(n => n.id === id)
    if (notification) {
      notification.read = true
    }
  }

  // 标记所有为已读
  const markAllAsRead = () => {
    notifications.value.forEach(n => {
      n.read = true
    })
  }

  // 清空所有通知
  const clearAll = () => {
    notifications.value = []
  }

  // 快捷方法
  const success = (title: string, message?: string, duration?: number) => {
    return addNotification({
      type: 'success',
      title,
      message,
      duration
    })
  }

  const error = (title: string, message?: string, duration?: number) => {
    return addNotification({
      type: 'error',
      title,
      message,
      duration: duration ?? 0 // 错误通知默认不自动消失
    })
  }

  const warning = (title: string, message?: string, duration?: number) => {
    return addNotification({
      type: 'warning',
      title,
      message,
      duration
    })
  }

  const info = (title: string, message?: string, duration?: number) => {
    return addNotification({
      type: 'info',
      title,
      message,
      duration
    })
  }

  return {
    // 状态
    notifications: computed(() => notifications.value),
    maxNotifications,
    defaultDuration,
    
    // 计算属性
    unreadCount,
    hasNotifications,
    latestNotification,
    
    // 方法
    addNotification,
    removeNotification,
    markAsRead,
    markAllAsRead,
    clearAll,
    
    // 快捷方法
    success,
    error,
    warning,
    info
  }
}) 