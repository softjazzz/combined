/**
 * 响应解析器 - 负责解析LLM API的响应
 */

import { ExtractedMedicalData, ExtractedDocument, DocumentType, LLMResponse } from '@/types/medical'
import { DocumentClassifier } from './documentClassifier'
import { EnhancedDocumentClassifier } from './enhancedDocumentClassifier'

export class ResponseParser {
  /**
   * 解析医疗文本提取的响应
   */
  static parseMedicalResponse(response: any): ExtractedMedicalData {
    try {
      let data: any

      // 移除调试日志，指针模式应该能避免解析问题

      // 处理不同格式的响应
      if (typeof response === 'string') {
        data = this.tryParseJsonLoose(response)
      } else if (response && response.choices && response.choices[0]) {
        // OpenAI格式响应
        const content = response.choices[0].message?.content || response.choices[0].text
        return this.parseMedicalResponse(content)
      } else if (response && typeof response.text === 'string') {
        // 后端代理在无法解析JSON时会返回 { text: '...' }
        return this.parseMedicalResponse(response.text)
      } else {
        data = response
      }

      // 兼容：若顶层就是数组，按 documents 数组处理
      if (Array.isArray(data)) {
        data = { documents: data }
      }

      // 验证和清理数据 - 增强患者信息处理
      const result: ExtractedMedicalData = {
        recordNumber: this.cleanString(data.recordNumber) || '未识别',
        patientName: this.extractPatientName(data, response) || '未识别',
        patientAge: this.extractPatientAge(data, response),
        patientGender: this.extractPatientGender(data, response),
        department: this.extractDepartment(data, response) || '未识别',
        primaryDiagnosis: this.cleanString(data.primaryDiagnosis) || '未识别',
        secondaryDiagnosis: this.parseStringArray(data.secondaryDiagnosis),
        majorSurgery: this.cleanString(data.majorSurgery) || '无',
        documents: this.parseDocuments(data.documents || []),
        confidence: this.parseConfidence(data.confidence),
        content: data.content
      }

      return result
    } catch (error) {
      console.error('解析医疗响应失败:', error)

      // 尝试从原始响应中提取一些基本信息作为fallback
      let fallbackData: any = {}
      if (typeof response === 'string') {
        // 尝试用正则提取一些基本字段
        const patientNameMatch = response.match(/["']?patientName["']?\s*:\s*["']([^"']+)["']?/i)
        const departmentMatch = response.match(/["']?department["']?\s*:\s*["']([^"']+)["']?/i)
        const diagnosisMatch = response.match(/["']?primaryDiagnosis["']?\s*:\s*["']([^"']+)["']?/i)

        if (patientNameMatch) fallbackData.patientName = patientNameMatch[1]
        if (departmentMatch) fallbackData.department = departmentMatch[1]
        if (diagnosisMatch) fallbackData.primaryDiagnosis = diagnosisMatch[1]
      }

      // 返回默认结构
      return {
        recordNumber: fallbackData.recordNumber || '未识别',
        patientName: fallbackData.patientName || '未识别',
        department: fallbackData.department || '未识别',
        primaryDiagnosis: fallbackData.primaryDiagnosis || '未识别',
        majorSurgery: fallbackData.majorSurgery || '无',
        documents: [],
        confidence: 0.1
      }
    }
  }

  // 尝试宽松解析字符串中的 JSON
  private static tryParseJsonLoose(raw: string): any {
    const removeCodeFence = (s: string) => s.replace(/```json/gi, '').replace(/```/g, '').trim()
    const removeTrailingCommas = (s: string) => s.replace(/,\s*([}\]])/g, '$1')
    const sanitize = (s: string) => s.replace(/[\u0000-\u001F]+/g, ' ').trim()

    const cleaned = sanitize(removeCodeFence(raw))

    // 如果返回里包含 "error" 或 "message" 且不是 JSON，很可能是供应商的提示文本；尽量截取第一对大括号
    if (/error\s*:/.test(cleaned) && !/^\s*[\[{]/.test(cleaned)) {
      const fb = cleaned.indexOf('{')
      const lb = cleaned.lastIndexOf('}')
      if (fb !== -1 && lb !== -1 && lb > fb) {
        const obj = cleaned.slice(fb, lb + 1)
        try { return JSON.parse(removeTrailingCommas(obj)) } catch {}
      }
    }

    // 1) 优先尝试直接解析（去掉尾随逗号）
    const direct = removeTrailingCommas(cleaned)
    try { return JSON.parse(direct) } catch {}

    // 2) 检查是否是被截断的JSON，尝试修复
    const repaired = this.repairTruncatedJson(cleaned)
    if (repaired) {
      try { return JSON.parse(removeTrailingCommas(repaired)) } catch {}
    }

    // 3) 提取最外层大括号或方括号中，最长“平衡”的片段
    const longestBalanced = this.extractLongestBalancedJson(cleaned)
    if (longestBalanced) {
      try { return JSON.parse(removeTrailingCommas(longestBalanced)) } catch {}
    }

    // 4) 简单的 { ... } 回退
    const fb = cleaned.indexOf('{')
    const lb = cleaned.lastIndexOf('}')
    if (fb !== -1 && lb !== -1 && lb > fb) {
      const obj = cleaned.slice(fb, lb + 1)
      try { return JSON.parse(removeTrailingCommas(obj)) } catch {}
    }

    throw new Error('无法从字符串中解析出有效的JSON')
  }

  // 修复被截断的JSON
  private static repairTruncatedJson(json: string): string | null {
    try {
      // 检查是否以 { 开始但没有正确结束
      if (json.trim().startsWith('{') && !json.trim().endsWith('}')) {
        let repaired = json.trim()

        // 找到最后一个完整的字段，移除可能不完整的内容
        const lastCommaIndex = repaired.lastIndexOf(',')
        const lastColonIndex = repaired.lastIndexOf(':')

        if (lastColonIndex > lastCommaIndex) {
          // 最后一个字段可能不完整，截断到最后一个逗号
          if (lastCommaIndex > 0) {
            repaired = repaired.substring(0, lastCommaIndex)
          }
        }

        // 确保字符串字段正确闭合
        let openQuotes = 0
        let lastQuoteIndex = -1
        for (let i = 0; i < repaired.length; i++) {
          if (repaired[i] === '"' && (i === 0 || repaired[i-1] !== '\\')) {
            openQuotes++
            lastQuoteIndex = i
          }
        }

        // 如果有未闭合的引号，在最后一个引号后截断
        if (openQuotes % 2 !== 0 && lastQuoteIndex > 0) {
          repaired = repaired.substring(0, lastQuoteIndex + 1)
          // 移除可能的尾随逗号
          repaired = repaired.replace(/,\s*$/, '')
        }

        // 添加闭合大括号
        repaired += '}'

        return repaired
      }

      return null
    } catch (e) {
      return null
    }
  }

  // 从字符串中提取最长的、括号配对完整的 JSON 片段
  private static extractLongestBalancedJson(s: string): string | null {
    const openers = new Set(['{', '['])
    const closers: Record<string, string> = { '}': '{', ']': '[' }

    let lastBalancedEnd = -1
    let stack: string[] = []
    let inString = false
    let escape = false
    let start = -1

    for (let i = 0; i < s.length; i++) {
      const ch = s[i]

      if (inString) {
        if (escape) {
          escape = false
        } else if (ch === '\\') {
          escape = true
        } else if (ch === '"') {
          inString = false
        }
        continue
      }

      if (ch === '"') { inString = true; if (start === -1) start = i; continue }
      if (openers.has(ch)) { stack.push(ch); if (start === -1) start = i; continue }
      if (ch in closers) {
        if (stack.length === 0 || stack[stack.length - 1] !== closers[ch]) {
          // 非法配对，重置
          stack = []
          start = -1
          continue
        }
        stack.pop()
        if (stack.length === 0 && start !== -1) {
          lastBalancedEnd = i
        }
      }
    }

    if (lastBalancedEnd !== -1 && start !== -1 && lastBalancedEnd > start) {
      let candidate = s.slice(start, lastBalancedEnd + 1)
      // 清理片段中的尾随逗号
      candidate = candidate.replace(/,\s*([}\]])/g, '$1')
      return candidate
    }
    return null
  }

  /**
   * 解析文档索引响应（指针模式专用）
   */
  static parseIndexResponse(response: any): any {
    try {
      let data: any

      // 处理不同格式的响应
      if (typeof response === 'string') {
        data = this.tryParseJsonLoose(response)
      } else if (response && response.choices && response.choices[0]) {
        const content = response.choices[0].message?.content || response.choices[0].text
        return this.parseIndexResponse(content)
      } else if (response && typeof response.text === 'string') {
        return this.parseIndexResponse(response.text)
      } else {
        data = response
      }

      // 确保返回基本结构
      return {
        recordNumber: this.cleanString(data.recordNumber) || '未识别',
        patientName: this.cleanString(data.patientName) || '未识别',
        patientAge: this.parseAge(data.patientAge),
        patientGender: this.parseGender(data.patientGender),
        department: this.cleanString(data.department) || '未识别',
        primaryDiagnosis: this.cleanString(data.primaryDiagnosis) || '未识别',
        secondaryDiagnosis: this.parseStringArray(data.secondaryDiagnosis),
        majorSurgery: this.cleanString(data.majorSurgery) || '无',
        documents: Array.isArray(data.documents) ? data.documents : [],
        confidence: this.parseConfidence(data.confidence)
      }
    } catch (error) {
      console.error('解析索引响应失败:', error)

      // 返回默认结构
      return {
        recordNumber: '未识别',
        patientName: '未识别',
        department: '未识别',
        primaryDiagnosis: '未识别',
        majorSurgery: '无',
        documents: [],
        confidence: 0.1
      }
    }
  }

  /**
   * 解析文档数组（升级版 - 支持层级化分类）
   */
  private static parseDocuments(documents: any[]): ExtractedDocument[] {
    if (!Array.isArray(documents)) {
      return []
    }

    const enhancedClassifier = new EnhancedDocumentClassifier()

    return documents.map((doc: any, index: any) => {
      try {
        // 创建基础文档对象
        const baseDoc: ExtractedDocument = {
          id: doc.id || `doc_${index + 1}`,
          type: this.parseDocumentType(doc.type),
          title: this.cleanString(doc.title) || `文书${index + 1}`,
          content: this.cleanString(doc.content) || '暂无内容',
          confidence: this.parseConfidence(doc.confidence),
          extractedAt: new Date(),
          position: doc.position ? {
            startMarker: doc.position.startMarker || '',
            endMarker: doc.position.endMarker || '',
            startIndex: doc.position.startIndex,
            endIndex: doc.position.endIndex,
            fullContent: doc.position.fullContent
          } : undefined
        }

        // 处理层级化分类
        let category = doc.category
        let type = doc.type

        // 如果LLM没有提供分类信息，使用增强分类器
        if (!category || !type) {
          const classification = enhancedClassifier.classify(baseDoc)
          category = category || classification.category
          type = type || classification.type

          // 更新置信度（如果分类器置信度更低，则降低整体置信度）
          if (classification.confidence < baseDoc.confidence) {
            baseDoc.confidence = Math.min(baseDoc.confidence, classification.confidence + 0.1)
          }
        }

        // 添加分类信息到文档对象
        return {
          ...baseDoc,
          category,
          type: this.parseDocumentType(type),
          classificationMethod: doc.category && doc.type ? 'llm_provided' : 'enhanced_classifier'
        }
      } catch (error) {
        console.error(`解析文档${index}失败:`, error)
        return {
          id: `doc_${index + 1}`,
          type: DocumentType.DAILY_PROGRESS_NOTE,
          title: `文书${index + 1}`,
          content: '解析失败',
          confidence: 0.1,
          extractedAt: new Date()
        }
      }
    })
  }

  /**
   * 解析文档类型
   */
  private static parseDocumentType(type: any): DocumentType {
    if (typeof type === 'string' && Object.values(DocumentType).includes(type as DocumentType)) {
      return type as DocumentType
    }
    return DocumentType.DAILY_PROGRESS_NOTE
  }

  /**
   * 清理字符串
   */
  private static cleanString(value: any): string | undefined {
    if (typeof value !== 'string') {
      return undefined
    }
    
    const cleaned = value.trim()
    if (cleaned === '' || cleaned === '未识别' || cleaned === 'null' || cleaned === 'undefined') {
      return undefined
    }
    
    return cleaned
  }

  /**
   * 解析年龄
   */
  private static parseAge(age): number | undefined {
    if (typeof age === 'number' && age > 0 && age < 150) {
      return Math.floor(age)
    }
    
    if (typeof age === 'string') {
      const match = age.match(/(\d+)/)
      if (match) {
        const parsed = parseInt(match[1])
        if (parsed > 0 && parsed < 150) {
          return parsed
        }
      }
    }
    
    return undefined
  }

  /**
   * 解析性别
   */
  private static parseGender(gender): string | undefined {
    if (typeof gender !== 'string') {
      return undefined
    }

    const cleaned = gender.trim().toLowerCase()
    if (cleaned.includes('男') || cleaned.includes('male') || cleaned === 'm') {
      return '男'
    }
    if (cleaned.includes('女') || cleaned.includes('female') || cleaned === 'f') {
      return '女'
    }

    return undefined
  }

  /**
   * 增强的患者姓名提取
   */
  private static extractPatientName(data: any, originalResponse?: any): string | undefined {
    // 首先尝试从结构化数据中获取
    let name = this.cleanString(data.patientName)
    if (name && name !== '未识别') {
      return name
    }

    // 如果没有找到，尝试从原始响应中提取
    if (typeof originalResponse === 'string') {
      // 匹配常见的姓名格式
      const patterns = [
        /姓名[:：]\s*([^\s\n,，。]+)/,
        /患者\s*([^\s\n,，。]+)，/,
        /患者姓名[:：]\s*([^\s\n,，。]+)/,
        /"patientName"\s*[:：]\s*"([^"]+)"/,
        /病人\s*([^\s\n,，。]+)，/
      ]

      for (const pattern of patterns) {
        const match = originalResponse.match(pattern)
        if (match && match[1] && match[1].trim().length >= 2) {
          const extractedName = match[1].trim()
          // 验证是否为有效姓名（中文姓名通常2-4个字符）
          if (/^[\u4e00-\u9fa5]{2,4}$/.test(extractedName)) {
            return extractedName
          }
        }
      }
    }

    return undefined
  }

  /**
   * 增强的患者年龄提取
   */
  private static extractPatientAge(data: any, originalResponse?: any): number | undefined {
    // 首先尝试从结构化数据中获取
    let age = this.parseAge(data.patientAge)
    if (age !== undefined) {
      return age
    }

    // 如果没有找到，尝试从原始响应中提取
    if (typeof originalResponse === 'string') {
      const patterns = [
        /年龄[:：]\s*(\d+)[岁]?/,
        /(\d+)岁/,
        /，(\d+)岁，/,
        /"patientAge"\s*[:：]\s*(\d+)/,
        /患者[^，]*，[^，]*，(\d+)岁/
      ]

      for (const pattern of patterns) {
        const match = originalResponse.match(pattern)
        if (match && match[1]) {
          const extractedAge = parseInt(match[1])
          if (extractedAge > 0 && extractedAge < 150) {
            return extractedAge
          }
        }
      }
    }

    return undefined
  }

  /**
   * 增强的患者性别提取
   */
  private static extractPatientGender(data: any, originalResponse?: any): string | undefined {
    // 首先尝试从结构化数据中获取
    let gender = this.parseGender(data.patientGender)
    if (gender) {
      return gender
    }

    // 如果没有找到，尝试从原始响应中提取
    if (typeof originalResponse === 'string') {
      const patterns = [
        /性别[:：]\s*([男女])/,
        /患者[^，]*，([男女])，/,
        /"patientGender"\s*[:：]\s*"([男女])"/,
        /，([男女])性，/,
        /，([男女])，\d+岁/
      ]

      for (const pattern of patterns) {
        const match = originalResponse.match(pattern)
        if (match && match[1]) {
          return match[1] === '男' ? '男' : '女'
        }
      }
    }

    return undefined
  }

  /**
   * 增强的科室信息提取
   */
  private static extractDepartment(data: any, originalResponse?: any): string | undefined {
    // 首先尝试从结构化数据中获取
    let department = this.cleanString(data.department)
    if (department && department !== '未识别') {
      return department
    }

    // 如果没有找到，尝试从原始响应中提取
    if (typeof originalResponse === 'string') {
      const patterns = [
        /科室[:：]\s*([^\s\n,，。]+)/,
        /入院科室[:：]\s*([^\s\n,，。]+)/,
        /"department"\s*[:：]\s*"([^"]+)"/,
        /([^\s]+科)\s*病程记录/,
        /([^\s]+科)\s*住院病历/
      ]

      for (const pattern of patterns) {
        const match = originalResponse.match(pattern)
        if (match && match[1] && match[1].trim().length >= 2) {
          const extractedDept = match[1].trim()
          // 验证是否为有效科室名称
          if (/科$/.test(extractedDept) || /部$/.test(extractedDept)) {
            return extractedDept
          }
        }
      }
    }

    return undefined
  }

  /**
   * 解析字符串数组
   */
  private static parseStringArray(value): string[] {
    if (Array.isArray(value)) {
      return value
        .map(item => this.cleanString(item))
        .filter(item => item !== undefined) as string[]
    }
    
    if (typeof value === 'string') {
      return [value].filter(item => this.cleanString(item) !== undefined) as string[]
    }
    
    return []
  }

  /**
   * 解析置信度
   */
  private static parseConfidence(confidence: any): number {
    if (typeof confidence === 'number') {
      return Math.max(0, Math.min(1, confidence))
    }
    
    if (typeof confidence === 'string') {
      const parsed = parseFloat(confidence)
      if (!isNaN(parsed)) {
        return Math.max(0, Math.min(1, parsed))
      }
    }
    
    return 0.5 // 默认置信度
  }

  /**
   * 解析批量处理响应
   */
  static parseBatchResponse(response): ExtractedMedicalData[] {
    try {
      let data: any[]

      if (typeof response === 'string') {
        const jsonMatch = response.match(/\[[\s\S]*\]/)
        if (jsonMatch) {
          data = JSON.parse(jsonMatch[0])
        } else {
          throw new Error('无法找到JSON数组格式的响应')
        }
      } else if (Array.isArray(response)) {
        data = response
      } else {
        throw new Error('响应格式不正确')
      }

      return data.map((item, index) => {
        try {
          return this.parseMedicalResponse(item)
        } catch (error) {
          console.error(`解析批量项目${index}失败:`, error)
          return {
            recordNumber: `批量_${index + 1}`,
            patientName: '解析失败',
            department: '未识别',
            primaryDiagnosis: '解析失败',
            majorSurgery: '无',
            documents: [],
            confidence: 0.1
          }
        }
      })
    } catch (error) {
      console.error('解析批量响应失败:', error)
      return []
    }
  }

  /**
   * 解析API使用统计
   */
  static parseUsageStats(response: any): { tokensUsed: number; cost?: number } {
    try {
      if (response.usage) {
        return {
          tokensUsed: response.usage.total_tokens || 0,
          cost: response.usage.cost
        }
      }
      
      // 尝试从其他字段获取
      if (response.token_usage) {
        return {
          tokensUsed: response.token_usage.total || 0
        }
      }
      
      return { tokensUsed: 0 }
    } catch (error) {
      console.error('解析使用统计失败:', error)
      return { tokensUsed: 0 }
    }
  }

  /**
   * 验证响应完整性
   */
  static validateResponse(data: ExtractedMedicalData): {
    isValid: boolean
    issues: string[]
    score: number
  } {
    const issues: string[] = []
    let score = 1.0

    // 检查必需字段
    if (!data.patientName || data.patientName === '未识别') {
      issues.push('缺少患者姓名')
      score -= 0.2
    }

    if (!data.primaryDiagnosis || data.primaryDiagnosis === '未识别') {
      issues.push('缺少主要诊断')
      score -= 0.2
    }

    if (!data.department || data.department === '未识别') {
      issues.push('缺少科室信息')
      score -= 0.1
    }

    // 检查数据合理性
    if (data.patientAge && (data.patientAge < 0 || data.patientAge > 150)) {
      issues.push('年龄数据异常')
      score -= 0.1
    }

    if (data.confidence < 0.3) {
      issues.push('整体置信度过低')
      score -= 0.2
    }

    // 检查文档质量
    if (data.documents.length === 0) {
      issues.push('未识别到任何文书')
      score -= 0.1
    } else {
      const lowConfidenceDocs = data.documents.filter(doc => doc.confidence < 0.5)
      if (lowConfidenceDocs.length > 0) {
        issues.push(`${lowConfidenceDocs.length}个文书置信度较低`)
        score -= 0.05 * lowConfidenceDocs.length
      }
    }

    return {
      isValid: issues.length === 0,
      issues,
      score: Math.max(0, score)
    }
  }
}
