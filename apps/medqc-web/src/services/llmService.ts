/**
 * LLM服务 - 医疗文本智能解析
 * 提供病历文本的智能解析和信息抽取功能
 */

import { llmConfigService, type UserLLMConfig } from './llmConfigService'
import { segmentMedicalDocument, findNearestSegment } from '@/utils/documentSegmenter'

// 数据类型定义
export interface ExtractedMedicalData {
  recordNumber: string
  patientName: string
  patientAge?: number
  patientGender?: string
  department: string
  primaryDiagnosis: string
  secondaryDiagnosis?: string[]
  majorSurgery: string
  documents: ExtractedDocument[]
  confidence: number
  content?: string // 原始全文，便于前端切片展示
}

export interface ExtractedDocument {
  id: string
  type: DocumentType
  title: string
  content: string // AI生成的摘要
  confidence: number
  extractedAt: Date
  // 新增：位置信息
  position?: {
    startMarker: string    // 文书开始的标识文本
    endMarker: string      // 文书结束的标识文本
    startIndex?: number    // 在原文中的起始位置（可选，由系统计算）
    endIndex?: number      // 在原文中的结束位置（可选，由系统计算）
    fullContent?: string   // 系统提取的完整原文（可选，由系统填充）
  }
}

// 阶段一：结构化索引返回的段落元数据（简化版）
interface IndexEntry {
  id?: number
  title: string
  timestamp: string | null
  type_code?: string
  start_snippet?: string
  end_snippet?: string
  start_line_hint?: number
  end_line_hint?: number
  summary?: string
  confidence?: number
}


// 一级文书分类
export enum DocumentCategory {
  ADMISSION_RECORD = 'admission_record',      // 入院记录
  PROGRESS_NOTE = 'progress_note',            // 病程记录
  OPERATION_RECORD = 'operation_record',      // 手术记录
  DISCHARGE_RECORD = 'discharge_record',      // 出院记录
  EXAMINATION_REPORT = 'examination_report',  // 辅助检查
  CONSENT_FORM = 'consent_form'               // 知情同意书
}

// 二级文书类型
export enum DocumentType {
  // 入院记录 (一级，无二级)
  ADMISSION_RECORD = 'admission_record',                    // 入院记录
  ADMISSION_RECORD_24H_IN = 'admission_record_24h_in',      // 24小时内入院记录
  ADMISSION_RECORD_24H_OUT = 'admission_record_24h_out',    // 24小时出入院记录

  // 病程记录 (二级)
  FIRST_PROGRESS_NOTE = 'first_progress_note',              // 首次病程记录
  DAILY_PROGRESS_NOTE = 'daily_progress_note',              // 日常病程记录
  ATTENDING_FIRST_PROGRESS = 'attending_first_progress',    // 主治医生首次查房记录
  ATTENDING_PROGRESS = 'attending_progress',                // 主治医生查房记录
  CONSULTATION_RECORD = 'consultation_record',              // 会诊记录
  HANDOVER_RECORD = 'handover_record',                      // 接班记录
  STAGE_SUMMARY = 'stage_summary',                          // 阶段小结

  // 手术记录 (二级)
  OPERATION_RECORD = 'operation_record',                    // 手术记录
  PREOPERATIVE_SUMMARY = 'preoperative_summary',           // 术前小结

  // 出院记录 (二级)
  DISCHARGE_RECORD = 'discharge_record',                    // 出院记录
  DEATH_RECORD = 'death_record',                            // 死亡记录
  DEATH_CASE_DISCUSSION = 'death_case_discussion',          // 死亡病例讨论记录

  // 辅助检查 (二级)
  IMAGING_REPORT = 'imaging_report',                        // 影像检查报告
  LAB_REPORT = 'lab_report',                               // 实验室检查报告
  OTHER_EXAMINATION = 'other_examination',                  // 其他检查报告

  // 知情同意书 (二级)
  SURGERY_CONSENT = 'surgery_consent',                      // 手术知情同意书
  ANESTHESIA_CONSENT = 'anesthesia_consent',               // 麻醉知情同意书
  BLOOD_TRANSFUSION_CONSENT = 'blood_transfusion_consent', // 输血知情同意书
  SPECIAL_TREATMENT_CONSENT = 'special_treatment_consent',  // 特殊治疗知情同意书
  CRITICAL_ILLNESS_NOTICE = 'critical_illness_notice'      // 病危(重)通知书
}

export interface ParseOptions {
  enableBatchProcessing?: boolean
  confidenceThreshold?: number
  extractPatientInfo?: boolean
  extractDiagnosis?: boolean
  extractSurgeryInfo?: boolean
  classifyDocuments?: boolean
}

export interface ParseResult {
  success: boolean
  data?: ExtractedMedicalData
  error?: string
  processingTime: number
  tokensUsed?: number
}

export interface BatchParseResult {
  success: boolean
  results: ParseResult[]
  totalProcessed: number
  successCount: number
  failureCount: number
  totalProcessingTime: number
}

/**
 * LLM医疗文本解析服务
 */
export class LLMService {
  private apiEndpoint: string
  private apiKey: string
  private model: string
  private currentConfig: UserLLMConfig | null = null
  // 新增：指针模式与摘要长度
  private pointerMode: boolean
  private summaryMaxLength: number

  constructor(config: {
    apiEndpoint?: string
    apiKey?: string
    model?: string
    pointerMode?: boolean
    summaryMaxLength?: number
  } = {}) {
    // 使用配置参数，支持运行时传入API信息
    this.apiEndpoint = config.apiEndpoint || 'https://api.openai.com/v1/chat/completions'
    this.apiKey = config.apiKey || ''
    this.model = config.model || 'gpt-4'

    // 从环境变量读取指针模式与摘要长度（可被传入参数覆盖）
    const envPointer = this.getEnvBoolean('VITE_LLM_POINTER_MODE', true)
    const envSumLen = this.getEnvNumber('VITE_LLM_SUMMARY_MAXLEN', 80)

    this.pointerMode = config.pointerMode ?? envPointer
    this.summaryMaxLength = config.summaryMaxLength ?? (envSumLen === 40 || envSumLen === 80 ? envSumLen : 80)
  }

  /**
   * 从数据库加载LLM配置
   */
  async loadConfigFromDatabase(configName: string = 'default', userId?: string): Promise<boolean> {
    try {
      // 1) 先尝试加载用户级默认配置
      let config = await llmConfigService.getConfigByName(configName, userId)

      // 2) 若用户级不存在，则回退到全局默认（user_id = null）
      if (!config) {
        config = await llmConfigService.getConfigByName(configName)
      }

      if (!config) {
        console.warn(`未找到LLM配置: ${configName}`)
        return false
      }

      this.currentConfig = config

      // 更新服务配置
      if (config.provider) {
        this.apiEndpoint = config.custom_endpoint || config.provider.base_endpoint
      }

      if ((config as any).api_key_decrypted) {
        this.apiKey = (config as any).api_key_decrypted
      }

      if (config.model) {
        this.model = config.model.model_code
      }

      console.log(`已加载LLM配置: ${config.config_name}`, {
        provider: config.provider?.provider_name,
        model: config.model?.model_name,
        endpoint: this.apiEndpoint
      })

      return true
    } catch (error) {
      console.error('加载LLM配置失败:', error)
      return false
    }
  }

  /**
   * 获取当前配置信息
   */
  getCurrentConfig(): UserLLMConfig | null {
    return this.currentConfig
  }

  /**
   * 更新LLM服务配置
   */
  updateConfig(config: {
    apiEndpoint?: string
    apiKey?: string
    model?: string
    pointerMode?: boolean
    summaryMaxLength?: number
  }) {
    if (config.apiEndpoint) this.apiEndpoint = config.apiEndpoint
    if (config.apiKey !== undefined) this.apiKey = config.apiKey
    if (config.model) this.model = config.model
    if (config.pointerMode !== undefined) this.pointerMode = !!config.pointerMode
    if (config.summaryMaxLength !== undefined) this.summaryMaxLength = Math.max(0, Math.min(80, config.summaryMaxLength))

    console.log('LLM服务配置已更新:', {
      endpoint: this.apiEndpoint,
      hasApiKey: !!this.apiKey,
      model: this.model,
      pointerMode: this.pointerMode,
      summaryMaxLength: this.summaryMaxLength
    })
  }



