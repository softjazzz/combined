// 消息通知服务
// 基于Supabase实时功能和LLM集成的智能消息通知系统

import type {
  QCNotification,
  MessageType,
  MessagePriority,
  RecipientType,
  MessageAction,
  NotificationRelatedData,
  UserNotificationPreferences
} from '@/types/audit-module'

import { supabase } from '@/lib/supabase'
import { dynamicPromptGenerator } from './dynamic-prompt-generator'
import { intelligentQCCache } from './intelligent-cache'

// 智能消息生成服务
class IntelligentMessageGenerator {
  async generateSmartNotification(
    type: MessageType,
    recipientType: RecipientType,
    relatedData: NotificationRelatedData,
    context?: any
  ): Promise<Partial<QCNotification>> {
    
    console.log(`生成智能消息: ${type} -> ${recipientType}`)

    try {
      // 使用现有的DynamicPromptGenerator生成消息内容
      const prompt = await dynamicPromptGenerator.generatePrompt({
        id: 'notification-gen',
        rule_code: 'NOTIFICATION_GEN',
        name: '智能消息生成',
        category: 'notification',
        quality_logic: {
          check_type: 'content_analysis',
          llm_prompt_template: this.buildNotificationPrompt(type, recipientType, relatedData, context)
        }
      } as any, { patientId: relatedData.patient_id || 'unknown',
        documents: context?.documents || [],
        executionId: 'notification-gen'
      })

      // 解析生成的内容
      const generatedContent = await this.parseGeneratedContent(prompt.userPrompt, type)
      
      return {
        type,
        title: generatedContent.title,
        content: generatedContent.content,
        summary: generatedContent.summary,
        priority: generatedContent.priority,
        actions: generatedContent.actions,
        related_data: relatedData
      }

    } catch (error) {
      console.warn('智能消息生成失败，使用默认模板:', error)
      return this.generateDefaultNotification(type, recipientType, relatedData)
    }
  }

  private buildNotificationPrompt(
    type: MessageType,
    recipientType: RecipientType,
    relatedData: NotificationRelatedData,
    context?: any
  ): string {
    
    const basePrompt = `
请生成一条专业的医疗质控消息通知：

消息类型：${type}
接收者类型：${recipientType}
关联数据：${JSON.stringify(relatedData, null, 2)}
`

    const typeSpecificPrompts = {
      'rectification_required': `
这是一条整改要求通知，需要包含：
1. 明确的问题描述
2. 具体的整改要求
3. 整改建议和参考标准
4. 预期完成时间
5. 联系方式

请生成专业、清晰、有建设性的通知内容。
`,
      'audit_result': `
这是一条审核结果通知，需要包含：
1. 审核结论概述
2. 主要发现和问题
3. 评分情况
4. 后续处理建议

请保持客观、专业的语调。
`,
      'task_assigned': `
这是一条任务分配通知，需要包含：
1. 任务基本信息
2. 工作要求和标准
3. 完成时间要求
4. 注意事项

请使用鼓励性和指导性的语言。
`
    }

    const specificPrompt = typeSpecificPrompts[type] || '请生成相应的通知内容。'

    return `${basePrompt}\n${specificPrompt}\n
请严格按照以下JSON格式返回：
{
  "title": "消息标题",
  "content": "详细内容",
  "summary": "内容摘要（50字以内）",
  "priority": "消息优先级(low/normal/high/urgent)",
  "actions": [
    {
      "id": "action_id",
      "label": "操作标签",
      "type": "primary|secondary|danger",
      "action": "navigate|api_call|modal",
      "config": {
        "url": "跳转链接",
        "params": {}
      }
    }
  ]
}
`
  }

  private async parseGeneratedContent(content: string, type: MessageType): Promise<unknown> {
    try {
      // 尝试解析JSON响应
      const jsonMatch = content.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        return JSON.parse(jsonMatch[0])
      }
    } catch (error) {
      console.warn('解析生成内容失败:', error)
    }

