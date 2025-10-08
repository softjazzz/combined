// 消息通知服务适配器
// 适配Python FastAPI后端的消息通知功能，支持WebSocket和Supabase实时功能

import type {
  QCNotification,
  MessageType,
  MessagePriority,
  MessageAction
} from '@/types/audit-module'

import { unifiedAPIClient, type PaginatedResponse } from './unified-api-client'
import { useAuthStore } from '@/stores/auth'

// WebSocket连接管理
class WebSocketManager {
  private ws: WebSocket | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000
  private heartbeatInterval: number | null = null
  private messageHandlers: Map<string, Function[]> = new Map()

  constructor(private userId: string, private authToken: string) {}

  async connect(): Promise<void> {
    try {
      const wsUrl = `${import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8001'}/api/notifications/ws/${this.userId}?token=${this.authToken}`
      
      this.ws = new WebSocket(wsUrl)
      
      this.ws.onopen = () => {
        console.log('WebSocket连接已建立')
        this.reconnectAttempts = 0
        this.startHeartbeat()
        this.emit('connected', { userId: this.userId })
      }
      
      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          this.handleMessage(message)
        } catch (error) {
          console.error('解析WebSocket消息失败:', error)
        }
      }
      
      this.ws.onclose = (event) => {
        console.log('WebSocket连接已关闭:', event.code, event.reason)
        this.stopHeartbeat()
        this.emit('disconnected', { code: event.code, reason: event.reason })
        
        if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.scheduleReconnect()
        }
      }
      
      this.ws.onerror = (error) => {
        console.error('WebSocket连接错误:', error)
        this.emit('error', error)
      }
      
    } catch (error) {
      console.error('建立WebSocket连接失败:', error)
      throw error
    }
  }

  disconnect(): void {
    if (this.ws) {
      this.stopHeartbeat()
      this.ws.close(1000, '主动断开连接')
      this.ws = null
    }
  }

  private scheduleReconnect(): void {
    this.reconnectAttempts++
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1)
    
    console.log(`${delay}ms后尝试重连 (${this.reconnectAttempts}/${this.maxReconnectAttempts})`)
    
    setTimeout(() => {
      this.connect().catch(error => {
        console.error('重连失败:', error)
      })
    }, delay)
  }

  private startHeartbeat(): void {
    this.heartbeatInterval = window.setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.send({ type: 'ping' })
      }
    }, 30000) // 30秒心跳
  }

  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval)
      this.heartbeatInterval = null
    }
  }

  private handleMessage(message): void {
    const { type, data } = message
    
    switch (type) {
      case 'notification':
        this.emit('notification', data)
        break
      case 'pong':
        // 心跳响应
        break
      case 'connection_established':
        console.log('WebSocket连接确认:', data.message)
        break
      case 'read_confirmed':
        this.emit('read_confirmed', data)
        break
      case 'unread_count':
        this.emit('unread_count', data)
        break
      case 'error':
        console.error('服务器错误:', data.message)
        this.emit('server_error', data)
        break
      default:
        console.log('未知消息类型:', type, data)
    }
  }

  send(message: unknown): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message))
    } else {
      console.warn('WebSocket未连接，无法发送消息')
    }
  }

  on(event: string, handler: Function): void {
    if (!this.messageHandlers.has(event)) {
      this.messageHandlers.set(event, : unknown[])
    }
    this.messageHandlers.get(event)!.push(handler)
  }

  off(event: string, handler: Function): void {
    const handlers = this.messageHandlers.get(event)
    if (handlers) {
      const index = handlers.indexOf(handler)
      if (index > -1) {
        handlers.splice(index, 1)
      }
    }
  }

  private emit(event: string, data: unknown): void {
    const handlers = this.messageHandlers.get(event)
    if (handlers) {
      handlers.forEach(handler => {
        try {
          handler(data)
        } catch (error) {
          console.error('消息处理器执行失败:', error)
        }
      })
    }
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }
}

export class NotificationServiceAdapter {
  private wsManager: WebSocketManager | null = null
  private eventHandlers: Map<string, Function[]> = new Map()

