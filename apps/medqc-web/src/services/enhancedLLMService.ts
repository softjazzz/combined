/**
 * 增强版LLM服务 - 支持层级化医疗文书分类
 * 集成新的分类引擎和数据库适配器
 */

import { ExtractedMedicalData, ExtractedDocument } from '../types/medical'
import { EnhancedDocumentClassifier } from './llm/enhancedDocumentClassifier'
import { DocumentClassificationAdapter, MedicalDocumentRecord } from './database/documentClassificationAdapter'
import { PromptBuilder } from './llm/promptBuilder'
import { ResponseParser } from './llm/responseParser'
import { llmConfigService } from './llmConfigService'

export interface EnhancedProcessingOptions {
  enableHierarchicalClassification?: boolean
  confidenceThreshold?: number
  enableManualReview?: boolean
  batchSize?: number
  enableContentValidation?: boolean
}

export interface ProcessingResult {
  success: boolean
  data?: {
    extractedData: ExtractedMedicalData
    documentRecords: MedicalDocumentRecord[]
    classificationStats: any
    processingTime: number
  }
  error?: string
  warnings?: string[]
}

export class EnhancedLLMService {
  private classifier: EnhancedDocumentClassifier
  private dbAdapter: DocumentClassificationAdapter
  private defaultOptions: EnhancedProcessingOptions = {
    enableHierarchicalClassification: true,
    confidenceThreshold: 0.5,
    enableManualReview: true,
    batchSize: 10,
    enableContentValidation: true
  }

  constructor() {
    this.classifier = new EnhancedDocumentClassifier()
    this.dbAdapter = new DocumentClassificationAdapter()
  }

  /**
   * 增强版医疗文本解析 - 支持层级化分类
   */
  async parseEnhancedMedicalText(
    text: string, 
    recordId?: string,
    options: EnhancedProcessingOptions = {}
  ): Promise<ProcessingResult> {
    const startTime = Date.now()
    const mergedOptions = { ...this.defaultOptions, ...options }
    const warnings: string[] = []

    try {
      // 1. 构建增强版提示词
      const prompt = PromptBuilder.buildMedicalParsePrompt(text, {
        classifyDocuments: true,
        extractPatientInfo: true,
        enableHierarchicalClassification: mergedOptions.enableHierarchicalClassification
      })

      // 2. 调用LLM API
      const llmResponse = await this.callLLMAPI(prompt)
      
      // 3. 解析响应
      const extractedData = ResponseParser.parseMedicalResponse(llmResponse)

      // 4. 增强分类处理
      if (mergedOptions.enableHierarchicalClassification) {
        await this.enhanceDocumentClassification(extractedData, mergedOptions, warnings)
      }

      // 5. 内容验证
      if (mergedOptions.enableContentValidation) {
        this.validateExtractedContent(extractedData, warnings)
      }

      // 6. 转换为数据库记录
      let documentRecords: MedicalDocumentRecord[] = []
      if (recordId) {
        documentRecords = await this.dbAdapter.convertToMedicalDocuments(recordId, extractedData)
      }

      // 7. 生成统计信息
      const classificationStats = this.dbAdapter.getClassificationStats(documentRecords)

      const processingTime = Date.now() - startTime

      return {
        success: true,
        data: {
          extractedData,
          documentRecords,
          classificationStats,
          processingTime
        },
        warnings: warnings.length > 0 ? warnings : undefined
      }

    } catch (error) {
      console.error('增强版LLM解析失败:', error)
      return {
        success: false,
        error: error.message,
        warnings: warnings.length > 0 ? warnings : undefined
      }
    }
  }

  /**
   * 增强文档分类处理
   */
  private async enhanceDocumentClassification(
    extractedData: ExtractedMedicalData,
    options: EnhancedProcessingOptions,
    warnings: string[]
  ): Promise<void> {
    const enhancedDocuments: ExtractedDocument[] = []

    for (const document of extractedData.documents) {
      try {
        // 如果LLM没有提供分类信息，使用增强分类器
        if (!document.category || !document.classificationMethod) {
          const classification = this.classifier.classify(document)
          
          // 更新文档分类信息
          document.category = classification.category
          document.classificationMethod = 'enhanced_classifier'
          
          // 如果置信度低于阈值，标记需要人工审核
          if (classification.confidence < options.confidenceThreshold!) {
            warnings.push(`文书"${document.title}"分类置信度较低(${classification.confidence.toFixed(2)})，建议人工审核`)
          }
          
          // 更新整体置信度
          document.confidence = Math.min(document.confidence, classification.confidence)
        }

        enhancedDocuments.push(document)
      } catch (error) {
        console.error(`增强分类失败 - 文书: ${document.title}`, error)
        warnings.push(`文书"${document.title}"分类处理失败: ${error.message}`)
        enhancedDocuments.push(document) // 保留原始文档
      }
    }

    extractedData.documents = enhancedDocuments
  }

