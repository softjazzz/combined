/**
 * WebSocket连接管理器
 * 优化实时质控监控的WebSocket连接性能
 */

import { supabase } from '@/lib/supabase'

// WebSocket连接状态
export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

// 连接配置
interface ConnectionConfig {
  maxRetries: number
  retryDelay: number
  heartbeatInterval: number
  reconnectOnError: boolean
  bufferSize: number
}

// 消息类型
interface WebSocketMessage {
  id: string
  type: string
  payload: Record<string, unknown>
  timestamp: number
  priority: 'low' | 'normal' | 'high' | 'critical'
}

// 连接统计
interface ConnectionStats {
  totalMessages: number
  messagesPerSecond: number
  averageLatency: number
  reconnectCount: number
  lastHeartbeat: number
  uptime: number
}

interface RealtimeChannelLike {
  on(
    event: string,
    filterOrCallback: unknown,
    callback?: (payload: unknown) => void,
  ): RealtimeChannelLike
}

export class WebSocketManager {
  private connections: Map<string, any> = new Map()
  private messageQueue: Map<string, WebSocketMessage[]> = new Map()
  private connectionStats: Map<string, ConnectionStats> = new Map()
  private heartbeatTimers: Map<string, NodeJS.Timeout> = new Map()
  private reconnectTimers: Map<string, NodeJS.Timeout> = new Map()

  private config: ConnectionConfig = {
    maxRetries: 5,
    retryDelay: 1000,
    heartbeatInterval: 30000, // 30秒
    reconnectOnError: true,
    bufferSize: 100,
  }

  /**
   * 创建优化的WebSocket连接
   */
  async createConnection(
    channelName: string,
    config?: Partial<ConnectionConfig>,
  ): Promise<unknown> {
    try {
      console.log(`🔌 创建WebSocket连接: ${channelName}`)

      // 合并配置
      const finalConfig = { ...this.config, ...config }

      // 如果连接已存在，先关闭
      if (this.connections.has(channelName)) {
        await this.closeConnection(channelName)
      }

      // 初始化连接统计
      this.connectionStats.set(channelName, {
        totalMessages: 0,
        messagesPerSecond: 0,
        averageLatency: 0,
        reconnectCount: 0,
        lastHeartbeat: Date.now(),
        uptime: Date.now(),
      })

      // 初始化消息队列
      this.messageQueue.set(channelName, [])

      // 创建Supabase实时连接
      const channel = supabase.channel(channelName, {
        config: {
          presence: {
            key: `user_${Date.now()}`,
          },
        },
      })

      // 设置连接事件监听
      this.setupConnectionEvents(channel, channelName, finalConfig)

      // 订阅连接
      const subscription = await channel.subscribe((status) => {
        console.log(`📡 连接状态变化 [${channelName}]:`, status)
        this.handleConnectionStatusChange(channelName, status)
      })

      // 保存连接
      this.connections.set(channelName, channel)

      // 启动心跳检测
      this.startHeartbeat(channelName, finalConfig.heartbeatInterval)

      console.log(`✅ WebSocket连接创建成功: ${channelName}`)
      return channel
    } catch (error) {
      console.error(`❌ 创建WebSocket连接失败 [${channelName}]:`, error)
      throw error
    }
  }