  /**
   * 初始化实时通信
   */
  async initializeRealTime(userId: string, userType: string): Promise<void> {
    try {
      const authStore = useAuthStore()
      const authToken = authStore.token || localStorage.getItem('auth_token') || ''
      
      if (!authToken) {
        console.warn('未找到认证令牌，无法建立WebSocket连接')
        return
      }

      this.wsManager = new WebSocketManager(userId, authToken)
      
      // 设置事件监听
      this.wsManager.on('connected', () => {
        this.emit('connected', { userId, userType })
      })
      
      this.wsManager.on('disconnected',  (data) => {
        this.emit('disconnected', data)
      })
      
      this.wsManager.on('notification',  (notification: unknown) => {
        this.emit('new-notification', notification)
        
        // 根据优先级显示不同的通知
        if (notification.priority === 'urgent') {
          this.emit('urgent-notification', notification)
        }
      })
      
      this.wsManager.on('read_confirmed',  (data: unknown) => {
        this.emit('notification-read', data)
      })
      
      this.wsManager.on('unread_count',  (data: unknown) => {
        this.emit('unread-count-updated', data)
      })
      
      await this.wsManager.connect()
      
      console.log('实时通信初始化完成')
      
    } catch (error) {
      console.error('初始化实时通信失败:', error)
      throw error
    }
  }

  /**
   * 发送通知
   */
  async sendNotification(
    recipientId: string,
    recipientType: 'clinician' | 'reviewer' | 'admin',
    type: MessageType,
    relatedData: Record<string, unknown>,
    customContent?: {
      title?: string
      content?: string
      summary?: string
      priority?: MessagePriority
      actions?: MessageAction[]
    }
  ): Promise<QCNotification> { try {
      const notificationData = {
        type,
        recipient_id: recipientId,
        recipient_type: recipientType,
        title: customContent?.title || '',
        content: customContent?.content || '',
        summary: customContent?.summary,
        priority: customContent?.priority || MessagePriority.NORMAL,
        related_data: relatedData,
        actions: customContent?.actions || [],
        auto_expire: false
      }

      const notification = await unifiedAPIClient.sendNotification(notificationData, true)
      
      console.log('通知发送成功:', notification.title)
      return notification
      
    } catch (error: unknown) {
      console.error('发送通知失败:', error)
      throw new Error(`发送通知失败: ${error.message}`)
    }
  }

  /**
   * 批量发送通知
   */
  async batchSendNotifications(
    notifications: Array<{
      recipientId: string
      recipientType: 'clinician' | 'reviewer' | 'admin'
      type: MessageType
      relatedData: Record<string, unknown>
      customContent?: {
        title?: string
        content?: string
        summary?: string
        priority?: MessagePriority
        actions?: MessageAction[]
      }
    }>
  ): Promise<QCNotification[]> { try {
      const notificationsData = notifications.map(notification => ({
        type: notification.type,
        recipient_id: notification.recipientId,
        recipient_type: notification.recipientType,
        title: notification.customContent?.title || '',
        content: notification.customContent?.content || '',
        summary: notification.customContent?.summary,
        priority: notification.customContent?.priority || MessagePriority.NORMAL,
        related_data: notification.relatedData,
        actions: notification.customContent?.actions || [],
        auto_expire: false
      }))

      const results = await unifiedAPIClient.batchSendNotifications(notificationsData)
      
      console.log(`批量发送 ${results.length} 条通知成功`)
      return results
      
    } catch (error) {
      console.error('批量发送通知失败:', error)
      throw new Error(`批量发送通知失败: ${error.message}`)
    }
  }

