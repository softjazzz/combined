/**
 * 重构后的LLM服务 - 主入口文件
 * 整合了所有子模块，提供统一的API接口
 */

import {
  ExtractedMedicalData,
  ExtractedDocument,
  DocumentType,
  ParseOptions,
  ParseResult,
  BatchParseResult,
  LLMConfig
} from '@/types/medical'

import { DocumentClassifier } from './llm/documentClassifier'
import { PromptBuilder } from './llm/promptBuilder'
import { ResponseParser } from './llm/responseParser'
import { LLMConfigManager } from './llm/configManager'

export class LLMService {
  private configManager: LLMConfigManager
  private isProcessing = false

  constructor(config: LLMConfig = {}) {
    this.configManager = new LLMConfigManager(config)
  }

  /**
   * 初始化服务（从数据库加载配置）
   */
  async initialize(configName: string = 'default', userId?: string): Promise<boolean> {
    return await this.configManager.loadConfigFromDatabase(configName, userId)
  }

  /**
   * 解析医疗文本（主要方法）
   */
  async parseMedicalText(text: string, options: ParseOptions = {}): Promise<ParseResult> {
    if (this.isProcessing) {
      return {
        success: false,
        error: '服务正在处理其他请求，请稍后重试'
      }
    }

    const startTime = Date.now()
    this.isProcessing = true

    try {
      // 检查配置
      if (!this.configManager.isConfigValid()) {
        throw new Error('LLM配置不完整，请检查API密钥和端点配置')
      }

      // 检查是否启用指针模式
      if (this.configManager.getPointerMode() && options.classifyDocuments) {
        // 指针模式：只获取文档索引，然后从原文提取完整内容
        return this.parseWithPointerMode(text, options)
      }

      // 传统模式：直接获取完整内容
      const prompt = PromptBuilder.buildMedicalParsePrompt(text, options)
      const response = await this.callLLMAPI(prompt)
      const extractedData = ResponseParser.parseMedicalResponse(response)
      const validatedData = this.validateAndCleanData(extractedData, text)

      // 如果启用了文档分类，进行额外处理
      if (options.classifyDocuments && validatedData.documents.length === 0) {
        // 尝试自动分类
        const classificationResult = DocumentClassifier.classifyByTitle(text.substring(0, 200), text)
        validatedData.documents = [{
          id: 'auto_classified',
          type: classificationResult,
          title: DocumentClassifier.getDocumentTypeName(classificationResult),
          content: text.substring(0, this.configManager.getSummaryMaxLength()),
          confidence: 0.7,
          extractedAt: new Date()
        }]
      }

      // 验证结果质量
      const validation = ResponseParser.validateResponse(validatedData)
      if (validation.score < 0.3) {
        console.warn('解析结果质量较低:', validation.issues)
      }

      // 获取使用统计
      const usage = ResponseParser.parseUsageStats(response)

      return {
        success: true,
        data: validatedData,
        processingTime: Date.now() - startTime,
        tokensUsed: usage.tokensUsed
      }

    } catch (error) {
      console.error('医疗文本解析失败:', error)
      return {
        success: false,
        error: error instanceof Error ? error.message : '未知错误',
        processingTime: Date.now() - startTime
      }
    } finally {
      this.isProcessing = false
    }
  }