  /**
   * 设置连接事件监听
   */
  private setupConnectionEvents(
    channel: RealtimeChannelLike,
    channelName: string,
    config: ConnectionConfig,
  ) {
    // 监听数据库变化
    channel.on('postgres_changes', { event: '*', schema: 'public' }, (payload: unknown) => {
      this.handleMessage(channelName, {
        id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        type: 'postgres_changes',
        payload: payload as Record<string, unknown>,
        timestamp: Date.now(),
        priority: this.determinePriority(payload as { eventType?: string; table?: string }),
      })
    })

    // 监听自定义事件
    channel.on('realtime_qc_event', (payload: unknown) => {
      this.handleMessage(channelName, {
        id: `qc_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        type: 'realtime_qc_event',
        payload: payload as Record<string, unknown>,
        timestamp: Date.now(),
        priority: 'high',
      })
    })

    // 监听心跳响应
    channel.on('heartbeat_response', (payload: unknown) => {
      const timestamp =
        typeof payload === 'object' &&
        payload !== null &&
        'timestamp' in payload &&
        typeof (payload as { timestamp: unknown }).timestamp === 'number'
          ? (payload as { timestamp: number }).timestamp
          : Date.now()
      this.updateHeartbeat(channelName, timestamp)
    })
  }

  /**
   * 处理连接状态变化
   */
  private handleConnectionStatusChange(channelName: string, status: string) {
    const stats = this.connectionStats.get(channelName)
    if (!stats) return

    switch (status) {
      case 'SUBSCRIBED':
        console.log(`🟢 连接已建立: ${channelName}`)
        break
      case 'CHANNEL_ERROR':
        console.log(`🔴 连接错误: ${channelName}`)
        if (this.config.reconnectOnError) {
          this.scheduleReconnect(channelName)
        }
        break
      case 'TIMED_OUT':
        console.log(`⏰ 连接超时: ${channelName}`)
        this.scheduleReconnect(channelName)
        break
      case 'CLOSED':
        console.log(`🔴 连接已关闭: ${channelName}`)
        break
    }
  }

  /**
   * 处理接收到的消息
   */
  private handleMessage(channelName: string, message: WebSocketMessage) {
    const stats = this.connectionStats.get(channelName)
    if (!stats) return

    // 更新统计信息
    stats.totalMessages++

    // 计算延迟
    const latency = Date.now() - message.timestamp
    stats.averageLatency = (stats.averageLatency + latency) / 2

    // 根据优先级处理消息
    if (message.priority === 'critical') {
      // 立即处理关键消息
      this.processMessage(channelName, message)
    } else {
      // 将消息加入队列
      const queue = this.messageQueue.get(channelName) || []
      queue.push(message)

      // 保持队列大小
      if (queue.length > this.config.bufferSize) {
        queue.shift() // 移除最老的消息
      }

      this.messageQueue.set(channelName, queue)

      // 批量处理消息
      this.processBatchMessages(channelName)
    }
  }

  /**
   * 处理单个消息
   */
  private processMessage(channelName: string, message: WebSocketMessage) {
    // 触发自定义事件
    const event = new CustomEvent(`ws_message_${channelName}`, {
      detail: message,
    })
    window.dispatchEvent(event)
  }

  /**
   * 批量处理消息
   */
  private processBatchMessages(channelName: string) {
    const queue = this.messageQueue.get(channelName) || []
    if (queue.length === 0) return

    // 按优先级排序
    queue.sort((a, b) => {
      const priorityOrder = { critical: 4, high: 3, normal: 2, low: 1 }
      return priorityOrder[b.priority] - priorityOrder[a.priority]
    })

    // 批量处理
    const batchSize = Math.min(10, queue.length)
    const batch = queue.splice(0, batchSize)

    batch.forEach((message) => {
      this.processMessage(channelName, message)
    })

    this.messageQueue.set(channelName, queue)
  }

  /**
   * 确定消息优先级
   */
  private determinePriority(payload: {
    eventType?: string
    table?: string
  }): WebSocketMessage['priority'] {
    if (payload.eventType === 'INSERT' && payload.table === 'medical_records') {
      return 'high' // 新病案记录优先级高
    }
    if (payload.eventType === 'UPDATE' && payload.table === 'qc_results') {
      return 'normal' // 质控结果更新正常优先级
    }
    if (payload.eventType === 'DELETE') {
      return 'low' // 删除操作优先级低
    }
    return 'normal'
  }

  /**
   * 启动心跳检测
   */
  private startHeartbeat(channelName: string, interval: number) {
    const timer = setInterval(() => {
      const channel = this.connections.get(channelName)
      if (channel) {
        // 发送心跳
        channel.send({
          type: 'heartbeat',
          timestamp: Date.now(),
        })
      }
    }, interval)

    this.heartbeatTimers.set(channelName, timer)
  }

  /**
   * 更新心跳时间
   */
  private updateHeartbeat(channelName: string, timestamp: number) {
    const stats = this.connectionStats.get(channelName)
    if (stats) {
      stats.lastHeartbeat = timestamp
    }
  }

  /**
   * 安排重连
   */
  private scheduleReconnect(channelName: string) {
    const stats = this.connectionStats.get(channelName)
    if (!stats) return

    if (stats.reconnectCount >= this.config.maxRetries) {
      console.error(`❌ 达到最大重连次数，停止重连: ${channelName}`)
      return
    }

    const delay = this.config.retryDelay * Math.pow(2, stats.reconnectCount) // 指数退避

    console.log(`🔄 安排重连 [${channelName}]: ${delay}ms 后重试`)

    const timer = setTimeout(async () => {
      try {
        stats.reconnectCount++
        await this.createConnection(channelName)
      } catch (error) {
        console.error(`重连失败 [${channelName}]:`, error)
        this.scheduleReconnect(channelName) // 继续重连
      }
    }, delay)

    this.reconnectTimers.set(channelName, timer)
  }

  /**
   * 获取连接统计
   */
  getConnectionStats(channelName: string): ConnectionStats | null {
    const stats = this.connectionStats.get(channelName)
    if (!stats) return null

    // 计算运行时间
    stats.uptime = Date.now() - stats.uptime

    // 计算每秒消息数
    if (stats.uptime > 0) {
      stats.messagesPerSecond = stats.totalMessages / (stats.uptime / 1000)
    }

    return { ...stats }
  }

  /**
   * 获取所有连接统计
   */
  getAllConnectionStats(): Map<string, ConnectionStats> {
    const allStats = new Map<string, ConnectionStats>()

    for (const [channelName, stats] of this.connectionStats) {
      allStats.set(channelName, this.getConnectionStats(channelName)!)
    }

    return allStats
  }

  /**
   * 关闭连接
   */
  async closeConnection(channelName: string): Promise<void> {
    try {
      console.log(`🔌 关闭WebSocket连接: ${channelName}`)

      // 关闭连接
      const channel = this.connections.get(channelName)
      if (channel) {
        await channel.unsubscribe()
        this.connections.delete(channelName)
      }

      // 清理定时器
      const heartbeatTimer = this.heartbeatTimers.get(channelName)
      if (heartbeatTimer) {
        clearInterval(heartbeatTimer)
        this.heartbeatTimers.delete(channelName)
      }

      const reconnectTimer = this.reconnectTimers.get(channelName)
      if (reconnectTimer) {
        clearTimeout(reconnectTimer)
        this.reconnectTimers.delete(channelName)
      }

      // 清理数据
      this.messageQueue.delete(channelName)
      this.connectionStats.delete(channelName)

      console.log(`✅ WebSocket连接已关闭: ${channelName}`)
    } catch (error) {
      console.error(`❌ 关闭WebSocket连接失败 [${channelName}]:`, error)
    }
  }

  /**
   * 关闭所有连接
   */
  async closeAllConnections(): Promise<void> {
    const channelNames = Array.from(this.connections.keys())

    await Promise.all(channelNames.map((channelName) => this.closeConnection(channelName)))

    console.log('✅ 所有WebSocket连接已关闭')
  }

  /**
   * 监听连接消息
   */
  onMessage(channelName: string, callback: (message: WebSocketMessage) => void): () => void {
    const eventHandler = (event: CustomEvent) => {
      callback(event.detail)
    }

    window.addEventListener(`ws_message_${channelName}`, eventHandler as EventListener)

    // 返回取消监听的函数
    return () => {
      window.removeEventListener(`ws_message_${channelName}`, eventHandler as EventListener)
    }
  }

  /**
   * 发送消息
   */
  sendMessage(channelName: string, type: string, payload: unknown): boolean {
    const channel = this.connections.get(channelName)
    if (!channel) {
      console.error(`❌ 连接不存在: ${channelName}`)
      return false
    }

    try {
      channel.send({
        type,
        payload,
        timestamp: Date.now(),
      })
      return true
    } catch (error) {
      console.error(`❌ 发送消息失败 [${channelName}]:`, error)
      return false
    }
  }
}

// 创建全局WebSocket管理器实例
export const wsManager = new WebSocketManager()

// 在窗口关闭时清理连接
if (typeof window !== 'undefined') {
  window.addEventListener('beforeunload', () => {
    wsManager.closeAllConnections()
  })
}
