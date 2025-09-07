/**
 * 文档质控服务
 * 处理文档保存时的自动质控分析
 */

export interface QCTaskStatus {
  task_id: string
  status: 'pending' | 'completed' | 'failed'
  document_id?: string
  qc_status?: string
  qc_score?: number
  applied_rules?: number
  failed_rules?: number
  analysis_time?: string
  results?: QCRuleResult[]
  suggestions?: string[]
  message?: string
}

export interface QCRuleResult {
  rule_code: string
  rule_name: string
  compliant: boolean
  score: number
  confidence: number
  message: string
  suggestion?: string
  severity?: 'critical' | 'major' | 'minor' | 'info'
}

export interface BatchQCResult {
  success: boolean
  batch_task_id: string
  record_id: string
  total_documents: number
  queued_tasks: number
  task_ids: string[]
  message: string
}

export interface DocumentUpdateRequest {
  title?: string
  content?: string
  summary?: string
  type_code?: string
  auto_qc?: boolean
}

export interface DocumentUpdateResponse {
  success: boolean
  message: string
  document_id: string
  updated_fields: string[]
  qc_task_id?: string
  auto_qc_triggered: boolean
}

class DocumentQCService {
  private baseURL: string

  constructor() {
    this.baseURL = window.location.hostname === 'localhost' 
      ? 'http://localhost:8001' 
      : 'http://124.220.6.136:8001'
  }

  /**
   * 更新文档并可选择触发自动质控
   */
  async updateDocument(
    documentId: string, 
    updates: DocumentUpdateRequest
  ): Promise<DocumentUpdateResponse> {
    try {
      const response = await fetch(`${this.baseURL}/api/medical-documents/${documentId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(updates)
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      return await response.json()
    } catch (error) {
      console.error('更新文档失败:', error)
      throw error
    }
  }

  /**
   * 获取质控任务状态
   */
  async getQCTaskStatus(taskId: string): Promise<QCTaskStatus> {
    try {
      const response = await fetch(`${this.baseURL}/api/qc-tasks/${taskId}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        }
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      return await response.json()
    } catch (error) {
      console.error('获取质控任务状态失败:', error)
      throw error
    }
  }

  /**
   * 批量质控分析
   */
  async batchQCAnalysis(
    recordId: string, 
    ruleCodes: string[] = ['POC_001', 'POC_002']
  ): Promise<BatchQCResult> {
    try {
      const response = await fetch(`${this.baseURL}/api/medical-records/${recordId}/batch-qc-analysis`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          rule_codes: ruleCodes
        })
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      return await response.json()
    } catch (error) {
      console.error('批量质控分析失败:', error)
      throw error
    }
  }

  /**
   * 轮询质控任务状态直到完成
   */
  async pollQCTaskStatus(
    taskId: string, 
    maxAttempts: number = 30, 
    interval: number = 2000
  ): Promise<QCTaskStatus> {
    let attempts = 0
    
    while (attempts < maxAttempts) {
      try {
        const status = await this.getQCTaskStatus(taskId)
        
        if (status.status === 'completed' || status.status === 'failed') {
          return status
        }
        
        // 等待指定间隔后重试
        await new Promise(resolve => setTimeout(resolve, interval))
        attempts++
        
      } catch (error) {
        console.error(`轮询质控任务状态失败 (尝试 ${attempts + 1}):`, error)
        attempts++
        
        if (attempts >= maxAttempts) {
          throw error
        }
        
        // 出错时等待更长时间再重试
        await new Promise(resolve => setTimeout(resolve, interval * 2))
      }
    }
    
    throw new Error(`质控任务 ${taskId} 轮询超时`)
  }

  /**
   * 保存文档并自动触发质控分析
   */
  async saveDocumentWithQC(
    documentId: string,
    updates: Omit<DocumentUpdateRequest, 'auto_qc'>,
    enableAutoQC: boolean = true
  ): Promise<{
    updateResult: DocumentUpdateResponse
    qcResult?: QCTaskStatus
  }> {
    try {
      // 1. 保存文档
      const updateResult = await this.updateDocument(documentId, {
        ...updates,
        auto_qc: enableAutoQC
      })

      // 2. 如果触发了自动质控，等待结果
      let qcResult: QCTaskStatus | undefined
      
      if (updateResult.auto_qc_triggered && updateResult.qc_task_id) {
        try {
          qcResult = await this.pollQCTaskStatus(updateResult.qc_task_id)
        } catch (qcError) {
          console.warn('质控分析超时或失败，但文档保存成功:', qcError)
        }
      }

      return {
        updateResult,
        qcResult
      }
    } catch (error) {
      console.error('保存文档并质控失败:', error)
      throw error
    }
  }

  /**
   * 批量保存文档并触发质控
   */
  async batchSaveWithQC(
    recordId: string,
    documents: Array<{ id: string; updates: DocumentUpdateRequest }>,
    enableAutoQC: boolean = true
  ): Promise<{
    saveResults: DocumentUpdateResponse[]
    batchQCResult?: BatchQCResult
  }> {
    try {
      // 1. 批量保存文档
      const saveResults: DocumentUpdateResponse[] = []
      
      for (const doc of documents) {
        try {
          const result = await this.updateDocument(doc.id, {
            ...doc.updates,
            auto_qc: false // 单独保存时不触发质控，统一批量质控
          })
          saveResults.push(result)
        } catch (error) {
          console.error(`保存文档 ${doc.id} 失败:`, error)
          // 继续保存其他文档
        }
      }

      // 2. 如果启用自动质控，触发批量质控
      let batchQCResult: BatchQCResult | undefined
      
      if (enableAutoQC) {
        try {
          batchQCResult = await this.batchQCAnalysis(recordId)
        } catch (qcError) {
          console.warn('批量质控分析失败，但文档保存成功:', qcError)
        }
      }

      return {
        saveResults,
        batchQCResult
      }
    } catch (error) {
      console.error('批量保存文档并质控失败:', error)
      throw error
    }
  }
}

// 导出单例实例
export const documentQCService = new DocumentQCService()
export default documentQCService
