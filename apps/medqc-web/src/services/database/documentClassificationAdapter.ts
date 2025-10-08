/**
 * 文书分类数据库适配器
 * 负责将LLM解析结果映射到新的层级化数据库表结构
 */

import { ExtractedMedicalData, ExtractedDocument } from '../../types/medical'
import { EnhancedDocumentClassifier, EnhancedClassificationResult } from '../llm/enhancedDocumentClassifier'

export interface DocumentCategoryMapping {
  id: string
  category_code: string
  category_name: string
}

export interface DocumentTypeMapping {
  id: string
  category_id: string
  type_code: string
  type_name: string
}

export interface MedicalDocumentRecord {
  id?: string
  record_id: string
  category_id: string
  type_id: string
  title: string
  content: string
  summary?: string
  ai_classified: boolean
  classification_confidence: number
  manual_verified: boolean
  position_info: Record<string, unknown>
  sort_order: number
  status: string
  qc_status: string
  metadata: Record<string, unknown>
}

export class DocumentClassificationAdapter {
  private categoryMappings: Map<string, DocumentCategoryMapping> = new Map()
  private typeMappings: Map<string, DocumentTypeMapping> = new Map()
  private classifier: EnhancedDocumentClassifier

  constructor() {
    this.classifier = new EnhancedDocumentClassifier()
    this.initializeMappings()
  }

  /**
   * 初始化分类映射
   */
  private initializeMappings(): void {
    // 一级分类映射 - 仅使用6个标准类别，非标准类别映射到相应的标准类别
    const categories: DocumentCategoryMapping[] = [
      { id: 'cat_admission', category_code: 'admission_record', category_name: '入院记录' },
      { id: 'cat_progress', category_code: 'progress_note', category_name: '病程记录' },
      { id: 'cat_operation', category_code: 'operation_record', category_name: '手术相关记录' },
      { id: 'cat_discharge', category_code: 'discharge_record', category_name: '出院记录' },
      { id: 'cat_examination', category_code: 'examination_report', category_name: '辅助检查' },
      { id: 'cat_consent', category_code: 'consent_form', category_name: '知情同意书' }
    ]

    // 非标准类别到标准类别的映射
    const legacyMappings = new Map([
      ['nursing_document', 'progress_note'], // 护理文书 -> 病程记录
      ['medical_order', 'progress_note'],    // 医嘱记录 -> 病程记录
      ['blood_transfusion', 'progress_note'] // 输血记录 -> 病程记录
    ])

    categories.forEach(cat => {
      this.categoryMappings.set(cat.category_code, cat)
    })

    // 添加遗留映射支持
    legacyMappings.forEach((standardCode, legacyCode) => {
      const standardCategory = categories.find(c => c.category_code === standardCode)
      if (standardCategory) {
        this.categoryMappings.set(legacyCode, {
          ...standardCategory,
          id: `legacy_${legacyCode}`,
          category_code: legacyCode
        })
      }
    })

    // 二级分类映射
    const types: DocumentTypeMapping[] = [
      // 入院记录类
      { id: 'type_admission_record', category_id: 'cat_admission', type_code: 'admission_record', type_name: '入院记录' },
      { id: 'type_admission_diagnosis', category_id: 'cat_admission', type_code: 'admission_diagnosis', type_name: '入院诊断' },
      
      // 病程记录类
      { id: 'type_first_progress', category_id: 'cat_progress', type_code: 'first_progress_note', type_name: '首次病程记录' },
      { id: 'type_daily_progress', category_id: 'cat_progress', type_code: 'daily_progress_note', type_name: '日常病程记录' },
      { id: 'type_attending_progress', category_id: 'cat_progress', type_code: 'attending_progress', type_name: '上级医师查房记录' },
      { id: 'type_consultation', category_id: 'cat_progress', type_code: 'consultation_record', type_name: '疑难病例讨论记录' },
      { id: 'type_handover', category_id: 'cat_progress', type_code: 'handover_record', type_name: '交接班记录' },
      { id: 'type_transfer', category_id: 'cat_progress', type_code: 'transfer_record', type_name: '转科记录' },
      { id: 'type_stage_summary', category_id: 'cat_progress', type_code: 'stage_summary', type_name: '阶段小结' },
      
      // 手术记录类
      { id: 'type_preop_summary', category_id: 'cat_operation', type_code: 'preoperative_summary', type_name: '术前小结' },
      { id: 'type_preop_discussion', category_id: 'cat_operation', type_code: 'preoperative_discussion', type_name: '术前讨论' },
      { id: 'type_operation', category_id: 'cat_operation', type_code: 'operation_record', type_name: '手术记录' },
      { id: 'type_postop_first', category_id: 'cat_operation', type_code: 'postoperative_first_note', type_name: '术后首次病程记录' },
      { id: 'type_anesthesia', category_id: 'cat_operation', type_code: 'anesthesia_record', type_name: '麻醉记录' },
      
      // 护理文书类
      { id: 'type_nursing_record', category_id: 'cat_nursing', type_code: 'nursing_record', type_name: '护理记录单' },
      { id: 'type_temperature', category_id: 'cat_nursing', type_code: 'temperature_chart', type_name: '体温单' },
      { id: 'type_nursing_plan', category_id: 'cat_nursing', type_code: 'nursing_plan', type_name: '护理计划单' },
      { id: 'type_nursing_assessment', category_id: 'cat_nursing', type_code: 'nursing_assessment', type_name: '护理评估单' },
      
      // 出院记录类
      { id: 'type_discharge', category_id: 'cat_discharge', type_code: 'discharge_record', type_name: '出院记录' },
      { id: 'type_discharge_summary', category_id: 'cat_discharge', type_code: 'discharge_summary', type_name: '出院小结' },
      { id: 'type_death', category_id: 'cat_discharge', type_code: 'death_record', type_name: '死亡记录' },
      
      // 检查报告类
      { id: 'type_imaging', category_id: 'cat_examination', type_code: 'imaging_examination', type_name: '影像学检查' },
      { id: 'type_laboratory', category_id: 'cat_examination', type_code: 'laboratory_test', type_name: '实验室检查' },
      { id: 'type_pathology', category_id: 'cat_examination', type_code: 'pathology_examination', type_name: '病理检查' },
      { id: 'type_special', category_id: 'cat_examination', type_code: 'special_examination', type_name: '特殊检查' },
      
      // 医嘱记录类
      { id: 'type_long_order', category_id: 'cat_order', type_code: 'long_term_order', type_name: '长期医嘱' },
      { id: 'type_temp_order', category_id: 'cat_order', type_code: 'temporary_order', type_name: '临时医嘱' },
      { id: 'type_order_execution', category_id: 'cat_order', type_code: 'order_execution', type_name: '医嘱执行记录' }
    ]

    types.forEach(type => {
      this.typeMappings.set(type.type_code, type)
    })
  }

