/**
 * 增强版医疗文档分类器（支持层级化分类）
 * 负责将解析出的文档进行层级化分类和标准化
 */

import { ExtractedDocument } from '../../types/medical'

export interface ClassificationRule {
  pattern: RegExp
  category: string  // 一级分类
  type: string      // 二级分类
  confidence: number
  keywords?: string[]
  contentPatterns?: RegExp[]  // 内容特征模式
}

export interface EnhancedClassificationResult {
  category: string    // 一级分类
  type: string       // 二级分类
  confidence: number
  matchedRule?: string
  suggestions?: string[]
  method: 'title_exact' | 'title_fuzzy' | 'content_feature' | 'keyword_match' | 'fallback'
  details?: any
}

export class EnhancedDocumentClassifier {
  private rules: ClassificationRule[] = []
  private categoryMapping: Map<string, string> = new Map()

  constructor() {
    this.initializeRules()
    this.initializeCategoryMapping()
  }

  /**
   * 初始化层级化分类规则
   */
  private initializeRules(): void {
    this.rules = [
      // ==================== 入院记录类 ====================
      {
        pattern: /^入院记录$/i,
        category: 'admission_record',
        type: 'admission_record',
        confidence: 0.95,
        keywords: ['入院', '主诉', '现病史', '既往史']
      },
      {
        pattern: /入院.*记录/i,
        category: 'admission_record',
        type: 'admission_record',
        confidence: 0.85,
        keywords: ['入院', '主诉', '现病史'],
        contentPatterns: [/主诉[:：]/, /现病史[:：]/, /既往史[:：]/]
      },
      {
        pattern: /^入院诊断$/i,
        category: 'admission_record',
        type: 'admission_diagnosis',
        confidence: 0.90,
        keywords: ['入院诊断', '初步诊断']
      },

      // ==================== 病程记录类 ====================
      {
        pattern: /^首次病程记录$/i,
        category: 'progress_note',
        type: 'first_progress_note',
        confidence: 0.95,
        keywords: ['首次', '病情分析', '诊疗计划']
      },
      {
        pattern: /(首次|术后首次).*病程/i,
        category: 'progress_note',
        type: 'first_progress_note',
        confidence: 0.90,
        keywords: ['首次', '入院后', '病情分析']
      },
      {
        pattern: /^病程记录$/i,
        category: 'progress_note',
        type: 'daily_progress_note',
        confidence: 0.80,
        keywords: ['病程', '病情变化', '治疗效果']
      },
      {
        pattern: /(主治|主任).*医师.*查房/i,
        category: 'progress_note',
        type: 'attending_progress',
        confidence: 0.90,
        keywords: ['查房', '主治', '主任', '医师']
      },
      {
        pattern: /查房.*记录/i,
        category: 'progress_note',
        type: 'attending_progress',
        confidence: 0.75,
        keywords: ['查房', '医师', '病情']
      },
      {
        pattern: /(会诊|疑难).*讨论/i,
        category: 'progress_note',
        type: 'consultation_record',
        confidence: 0.85,
        keywords: ['会诊', '讨论', '疑难']
      },
      {
        pattern: /交接班.*记录/i,
        category: 'progress_note',
        type: 'handover_record',
        confidence: 0.85,
        keywords: ['交接班', '交班', '接班']
      },
      {
        pattern: /转科.*记录/i,
        category: 'progress_note',
        type: 'transfer_record',
        confidence: 0.85,
        keywords: ['转科', '转入', '转出']
      },
      {
        pattern: /阶段.*小结/i,
        category: 'progress_note',
        type: 'stage_summary',
        confidence: 0.85,
        keywords: ['阶段', '小结', '总结']
      },

      // ==================== 手术记录类 ====================
      {
        pattern: /^术前小结$/i,
        category: 'operation_record',
        type: 'preoperative_summary',
        confidence: 0.95,
        keywords: ['术前', '小结', '手术指征']
      },
      {
        pattern: /术前.*讨论/i,
        category: 'operation_record',
        type: 'preoperative_discussion',
        confidence: 0.90,
        keywords: ['术前', '讨论', '手术方案']
      },
      {
        pattern: /^手术记录$/i,
        category: 'operation_record',
        type: 'operation_record',
        confidence: 0.95,
        keywords: ['手术', '术中', '手术过程']
      },
      {
        pattern: /手术.*记录/i,
        category: 'operation_record',
        type: 'operation_record',
        confidence: 0.85,
        keywords: ['手术', '术前诊断', '术中所见', '术后处理'],
        contentPatterns: [/术前诊断[:：]/, /手术过程[:：]/, /术中所见[:：]/]
      },
      {
        pattern: /术后首次.*病程/i,
        category: 'operation_record',
        type: 'postoperative_first_note',
        confidence: 0.90,
        keywords: ['术后', '首次', '病程']
      },
      {
        pattern: /麻醉.*记录/i,
        category: 'operation_record',
        type: 'anesthesia_record',
        confidence: 0.90,
        keywords: ['麻醉', '麻醉方式', '麻醉效果']
      },

      // ==================== 护理文书类 ====================
      {
        pattern: /护理.*记录/i,
        category: 'nursing_document',
        type: 'nursing_record',
        confidence: 0.90,
        keywords: ['护理', '护理措施', '病情观察'],
        contentPatterns: [/护理措施[:：]/, /病情观察[:：]/, /护理记录[:：]/]
      },
      {
        pattern: /(体温|生命体征).*单/i,
        category: 'nursing_document',
        type: 'temperature_chart',
        confidence: 0.95,
        keywords: ['体温', '脉搏', '呼吸', '血压', '生命体征']
      },
      {
        pattern: /护理.*计划/i,
        category: 'nursing_document',
        type: 'nursing_plan',
        confidence: 0.90,
        keywords: ['护理计划', '护理目标', '护理措施']
      },
      {
        pattern: /护理.*评估/i,
        category: 'nursing_document',
        type: 'nursing_assessment',
        confidence: 0.90,
        keywords: ['护理评估', '风险评估', '跌倒评估']
      },

      // ==================== 出院记录类 ====================
      {
        pattern: /^出院记录$/i,
        category: 'discharge_record',
        type: 'discharge_record',
        confidence: 0.95,
        keywords: ['出院', '出院诊断', '出院医嘱']
      },
      {
        pattern: /出院.*小结/i,
        category: 'discharge_record',
        type: 'discharge_summary',
        confidence: 0.90,
        keywords: ['出院', '小结', '康复']
      },
      {
        pattern: /死亡.*记录/i,
        category: 'discharge_record',
        type: 'death_record',
        confidence: 0.95,
        keywords: ['死亡', '死因', '抢救']
      },

      // ==================== 检查报告类 ====================
      // 影像检查（更宽松的标题匹配，覆盖“检查记录/检查/扫描/报告”等）
      {
        pattern: /(CT|MRI|核磁|磁共振|计算机断层扫描|DR|CTA|MRA)[^\n]{0,20}(检查记录|检查报告|检查|扫描|影像|所见)/i,
        category: 'examination_report',
        type: 'imaging_examination',
        confidence: 0.95,
        keywords: ['CT', 'MRI', '核磁', '磁共振', '计算机断层扫描', '影像', '所见', '平扫', '增强', '扫描'],
        contentPatterns: [/检查所见[:：]/i, /影像所见/i, /所见[:：]/i, /平扫/i, /增强/i, /扫描/i, /层厚/i, /窗位/i]
      },
      // 兼容原有“.*报告”形式
      {
        pattern: /(CT|MRI|核磁|彩超|超声|X线|影像).*报告/i,
        category: 'examination_report',
        type: 'imaging_examination',
        confidence: 0.92,
        keywords: ['CT', 'MRI', '核磁', '超声', 'X线', '影像']
      },
      {
        pattern: /(血常规|尿常规|生化|肝功|肾功|实验室).*报告/i,
        category: 'examination_report',
        type: 'laboratory_test',
        confidence: 0.90,
        keywords: ['血常规', '尿常规', '生化', '化验', '实验室']
      },
      {
        pattern: /病理.*报告/i,
        category: 'examination_report',
        type: 'pathology_examination',
        confidence: 0.95,
        keywords: ['病理', '切片', '活检']
      },
      {
        pattern: /(心电图|脑电图|肌电图).*报告/i,
        category: 'examination_report',
        type: 'special_examination',
        confidence: 0.90,
        keywords: ['心电图', '脑电图', '肌电图']
      },

      // ==================== 医嘱记录类 ====================
      {
        pattern: /长期.*医嘱/i,
        category: 'medical_order',
        type: 'long_term_order',
        confidence: 0.90,
        keywords: ['长期医嘱', '口服药物', '静脉输液'],
        contentPatterns: [/长期医嘱[:：]/, /口服[:：]/, /静脉[:：]/]
      },
      {
        pattern: /临时.*医嘱/i,
        category: 'medical_order',
        type: 'temporary_order',
        confidence: 0.90,
        keywords: ['临时医嘱', '临时用药', '检查医嘱']
      },
      {
        pattern: /医嘱.*执行/i,
        category: 'medical_order',
        type: 'order_execution',
        confidence: 0.85,
        keywords: ['执行时间', '执行护士', '执行情况']
      }
    ]
  }