  /**
   * 解析单个病历文本
   */
  async parseMedicalText(
    text: string,
    options: ParseOptions = {}
  ): Promise<ParseResult> {
    const startTime = Date.now()

    try {
      // 新方案：当 pointerMode 开启时，走“结构化索引 -> 本地切片”两阶段
      if (this.pointerMode) {
        // 1) 一次性索引
        const indexingPrompt = this.buildSimpleIndexingPrompt(text)
        const resp = await this.callLLMAPI(indexingPrompt)
        const entries = this.parseIndexingResponse(resp)

        // 2) 确定性切片（基于Gemini建议）
        let docs: ExtractedDocument[] = []
        if (entries && entries.length > 0) {
          console.log('[LLM Index] Found', entries.length, 'document entries, using deterministic slicing')

          // 检查是否遗漏了手术记录，如果遗漏则添加
          const hasOperationRecord = entries.some(e =>
            e.title?.includes('手术记录') ||
            e.title?.includes('术中记录') ||
            e.type_code === 'operation_record'
          )

          if (!hasOperationRecord) {
            // 尝试通过内容特征检测手术记录
            const surgeryMatch = text.match(/记录时间.*\d{4}年\d{1,2}月\d{1,2}日.*手术日期.*\d{4}年\d{1,2}月\d{1,2}日/s)
            if (surgeryMatch) {
              console.log('[Surgery Detection] Adding missing surgery record to entries')
              entries.push({
                title: '手术记录',
                timestamp: null,
                type_code: 'operation_record'
              })
            }
          }

          docs = this.sliceDocumentsDeterministically(text, entries as IndexEntry[])
          if (!docs || docs.length === 0) {
            console.warn('[LLM解析失败] LLM索引未产生有效文档，回退到本地规则分段')
            console.warn('[警告] 当前显示的是本地算法结果，不是LLM精准解析结果')
            const segs = segmentMedicalDocument(text)
            docs = segs.map((seg, i) => {
            let typeCode = seg.typeCode || ''
            const title = seg.title || ''
            if (!typeCode) {
              if (/入\s*院\s*记\s*录|入院记录/.test(title)) typeCode = 'admission_record'
              else if (/首次病程记录|术后首次病程记录/.test(title)) typeCode = 'first_progress_note'
              else if (/主治医师查房记录|主任医师查房记录|病程记录|查房记录/.test(title)) typeCode = 'daily_progress_note'
              else if (/术前小结|术前讨论|术前主刀医师查房记录/.test(title)) typeCode = 'preoperative_summary'
              else if (/手术记录|术中记录/.test(title)) typeCode = 'operation_record'
              else if (/出院记录|出院小结/.test(title)) typeCode = 'discharge_record'
              else if (/阶段小结/.test(title)) typeCode = 'stage_summary'
              else if (/(活体组织病理|组织病理|病理诊断|病理报告|活检|穿刺|冰冻切片)/i.test(title)) typeCode = 'other_examination'
              else if (/(CT|核磁|MRI|彩超|超声|X线|影像|检查记录)/i.test(title)) typeCode = 'imaging_report'
            }
            const snippet = text.slice(seg.startIndex, Math.min(seg.endIndex, seg.startIndex + 120))
            const summary = snippet.replace(/\s+/g, ' ').slice(0, this.summaryMaxLength || 80)
            return {
              id: `doc_${Date.now()}_${i}`,
              type: this.toDocumentType(typeCode || ''),
              title: title,
              content: summary,
              confidence: 80,
              extractedAt: new Date(),
              position: { startIndex: seg.startIndex, endIndex: seg.endIndex, startMarker: '', endMarker: '' }
            } as ExtractedDocument
          })
          // 规则分段结果按起点排序并防交叠
          docs.sort((a,b)=> (a.position?.startIndex||0) - (b.position?.startIndex||0))
          for (let i=0;i<docs.length-1;i++){
            const cur=docs[i], nxt=docs[i+1]
            if (cur.position && nxt.position && cur.position.endIndex! > nxt.position.startIndex!) {
              cur.position.endIndex = Math.max(cur.position.startIndex!, nxt.position.startIndex!)
            }
          }
          // 结束 fallback 分支
        }
        // 结束 entries>0 分支
        } else {
          // 索引为空时使用规则分段兜底
          const segs = segmentMedicalDocument(text)
          docs = segs.map((seg, i) => ({
            id: `doc_${Date.now()}_${i}`,
            type: this.toDocumentType(seg.typeCode || ''),
            title: seg.title || '',
            content: text.slice(seg.startIndex, Math.min(seg.endIndex, seg.startIndex + (this.summaryMaxLength || 80))).replace(/\s+/g,' '),
            confidence: 80,
            extractedAt: new Date(),
            position: { startIndex: seg.startIndex, endIndex: seg.endIndex, startMarker: '', endMarker: '' }
          }))
          docs.sort((a,b)=> (a.position?.startIndex||0) - (b.position?.startIndex||0))
          for (let i=0;i<docs.length-1;i++){
            const cur=docs[i], nxt=docs[i+1]
            if (cur.position && nxt.position && cur.position.endIndex! > nxt.position.startIndex!) {
              cur.position.endIndex = Math.max(cur.position.startIndex!, nxt.position.startIndex!)
            }
          }
        }

        console.log('[LLM Parse] Successfully extracted', docs.length, 'documents:', docs.map(d => d.title))

        // 在指针模式下也需要提取患者基本信息
        const patientInfo = this.extractPatientInfoFromText(text)

        const data: ExtractedMedicalData = {
          recordNumber: patientInfo.recordNumber || '',
          patientName: patientInfo.patientName || '',
          patientAge: patientInfo.patientAge,
          patientGender: patientInfo.patientGender,
          department: patientInfo.department || '',
          primaryDiagnosis: patientInfo.primaryDiagnosis || '',
          secondaryDiagnosis: patientInfo.secondaryDiagnosis || [],
          majorSurgery: patientInfo.majorSurgery || '',
          documents: docs,
          confidence: Math.round(docs.reduce((s,d)=>s+(d.confidence||0),0)/(docs.length||1)),
          content: text
        }

        const processingTime = Date.now() - startTime
        // 后处理：统一类型并优先修正影像检查
        data.documents = this.normalizeAndCorrectDocumentTypes(data.documents || [], text)
        return { success: true, data: this.validateAndCleanData(data), processingTime, tokensUsed: resp?.tokensUsed || 0 }
      } else {
        // 兼容：非指针模式保持原逻辑
        const cleanedText = this.preprocessText(text)
        const extractionPrompt = this.buildExtractionPrompt(cleanedText, options)
        const response = await this.callLLMAPI(extractionPrompt)
        const extractedData = this.parseResponse(response)
        const validatedData = this.validateAndCleanData(extractedData)
        // 后处理：统一类型并优先修正影像检查
        if (validatedData?.documents) {
          validatedData.documents = this.normalizeAndCorrectDocumentTypes(validatedData.documents, cleanedText || text)
        }
        const processingTime = Date.now() - startTime
        return { success: true, data: validatedData, processingTime, tokensUsed: response.tokensUsed }
      }
    } catch (error) {
      console.error('LLM解析失败:', error)
      return { success: false, error: error instanceof Error ? error.message : '未知错误', processingTime: Date.now() - startTime }
    }
  }

  /**
   * 通过后端解析医疗文件（支持PDF等格式）
   */
  async parseMedicalFileViaBackend(
    file: File,
    options: ParseOptions = {}
  ): Promise<ParseResult> {
    const startTime = Date.now()

    try {
      console.log('通过后端解析文件:', file.name, file.type)

      // 上传文件到后端并进行解析
      const formData = new FormData()
      formData.append('file', file)

      // 传递解析选项和API配置
      const requestOptions = {
        ...options,
        apiConfig: {
          apiEndpoint: this.apiEndpoint,
          apiKey: this.apiKey,
          model: this.model
        }
      }
      formData.append('options', JSON.stringify(requestOptions))

      // 直接调用后端，不需要认证（优先使用环境变量 VITE_API_BASE_URL；否则回退到同主机:8001）
      const BASE = this.resolveApiBase()
      const apiUrl = BASE ? `${BASE}/api/parse-medical-file-public` : '/api/parse-medical-file-public'

      const response = await fetch(apiUrl, { method: 'POST', body: formData })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({})) as any
        throw new Error(errorData.message || `HTTP ${response.status}: ${response.statusText}`)
      }

      const result = await response.json() as any

      const processingTime = Date.now() - startTime

      // 若启用指针模式，使用后端抽取的全文，在前端执行窗口化+指针解析，以降低输出token
      if (this.pointerMode && result?.data?.content) {
        const text = String(result.data.content)
        const pointerParsed = await this.parseMedicalText(text, options)
        if (pointerParsed.success && pointerParsed.data) {
          const merged = { ...result.data, documents: pointerParsed.data.documents, content: text }
          return { success: true, data: merged, processingTime, tokensUsed: (pointerParsed.tokensUsed || 0) }
        }
      }