    // 回退到默认解析
    return this.extractContentFromText(content, type)
  }

  private extractContentFromText(content: string, type: MessageType): any {
    const lines = content.split('\n').filter(line => line.trim())
    
    return {
      title: lines[0] || `${type}通知`,
      content: content,
      summary: lines[0]?.substring(0, 50) || '',
      priority: 'normal' as MessagePriority,
      actions: this.getDefaultActions(type)
    }
  }

  private generateDefaultNotification(
    type: MessageType,
    recipientType: RecipientType,
    relatedData: NotificationRelatedData
  ): Partial<QCNotification> {
    
    const templates = {
      'rectification_required': {
        title: '病历整改通知',
        content: '您的病历存在质控问题，请及时整改。',
        priority: 'high' as MessagePriority
      },
      'audit_result': {
        title: '审核结果通知',
        content: '您的病历审核已完成，请查看结果。',
        priority: 'normal' as MessagePriority
      },
      'task_assigned': {
        title: '审核任务分配',
        content: '您有新的审核任务，请及时处理。',
        priority: 'normal' as MessagePriority
      }
    }

    const template = templates[type] || {
      title: '系统通知',
      content: '您有新的消息。',
      priority: 'normal' as MessagePriority
    }

    return {
      type,
      ...template,
      summary: template.content.substring(0, 50),
      actions: this.getDefaultActions(type),
      related_data: relatedData
    }
  }

  private getDefaultActions(type: MessageType): MessageAction[] {
    const actionMap: Record<MessageType, MessageAction[]> = {
      'rectification_required': [
        {
          id: 'view_defects',
          label: '查看详情',
          type: 'primary',
          action: 'navigate',
          config: {
            url: '/clinical/rectification',
            params: {}
          }
        }
      ],
      'audit_result': [
        {
          id: 'view_result',
          label: '查看结果',
          type: 'primary',
          action: 'navigate',
          config: {
            url: '/clinical/audit-result',
            params: {}
          }
        }
      ],
      'task_assigned': [
        {
          id: 'view_task',
          label: '查看任务',
          type: 'primary',
          action: 'navigate',
          config: {
            url: '/reviewer/audit-tasks',
            params: {}
          }
        }
      ]
    }

    return actionMap[type] || []
  }
}

// Supabase实时通信管理器
class SupabaseRealtimeManager {
  private channels: Map<string, any> = new Map()

  async initializeUserChannel(userId: string, userType: RecipientType): Promise<void> {
    const channelName = `user_notifications_${userId}`
    
    if (this.channels.has(channelName)) {
      return
    }

    const channel = supabase
      .channel(channelName)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'qc_notifications',
          filter: `recipient_id=eq.${userId}`
        },
        (payload) => this.handleNewNotification(payload.new as QCNotification)
      )
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'qc_notifications',
          filter: `recipient_id=eq.${userId}`
        },
        (payload) => this.handleNotificationUpdate(payload.new as QCNotification)
      )
      .subscribe()

    this.channels.set(channelName, channel)
    console.log(`用户 ${userId} 的实时通道已建立`)
  }

  private handleNewNotification(notification: QCNotification): void {
    console.log('收到新消息:', notification.title)
    
    // 触发前端事件
    window.dispatchEvent(new CustomEvent('new-notification', {
      detail: notification
    }))

    // 显示浏览器通知
    if (notification.priority === 'urgent' || notification.priority === 'high') {
      this.showBrowserNotification(notification)
    }
  }

  private handleNotificationUpdate(notification: QCNotification): void {
    window.dispatchEvent(new CustomEvent('notification-updated', {
      detail: notification
    }))
  }

  private showBrowserNotification(notification: QCNotification): void {
    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification(notification.title, {
        body: notification.summary || notification.content.substring(0, 100),
        icon: '/favicon.ico',
        tag: notification.id
      })
    }
  }

  async cleanup(): Promise<void> {
    for (const [channelName, channel] of this.channels) {
      await channel.unsubscribe()
      console.log(`通道 ${channelName} 已关闭`)
    }
    this.channels.clear()
  }
}

// 主要的通知服务
export class NotificationService {
  private messageGenerator: IntelligentMessageGenerator
  private realtimeManager: SupabaseRealtimeManager

  constructor() {
    this.messageGenerator = new IntelligentMessageGenerator()
    this.realtimeManager = new SupabaseRealtimeManager()
  }

  async sendNotification(
    recipientId: string,
    recipientType: RecipientType,
    type: MessageType,
    relatedData: NotificationRelatedData,
    customContent?: Partial<QCNotification>
  ): Promise<QCNotification> {
    
    console.log(`发送通知: ${type} -> ${recipientId}`)

    try {
      // 1. 生成智能消息内容
      const generatedContent = await this.messageGenerator.generateSmartNotification(
        type,
        recipientType,
        relatedData
      )

      // 2. 合并自定义内容
      const notificationData = {
        ...generatedContent,
        ...customContent,
        recipient_id: recipientId,
        recipient_type: recipientType,
        status: 'pending' as const,
        auto_expire: this.shouldAutoExpire(type),
        expires_at: this.calculateExpiryTime(type),
        delivery_attempts: 0
      }

      // 3. 保存到数据库
      const { data, error } = await supabase
        .from('qc_notifications')
        .insert(notificationData)
        .select()
        .single()

      if (error) {
        throw new Error(`保存通知失败: ${error.message}`)
      }

      // 4. 实时推送
      await this.pushRealTimeNotification(data)

      // 5. 记录发送日志
      await this.logNotificationDelivery(data.id, 'sent')

      return data

    } catch (error) {
      console.error('发送通知失败:', error)
      throw error
    }
  }