  /**
   * 初始化分类映射
   */
  private initializeCategoryMapping(): void {
    this.categoryMapping.set('admission_record', '入院记录')
    this.categoryMapping.set('progress_note', '病程记录')
    this.categoryMapping.set('operation_record', '手术记录')
    this.categoryMapping.set('nursing_document', '护理文书')
    this.categoryMapping.set('discharge_record', '出院记录')
    this.categoryMapping.set('examination_report', '检查报告')
    this.categoryMapping.set('medical_order', '医嘱记录')
  }

  /**
   * 主分类方法
   */
  classify(document: ExtractedDocument): EnhancedClassificationResult {
    // 1. 尝试精确标题匹配
    const exactMatch = this.classifyByExactTitle(document.title)
    if (exactMatch.confidence >= 0.9) {
      return exactMatch
    }

    // 2. 尝试模糊标题匹配
    const fuzzyMatch = this.classifyByFuzzyTitle(document.title)
    if (fuzzyMatch.confidence >= 0.7) {
      return fuzzyMatch
    }

    // 3. 基于内容特征分类
    const contentMatch = this.classifyByContent(document)
    if (contentMatch.confidence >= 0.6) {
      return contentMatch
    }

    // 4. 关键词匹配
    const keywordMatch = this.classifyByKeywords(document)
    if (keywordMatch.confidence >= 0.5) {
      return keywordMatch
    }

    // 5. 降级处理前，优先拦截影像检查关键词，避免误落入病程记录
    const titleLc = document.title.toLowerCase()
    const contentLc = (document.content || '').toLowerCase()
    const imagingKeywords = ['ct', 'mri', '核磁', '磁共振', '计算机断层扫描', '影像']
    if (imagingKeywords.some(k => titleLc.includes(k) || contentLc.includes(k))) {
      return {
        category: 'examination_report',
        type: 'imaging_examination',
        confidence: 0.6,
        method: 'keyword_match',
        details: { reason: 'fallback_imaging_guard' }
      }
    }

    // 6. 降级处理
    return this.getFallbackClassification(document)
  }