  /**
   * 内容验证
   */
  private validateExtractedContent(
    extractedData: ExtractedMedicalData,
    warnings: string[]
  ): void {
    // 验证患者信息
    if (!extractedData.patientName || extractedData.patientName === '未识别') {
      warnings.push('未能识别患者姓名')
    }

    if (!extractedData.patientAge) {
      warnings.push('未能识别患者年龄')
    }

    if (!extractedData.patientGender) {
      warnings.push('未能识别患者性别')
    }

    // 验证文书内容
    const emptyDocuments = extractedData.documents.filter(doc => 
      !doc.content || doc.content.trim().length < 10
    )
    
    if (emptyDocuments.length > 0) {
      warnings.push(`发现${emptyDocuments.length}个内容过短的文书`)
    }

    // 验证分类完整性
    const unclassifiedDocuments = extractedData.documents.filter(doc => 
      !doc.category || !doc.type
    )
    
    if (unclassifiedDocuments.length > 0) {
      warnings.push(`发现${unclassifiedDocuments.length}个未分类的文书`)
    }

    // 验证护理文书和医嘱记录识别
    const nursingDocs = extractedData.documents.filter(doc => 
      doc.category === 'nursing_document'
    )
    const orderDocs = extractedData.documents.filter(doc => 
      doc.category === 'medical_order'
    )

    if (nursingDocs.length === 0) {
      warnings.push('未识别到护理文书，可能存在遗漏')
    }

    if (orderDocs.length === 0) {
      warnings.push('未识别到医嘱记录，可能存在遗漏')
    }
  }

  /**
   * 调用LLM API
   */
  private async callLLMAPI(prompt: string): Promise<any> {
    const config = llmConfigService.getConfig()
    
    try {
      const response = await fetch('/api/llm/parse', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          prompt,
          config: {
            ...config,
            enableHierarchicalClassification: true
          }
        })
      })

      if (!response.ok) {
        throw new Error(`LLM API调用失败: ${response.status} ${response.statusText}`)
      }

      return await response.json()
    } catch (error) {
      console.error('LLM API调用失败:', error)
      throw error
    }
  }

  /**
   * 批量处理文档
   */
  async batchProcessDocuments(
    texts: string[],
    recordIds?: string[],
    options: EnhancedProcessingOptions = {}
  ): Promise<ProcessingResult[]> {
    const results: ProcessingResult[] = []
    const batchSize = options.batchSize || this.defaultOptions.batchSize!

    for (let i = 0; i < texts.length; i += batchSize) {
      const batch = texts.slice(i, i + batchSize)
      const batchRecordIds = recordIds?.slice(i, i + batchSize)

      const batchPromises = batch.map((text, index) => 
        this.parseEnhancedMedicalText(
          text, 
          batchRecordIds?.[index], 
          options
        )
      )

      const batchResults = await Promise.all(batchPromises)
      results.push(...batchResults)
    }

    return results
  }

  /**
   * 重新分类文档
   */
  async reclassifyDocument(
    document: ExtractedDocument,
    forceClassification: boolean = false
  ): Promise<ExtractedDocument> {
    const classification = this.classifier.classify(document)
    
    if (forceClassification || classification.confidence > document.confidence) {
      return {
        ...document,
        category: classification.category,
        classificationMethod: 'enhanced_classifier',
        confidence: classification.confidence
      }
    }

    return document
  }

  /**
   * 获取分类建议
   */
  getClassificationSuggestions(document: ExtractedDocument): any {
    const classification = this.classifier.classify(document)
    
    return {
      currentClassification: {
        category: document.category,
        type: document.type,
        confidence: document.confidence
      },
      suggestedClassification: {
        category: classification.category,
        type: classification.type,
        confidence: classification.confidence,
        method: classification.method
      },
      shouldUpdate: classification.confidence > document.confidence,
      details: classification.details
    }
  }

  /**
   * 验证分类结果
   */
  validateClassification(document: ExtractedDocument): boolean {
    if (!document.category || !document.type) {
      return false
    }

    return this.dbAdapter.validateClassification({
      category: document.category,
      type: document.type,
      confidence: document.confidence,
      method: document.classificationMethod || 'unknown'
    })
  }

  /**
   * 获取分类统计
   */
  getProcessingStats(results: ProcessingResult[]): any {
    const stats = {
      totalProcessed: results.length,
      successful: results.filter(r => r.success).length,
      failed: results.filter(r => !r.success).length,
      totalDocuments: 0,
      totalWarnings: 0,
      averageProcessingTime: 0,
      classificationDistribution: new Map<string, number>()
    }

    let totalTime = 0
    
    results.forEach(result => {
      if (result.success && result.data) {
        stats.totalDocuments += result.data.extractedData.documents.length
        totalTime += result.data.processingTime
        
        // 统计分类分布
        result.data.extractedData.documents.forEach(doc => {
          if (doc.category) {
            const count = stats.classificationDistribution.get(doc.category) || 0
            stats.classificationDistribution.set(doc.category, count + 1)
          }
        })
      }
      
      if (result.warnings) {
        stats.totalWarnings += result.warnings.length
      }
    })

    stats.averageProcessingTime = stats.successful > 0 ? totalTime / stats.successful : 0

    return {
      ...stats,
      classificationDistribution: Object.fromEntries(stats.classificationDistribution)
    }
  }
}