  async batchSendNotifications(
    recipients: Array<{
      userId: string
      userType: RecipientType
    }>,
    type: MessageType,
    relatedData: NotificationRelatedData,
    customContent?: Partial<QCNotification>
  ): Promise<QCNotification[]> {
    
    const results: QCNotification[] = []
    const batchSize = 10 // 批量处理大小

    for (let i = 0; i < recipients.length; i += batchSize) {
      const batch = recipients.slice(i, i + batchSize)
      
      const batchPromises = batch.map(recipient =>
        this.sendNotification(
          recipient.userId,
          recipient.userType,
          type,
          relatedData,
          customContent
        )
      )

      try {
        const batchResults = await Promise.all(batchPromises)
        results.push(...batchResults)
      } catch (error) {
        console.error(`批量发送失败 (批次 ${i / batchSize + 1}):`, error)
      }

      // 避免过载，添加延迟
      if (i + batchSize < recipients.length) {
        await new Promise(resolve => setTimeout(resolve, 100))
      }
    }

    return results
  }

  async getUserNotifications(
    userId: string,
    options?: {
      status?: string[]
      types?: MessageType[]
      limit?: number
      offset?: number
    }
  ): Promise<QCNotification[]> {
    
    // 尝试从缓存获取
    const cacheKey = `user_notifications_${userId}_${JSON.stringify(options || {})}`
    const cached = await intelligentQCCache.getCachedResult(cacheKey)
    
    if (cached) {
      return cached
    }

    let query = supabase
      .from('qc_notifications')
      .select('*')
      .eq('recipient_id', userId)

    if (options?.status) {
      query = query.in('status', options.status)
    }

    if (options?.types) {
      query = query.in('type', options.types)
    }

    const { data, error } = await query
      .order('created_at', { ascending: false })
      .range(options?.offset || 0, (options?.offset || 0) + (options?.limit || 50) - 1)

    if (error) {
      throw new Error(`获取用户通知失败: ${error.message}`)
    }

    // 缓存结果
    await intelligentQCCache.cacheResult(cacheKey, data || [], 60) // 1分钟缓存

    return data || []
  }

  async markAsRead(notificationId: string): Promise<void> {
    const { error } = await supabase
      .from('qc_notifications')
      .update({
        status: 'read',
        read_at: new Date().toISOString()
      })
      .eq('id', notificationId)

    if (error) {
      throw new Error(`标记已读失败: ${error.message}`)
    }
  }

  async markAsProcessed(notificationId: string): Promise<void> {
    const { error } = await supabase
      .from('qc_notifications')
      .update({
        status: 'processed',
        processed_at: new Date().toISOString()
      })
      .eq('id', notificationId)

    if (error) {
      throw new Error(`标记已处理失败: ${error.message}`)
    }
  }

  async initializeRealTime(userId: string, userType: RecipientType): Promise<void> {
    await this.realtimeManager.initializeUserChannel(userId, userType)
  }

  async cleanup(): Promise<void> {
    await this.realtimeManager.cleanup()
  }

  private async pushRealTimeNotification(notification: QCNotification): Promise<void> {
    // 实时推送通过Supabase的postgres_changes事件自动触发
    // 这里可以添加额外的推送逻辑，如WebSocket、推送通知等
  }

  private shouldAutoExpire(type: MessageType): boolean {
    const autoExpireTypes: MessageType[] = [
      'deadline_reminder',
      'system_announcement'
    ]
    return autoExpireTypes.includes(type)
  }

  private calculateExpiryTime(type: MessageType): string | undefined {
    if (!this.shouldAutoExpire(type)) {
      return undefined
    }

    const expiryHours = {
      'deadline_reminder': 24,
      'system_announcement': 72
    }

    const hours = expiryHours[type] || 24
    const expiryTime = new Date()
    expiryTime.setHours(expiryTime.getHours() + hours)
    
    return expiryTime.toISOString()
  }

  private async logNotificationDelivery(
    notificationId: string,
    status: string,
    error?: string
  ): Promise<void> {
    try {
      await supabase
        .from('message_distribution_logs')
        .insert({
          message_id: notificationId,
          distribution_channel: 'supabase_realtime',
          attempt_number: 1,
          status,
          error_message: error,
          response_time: 0
        })
    } catch (logError) {
      console.warn('记录通知日志失败:', logError)
    }
  }
}

// 导出单例实例
export const notificationService = new NotificationService()