  /**
   * 批量解析医疗文本
   */
  async parseBatchMedicalTexts(texts: string[], options: ParseOptions = {}): Promise<BatchParseResult> {
    const results: ParseResult[] = []
    let successCount = 0
    let failureCount = 0

    if (options.enableBatchProcessing) {
      // 使用批量处理模式
      try {
        const prompt = PromptBuilder.buildBatchPrompt(texts, options)
        const response = await this.callLLMAPI(prompt)
        const batchData = ResponseParser.parseBatchResponse(response)

        for (let i = 0; i < texts.length; i++) {
          const data = batchData[i]
          if (data) {
            results.push({ success: true, data })
            successCount++
          } else {
            results.push({ success: false, error: '批量处理中未找到对应结果' })
            failureCount++
          }
        }
      } catch (error) {
        // 批量处理失败，回退到逐个处理
        console.warn('批量处理失败，回退到逐个处理:', error)
        return this.parseBatchMedicalTexts(texts, { ...options, enableBatchProcessing: false })
      }
    } else {
      // 逐个处理模式
      for (const text of texts) {
        const result = await this.parseMedicalText(text, options)
        results.push(result)
        
        if (result.success) {
          successCount++
        } else {
          failureCount++
        }

        // 添加延迟避免API限流
        await this.delay(100)
      }
    }

    return {
      success: successCount > 0,
      results,
      totalProcessed: texts.length,
      successCount,
      failureCount
    }
  }

  /**
   * 生成文档摘要
   */
  async generateSummary(text: string, maxLength?: number): Promise<string> {
    try {
      const length = maxLength || this.configManager.getSummaryMaxLength()
      const prompt = PromptBuilder.buildSummaryPrompt(text, length)
      const response = await this.callLLMAPI(prompt)
      
      // 提取摘要内容
      if (typeof response === 'string') {
        return response.trim()
      } else if (response.choices && response.choices[0]) {
        return response.choices[0].message?.content?.trim() || response.choices[0].text?.trim() || '生成摘要失败'
      }
      
      return '生成摘要失败'
    } catch (error) {
      console.error('生成摘要失败:', error)
      return '生成摘要失败'
    }
  }

  /**
   * 分类文档
   */
  async classifyDocument(text: string): Promise<{ type: string; confidence: number; title: string }> {
    try {
      // 首先尝试规则分类
      const ruleBasedType = DocumentClassifier.classifyByTitle(text.substring(0, 200), text)
      
      // 如果启用了LLM分类，使用LLM进行二次确认
      if (this.configManager.isConfigValid()) {
        const prompt = DocumentClassifier.buildClassificationPrompt(text)
        const response = await this.callLLMAPI(prompt)
        const llmResult = DocumentClassifier.parseClassificationResponse(response)
        
        return {
          type: llmResult.type,
          confidence: llmResult.confidence,
          title: llmResult.title || DocumentClassifier.getDocumentTypeName(llmResult.type)
        }
      }
      
      // 回退到规则分类
      return {
        type: ruleBasedType,
        confidence: 0.8,
        title: DocumentClassifier.getDocumentTypeName(ruleBasedType)
      }
    } catch (error) {
      console.error('文档分类失败:', error)
      return {
        type: 'daily_progress_note',
        confidence: 0.3,
        title: '未知文书'
      }
    }
  }

  /**
   * 更新配置
   */
  updateConfig(config: LLMConfig): void {
    this.configManager.updateConfig(config)
  }

  /**
   * 获取当前配置
   */
  getCurrentConfig() {
    return this.configManager.getCurrentConfig()
  }

  /**
   * 获取配置摘要
   */
  getConfigSummary() {
    return this.configManager.getConfigSummary()
  }

  /**
   * 检查服务状态
   */
  getStatus(): {
    isReady: boolean
    isProcessing: boolean
    configValid: boolean
    lastError?: string
  } {
    return {
      isReady: this.configManager.isConfigValid(),
      isProcessing: this.isProcessing,
      configValid: this.configManager.isConfigValid()
    }
  }

  // ===== 兼容性方法 =====

  /**
   * 兼容性方法：extractMedicalData -> parseMedicalText
   * @deprecated 请使用 parseMedicalText 方法
   */
  async extractMedicalData(text: string, options: ParseOptions = {}): Promise<ParseResult> {
    console.warn('extractMedicalData 方法已废弃，请使用 parseMedicalText')
    return this.parseMedicalText(text, options)
  }