  /**
   * 将LLM解析结果转换为数据库记录
   */
  async convertToMedicalDocuments(
    recordId: string, 
    extractedData: ExtractedMedicalData
  ): Promise<MedicalDocumentRecord[]> {
    const documents: MedicalDocumentRecord[] = []

    for (let i = 0; i < extractedData.documents.length; i++) {
      const doc = extractedData.documents[i]
      const dbRecord = await this.convertSingleDocument(recordId, doc, i)
      documents.push(dbRecord)
    }

    return documents
  }

  /**
   * 转换单个文书
   */
  private async convertSingleDocument(
    recordId: string, 
    document: ExtractedDocument, 
    sortOrder: number
  ): Promise<MedicalDocumentRecord> {
    // 获取或生成分类信息
    let classification: EnhancedClassificationResult
    
    if (document.category && document.classificationMethod === 'llm_provided') {
      // 使用LLM提供的分类
      classification = {
        category: document.category,
        type: this.mapDocumentTypeToCode(document.type),
        confidence: document.confidence,
        method: 'llm_provided'
      }
    } else {
      // 使用增强分类器
      classification = this.classifier.classify(document)
    }

    // 获取分类ID
    const categoryId = this.getCategoryId(classification.category)
    const typeId = this.getTypeId(classification.type)

    // 构建数据库记录
    return {
      record_id: recordId,
      category_id: categoryId,
      type_id: typeId,
      title: document.title,
      content: this.extractFullContent(document),
      summary: document.content, // 原来的content作为摘要
      ai_classified: true,
      classification_confidence: classification.confidence,
      manual_verified: classification.confidence >= 0.9,
      position_info: document.position || {},
      sort_order: sortOrder,
      status: 'active',
      qc_status: 'pending',
      metadata: {
        originalDocument: document,
        classificationDetails: classification,
        extractedAt: document.extractedAt,
        classificationMethod: document.classificationMethod || classification.method
      }
    }
  }

  /**
   * 获取分类ID
   */
  private getCategoryId(categoryCode: string): string {
    const mapping = this.categoryMappings.get(categoryCode)
    if (!mapping) {
      console.warn(`未找到分类映射: ${categoryCode}`)
      return this.categoryMappings.get('progress_note')?.id || 'cat_progress'
    }
    return mapping.id
  }