  /**
   * 获取用户通知列表
   */
  async getUserNotifications(
    userId: string,
    options: {
      page?: number
      pageSize?: number
      status?: string[]
      types?: MessageType[]
      priority?: MessagePriority
      unreadOnly?: boolean
    } = {}
  ): Promise<{ notifications: QCNotification[]; total: number }> {
    try {
      const params = {
        page: options.page || 1,
        page_size: options.pageSize || 20,
        status: options.status,
        types: options.types,
        priority: options.priority,
        unread_only: options.unreadOnly || false
      }

      const response = await unifiedAPIClient.getUserNotifications(params)
      
      return {
        notifications: response.items,
        total: response.total
      }
      
    } catch (error: unknown) {
      console.error('获取用户通知失败:', error)
      throw new Error(`获取用户通知失败: ${error.message}`)
    }
  }

  /**
   * 标记通知为已读
   */
  async markAsRead(notificationId: string): Promise<void> {
    try {
      await unifiedAPIClient.markNotificationAsRead(notificationId)
      
      // 通过WebSocket通知服务器
      if (this.wsManager?.isConnected()) {
        this.wsManager.send({
          type: 'mark_read',
          data: { notification_id: notificationId }
        })
      }
      
      console.log('消息已标记为已读')
      
    } catch (error: unknown) {
      console.error('标记已读失败:', error)
      throw new Error(`标记已读失败: ${error.message}`)
    }
  }

  /**
   * 标记通知为已处理
   */
  async markAsProcessed(notificationId: string): Promise<void> {
    try {
      await unifiedAPIClient.markNotificationAsProcessed(notificationId)
      console.log('消息已标记为已处理')
    } catch (error: unknown) {
      console.error('标记已处理失败:', error)
      throw new Error(`标记已处理失败: ${error.message}`)
    }
  }

  /**
   * 批量标记为已读
   */
  async batchMarkAsRead(notificationIds: string[]): Promise<void> {
    try {
      await unifiedAPIClient.batchMarkAsRead(notificationIds)
      console.log(`批量标记 ${notificationIds.length} 条消息为已读`)
    } catch (error: unknown) {
      console.error('批量标记已读失败:', error)
      throw new Error(`批量标记已读失败: ${error.message}`)
    }
  }

  /**
   * 获取通知统计信息
   */
  async getNotificationStats(): Promise<unknown> {
    try {
      return await unifiedAPIClient.getNotificationStats()
    } catch (error: unknown) {
      console.error('获取通知统计失败:', error)
      return {
        connection_stats: { connected_users: 0, total_connections: 0 },
        user_stats: { total_notifications: 0, unread_count: 0 }
      }
    }
  }

  /**
   * 发送测试通知
   */
  async sendTestNotification(
    recipientId: string,
    messageType: MessageType = MessageType.SYSTEM_ANNOUNCEMENT,
    priority: MessagePriority = MessagePriority.NORMAL
  ): Promise<QCNotification> {
    try {
      return await unifiedAPIClient.sendTestNotification(recipientId, messageType, priority)
    } catch (error: unknown) {
      console.error('发送测试通知失败:', error)
      throw new Error(`发送测试通知失败: ${error.message}`)
    }
  }

  /**
   * 事件监听
   */
  on(event: string, handler: Function): void {
    if (!this.eventHandlers.has(event)) {
      this.eventHandlers.set(event, : unknown[])
    }
    this.eventHandlers.get(event)!.push(handler)
  }

  off(event: string, handler: Function): void {
    const handlers = this.eventHandlers.get(event)
    if (handlers) {
      const index = handlers.indexOf(handler)
      if (index > -1) {
        handlers.splice(index, 1)
      }
    }
  }

  private emit(event: string, data: unknown): void {
    const handlers = this.eventHandlers.get(event)
    if (handlers) {
      handlers.forEach(handler => {
        try {
          handler(data)
        } catch (error) {
          console.error('事件处理器执行失败:', error)
        }
      })
    }
  }

  /**
   * 清理资源
   */
  cleanup(): void {
    if (this.wsManager) {
      this.wsManager.disconnect()
      this.wsManager = null
    }
    this.eventHandlers.clear()
    console.log('通知服务资源已清理')
  }

  /**
   * 获取连接状态
   */
  isConnected(): boolean {
    return this.wsManager?.isConnected() || false
  }
}

// 导出单例实例
export const notificationService = new NotificationServiceAdapter()