  /**
   * 兼容性方法：通过后端解析文件
   * @deprecated 需要重新实现或使用其他方法
   */
  async parseMedicalFileViaBackend(file: File, options: ParseOptions = {}): Promise<ParseResult> {
    console.warn('parseMedicalFileViaBackend 方法需要重新实现')
    // 临时实现：将文件转换为文本后解析
    try {
      const text = await this.fileToText(file)
      return this.parseMedicalText(text, options)
    } catch (error) {
      return {
        success: false,
        error: `文件解析失败: ${error instanceof Error ? error.message : '未知错误'}`
      }
    }
  }

  /**
   * 兼容性方法：结构化分析
   * @deprecated 需要根据具体需求实现
   */
  async analyzeStructured(request: any): Promise<any> {
    console.warn('analyzeStructured 方法需要根据具体需求实现')
    // 临时实现：使用 parseMedicalText
    const prompt = request.userPrompt || request.prompt || ''
    const result = await this.parseMedicalText(prompt, {})

    return {
      content: JSON.stringify(result.data),
      usage: {
        total_tokens: result.tokensUsed || 0
      }
    }
  }

  /**
   * 调用LLM API（私有方法）
   * 通过后端代理调用，避免CORS问题
   */
  private async callLLMAPI(prompt: string): Promise<any> {
    const requestBody = this.configManager.buildAPIRequest(prompt)
    const apiConfig = {
      apiEndpoint: this.configManager.getApiEndpoint(),
      apiKey: this.configManager.getApiKey()
    }

    // 强制加上阿里 DashScope 的推荐参数
    if (apiConfig.apiEndpoint.includes('dashscope.aliyuncs.com')) {
      ;(requestBody as any).model = (requestBody as any).model || this.configManager.getModel()
      ;(requestBody as any).temperature = 0.1
      ;(requestBody as any).top_p = 0
      ;(requestBody as any).max_tokens = Math.min(2000, (requestBody as any).max_tokens || 2000)
    }

    console.log('发送LLM请求:', {
      apiEndpoint: apiConfig.apiEndpoint,
      hasApiKey: !!apiConfig.apiKey,
      requestBodyKeys: Object.keys(requestBody)
    })

    // 通过后端代理调用LLM API
    const response = await fetch('/api/llm/parse-text', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        requestBody,
        apiConfig
      })
    })

    let respJson: any = null
    try {
      respJson = await response.json()
    } catch (e) {
      // ignore json parse error
    }

    if (!response.ok) {
      console.error('LLM代理返回错误', {
        status: response.status,
        statusText: response.statusText,
        body: respJson
      })
      const upstream = respJson?.upstream_body || respJson
      const upstreamMsg = typeof upstream === 'string' ? upstream : JSON.stringify(upstream)
      throw new Error(`API请求失败: ${response.status} ${response.statusText}${upstreamMsg ? ' - ' + upstreamMsg : ''}`)
    }

    console.log('LLM代理返回成功', { status: response.status })
    return respJson
  }

  /**
   * 延迟工具方法
   */
  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms))
  }

  /**
   * 文件转文本（简单实现）
   */
  private async fileToText(file: File): Promise<string> {
    return new Promise((resolve: any,  reject: any) => {
      const reader = new FileReader()
      reader.onload = () => resolve(reader.result as string)
      reader.onerror = () => reject(new Error('文件读取失败'))
      reader.readAsText(file)
    })
  }

  /**
   * 指针模式解析：先获取文档索引，再提取完整内容 - 基于原版精准实现
   */
  private async parseWithPointerMode(text: string, options: ParseOptions): Promise<ParseResult> {
    const startTime = Date.now()

    try {
      // 第一阶段：获取文档索引（只要标题和时间戳）
      const indexPrompt = PromptBuilder.buildDocumentIndexPrompt(text)
      const indexResponse = await this.callLLMAPI(indexPrompt)
      const indexEntries = this.parseIndexingResponse(indexResponse)

      // 第二阶段：基于索引在原文中精确切分文档
      const documents = this.refineSegmentsWithLocalRules(text, indexEntries)

      // 第三阶段：提取基本医疗信息
      const basicInfo = this.extractBasicMedicalInfo(text)

      // 构建完整的医疗数据
      const result: ExtractedMedicalData = {
        recordNumber: basicInfo.recordNumber || '未识别',
        patientName: basicInfo.patientName || '未识别',
        patientAge: basicInfo.patientAge,
        patientGender: basicInfo.patientGender,
        department: basicInfo.department || '未识别',
        primaryDiagnosis: basicInfo.primaryDiagnosis || '未识别',
        secondaryDiagnosis: basicInfo.secondaryDiagnosis || [],
        majorSurgery: basicInfo.majorSurgery || '无',
        documents,
        confidence: 0.9,
        content: text
      }

      return {
        success: true,
        data: result,
        processingTime: Date.now() - startTime,
        tokensUsed: 0
      }
    } catch (error) {
      console.error('指针模式解析失败:', error)
      throw error
    }
  }

  /**
   * 解析索引响应为结构化 entries - 基于原版实现
   */
  private parseIndexingResponse(resp: any): IndexEntry[] {
    try {
      const txt = resp?.choices?.[0]?.message?.content || resp?.content || resp || ''
      const start = txt.indexOf('[')
      const end = txt.lastIndexOf(']') + 1
      const jsonStr = (start >= 0 && end > start) ? txt.slice(start, end) : txt
      const arr = JSON.parse(jsonStr)

      if (!Array.isArray(arr)) return []

      // 过滤掉无效条目，只保留 title 和 timestamp
      return arr.filter(o => o && typeof o.title === 'string' && o.title.trim() !== '')
        .map(o => ({
          title: o.title.trim(),
          timestamp: o.timestamp || null
        }))
    } catch {
      return []
    }
  }

  /**
   * 基于索引在原文中精确切分文档 - 基于原版实现
   */
  private refineSegmentsWithLocalRules(fullText: string, entries: IndexEntry[]): ExtractedDocument[] {
    if (!Array.isArray(entries) || entries.length === 0) return []

    const lines = fullText.split('\n')
    const offsets: number[] = []
    {
      let acc = 0
      for (const line of lines) {
        offsets.push(acc)
        acc += line.length + 1
      }
    }

    // 页眉/页脚识别
    const headerFooter = new RegExp([
      '^===\\s*第\\d+页\\s*===\\s*$',
      '^第\\s*\\d+\\s*页/共\\s*\\d+\\s*页$',
      '^第\\s*\\(\\d+\\)\\s*页$',
      '^(?:.{0,12}医院|病\\s*程\\s*记\\s*录)\\s*$',
      '^(?:科室|姓名|性别|年龄|住院号)[:：].*$',
      '(?:住院|记录|主治|主任|医生|医师)签名[:：]?',
      '记录医师[:：]',
      '主持人签名[:：]'
    ].join('|'), 'u')

    // 标题正则（含空格容错）
    const titleRes: Array<{ re: RegExp; code: string }> = [
      { re: /入\s*院\s*记\s*录|入院记录/, code: 'admission_record' },
      { re: /首次病程记录|术后首次病程记录/, code: 'first_progress_note' },
      { re: /主治医师查房记录|主任医师查房记录|病程记录|查房记录/, code: 'daily_progress_note' },
      { re: /术前小结|术前讨论|术前主刀医师查房记录/, code: 'preoperative_summary' },
      { re: /手术记录|术中记录|手\s*术\s*记\s*录/, code: 'operation_record' },
      { re: /出院记录|出院小结/, code: 'discharge_record' },
      { re: /阶段小结/, code: 'stage_summary' },
    ]

    const results: ExtractedDocument[] = []

    for (let i = 0; i < entries.length; i++) {
      const e = entries[i]

      // 1) 标题吸附 - 在文本中找到匹配的标题行
      let titleLine = 0
      let foundTitle = false
      let documentType = DocumentType.DAILY_PROGRESS_NOTE

      for (let lineIdx = 0; lineIdx < lines.length; lineIdx++) {
        const lineText = lines[lineIdx].trim()

        // 检查是否匹配索引中的标题
        if (lineText.includes(e.title) || e.title.includes(lineText)) {
          titleLine = lineIdx
          foundTitle = true

          // 确定文档类型
          for (const { re, code } of titleRes) {
            if (re.test(lineText)) {
              documentType = this.toDocumentType(code)
              break
            }
          }
          break
        }
      }

      // 2) 确定文档边界
      let start = offsets[titleLine] ?? 0
      let end = fullText.length

      // 找到下一个文档的开始位置作为当前文档的结束
      if (i < entries.length - 1) {
        const nextEntry = entries[i + 1]
        for (let lineIdx = titleLine + 1; lineIdx < lines.length; lineIdx++) {
          const lineText = lines[lineIdx].trim()
          if (lineText.includes(nextEntry.title) || nextEntry.title.includes(lineText)) {
            end = offsets[lineIdx]
            break
          }
        }
      }

      // 3) 提取内容并清理页眉页脚
      let content = fullText.slice(start, end)
      const contentLines = content.split('\n')
      const cleanedLines = contentLines.filter(line => !headerFooter.test(line.trim()))
      content = cleanedLines.join('\n').trim()

      if (content) {
        results.push({
          id: `doc_${Date.now()}_${i}`,
          type: documentType,
          title: e.title,
          content,
          confidence: 0.9,
          extractedAt: new Date(),
          position: {
            startMarker: e.title,
            endMarker: '',
            startIndex: start,
            endIndex: end,
            fullContent: content
          }
        })
      }
    }

    return results
  }

  /**
   * 文档类型映射 - 基于原版实现
   */
  private toDocumentType(code: string): DocumentType {
    const mapping: Record<string, DocumentType> = {
      admission_record: DocumentType.ADMISSION_RECORD,
      first_progress_note: DocumentType.FIRST_PROGRESS_NOTE,
      daily_progress_note: DocumentType.DAILY_PROGRESS_NOTE,
      attending_progress: DocumentType.ATTENDING_PROGRESS,
      stage_summary: DocumentType.STAGE_SUMMARY,
      operation_record: DocumentType.OPERATION_RECORD,
      preoperative_summary: DocumentType.PREOPERATIVE_SUMMARY,
      discharge_record: DocumentType.DISCHARGE_RECORD,
      imaging_report: DocumentType.IMAGING_REPORT,
      lab_report: DocumentType.LAB_REPORT,
      other_examination: DocumentType.OTHER_EXAMINATION,
      surgery_consent: DocumentType.SURGERY_CONSENT,
      anesthesia_consent: DocumentType.ANESTHESIA_CONSENT,
      blood_transfusion_consent: DocumentType.BLOOD_TRANSFUSION_CONSENT,
      special_treatment_consent: DocumentType.SPECIAL_TREATMENT_CONSENT,
      critical_illness_notice: DocumentType.CRITICAL_ILLNESS_NOTICE
    }
    const key = String(code || '').toLowerCase().trim()
    return mapping[key] ?? DocumentType.DAILY_PROGRESS_NOTE
  }

  /**
   * 从文本中提取基本医疗信息
   */
  private extractBasicMedicalInfo(text: string): Partial<ExtractedMedicalData> {
    const result: Partial<ExtractedMedicalData> = {}

    // 提取病历号
    const recordMatch = text.match(/(?:病历号|住院号|病案号)[:：]\s*(\w+)/i)
    if (recordMatch) result.recordNumber = recordMatch[1]

    // 提取患者姓名
    const nameMatch = text.match(/(?:患者|姓名)[:：]\s*([^\s,，。]+)/i)
    if (nameMatch) result.patientName = nameMatch[1]

    // 提取年龄
    const ageMatch = text.match(/(?:年龄|岁数)[:：]\s*(\d+)/i)
    if (ageMatch) result.patientAge = parseInt(ageMatch[1])

    // 提取性别
    const genderMatch = text.match(/(?:性别)[:：]\s*([男女])/i)
    if (genderMatch) result.patientGender = genderMatch[1]

    // 提取科室
    const deptMatch = text.match(/(?:科室|入院科室)[:：]\s*([^\s,，。]+)/i)
    if (deptMatch) result.department = deptMatch[1]

    // 提取主要诊断
    const diagnosisMatch = text.match(/(?:主要诊断|初步诊断|诊断)[:：]\s*([^\n。；;]+)/i)
    if (diagnosisMatch) result.primaryDiagnosis = diagnosisMatch[1].trim()

    // 提取手术信息
    const surgeryMatch = text.match(/(?:手术名称|主要手术|手术)[:：]\s*([^\n。；;]+)/i)
    if (surgeryMatch) result.majorSurgery = surgeryMatch[1].trim()

    return result
  }

  /**
   * 验证和清理数据，并提取完整文书内容
   */
  private validateAndCleanData(data: ExtractedMedicalData, originalText?: string): ExtractedMedicalData {
    // 基础数据验证和清理
    const cleanedData = {
      ...data,
      patientName: data.patientName?.trim() || '',
      department: data.department?.trim() || '',
      primaryDiagnosis: data.primaryDiagnosis?.trim() || '',
      majorSurgery: data.majorSurgery?.trim() || '',
      // 保留所有文档（即便 content 为空），后续用位置标记提取完整内容
      documents: Array.isArray(data.documents) ? data.documents : []
    }

    // 如果有原始文本，提取完整文书内容
    if (originalText && cleanedData.documents) {
      cleanedData.documents = cleanedData.documents.map(doc =>
        this.extractFullDocumentContent(doc, originalText)
      )
    }

    return cleanedData
  }

  /**
   * 从原始文本中提取完整的文书内容
   */
  private extractFullDocumentContent(document: ExtractedDocument, originalText: string): ExtractedDocument {
    if (!document.position?.startMarker || !document.position?.endMarker) {
      console.warn(`文书 ${document.title} 缺少位置标记，无法提取完整内容`)
      return document
    }

    try {
      const result = this.findDocumentBoundaries(
        originalText,
        document.position.startMarker,
        document.position.endMarker,
        document.type
      )

      if (result.success) {
        return {
          ...document,
          content: result.fullContent, // 使用完整内容替换摘要
          position: {
            ...document.position,
            startIndex: result.startIndex,
            endIndex: result.endIndex,
            fullContent: result.fullContent
          }
        }
      } else {
        console.warn(`文书 ${document.title} 内容提取失败: ${result.error}`)
        return document
      }
    } catch (error) {
      console.error(`文书 ${document.title} 内容提取异常:`, error)
      return document
    }
  }

  /**
   * 由开始/结束标记在原文中定位边界
   */
  private findDocumentBoundaries(
    text: string,
    startMarker: string,
    endMarker: string,
    documentType: DocumentType
  ): { success: boolean; startIndex?: number; endIndex?: number; fullContent?: string; error?: string } {
    try {
      const startIndex = text.indexOf(startMarker)
      if (startIndex === -1) {
        return { success: false, error: `找不到开始标记: ${startMarker}` }
      }

      const endIndex = text.indexOf(endMarker, startIndex + startMarker.length)
      if (endIndex === -1) {
        return { success: false, error: `找不到结束标记: ${endMarker}` }
      }

      const fullContent = text.substring(startIndex, endIndex + endMarker.length)

      return {
        success: true,
        startIndex,
        endIndex: endIndex + endMarker.length,
        fullContent
      }
    } catch (error) {
      return { success: false, error: `边界定位异常: ${error}` }
    }
  }
}

// 创建默认实例
export const llmService = new LLMService()

// 导出类型和工具类
export { DocumentClassifier, PromptBuilder, ResponseParser, LLMConfigManager }
export * from '@/types/medical'