  /**
   * 精确标题匹配
   */
  private classifyByExactTitle(title: string): EnhancedClassificationResult {
    for (const rule of this.rules) {
      if (rule.pattern.test(title) && rule.confidence >= 0.9) {
        return {
          category: rule.category,
          type: rule.type,
          confidence: rule.confidence,
          method: 'title_exact',
          matchedRule: rule.pattern.source,
          details: { title, pattern: rule.pattern.source }
        }
      }
    }

    return {
      category: '',
      type: '',
      confidence: 0.1,
      method: 'title_exact',
      details: { title, result: 'no_exact_match' }
    }
  }

  /**
   * 模糊标题匹配
   */
  private classifyByFuzzyTitle(title: string): EnhancedClassificationResult {
    let bestMatch: EnhancedClassificationResult = {
      category: '',
      type: '',
      confidence: 0.1,
      method: 'title_fuzzy'
    }

    for (const rule of this.rules) {
      if (rule.pattern.test(title) && rule.confidence > bestMatch.confidence) {
        bestMatch = {
          category: rule.category,
          type: rule.type,
          confidence: rule.confidence * 0.9, // 模糊匹配降权
          method: 'title_fuzzy',
          matchedRule: rule.pattern.source,
          details: { title, pattern: rule.pattern.source }
        }
      }
    }

    return bestMatch
  }