      return {
        success: true,
        data: result.data,
        processingTime,
        tokensUsed: result.tokensUsed || 0
      }
    } catch (error) {
      console.error('后端文件解析失败:', error)
      return {
        success: false,
        error: error instanceof Error ? error.message : '文件解析失败',
        processingTime: Date.now() - startTime
      }
    }
  }

  /**
   * 提取医疗数据（文本解析）
   */
  async extractMedicalData(
    text: string,
    options: ParseOptions = {}
  ): Promise<ParseResult> {
    // 直接调用现有的parseMedicalText方法
    return this.parseMedicalText(text, options)
  }

  /**
   * 解析医疗文件（支持PDF等格式）- 直接调用LLM API（已废弃）
   */
  async parseMedicalFile(
    file: File,
    options: ParseOptions = {}
  ): Promise<ParseResult> {
    const startTime = Date.now()

    try {
      console.log('开始解析文件:', file.name, file.type)

      // 构建文件上传的提示词
      const prompt = this.buildFileExtractionPrompt(options)

      // 调用支持文件上传的LLM API
      const response = await this.callLLMAPIWithFile(prompt, file)

      // 解析响应
      const extractedData = this.parseResponse(response)

      // 后处理和验证
      const validatedData = this.validateAndCleanData(extractedData)

      const processingTime = Date.now() - startTime

      return {
        success: true,
        data: validatedData,
        processingTime,
        tokensUsed: response.tokensUsed
      }
    } catch (error) {
      console.error('LLM文件解析失败:', error)
      return {
        success: false,
        error: error instanceof Error ? error.message : '文件解析失败',
        processingTime: Date.now() - startTime
      }
    }
  }

  /**
   * 批量解析病历文本
   */
  async batchParseMedicalTexts(
    texts: string[],
    options: ParseOptions = {}
  ): Promise<BatchParseResult> {
    const startTime = Date.now()
    const results: ParseResult[] = []

    try {
      // 并发处理多个文本
      const promises = texts.map(text => this.parseMedicalText(text, options))
      const batchResults = await Promise.allSettled(promises)

      batchResults.forEach((result, index) => {
        if (result.status === 'fulfilled') {
          results.push(result.value)
        } else {
          results.push({
            success: false,
            error: `批量处理第${index + 1}个文本失败: ${result.reason}`,
            processingTime: 0
          })
        }
      })

      const successCount = results.filter(r => r.success).length
      const failureCount = results.length - successCount

      return {
        success: true,
        results,
        totalProcessed: texts.length,
        successCount,
        failureCount,
        totalProcessingTime: Date.now() - startTime
      }
    } catch (error) { return {
        success: false,
        results:  [],
        totalProcessed: 0,
        successCount: 0,
        failureCount: texts.length,
        totalProcessingTime: Date.now() - startTime
      }
    }
  }

  /**
   * 文档分类
   */
  async classifyDocument(text: string): Promise<{
    type: DocumentType
    confidence: number
    title?: string
  }> {
    try {
      const prompt = this.buildClassificationPrompt(text)
      const response = await this.callLLMAPI(prompt)

      return this.parseClassificationResponse(response)
    } catch (error) {
      console.error('文档分类失败:', error)
      return {
        type: DocumentType.DAILY_PROGRESS_NOTE,
        confidence: 0.5
      }
    }
  }

  /**
   * 预处理文本
   */
  private getEnvBoolean(key: string, def: boolean): boolean {
    try {
      const v = this.safeEnv(key)
      if (v === undefined || v === null) return def
      const s = String(v).toLowerCase()
      if (s === '1' || s === 'true' || s === 'yes') return true
      if (s === '0' || s === 'false' || s === 'no') return false
      return def
    } catch { return def }
  }

  private getEnvNumber(key: string, def: number): number {
    try {
      const v = this.safeEnv(key)
      const n = Number(v)
      return isFinite(n) ? n : def
    } catch { return def }
  }

  // 安全获取环境变量
  private safeEnv(key: string): string | undefined {
    try {
      const g: any = (globalThis as any)
      if (g && g.import && g.import.meta && g.import.meta.env) return g.import.meta.env[key]
      if (typeof process !== 'undefined' && (process as any).env) return (process as any).env[key]
      return undefined
    } catch { return undefined }
  }

  private resolveApiBase(): string {
    const fromEnv = this.safeEnv('VITE_API_BASE_URL')
    if (fromEnv !== undefined && String(fromEnv).trim() !== '') {
      return String(fromEnv).trim()
    }
    // 默认返回空串，使用相对路径走 Vite 代理
    return ''
  }

  private preprocessText(text: string): string {
    return text
      .trim()
      .replace(/\s+/g, ' ')  // 合并多个空格
      .replace(/\n\s*\n/g, '\n')  // 合并多个换行
      .replace(/[^\u4e00-\u9fa5\w\s\.,;:!?()（）【】\[\]""'']/g, '')  // 清理特殊字符
  }

  /**
   * 从文本中直接提取患者基本信息（用于指针模式）
   */
  private extractPatientInfoFromText(text: string): Partial<ExtractedMedicalData> {
    const result: Partial<ExtractedMedicalData> = {}

    // 提取患者姓名
    const namePatterns = [
      /姓名[:：]\s*([^\s\n,，。]+)/,
      /患者\s*([^\s\n,，。]+)，/,
      /患者姓名[:：]\s*([^\s\n,，。]+)/,
      /病人\s*([^\s\n,，。]+)，/
    ]

    for (const pattern of namePatterns) {
      const match = text.match(pattern)
      if (match && match[1] && match[1].trim().length >= 2) {
        const extractedName = match[1].trim()
        if (/^[\u4e00-\u9fa5]{2,4}$/.test(extractedName)) {
          result.patientName = extractedName
          break
        }
      }
    }

    // 提取年龄
    const agePatterns = [
      /年龄[:：]\s*(\d+)[岁]?/,
      /(\d+)岁/,
      /，(\d+)岁，/,
      /患者[^，]*，[^，]*，(\d+)岁/
    ]

    for (const pattern of agePatterns) {
      const match = text.match(pattern)
      if (match && match[1]) {
        const extractedAge = parseInt(match[1])
        if (extractedAge > 0 && extractedAge < 150) {
          result.patientAge = extractedAge
          break
        }
      }
    }

    // 提取性别
    const genderPatterns = [
      /性别[:：]\s*([男女])/,
      /患者[^，]*，([男女])，/,
      /，([男女])性，/,
      /，([男女])，\d+岁/
    ]

    for (const pattern of genderPatterns) {
      const match = text.match(pattern)
      if (match && match[1]) {
        result.patientGender = match[1] === '男' ? '男' : '女'
        break
      }
    }

    // 提取科室
    const deptPatterns = [
      /科室[:：]\s*([^\s\n,，。]+)/,
      /入院科室[:：]\s*([^\s\n,，。]+)/,
      /([^\s]+科)\s*病程记录/,
      /([^\s]+科)\s*住院病历/
    ]

    for (const pattern of deptPatterns) {
      const match = text.match(pattern)
      if (match && match[1] && match[1].trim().length >= 2) {
        const extractedDept = match[1].trim()
        if (/科$/.test(extractedDept) || /部$/.test(extractedDept)) {
          result.department = extractedDept
          break
        }
      }
    }

    // 提取主要诊断
    const diagnosisPatterns = [
      /初步诊断[:：]\s*\d*\.?\s*([^\n\r]+)/,
      /入院诊断[:：]\s*\d*\.?\s*([^\n\r]+)/,
      /术前诊断[:：]\s*\d*\.?\s*([^\n\r]+)/,
      /主要诊断[:：]\s*([^\n\r]+)/
    ]

    for (const pattern of diagnosisPatterns) {
      const match = text.match(pattern)
      if (match && match[1] && match[1].trim().length >= 2) {
        result.primaryDiagnosis = match[1].trim()
        break
      }
    }

    return result
  }

  /**
   * 构建信息抽取提示词
   */
  // 基于指针模式的窗口划分
  private createCandidateWindows(text: string): Array<{ start: number; end: number; label?: string }> {
    const anchors = [
      /入院记录|入院小结|入院情况/g,
      /首次病程记录|病程记录|查房记录|阶段小结|术后首次病程/g,
      /术前小结|术前讨论|手术前/g,
      /手术记录|手术经过|术中记录/g,
      /出院记录|出院小结/g,
      /护理记录|护理文书/g,
      /知情同意书|签署同意/g
    ]

    const hits: number[] = []
    for (const re of anchors) {
      let m: RegExpExecArray | null
      while ((m = re.exec(text)) !== null) {
        hits.push(m.index)
      }
    }
    // 加入文首作为起点候选
    hits.push(0)
    // 去重排序
    const uniq = Array.from(new Set(hits)).sort((a,b)=>a-b)

    const windows: Array<{ start:number; end:number; label?:string }> = []
    const minWin = 400, maxWin = 800
    for (let i=0;i<uniq.length;i++) {
      const center = uniq[i]
      const start = Math.max(0, center - Math.floor(minWin/2))
      const end = Math.min(text.length, center + maxWin/2)
      windows.push({ start, end  })
    }

    // 如果没有任何命中，则按固定步长切片
    if (windows.length === 0) {
      const step = 700
      for (let s=0;s<text.length;s+=step) {
        windows.push({ start: s, end: Math.min(text.length, s + step + 200) })
      }
    }
    return windows
  }

  private buildPointerPrompt(windowText: string): string {
    const maxSummary = Math.max(0, Math.min(80, this.summaryMaxLength ?? 80))
    const sys = `你是医疗文书分段专家。禁止输出原文全文内容！只返回指针（位置）与短摘要。`;
    const rules = `
严格要求：
- 仅返回 JSON 数组，无其它文本。
- 每个元素必须包含字段：
  id, type_code, title, start_delta, end_delta, start_snippet, end_snippet, summary, confidence
- start_delta 与 end_delta 是相对“当前窗口文本”的字符偏移（可为负）。
- start_snippet 与 end_snippet 各不超过20个字符；summary 最长${maxSummary}字符（若为0则置空字符串）。
- 严禁返回 fullContent、content、raw、原文大段内容等字段。
允许类型枚举（type_code）：admission_record, first_progress_note, daily_progress_note, attending_progress, stage_summary, operation_record, preoperative_summary, discharge_record, imaging_report, lab_report, other_examination, surgery_consent, anesthesia_consent, blood_transfusion_consent, special_treatment_consent
`;
    const format = `
仅返回类似如下JSON：
[
  {
    "id": "seg_1",
    "type_code": "first_progress_note",
    "title": "首次病程记录",
    "start_delta": -10,
    "end_delta": 320,
    "start_snippet": "首次病程记",
    "end_snippet": "医师签名",
    "summary": "简要概述（<=" + maxSummary + "字）",
    "confidence": 92
  }
]
`;
    return `${sys}\n${rules}\n窗口文本：\n${windowText}\n\n${format}`
  }

  private parsePointerItems(resp: any): any[] {
    try {
      const txt = resp?.content || ''
      const start = txt.indexOf('[')
      const end = txt.lastIndexOf(']')+1
      const jsonStr = start>=0 && end>start ? txt.slice(start,end) : txt
      const arr = JSON.parse(jsonStr)
      if (Array.isArray(arr)) return arr
      if (arr && Array.isArray(arr.items)) return arr.items
      return []
    } catch { return [] }
  }

  /**
   * 阶段一：结构化索引提示词（不返回全文，仅返回元数据+锚点）
   */
  private buildIndexingPrompt(fullText: string): string {
    const system = `你是专业的医疗病历结构化助手。请严格按JSON数组输出段落索引，禁止输出任何与JSON无关的文字。`;
    const rules = `输出要求：
- 仅输出一个JSON数组，不包含任何其他文本。
- 数组元素字段如下（不要返回全文内容，不要出现content字段）：
  id(数字)、type_code(字符串)、title(字符串，保留原始格式)、timestamp(YYYY-MM-DD HH:MM)、
  start_snippet(字符串，10-20字)、end_snippet(字符串，10-20字)、
  start_line_hint(整数)、end_line_hint(整数)、summary(40-80字中文)、confidence(0-100)
- type_code 取值：admission_record, first_progress_note, daily_progress_note, attending_progress, stage_summary, preoperative_summary, operation_record, discharge_record, consultation_record, handover_record
- 段落通常以“标题或时间戳+标题”开始，直到下一个段落开始为止；页眉页脚（如“=== 第n页 ===”、“第n页/共m页”、“医院名/病 程 记 录”、“科室/姓名/住院号”等）不计入内容范围。
- 特别注意：手术记录可能没有明确标题，而是以"记录时间"、"手术日期"、"术前诊断"等关键字开始，这种情况下应识别为operation_record类型，title设为"手术记录"。
- 手术记录识别特征：包含"记录时间"、"手术日期"、"术前诊断"、"术中诊断"、"手术名称"、"手术者"、"麻醉方法"、"手术经过"等多个关键字段的内容应识别为手术记录。
- start_snippet/end_snippet 请选择该段落在标题之后/结尾处的原文片段，各10-20字，不要包含标题本身。`;
    const user = `请对以下原始病历文本进行索引（不要改动任何字符）：\n\n${fullText}`;
    return `${system}\n\n${rules}\n\n${user}`;
  }

  /** 确定性文档切片（基于Gemini建议） */
  private sliceDocumentsDeterministically(fullText: string, entries: IndexEntry[]): ExtractedDocument[] {
    const documentPositions: Array<{ title: string; timestamp: string | null; startIndex: number }> = []

    // 1. 在原文中定位每一个目录条目的起始位置（处理重复标题）
    let lastFoundIndex = -1 // 记录上一次查找结束的位置
    for (const entry of entries) {
      // 优先使用时间戳+标题的组合来定位，更精确
      const searchPattern = entry.timestamp ? `${entry.timestamp} ${entry.title}` : entry.title
      let startIndex = fullText.indexOf(searchPattern, lastFoundIndex + 1)

      // 如果组合找不到，尝试仅用标题（容忍时间戳和标题之间有换行）
      if (startIndex === -1) {
        const titleIndex = fullText.indexOf(entry.title, lastFoundIndex + 1)
        if (titleIndex !== -1) {
          // 简单回溯查找时间戳
          const searchArea = fullText.substring(Math.max(0, titleIndex - 30), titleIndex)
          if (entry.timestamp && searchArea.includes(entry.timestamp)) {
            startIndex = Math.max(0, titleIndex - 30) + searchArea.indexOf(entry.timestamp)
          } else {
            startIndex = titleIndex
          }
        }
      }

      // 特殊处理：如果是手术记录但找不到标题，尝试通过特征识别
      if (startIndex === -1 && entry.title === '手术记录') {
        const surgeryFeatures = [
          /记录时间.*\d{4}年\d{1,2}月\d{1,2}日/,
          /手术日期.*\d{4}年\d{1,2}月\d{1,2}日/,
          /术前诊断.*[:：]/
        ]

        for (const feature of surgeryFeatures) {
          const match = fullText.substring(lastFoundIndex + 1).match(feature)
          if (match) {
            startIndex = lastFoundIndex + 1 + match.index!
            console.log(`[Surgery Record] Found by feature pattern at index ${startIndex}`)
            break
          }
        }
      }

      if (startIndex !== -1) {
        documentPositions.push({ ...entry, startIndex  })
        lastFoundIndex = startIndex // 更新位置，确保下次从这个位置之后开始搜索
      } else {
        console.warn(`Could not find entry in text:`, entry)
      }
    }

    // 按起始位置排序，防止LLM返回乱序的目录
    documentPositions.sort((a, b) => a.startIndex - b.startIndex)

    const extractedDocs: ExtractedDocument[] = []

    // 2. 根据起止位置进行切割
    for (let i = 0; i < documentPositions.length; i++) {
      const currentDoc = documentPositions[i]
      const nextDoc = documentPositions[i + 1]

      const startIndex = currentDoc.startIndex
      // 结束位置是下一个文档的开始位置，或者是全文末尾
      const endIndex = nextDoc ? nextDoc.startIndex : fullText.length

      if (startIndex >= endIndex) continue // 跳过无效或重复的条目

      let docContent = fullText.substring(startIndex, endIndex)

      // 3. 清理页眉页脚（增强版）
      docContent = this.cleanHeaderFooter(docContent)

      // 4. 进行分类和摘要（纯净版 - 去除标题冗余）
      const type = this.classifyTitle(currentDoc.title, docContent) // 基于标题和内容的规则分类

      // 从完整内容中找到标题的结束位置，以获取纯净的正文
      const contentStartOffset = docContent.indexOf(currentDoc.title)
      let actualContent = docContent
      if (contentStartOffset !== -1) {
        actualContent = docContent.substring(contentStartOffset + currentDoc.title.length).trim()
        // 如果有时间戳，也跳过时间戳
        if (currentDoc.timestamp && actualContent.startsWith(currentDoc.timestamp)) {
          actualContent = actualContent.substring(currentDoc.timestamp.length).trim()
        }
      }

      // 基于纯净的正文生成摘要
      const summary = actualContent.replace(/\s+/g, ' ').slice(0, this.summaryMaxLength || 80)

      extractedDocs.push({
        id: `doc_${Date.now()}_${i}`,
        type: type,
        title: currentDoc.title,
        content: summary, // 现在这个摘要是基于准确的切片生成的
        confidence: 95, // 因为是确定性切割，置信度可以给很高
        extractedAt: new Date(),
        position: {
          startMarker: currentDoc.title, // 使用标题作为稳定的标记
          endMarker: '', // 结束标记可以后续再定
          startIndex: startIndex,
          endIndex: endIndex,
          fullContent: docContent // 存储包含标题的完整原文
        }
      })
    }

    return extractedDocs
  }

  /** 清理页眉页脚（可配置） */
  private cleanHeaderFooter(content: string): string {
    // 基础的页眉页脚模式
    const patterns = [
      /^(?:泸县人民医院|.*人民医院)\s*\n?/gm,
      /^(?:病\s*程\s*记\s*录)\s*\n?/gm,
      /^(?:科室：.*|姓名：.*|年龄：.*|性别：.*|床号：.*|住院号.*)\s*\n?/gm,
      /^(?:=== 第\d+页 ===|第\(\d+\)页)\s*\n?/gm,
      /\n?\s*(?:医师签名|记录医师|主持人签名)：.*$/gm,
      /\n?\s*第\(\d+\)页\s*$/gm
    ]

    let cleaned = content
    for (const pattern of patterns) {
      cleaned = cleaned.replace(pattern, '')
    }

    return cleaned.trim()
  }

  /** 基于标题和内容的规则分类（增强版） */
  private classifyTitle(title: string, content?: string): DocumentType {
    const lowerTitle = title.toLowerCase()
    const lowerContent = content?.toLowerCase() || ''

    // 特殊处理：手术记录内容特征识别
    if (title === '手术记录' || lowerTitle.includes('手术记录') || lowerTitle.includes('术中记录')) {
      return DocumentType.OPERATION_RECORD
    }

    // 如果标题不明确，通过内容特征识别手术记录
    if (content) {
      const surgeryFeatures = [
        /记录时间.*\d{4}年\d{1,2}月\d{1,2}日/,
        /手术日期.*\d{4}年\d{1,2}月\d{1,2}日/,
        /术前诊断.*[:：]/,
        /术中诊断.*[:：]/,
        /手术名称.*[:：]/,
        /手术者.*[:：]/,
        /麻醉方法.*[:：]/,
        /手术经过.*[:：]/,
        /术中出现的情况/,
        /植入物名称/,
        /术者签名/
      ]

      let surgeryFeatureCount = 0
      for (const feature of surgeryFeatures) {
        if (feature.test(content)) {
          surgeryFeatureCount++
        }
      }

      // 如果包含3个或以上手术记录特征，认定为手术记录
      if (surgeryFeatureCount >= 3) {
        console.log(`[Surgery Record] Identified by content features (${surgeryFeatureCount} matches)`)
        return DocumentType.OPERATION_RECORD
      }
    }

    // 按优先级和特异性排序的分类规则
    const rules = [
      // 高特异性规则（优先匹配）
      { keywords: ['术后首次病程'], type: DocumentType.FIRST_PROGRESS_NOTE },
      { keywords: ['首次病程记录', '首次病程'], type: DocumentType.FIRST_PROGRESS_NOTE },
      { keywords: ['手术记录', '术中记录'], type: DocumentType.OPERATION_RECORD },

      // 影像检查类
      { keywords: ['ct检查', 'mri检查', '核磁检查', '彩超检查', 'x线检查'], type: DocumentType.IMAGING_REPORT },
      { keywords: ['ct', 'mri', '核磁', '彩超', '超声', 'x线', '影像', '检查记录'], type: DocumentType.IMAGING_REPORT },

      // 病理检查类（并入“其他检查”分类下显示）
      { keywords: ['病理诊断', '病理报告', '组织病理', '活体组织病理', '冰冻切片', '活检', '穿刺病理'], type: DocumentType.OTHER_EXAMINATION },

      // 术前相关
      { keywords: ['术前小结'], type: DocumentType.PREOPERATIVE_SUMMARY },
      { keywords: ['术前讨论记录', '术前讨论'], type: DocumentType.PREOPERATIVE_SUMMARY },
      { keywords: ['术前主刀医师查房'], type: DocumentType.PREOPERATIVE_SUMMARY },

      // 查房记录类
      { keywords: ['主任医师查房记录', '主治医师查房记录'], type: DocumentType.ATTENDING_PROGRESS },
      { keywords: ['查房记录'], type: DocumentType.ATTENDING_PROGRESS },

      // 出院相关
      { keywords: ['出院记录', '出院小结'], type: DocumentType.DISCHARGE_RECORD },

      // 其他特殊类型
      { keywords: ['会诊记录', '会诊'], type: DocumentType.DAILY_PROGRESS_NOTE }, // 暂用通用类型
      { keywords: ['阶段小结'], type: DocumentType.STAGE_SUMMARY },
      { keywords: ['病程记录'], type: DocumentType.DAILY_PROGRESS_NOTE }
    ]

    // 按规则优先级匹配
    for (const rule of rules) {
      if (rule.keywords.some(keyword => lowerTitle.includes(keyword))) {
        return rule.type
      }
    }

    return DocumentType.DAILY_PROGRESS_NOTE // 默认值
  }

  /** 新的简化索引提示词 */
  private buildSimpleIndexingPrompt(fullText: string): string {
    const system = `你是专业的医疗病历结构化助手。你的唯一任务是从文本中识别出所有独立的医疗文书记录，并提取它们的【确切标题】和【时间戳】。

严格要求：
- 仅输出一个JSON数组，不包含任何解释性文字。
- 数组中的每个对象只包含以下字段：
  - title (字符串): 必须是文书中逐字提取的、完整的标题，例如 "首次病程记录" 或 "孙治庆主治医师查房记录"。对于手术记录，如果没有明确标题但包含"记录时间"、"手术日期"、"术前诊断"等特征，请使用"手术记录"作为标题。
  - timestamp (字符串): 如果标题附近有明确的时间戳 (格式 YYYY-MM-DD HH:MM)，请提取。如果没有，则为 null。
- 不要生成ID、类型、摘要、代码片段(snippet)、行号或任何其他字段。
- 忽略所有页眉和页脚信息。
- 特别注意：手术记录可能没有明确的"手术记录"标题，而是直接以"记录时间：YYYY年MM月DD日"开始，这种情况下应识别为手术记录。`;

    const example = `输出格式示例：
[
  { "title": "首次病程记录", "timestamp": "2025-03-30 01:08" },
  { "title": "孙治庆主治医师查房记录", "timestamp": "2025-03-30 08:29" },
  { "title": "CT检查记录", "timestamp": "2025-03-30 10:35" },
  { "title": "术后首次病程记录", "timestamp": "2025-03-31 13:09" }
]`;

    const user = `请对以下原始病历文本进行索引，只提取 title 和 timestamp：\n\n${fullText}`;
    return `${system}\n\n${example}\n\n${user}`;
  }

  /** 解析索引响应为结构化 entries */
  private parseIndexingResponse(resp): IndexEntry[] {
    try {
      const txt = resp?.content || ''
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


  private toDocumentType(code: string): DocumentType {
    const m: Record<string, DocumentType> = {
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
    const key = String(code||'').toLowerCase().trim()
    return m[key] ?? DocumentType.DAILY_PROGRESS_NOTE
  }

  /**
   * 阶段二：本地精修切片
   * 基于索引 entries 在原文中对齐标题/对齐 snippet/裁剪页眉脚/质量回退
   */
  private refineSegmentsWithLocalRules(fullText: string, entries: IndexEntry[]): ExtractedDocument[] {
    if (!Array.isArray(entries) || entries.length === 0) return []

    const lines = fullText.split('\n')
    const offsets: number[] = []
    {
      let acc = 0
      for (const line of lines) { offsets.push(acc); acc += line.length + 1 }
    }

    // 页眉/页脚识别
    const headerFooter = new RegExp(
      [
        '^===\s*第\d+页\s*===\s*$',
        '^第\s*\d+\s*页/共\s*\d+\s*页$',
        '^第\s*\(\d+\)\s*页$',
        '^(?:.{0,12}医院|病\s*程\s*记\s*录)\s*$',
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

    // 规则分段兜底
    let fallbackSegments: ReturnType<typeof segmentMedicalDocument> | null = null

    for (const e of entries) {
      // 1) 标题吸附
      const approxLine = Math.min(Math.max(0, (e.start_line_hint ?? 0)), Math.max(0, lines.length - 1))
      const scanRange = 15
      let titleLine = approxLine
      let foundTitle = false
      for (let i = Math.max(0, approxLine - scanRange); i <= Math.min(lines.length - 1, approxLine + scanRange); i++) {
        const t = lines[i].trim()
        for (const { re, code } of titleRes) {
          if (re.test(t) && (!e.type_code || e.type_code === code || e.title?.replace(/\s/g, '')?.includes(t.replace(/\s/g, '')))) {
            titleLine = i; foundTitle = true; break
          }
        }
        if (foundTitle) break
      }

      let start = offsets[titleLine] ?? 0
      let end = fullText.length

      // 2) snippet 对齐和结束定位（在标题之后搜索 end_snippet）
      const nearIndex = (snippet?: string, around?: number, span = 1200) => {
        if (!snippet || !snippet.trim()) return undefined
        const s = Math.max(0, (around ?? 0) - span)
        const epos = Math.min(fullText.length, (around ?? 0) + span)
        const window = fullText.slice(s, epos)

        // 构造安全正则：逐段构造，避免在已转义文本上做全局替换产生非法转义
        const isWs = (ch: string) => /\s/u.test(ch)
        const isPunc = (ch: string) => /[，。；、：:,.?？!！]/u.test(ch)
        const esc = (x: string) => x.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
        let pat = ''
        for (let i = 0; i < snippet.length;) {
          const ch = snippet[i]
          if (isWs(ch)) {
            while (i < snippet.length && isWs(snippet[i])) i++
            pat += '[\\s\\u3000]*'
          } else if (isPunc(ch)) {
            while (i < snippet.length && isPunc(snippet[i])) i++
            pat += '[\\s\\u3000,，。；、：:,.?？!！\\-—·]*'
          } else {
            let lit = ''
            while (i < snippet.length && !isWs(snippet[i]) && !isPunc(snippet[i])) { lit += snippet[i]; i++ }
            pat += esc(lit)
          }
        }

        try {
          const re = new RegExp(pat, 'u')
          const m = re.exec(window)
          if (m && typeof m.index === 'number') return s + m.index
        } catch (e) {
          // 忽略正则构造错误，进入退化路径
        }
        // 退化：精确子串匹配
        const idxRaw = window.indexOf(snippet)
        if (idxRaw >= 0) return s + idxRaw
        return undefined
      }

      const startHint = offsets[Math.max(0, Math.min(lines.length - 1, (e.start_line_hint ?? titleLine)))]
      const start2 = nearIndex(e.start_snippet, startHint)
      // 标题钉死策略：找到标题时，禁止用 snippet 把起点前推
      if (!foundTitle && start2 && start2 > start) start = start2 - Math.min(10, e.start_snippet?.length || 0)

      // 结束：优先 end_snippet；否则到下一个标题行或“签名”类锚点/文本末尾
      const end2 = nearIndex(e.end_snippet, start + 200)
      if (end2 && end2 > start) end = end2 + Math.min(10, e.end_snippet?.length || 0)
      else {
        // 到下一个标题或签名
        for (let i = titleLine + 1; i < Math.min(lines.length, titleLine + 2000); i++) {
          const t = lines[i].trim()
          if (headerFooter.test(t)) { end = offsets[i]; break }
          if (titleRes.some(x => x.re.test(t))) { end = offsets[i]; break }
        }
      }

      // 3) 页眉/页脚裁剪（剔除首尾的页眉脚行）
      const sliceText = fullText.slice(start, end)
      const sliceLines = sliceText.split('\n')
      let a = 0, b = sliceLines.length
      while (a < b && headerFooter.test(sliceLines[a].trim())) a++
      while (b - 1 > a && headerFooter.test(sliceLines[b - 1].trim())) b--
      const trimmed = sliceLines.slice(a, b).join('\n')

      // 4) 质量校验 + 回退
      const chinese = (trimmed.match(/[\u4e00-\u9fa5]/g) || []).length
      const ok = trimmed.length >= 20 && chinese / Math.max(1, trimmed.length) >= 0.3 && (foundTitle || (e.title && trimmed.includes(e.title.replace(/\s/g, ''))))
      let finalStart = start + (sliceLines.slice(0, a).join('\n').length + (a>0?1:0))
      let finalEnd = finalStart + trimmed.length

      if (!ok) {
        if (!fallbackSegments) fallbackSegments = segmentMedicalDocument(fullText)
        const near = findNearestSegment(fallbackSegments, start, e.type_code)
        if (near) { finalStart = near.startIndex; finalEnd = near.endIndex }
      }

      // 标题驱动的类型校正
      const titleText = (e.title || '').toLowerCase()
      let typeCode = e.type_code || ''
      if (/ct|核磁|mri|彩超|超声|x线|影像|检查记录/i.test(e.title || '')) {
        typeCode = 'imaging_report'
      } else if (/术前讨论记录/.test(e.title || '')) {
        typeCode = 'preoperative_summary'
      }

      // 确保 content 不为空，否则会被 validateAndCleanData 过滤掉
      const summary = e.summary || ''
      const contentText = summary.trim() ||
        fullText.slice(finalStart, Math.min(finalEnd, finalStart + (this.summaryMaxLength || 80))).replace(/\s+/g, ' ').trim() ||
        `${e.title || '未知文档'} - 内容摘要`

      results.push({
        id: `doc_${Date.now()}_${results.length}`,
        type: this.toDocumentType(typeCode || ''),
        title: e.title || '',
        content: contentText.slice(0, this.summaryMaxLength || 80),
        confidence: Math.max(0, Math.min(100, Number(e.confidence ?? 0))),
        extractedAt: new Date(),
        position: { startIndex: finalStart, endIndex: finalEnd, startMarker: e.start_snippet || '', endMarker: e.end_snippet || '' }
      })
    }

    // 结果收口：排序、防交叠、过滤
    results.sort((a,b)=> (a.position?.startIndex||0) - (b.position?.startIndex||0))
    for (let i=0;i<results.length-1;i++) {
      const cur = results[i], nxt = results[i+1]
      if (cur.position && nxt.position && cur.position.endIndex! > nxt.position.startIndex!) {
        cur.position.endIndex = Math.max(cur.position.startIndex!, Math.min(cur.position.endIndex!, nxt.position.startIndex!))
      }
    }
    const isChinese = (s:string)=> (s.match(/[\u4e00-\u9fa5]/g)||[]).length
    const filtered = results.filter((r, i)=>{
      const len = (r.position?.endIndex||0) - (r.position?.startIndex||0)
      const slice = fullText.slice(r.position?.startIndex||0, r.position?.endIndex||0)
      const zh = isChinese(slice)
      const zhRatio = zh/Math.max(1, slice.length)

      // 调试：打印被过滤的段落信息
      if (len < 5 || zhRatio < 0.05) {
        console.log(`[Filter] Removing doc ${i}: "${r.title}" len=${len} zhRatio=${zhRatio.toFixed(3)} slice="${slice.slice(0,50)}..."`)
        return false
      }
      return true
    })

    console.log('[Refine] entries:', entries.length, ' -> results:', results.length, ' -> filtered:', filtered.length)
    if (filtered.length === 0) {
      console.warn('[Refine] filtered to 0, returning unfiltered results as fallback')
      return results
    }
    return filtered
  }

  private getTypeLabel(t: DocumentType): string {
    const m: Record<DocumentType, string> = {
      [DocumentType.ADMISSION_RECORD]: '入院记录',
      [DocumentType.ADMISSION_RECORD_24H_IN]: '24小时内入院记录',
      [DocumentType.ADMISSION_RECORD_24H_OUT]: '24小时出入院记录',
      [DocumentType.FIRST_PROGRESS_NOTE]: '首次病程记录',
      [DocumentType.DAILY_PROGRESS_NOTE]: '日常病程记录',
      [DocumentType.ATTENDING_FIRST_PROGRESS]: '主治医生首次查房记录',
      [DocumentType.ATTENDING_PROGRESS]: '主治医生查房记录',
      [DocumentType.CONSULTATION_RECORD]: '会诊记录',
      [DocumentType.HANDOVER_RECORD]: '接班记录',
      [DocumentType.STAGE_SUMMARY]: '阶段小结',
      [DocumentType.OPERATION_RECORD]: '手术记录',
      [DocumentType.PREOPERATIVE_SUMMARY]: '术前小结',
      [DocumentType.DISCHARGE_RECORD]: '出院记录',
      [DocumentType.DEATH_RECORD]: '死亡记录',
      [DocumentType.DEATH_CASE_DISCUSSION]: '死亡病例讨论',
      [DocumentType.IMAGING_REPORT]: '影像检查报告',
      [DocumentType.LAB_REPORT]: '实验室检查报告',
      [DocumentType.OTHER_EXAMINATION]: '其他检查',
      [DocumentType.SURGERY_CONSENT]: '手术知情同意书',
      [DocumentType.ANESTHESIA_CONSENT]: '麻醉知情同意书',
      [DocumentType.BLOOD_TRANSFUSION_CONSENT]: '输血知情同意书',
      [DocumentType.SPECIAL_TREATMENT_CONSENT]: '特殊治疗知情同意书',
      [DocumentType.CRITICAL_ILLNESS_NOTICE]: '病危(重)通知书'
    }
    return m[t] || '文书'
  }

  private buildExtractionPrompt(text: string, options: ParseOptions): string {
    const systemPrompt = `你是一个专业的医疗信息抽取助手。请从以下病历文本中准确抽取结构化信息。

要求：
1. 严格按照JSON格式输出
2. 如果某个字段无法确定，请设置为null
3. 为每个抽取的字段提供置信度评分(0-100)
4. 自动识别和分类不同类型的医疗文书
5. 为每个文书提供在原文中的位置标识，用于后续提取完整内容

输出格式：
{
  "patientName": "患者姓名",
  "patientAge": 年龄数字,
  "patientGender": "性别",
  "department": "科室名称",
  "primaryDiagnosis": "主要诊断",
  "secondaryDiagnosis": ["次要诊断1", "次要诊断2"],
  "majorSurgery": "主要手术及操作",
  "documents": [
    {
      "type": "文书类型",
      "title": "文书标题",
      "content": "文书关键信息摘要（50-200字）",
      "confidence": 置信度分数,
      "position": {
        "startMarker": "文书开始的特征文本（10-30字）",
        "endMarker": "文书结束的特征文本（10-30字）"
      }
    }
  ],
  "confidence": 整体置信度分数
}

注意：
- content字段请提供简洁的摘要，不要包含完整内容
- startMarker应该是该文书开头的独特文本片段
- endMarker应该是该文书结尾的独特文本片段
- 标记文本应该足够独特，避免在其他地方重复出现`

    const userPrompt = `请分析以下病历文本：

${text}

请按照要求的JSON格式输出抽取结果。`

    return `${systemPrompt}\n\n${userPrompt}`
  }

  /**
   * 构建文档分类提示词
   */
  private buildClassificationPrompt(text: string): string {
    return `请判断以下医疗文本属于哪种类型的文书，并给出置信度评分：

文本内容：
${text.substring(0, 500)}...

可选类型：
- admission_record: 入院记录
- progress_note: 病程记录
- discharge_summary: 出院记录
- operation_record: 手术记录
- consultation: 会诊记录
- examination_report: 检查报告
- lab_report: 化验报告

请以JSON格式回复：
{
  "type": "文书类型",
  "confidence": 置信度分数(0-100),
  "title": "建议的文书标题"
}`
  }



  /**
   * 调用LLM API - 支持真实API和模拟模式
   */
  private async callLLMAPI(prompt: string): Promise<any> {
    // 如果没有配置API密钥，使用模拟模式
    if (!this.apiKey || this.apiKey === '') {
      console.warn('未配置API密钥，使用模拟模式')
      return this.getMockResponse()
    }

    try {
      // 调用真实的LLM API
      const response = await this.callRealAPI(prompt)
      return response
    } catch (error) {
      console.error('LLM API调用失败，回退到模拟模式:', error)
      return this.getMockResponse()
    }
  }

  /**
   * 调用真实的LLM API
   */
  private async callRealAPI(prompt: string): Promise<any> {
    // 通过后端代理调用，避免浏览器直连厂商引发CORS
    const requestBody = this.buildAPIRequest(prompt)

    // 代理URL：优先使用 VITE_API_BASE_URL；否则回退到同主机:8001；再不行用相对路径
    const BASE = this.resolveApiBase()
    const proxyUrl = BASE ? `${BASE}/api/v1/llm/parse-text` : '/api/v1/llm/parse-text'

    const payload = {
      requestBody,
      apiConfig: {
        apiEndpoint: this.apiEndpoint,
        apiKey: this.apiKey,
        model: this.model
      }
    }

    const response = await fetch(proxyUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })

    if (!response.ok) {
      const errText = await response.text().catch(() => '')
      throw new Error(`代理API请求失败: ${response.status} ${response.statusText} ${errText}`)
    }

    const data = await response.json()
    // 后端返回的是厂商原始响应或解析后的统一结构，统一用解析器兜底
    return this.parseAPIResponse(data)
  }

  /**
   * 构建API请求体 - 支持多种API格式
   */
  private buildAPIRequest(prompt: string): Record<string, unknown> {
    // OpenAI格式 (包括阿里云DashScope兼容模式)
    if (this.apiEndpoint.includes('openai.com') || this.apiEndpoint.includes('dashscope.aliyuncs.com')) {
      return {
        model: this.model,
        messages: [
          {
            role: 'system',
            content: '你是一个专业的医疗信息抽取助手，请严格按照JSON格式输出结果。'
          },
          {
            role: 'user',
            content: prompt
          }
        ],
        temperature: 0.1,
        max_tokens: 4000
      }
    }

    // 百度文心一言格式
    if (this.apiEndpoint.includes('baidu.com')) {
      return {
        messages: [
          {
            role: 'user',
            content: prompt
          }
        ],
        temperature: 0.1,
        top_p: 0.8,
        penalty_score: 1.0
      }
    }

    // 智谱ChatGLM格式 (也使用OpenAI兼容格式)
    if (this.apiEndpoint.includes('bigmodel.cn')) {
      return {
        model: this.model,
        messages: [
          {
            role: 'system',
            content: '你是一个专业的医疗信息抽取助手，请严格按照JSON格式输出结果。'
          },
          {
            role: 'user',
            content: prompt
          }
        ],
        temperature: 0.1,
        max_tokens: 4000
      }
    }

    // 默认使用OpenAI兼容格式 (大多数API都支持)
    return {
      model: this.model,
      messages: [
        {
          role: 'system',
          content: '你是一个专业的医疗信息抽取助手，请严格按照JSON格式输出结果。'
        },
        {
          role: 'user',
          content: prompt
        }
      ],
      temperature: 0.1,
      max_tokens: 4000
    }
  }

  /**
   * 解析API响应 - 支持多种API格式
   */
  private parseAPIResponse(data: any): any {
    let content = ''
    let tokensUsed = 0

    // OpenAI格式 (包括阿里云DashScope)
    if (data.choices && data.choices[0]) {
      content = data.choices[0].message?.content || data.choices[0].text || ''
      tokensUsed = data.usage?.total_tokens || 0
    }
    // 百度文心一言格式
    else if (data.result) {
      content = data.result
      tokensUsed = data.usage?.total_tokens || 0
    }
    // 通用格式
    else if (data.content) {
      content = data.content
      tokensUsed = data.tokens_used || 0
    }

    return {
      content,
      tokensUsed
    }
  }

  /**
   * 模拟响应数据
   */
  private async getMockResponse(): Promise<any> {
    // 模拟API调用延迟
    await new Promise(resolve => setTimeout(resolve, 2000 + Math.random() * 3000))

    return {
      content: JSON.stringify({
        patientName: "张三",
        patientAge: 65,
        patientGender: "男",
        department: "内科",
        primaryDiagnosis: "高血压病",
        secondaryDiagnosis: ["糖尿病", "冠心病"],
        majorSurgery: "无",
        documents: [
          {
            type: "admission_record",
            title: "入院记录",
            content: "患者张三，男，65岁，因头晕、头痛3天入院。患者3天前无明显诱因出现头晕、头痛，伴恶心，无呕吐...",
            confidence: 95
          },
          {
            type: "first_progress_note",
            title: "首次病程记录",
            content: "患者入院后完善相关检查，血压180/100mmHg，心率78次/分，律齐，各瓣膜听诊区未闻及病理性杂音...",
            confidence: 88
          }
        ],
        confidence: 89
      }),
      tokensUsed: 1250
    }
  }

  /**
   * 解析LLM响应 - 智能处理各种JSON格式
   */
  private parseResponse(response: any): ExtractedMedicalData {
    try {
      // 尝试直接解析JSON
      const data = JSON.parse(response.content)

      // 生成文档ID和时间戳
      if (data.documents) {
        data.documents = data.documents.map((doc, index: number) => ({
          ...doc,
          id: `doc_${Date.now()}_${index}`,
          extractedAt: new Date()
        }))
      }

      return data
    } catch (error) {
      // 尝试提取Markdown格式中的JSON部分
      try {
        const content = response.content
        const jsonStart = content.indexOf('{')
        const jsonEnd = content.lastIndexOf('}') + 1

        if (jsonStart !== -1 && jsonEnd > jsonStart) {
          const jsonStr = content.substring(jsonStart, jsonEnd)
          const data = JSON.parse(jsonStr)

          // 生成文档ID和时间戳
          if (data.documents) {
            data.documents = data.documents.map((doc, index: number) => ({
              ...doc,
              id: `doc_${Date.now()}_${index}`,
              extractedAt: new Date()
            }))
          }

          return data
        }
      } catch (extractError) {
        console.error('LLM响应解析失败:', extractError)
      }

      throw new Error('LLM响应解析失败')
    }
  }

  /**
   * 解析分类响应
   */
  private parseClassificationResponse(response: any): {
    type: DocumentType
    confidence: number
    title?: string
  } {
    try {
      const data = JSON.parse(response.content)
      return {
        type: data.type as DocumentType,
        confidence: data.confidence,
        title: data.title
      }
    } catch (error) {
      return {
        type: DocumentType.DAILY_PROGRESS_NOTE,
        confidence: 50
      }
    }
  }

  /**
   * 归一化类型并优先修正影像检查类型
   */
  private normalizeAndCorrectDocumentTypes(docs: ExtractedDocument[], fullText: string): ExtractedDocument[] {
    const lc = (s: any) => String(s || '').toLowerCase()

    // 严格的标题模式（仅当标题匹配时才重分类，避免内容提及误命中）
    const imagingTitleRe = /(ct|mri|核磁|磁共振|计算机断层扫描|cta|mra|dr)[^\n]{0,15}(检查(报告|记录|单)?|扫描(报告|记录|单)?|影像(报告|所见)?)/i
    const pathologyTitleRe = /(活体组织病理|组织病理|病理诊断|病理报告|冰冻切片|活检|穿刺病理)/i
    const surgeryTitleRe = /(手术记录|术中记录)/i
    const preopTitleRe = /(术前小结|术前讨论|术前主刀)/i

    // 进程/病程标题保护
    const progressGuardRe = /(病程|查房|首次|阶段小结|术后首次|主治医师|主任医师)/

    // 辅助内容特征（仅在标题含CT/MRI/病理关键词但未出现“报告/所见”时，用于增强判断）
    const imagingHeaderRe = /(检查所见|影像所见|所见[:：]|结论[:：]|建议[:：])/i
    const pathologyHeaderRe = /(肉眼检查|病理诊断|病理号|石蜡切片|冰冻切片)/i

    return (docs || []).map(d => {
      const title = d.title || ''
      const lowerTitle = lc(title)
      const typeStr = lc((d as any).type || (d as any).type_code || '')
      const header = lc((d.position?.fullContent || d.content || '').slice(0, 200))

      // 1) 先做别名归一
      const aliasMap: Record<string, DocumentType> = {
        imaging_examination: DocumentType.IMAGING_REPORT,
        imaging_exam: DocumentType.IMAGING_REPORT,
        imagingreport: DocumentType.IMAGING_REPORT,
        lab_report: DocumentType.LAB_REPORT,
        laboratory_test: DocumentType.LAB_REPORT,
        pathology_examination: DocumentType.OTHER_EXAMINATION,
        special_examination: DocumentType.OTHER_EXAMINATION,
        other_examination: DocumentType.OTHER_EXAMINATION
      }
      let normalized: DocumentType = this.toDocumentType(typeStr)
      if (aliasMap[typeStr]) normalized = aliasMap[typeStr]

      // 2) 手术/术前类优先级最高，直接保护
      if (surgeryTitleRe.test(title)) return { ...d, type: DocumentType.OPERATION_RECORD }
      if (preopTitleRe.test(title)) return { ...d, type: DocumentType.PREOPERATIVE_SUMMARY }

      // 3) 病程标题保护：若明显是病程/查房，不做影像/病理重分类
      if (progressGuardRe.test(title)) {
        return { ...d, type: normalized }
      }

      // 4) 影像/病理严格基于标题判断；如果标题只有“CT/MRI”等缩写，要求正文头部出现“所见/结论/建议”等
      const ctOrMriInTitle = /(ct|mri|核磁|磁共振|计算机断层扫描|cta|mra|dr)/i.test(title)

      if (imagingTitleRe.test(title) || (ctOrMriInTitle && imagingHeaderRe.test(header))) {
        normalized = DocumentType.IMAGING_REPORT
      } else if (pathologyTitleRe.test(title) || (/(病理)/.test(title) && pathologyHeaderRe.test(header))) {
        normalized = DocumentType.OTHER_EXAMINATION
      }

      return { ...d, type: normalized }
    })
  }

   private validateAndCleanData(data: ExtractedMedicalData, originalText?: string): ExtractedMedicalData {
    // 基础数据验证和清理
    const cleanedData = {
      ...data,
      patientName: data.patientName?.trim() || '',
      department: data.department?.trim() || '',
      primaryDiagnosis: data.primaryDiagnosis?.trim() || '',
      majorSurgery: data.majorSurgery?.trim() || '',
      documents: data.documents?.filter(doc => doc.content?.trim()) || []
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
   * 由开始/结束标记在原文中定位边界（兼容旧逻辑）
   */
  private findDocumentBoundaries(
    text: string,
    startMarker: string,
    endMarker: string,
    documentType: DocumentType
  ): { success: boolean; startIndex?: number; endIndex?: number; fullContent?: string; error?: string } {
    let startIndex = text.indexOf(startMarker)
    if (startIndex < 0) {
      // 允许稍微模糊匹配
      const m = this.findBestMatch(text, startMarker)
      if (m.found) startIndex = m.index
    }
    if (startIndex < 0) return { success: false, error: '未找到startMarker' }

    let endIndex = -1
    if (endMarker) {
      const after = text.indexOf(endMarker, startIndex + startMarker.length)
      if (after > startIndex) endIndex = after
    }

    if (endIndex < 0) {
      const tryEnd = this.inferDocumentEnd(text, startIndex, documentType)
      if (tryEnd.success && tryEnd.endIndex) endIndex = tryEnd.endIndex
    }

    if (endIndex <= startIndex) return { success: false, error: 'endIndex无效' }

    const valid = this.validateDocumentBoundaries(text, startIndex, endIndex, documentType)
    if (!valid.valid) return { success: false, error: valid.error }

    return {
      success: true,
      startIndex,
      endIndex,
      fullContent: text.slice(startIndex, endIndex)
    }
  }

  /**
   * 获取支持的文档类型
   */
  static getSupportedDocumentTypes(): Array<{
    value: DocumentType
    label: string
    description: string
  }> {
    return [
      // 入院记录
      { value: DocumentType.ADMISSION_RECORD, label: '入院记录', description: '患者入院时的基本信息和病情记录' },
      { value: DocumentType.ADMISSION_RECORD_24H_IN, label: '24小时内入院记录', description: '24小时内入院患者的记录' },
      { value: DocumentType.ADMISSION_RECORD_24H_OUT, label: '24小时出入院记录', description: '24小时内出入院患者的记录' },

      // 病程记录
      { value: DocumentType.FIRST_PROGRESS_NOTE, label: '首次病程记录', description: '患者入院后的首次病程记录' },
      { value: DocumentType.DAILY_PROGRESS_NOTE, label: '日常病程记录', description: '住院期间的日常病程变化记录' },
      { value: DocumentType.ATTENDING_FIRST_PROGRESS, label: '主治医生首次查房记录', description: '主治医生首次查房的详细记录' },
      { value: DocumentType.ATTENDING_PROGRESS, label: '主治医生查房记录', description: '主治医生查房的记录' },
      { value: DocumentType.CONSULTATION_RECORD, label: '会诊记录', description: '多科室会诊的讨论和建议记录' },
      { value: DocumentType.HANDOVER_RECORD, label: '接班记录', description: '医生交接班的记录' },
      { value: DocumentType.STAGE_SUMMARY, label: '阶段小结', description: '治疗阶段的总结记录' },

      // 手术记录
      { value: DocumentType.OPERATION_RECORD, label: '手术记录', description: '手术过程的详细记录' },
      { value: DocumentType.PREOPERATIVE_SUMMARY, label: '术前小结', description: '手术前的病情总结和手术计划' },

      // 出院记录
      { value: DocumentType.DISCHARGE_RECORD, label: '出院记录', description: '患者出院时的病情总结和后续建议' },
      { value: DocumentType.DEATH_RECORD, label: '死亡记录', description: '患者死亡的相关记录' },
      { value: DocumentType.DEATH_CASE_DISCUSSION, label: '死亡病例讨论记录', description: '死亡病例的讨论和分析记录' },

      // 辅助检查
      { value: DocumentType.IMAGING_REPORT, label: '影像检查报告', description: 'X光、CT、MRI等影像检查报告' },
      { value: DocumentType.LAB_REPORT, label: '实验室检查报告', description: '血液、尿液等实验室检验报告' },
      { value: DocumentType.OTHER_EXAMINATION, label: '其他检查报告', description: '其他各种医学检查报告' },

      // 知情同意书
      { value: DocumentType.SURGERY_CONSENT, label: '手术知情同意书', description: '手术前的知情同意文件' },
      { value: DocumentType.ANESTHESIA_CONSENT, label: '麻醉知情同意书', description: '麻醉前的知情同意文件' },
      { value: DocumentType.BLOOD_TRANSFUSION_CONSENT, label: '输血知情同意书', description: '输血前的知情同意文件' },
      { value: DocumentType.SPECIAL_TREATMENT_CONSENT, label: '特殊治疗知情同意书', description: '特殊治疗的知情同意文件' },
      { value: DocumentType.CRITICAL_ILLNESS_NOTICE, label: '病危(重)通知书', description: '病危或病重患者的通知文件' }
    ]
  }

  /**
   * 文本标准化处理
   */
  private normalizeText(text: string): string {
    return text
      .replace(/\s+/g, ' ')           // 合并多个空格
      .replace(/[\r\n]+/g, '\n')      // 统一换行符
      .replace(/[""'']/g, '"')        // 统一引号
      .replace(/[（）]/g, match => match === '（' ? '(' : ')')  // 统一括号
      .trim()
  }

  /**
   * 模糊匹配查找最佳位置
   */
  private findBestMatch(text: string, marker: string): { found: boolean; index: number; similarity?: number } {
    // 1. 精确匹配
    const exactIndex = text.indexOf(marker)
    if (exactIndex !== -1) {
      return { found: true, index: exactIndex, similarity: 1.0 }
    }

    // 2. 模糊匹配（处理轻微的文本差异）
    const markerWords = marker.split(/\s+/).filter(word => word.length > 1)
    if (markerWords.length === 0) {
      return { found: false, index: -1 }
    }

    let bestMatch = { found: false, index: -1, similarity: 0 }
    const windowSize = marker.length + 50 // 搜索窗口

    for (let i = 0; i <= text.length - marker.length; i += 10) {
      const window = text.substring(i, i + windowSize)
      const similarity = this.calculateSimilarity(marker, window)

      if (similarity > 0.8 && similarity > bestMatch.similarity) {
        bestMatch = { found: true, index: i, similarity }
      }
    }

    return bestMatch
  }

  /**
   * 计算文本相似度
   */
  private calculateSimilarity(text1: string, text2: string): number {
    const words1 = text1.split(/\s+/)
    const words2 = text2.split(/\s+/)

    let matchCount = 0
    for (const word of words1) {
      if (word.length > 1 && text2.includes(word)) {
        matchCount++
      }
    }

    return matchCount / words1.length
  }

  /**
   * 智能推断文书结束位置
   */
  private inferDocumentEnd(
    text: string,
    startIndex: number,
    documentType: DocumentType
  ): { success: boolean; endIndex?: number } {
    // 常见的文书结束标识
    const endPatterns = [
      /\n\s*[一二三四五六七八九十]+[、\.]\s*\w+[:：]/,  // 下一个章节开始
      /\n\s*\d+[、\.]\s*\w+[:：]/,                    // 数字编号的下一节
      /\n\s*[A-Z]+[、\.]\s*\w+[:：]/,                 // 字母编号的下一节
      /\n\s*(主治医师|主任医师|医师|护士)[:：]/,        // 下一个医护人员记录
      /\n\s*(入院记录|病程记录|出院记录|手术记录)[:：]/, // 下一个文书类型
      /\n\s*\d{4}年\d{1,2}月\d{1,2}日/,              // 日期标识
      /\n\s*签名[:：]/,                               // 签名标识
      /\n\s*医师[:：]/                                // 医师签名
    ]

    const searchText = text.substring(startIndex)
    let bestEndIndex = -1
    let minDistance = Infinity

    for (const pattern of endPatterns) {
      const match = pattern.exec(searchText)
      if (match && match.index < minDistance) {
        minDistance = match.index
        bestEndIndex = startIndex + match.index
      }
    }

    // 如果没有找到明确的结束标识，使用启发式方法
    if (bestEndIndex === -1) {
      const maxLength = this.getMaxDocumentLength(documentType)
      const heuristicEnd = Math.min(startIndex + maxLength, text.length)

      // 尝试在合理位置找到句号或换行
      const reasonableEnd = this.findReasonableEndPoint(
        text.substring(startIndex, heuristicEnd)
      )

      if (reasonableEnd > 0) {
        bestEndIndex = startIndex + reasonableEnd
      }
    }

    return bestEndIndex > startIndex
      ? { success: true, endIndex: bestEndIndex }
      : { success: false }
  }

  /**
   * 获取不同文书类型的最大长度
   */
  private getMaxDocumentLength(documentType: DocumentType): number {
    const lengthMap: Record<DocumentType, number> = {
      [DocumentType.ADMISSION_RECORD]: 2000,
      [DocumentType.ADMISSION_RECORD_24H_IN]: 1500,
      [DocumentType.ADMISSION_RECORD_24H_OUT]: 1500,
      [DocumentType.FIRST_PROGRESS_NOTE]: 1000,
      [DocumentType.DAILY_PROGRESS_NOTE]: 800,
      [DocumentType.ATTENDING_FIRST_PROGRESS]: 1200,
      [DocumentType.ATTENDING_PROGRESS]: 800,
      [DocumentType.CONSULTATION_RECORD]: 1000,
      [DocumentType.HANDOVER_RECORD]: 600,
      [DocumentType.STAGE_SUMMARY]: 800,
      [DocumentType.OPERATION_RECORD]: 1500,
      [DocumentType.PREOPERATIVE_SUMMARY]: 800,
      [DocumentType.DISCHARGE_RECORD]: 1200,
      [DocumentType.DEATH_RECORD]: 1000,
      [DocumentType.DEATH_CASE_DISCUSSION]: 1500,
      [DocumentType.IMAGING_REPORT]: 600,
      [DocumentType.LAB_REPORT]: 400,
      [DocumentType.OTHER_EXAMINATION]: 600,
      [DocumentType.SURGERY_CONSENT]: 800,
      [DocumentType.ANESTHESIA_CONSENT]: 600,
      [DocumentType.BLOOD_TRANSFUSION_CONSENT]: 500,
      [DocumentType.SPECIAL_TREATMENT_CONSENT]: 700,
      [DocumentType.CRITICAL_ILLNESS_NOTICE]: 400
    }

    return lengthMap[documentType] || 1000
  }

  /**
   * 在文本中找到合理的结束点
   */
  private findReasonableEndPoint(text: string): number {
    // 优先在句号后结束
    const sentences = text.split(/[。！？]/)
    if (sentences.length > 1) {
      let totalLength = 0
      for (let i = 0; i < sentences.length - 1; i++) {
        totalLength += sentences[i].length + 1 // +1 for the punctuation
        if (totalLength > text.length * 0.8) { // 至少80%的内容
          return totalLength
        }
      }
    }

    // 其次在换行符处结束
    const lines = text.split('\n')
    if (lines.length > 1) {
      let totalLength = 0
      for (let i = 0; i < lines.length - 1; i++) {
        totalLength += lines[i].length + 1 // +1 for the newline
        if (totalLength > text.length * 0.9) { // 至少90%的内容
          return totalLength
        }
      }
    }

    return text.length
  }

  /**
   * 验证文书边界的合理性
   */
  private validateDocumentBoundaries(
    text: string,
    startIndex: number,
    endIndex: number,
    documentType: DocumentType
  ): { valid: boolean; error?: string } {
    // 1. 基本边界检查
    if (startIndex < 0 || endIndex <= startIndex || endIndex > text.length) {
      return { valid: false, error: '边界索引无效' }
    }

    // 2. 长度合理性检查
    const contentLength = endIndex - startIndex
    const minLength = 20  // 最小长度
    const maxLength = this.getMaxDocumentLength(documentType) * 2 // 最大长度的2倍作为上限

    if (contentLength < minLength) {
      return { valid: false, error: `内容过短 (${contentLength} < ${minLength})` }
    }

    if (contentLength > maxLength) {
      return { valid: false, error: `内容过长 (${contentLength} > ${maxLength})` }
    }

    // 3. 内容质量检查
    const content = text.substring(startIndex, endIndex)
    const chineseCharCount = (content.match(/[\u4e00-\u9fa5]/g) || []).length
    const chineseRatio = chineseCharCount / content.length

    if (chineseRatio < 0.3) { // 中文字符比例过低
      return { valid: false, error: '中文内容比例过低，可能不是有效的医疗文书' }
    }

    return { valid: true }
  }

  /**
   * 构建文件解析提示词
   */
  private buildFileExtractionPrompt(options: ParseOptions): string {
    const sections = []

    sections.push('你是一个专业的医疗信息抽取助手。请分析上传的医疗文档，提取其中的结构化信息。')

    if (options.extractPatientInfo) {
      sections.push('\n请提取以下患者基本信息：')
      sections.push('- 姓名、性别、年龄')
      sections.push('- 入院日期、出院日期')
      sections.push('- 科室、床号')
      sections.push('- 住院号、病历号')
    }

    if (options.extractDiagnosis) {
      sections.push('\n请提取诊断信息：')
      sections.push('- 入院诊断')
      sections.push('- 出院诊断')
      sections.push('- 主要诊断')
      sections.push('- 次要诊断')
    }

    if (options.extractSurgeryInfo) {
      sections.push('\n请提取手术信息：')
      sections.push('- 手术名称')
      sections.push('- 手术日期')
      sections.push('- 主刀医师')
      sections.push('- 手术部位')
    }

    if (options.classifyDocuments) {
      sections.push('\n请识别并分类文档中包含的所有医疗文书类型：')
      sections.push('- 入院记录')
      sections.push('- 病程记录')
      sections.push('- 出院小结')
      sections.push('- 手术记录')
      sections.push('- 检查报告')
      sections.push('- 化验报告')
      sections.push('- 医嘱单')
      sections.push('- 护理记录')
      sections.push('- 知情同意书')
      sections.push('- 其他医疗文书')
    }

    sections.push('\n请严格按照以下JSON格式输出结果：')
    sections.push(JSON.stringify({
      patientName: "患者姓名",
      gender: "性别",
      age: "年龄",
      department: "科室",
      admissionDate: "入院日期",
      dischargeDate: "出院日期",
      primaryDiagnosis: "主要诊断",
      secondaryDiagnosis: ["次要诊断列表"],
      majorSurgery: "主要手术",
      documents: [
        {
          id: "文书ID",
          type: "文书类型",
          title: "文书标题",
          content: "文书内容摘要",
          confidence: 0.95
        }
      ]
    }, null, 2))

    return sections.join('\n')
  }

  /**
   * 调用支持文件上传的LLM API
   */
  private async callLLMAPIWithFile(prompt: string, file: File): Promise<any> {
    try {
      // 构建FormData
      const formData = new FormData()
      formData.append('file', file)
      formData.append('prompt', prompt)
      formData.append('model', this.model)

      // 构建请求头
      const headers: Record<string, string> = {
        'Authorization': `Bearer ${this.apiKey}`
      }

      console.log('发送文件到LLM API:', {
        endpoint: this.apiEndpoint,
        fileName: file.name,
        fileSize: file.size,
        model: this.model
      })

      // 发送请求
      const response = await fetch(this.apiEndpoint, {
        method: 'POST',
        headers,
        body: formData
      })

      if (!response.ok) {
        const errorText = await response.text()
        console.error('LLM API错误响应:', {
          status: response.status,
          statusText: response.statusText,
          body: errorText
        })
        throw new Error(`API请求失败: ${response.status} ${response.statusText}`)
      }

      const data = await response.json()
      console.log('LLM API响应:', data)

      return this.parseAPIResponse(data)
    } catch (error) {
      console.error('调用LLM API失败:', error)
      throw error
    }
  }
}

// 创建默认实例
export const llmService = new LLMService()

// 类型已在上面导出，这里不需要重复导出