  /**
   * 获取类型ID
   */
  private getTypeId(typeCode: string): string {
    const mapping = this.typeMappings.get(typeCode)
    if (!mapping) {
      console.warn(`未找到类型映射: ${typeCode}`)
      return this.typeMappings.get('daily_progress_note')?.id || 'type_daily_progress'
    }
    return mapping.id
  }

  /**
   * 映射DocumentType枚举到代码字符串
   */
  private mapDocumentTypeToCode(type: unknown): string {
    // 这里需要根据实际的DocumentType枚举进行映射
    const typeMapping: Record<string, string> = {
      'ADMISSION_RECORD': 'admission_record',
      'FIRST_PROGRESS_NOTE': 'first_progress_note',
      'DAILY_PROGRESS_NOTE': 'daily_progress_note',
      'ATTENDING_PROGRESS': 'attending_progress',
      'CONSULTATION_RECORD': 'consultation_record',
      'HANDOVER_RECORD': 'handover_record',
      'TRANSFER_RECORD': 'transfer_record',
      'STAGE_SUMMARY': 'stage_summary',
      'PREOPERATIVE_SUMMARY': 'preoperative_summary',
      'PREOPERATIVE_DISCUSSION': 'preoperative_discussion',
      'OPERATION_RECORD': 'operation_record',
      'POSTOPERATIVE_FIRST_NOTE': 'postoperative_first_note',
      'ANESTHESIA_RECORD': 'anesthesia_record',
      'NURSING_RECORD': 'nursing_record',
      'TEMPERATURE_CHART': 'temperature_chart',
      'NURSING_PLAN': 'nursing_plan',
      'NURSING_ASSESSMENT': 'nursing_assessment',
      'DISCHARGE_RECORD': 'discharge_record',
      'DISCHARGE_SUMMARY': 'discharge_summary',
      'DEATH_RECORD': 'death_record',
      'IMAGING_EXAMINATION': 'imaging_examination',
      'LABORATORY_TEST': 'laboratory_test',
      'PATHOLOGY_EXAMINATION': 'pathology_examination',
      'SPECIAL_EXAMINATION': 'special_examination',
      'LONG_TERM_ORDER': 'long_term_order',
      'TEMPORARY_ORDER': 'temporary_order',
      'ORDER_EXECUTION': 'order_execution'
    }

    return typeMapping[type] || 'daily_progress_note'
  }

  /**
   * 提取完整内容
   */
  private extractFullContent(document: ExtractedDocument): string {
    return document.position?.fullContent || document.content || ''
  }

  /**
   * 验证分类结果
   */
  validateClassification(classification: EnhancedClassificationResult): boolean {
    return classification.confidence >= 0.3 && 
           this.categoryMappings.has(classification.category) &&
           this.typeMappings.has(classification.type)
  }

  /**
   * 获取分类统计信息
   */
  getClassificationStats(documents: MedicalDocumentRecord[]): Record<string, unknown> {
    const stats = {
      totalDocuments: documents.length,
      byCategory: new Map<string, number>(),
      byType: new Map<string, number>(),
      averageConfidence: 0,
      highConfidenceCount: 0,
      lowConfidenceCount: 0
    }

    let totalConfidence = 0

    documents.forEach(doc => {
      // 统计分类
      const categoryMapping = Array.from(this.categoryMappings.values())
        .find(cat => cat.id === doc.category_id)
      if (categoryMapping) {
        stats.byCategory.set(
          categoryMapping.category_name, 
          (stats.byCategory.get(categoryMapping.category_name) || 0) + 1
        )
      }

      const typeMapping = Array.from(this.typeMappings.values())
        .find(type => type.id === doc.type_id)
      if (typeMapping) {
        stats.byType.set(
          typeMapping.type_name,
          (stats.byType.get(typeMapping.type_name) || 0) + 1
        )
      }

      // 统计置信度
      totalConfidence += doc.classification_confidence
      if (doc.classification_confidence >= 0.8) {
        stats.highConfidenceCount++
      } else if (doc.classification_confidence < 0.5) {
        stats.lowConfidenceCount++
      }
    })

    stats.averageConfidence = documents.length > 0 ? totalConfidence / documents.length : 0

    return {
      ...stats,
      byCategory: Object.fromEntries(stats.byCategory),
      byType: Object.fromEntries(stats.byType)
    }
  }
}