  /**
   * 基于内容特征分类
   */
  private classifyByContent(document: ExtractedDocument): EnhancedClassificationResult {
    const content = document.content.toLowerCase()
    const fullContent = document.position?.fullContent?.toLowerCase() || content

    let bestMatch: EnhancedClassificationResult = {
      category: '',
      type: '',
      confidence: 0.1,
      method: 'content_feature'
    }

    for (const rule of this.rules) {
      if (rule.contentPatterns) {
        const matchedPatterns = rule.contentPatterns.filter(pattern => 
          pattern.test(fullContent)
        )
        
        if (matchedPatterns.length > 0) {
          const confidence = (matchedPatterns.length / rule.contentPatterns.length) * rule.confidence * 0.8
          
          if (confidence > bestMatch.confidence) {
            bestMatch = {
              category: rule.category,
              type: rule.type,
              confidence,
              method: 'content_feature',
              details: {
                matchedPatterns: matchedPatterns.map(p => p.source),
                totalPatterns: rule.contentPatterns.length
              }
            }
          }
        }
      }
    }

    return bestMatch
  }

  /**
   * 关键词匹配
   */
  private classifyByKeywords(document: ExtractedDocument): EnhancedClassificationResult {
    const title = document.title.toLowerCase()
    const content = document.content.toLowerCase()
    const fullText = `${title} ${content}`.toLowerCase()

    let bestMatch: EnhancedClassificationResult = {
      category: '',
      type: '',
      confidence: 0.1,
      method: 'keyword_match'
    }

    for (const rule of this.rules) {
      if (rule.keywords) {
        const matchedKeywords = rule.keywords.filter(keyword => 
          fullText.includes(keyword.toLowerCase())
        )
        
        if (matchedKeywords.length > 0) {
          const confidence = (matchedKeywords.length / rule.keywords.length) * rule.confidence * 0.7
          
          if (confidence > bestMatch.confidence) {
            bestMatch = {
              category: rule.category,
              type: rule.type,
              confidence,
              method: 'keyword_match',
              details: {
                matchedKeywords,
                totalKeywords: rule.keywords.length
              }
            }
          }
        }
      }
    }

    return bestMatch
  }

  /**
   * 降级分类处理
   */
  private getFallbackClassification(document: ExtractedDocument): EnhancedClassificationResult {
    const title = document.title.toLowerCase()
    
    // 基于简单规则的降级分类
    if (title.includes('入院')) {
      return {
        category: 'admission_record',
        type: 'admission_record',
        confidence: 0.3,
        method: 'fallback',
        details: { reason: 'contains_admission_keyword' }
      }
    }
    
    if (title.includes('病程') || title.includes('查房')) {
      return {
        category: 'progress_note',
        type: 'daily_progress_note',
        confidence: 0.3,
        method: 'fallback',
        details: { reason: 'contains_progress_keyword' }
      }
    }
    
    if (title.includes('手术')) {
      return {
        category: 'operation_record',
        type: 'operation_record',
        confidence: 0.3,
        method: 'fallback',
        details: { reason: 'contains_surgery_keyword' }
      }
    }
    
    if (title.includes('出院')) {
      return {
        category: 'discharge_record',
        type: 'discharge_record',
        confidence: 0.3,
        method: 'fallback',
        details: { reason: 'contains_discharge_keyword' }
      }
    }
    
    // 默认分类为病程记录
    return {
      category: 'progress_note',
      type: 'daily_progress_note',
      confidence: 0.1,
      method: 'fallback',
      details: { reason: 'default_classification' }
    }
  }

  /**
   * 获取分类名称
   */
  getCategoryName(categoryCode: string): string {
    return this.categoryMapping.get(categoryCode) || categoryCode
  }

  /**
   * 验证分类结果
   */
  validateClassification(result: EnhancedClassificationResult): boolean {
    return result.confidence >= 0.5 && 
           result.category.length > 0 && 
           result.type.length > 0
  }
}
