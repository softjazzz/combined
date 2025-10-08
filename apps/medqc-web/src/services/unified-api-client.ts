// 统一API客户端
// 适配Python FastAPI后端的统一API调用服务

import type {
  QCAuditTask,
  QCAuditTaskItem,
  CreateAuditTaskRequest,
  QCAuditResult,
  QCDefect,
  QCNotification,
  AIDefectSuggestion,
  DefectAnalysisContext,
  BatchAuditRequest,
  BatchAuditResult
} from '@/types/audit-module'

// API响应包装类型
interface APIResponse<T> {
  success: boolean
  message: string
  data: T
  errors?: string[]
}

interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

class UnifiedAPIClient {
  private baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001'
  
  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseURL}${endpoint}`
    
    const defaultHeaders = {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${this.getAuthToken()}`
    }
    
    const response = await fetch(url, {
      ...options,
      headers: {
        ...defaultHeaders,
        ...options.headers
      }
    })
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
    }
    
    const data = await response.json()
    return data.success ? data.data : data
  }
  
  private getAuthToken(): string {
    // 从localStorage或其他地方获取认证令牌
    return localStorage.getItem('auth_token') || ''
  }
  
  // ==================== 审核任务管理API ====================
  
  async createAuditTask(request: CreateAuditTaskRequest): Promise<QCAuditTask> {
    return this.request<QCAuditTask>('/api/audit-tasks', {
      method: 'POST',
      body: JSON.stringify(request)
    })
  }
  
  async getAuditTasks(params: {
    page?: number
    page_size?: number
    task_type?: string
    audit_level?: string
    status?: string
    assigned_reviewer?: string
    search?: string
  } = {}): Promise<PaginatedResponse<QCAuditTask>> {
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key,  value]) => {
      if (value !== undefined) {
        searchParams.append(key, String(value))
      }
    })
    
    return this.request<PaginatedResponse<QCAuditTask>>(
      `/api/audit-tasks?${searchParams.toString()}`
    )
  }
  
  async getAuditTask(taskId: string): Promise<QCAuditTask> {
    return this.request<QCAuditTask>(`/api/audit-tasks/${taskId}`)
  }
  
  async getTaskItems(
    taskId: string,
    params: {
      page?: number
      page_size?: number
      status?: string
      risk_level?: string
      assigned_reviewer?: string
    } = {}
  ): Promise<PaginatedResponse<QCAuditTaskItem>> {
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key,  value]) => {
      if (value !== undefined) {
        searchParams.append(key, String(value))
      }
    })
    
    return this.request<PaginatedResponse<QCAuditTaskItem>>(
      `/api/audit-tasks/${taskId}/items?${searchParams.toString()}`
    )
  }
  
  async startAuditTask(taskId: string): Promise<QCAuditTask> {
    return this.request<QCAuditTask>(`/api/audit-tasks/${taskId}/start`, {
      method: 'POST'
    })
  }
  
  async completeAuditTask(taskId: string): Promise<QCAuditTask> {
    return this.request<QCAuditTask>(`/api/audit-tasks/${taskId}/complete`, {
      method: 'POST'
    })
  }
  
  async performIntelligentSampling(taskId: string): Promise<QCAuditTaskItem[]> {
    return this.request<QCAuditTaskItem[]>(`/api/audit-tasks/${taskId}/intelligent-sampling`, {
      method: 'POST'
    })
  }
  
  async batchAssignReviewers(
    taskId: string,
    assignments: Record<string, string>
  ): Promise<unknown> {
    return this.request(`/api/audit-tasks/${taskId}/batch-assign`, {
      method: 'POST',
      body: JSON.stringify(assignments)
    })
  }
  
  async getTaskStatistics(taskId: string): Promise<unknown> {
    return this.request(`/api/audit-tasks/${taskId}/statistics`)
  }
  
  async deleteAuditTask(taskId: string): Promise<void> {
    await this.request(`/api/audit-tasks/${taskId}`, {
      method: 'DELETE'
    })
  }
  
  // ==================== AI辅助功能API ====================
  
  async detectDefectsForTaskItem(
    taskItemId: string,
    analysisContext: DefectAnalysisContext
  ): Promise<AIDefectSuggestion[]> {
    return this.request<AIDefectSuggestion[]>(
      `/api/ai-assistance/defect-detection/${taskItemId}`,
      {
        method: 'POST',
        body: JSON.stringify(analysisContext)
      }
    )
  }
  
  async batchDetectDefects(
    request: BatchAuditRequest,
    analysisContext: DefectAnalysisContext
  ): Promise<Record<string, AIDefectSuggestion[]>> {
    return this.request<Record<string, AIDefectSuggestion[]>>(
      '/api/ai-assistance/batch-defect-detection',
      {
        method: 'POST',
        body: JSON.stringify({
          ...request,
          analysis_context: analysisContext
        })
      }
    )
  }
  
  async generateRectificationPlan(
    defectsData[],
    medicalRecordId: string,
    context?: any
  ): Promise<unknown> {
    return this.request('/api/ai-assistance/rectification-plan', {
      method: 'POST',
      body: JSON.stringify({
        defects_data: defectsData,
        medical_record_id: medicalRecordId,
        context
      })
    })
  }
  
  async smartMedicalRecordAnalysis(
    medicalRecordId: string,
    analysisConfig: any
  ): Promise<unknown> {
    return this.request(`/api/ai-assistance/smart-analysis/${medicalRecordId}`, {
      method: 'POST',
      body: JSON.stringify(analysisConfig)
    })
  }
  
  async predictQualityScore(
    medicalRecordId: string,
    predictionConfig: any
  ): Promise<unknown> {
    return this.request('/api/ai-assistance/quality-score-prediction', {
      method: 'POST',
      body: JSON.stringify({
        medical_record_id: medicalRecordId,
        prediction_config: predictionConfig
      })
    })
  }
  
  async getAIAnalysisHistory(
    taskItemId: string,
    limit: number = 10
  ): Promise<any[]> {
    return this.request(`/api/ai-assistance/analysis-history/${taskItemId}?limit=${limit}`)
  }
  
  async submitAIFeedback(feedbackData: unknown): Promise<unknown> {
    return this.request('/api/ai-assistance/feedback', {
      method: 'POST',
      body: JSON.stringify(feedbackData)
    })
  }
  
  // ==================== 消息通知API ====================
  
  async sendNotification(
    notificationData: unknown,
    immediate: boolean = true
  ): Promise<QCNotification> {
    return this.request<QCNotification>(`/api/notifications?immediate=${immediate}`, {
      method: 'POST',
      body: JSON.stringify(notificationData)
    })
  }
  
  async batchSendNotifications(notificationsData: unknown[]): Promise<QCNotification[]> {
    return this.request<QCNotification[]>('/api/notifications/batch', {
      method: 'POST',
      body: JSON.stringify(notificationsData)
    })
  }
  
  async getUserNotifications(params: {
    page?: number
    page_size?: number
    status?: string[]
    types?: string[]
    priority?: string
    unread_only?: boolean
  } = {}): Promise<PaginatedResponse<QCNotification>> {
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key,  value]) => {
      if (value !== undefined) {
        if (Array.isArray(value)) {
          value.forEach(v => searchParams.append(key, v))
        } else {
          searchParams.append(key, String(value))
        }
      }
    })
    
    return this.request<PaginatedResponse<QCNotification>>(
      `/api/notifications?${searchParams.toString()}`
    )
  }
  
  async markNotificationAsRead(notificationId: string): Promise<void> {
    await this.request(`/api/notifications/${notificationId}/read`, {
      method: 'PUT'
    })
  }
  
  async markNotificationAsProcessed(notificationId: string): Promise<void> {
    await this.request(`/api/notifications/${notificationId}/processed`, {
      method: 'PUT'
    })
  }
  
  async batchMarkAsRead(notificationIds: string[]): Promise<void> {
    await this.request('/api/notifications/batch-read', {
      method: 'POST',
      body: JSON.stringify(notificationIds)
    })
  }
  
  async getNotificationStats(): Promise<unknown> {
    return this.request('/api/notifications/stats')
  }
  
  async sendTestNotification(
    recipientId: string,
    messageType: string = 'system_announcement',
    priority: string = 'normal'
  ): Promise<QCNotification> {
    return this.request<QCNotification>('/api/notifications/test', {
      method: 'POST',
      body: JSON.stringify({
        recipient_id: recipientId,
        message_type: messageType,
        priority
      })
    })
  }
  
  // ==================== 系统信息API ====================
  
  async getSystemHealth(): Promise<unknown> {
    return this.request('/health')
  }
  
  async getSystemInfo(): Promise<unknown> {
    return this.request('/api/system/info')
  }
  
  async getSystemStats(): Promise<unknown> {
    return this.request('/api/system/stats')
  }
}

// 导出单例实例
export const unifiedAPIClient = new UnifiedAPIClient()

// 导出类型
export type { APIResponse, PaginatedResponse }
