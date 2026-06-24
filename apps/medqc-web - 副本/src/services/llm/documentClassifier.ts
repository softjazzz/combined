/**
 * Document classifier for medical records.
 */

import { DocumentType, ClassificationResult } from '@/types/medical'

const DT = DocumentType as Record<string, DocumentType>

export class DocumentClassifier {
  static classifyByTitle(title: string, content?: string): DocumentType {
    const lowerTitle = title.toLowerCase()
    const lowerContent = content?.toLowerCase() || ''

    if (lowerTitle.includes('入院记录') || lowerTitle.includes('入院病历')) {
      return DocumentType.ADMISSION_RECORD
    }

    if (lowerTitle.includes('病程记录') || lowerTitle.includes('病程')) {
      if (lowerTitle.includes('首次') || lowerTitle.includes('首程')) {
        return DocumentType.FIRST_PROGRESS_NOTE
      }
      if (lowerTitle.includes('上级医师') || lowerTitle.includes('主治')) {
        return DocumentType.ATTENDING_PROGRESS
      }
      if (lowerTitle.includes('会诊')) {
        return DocumentType.CONSULTATION_RECORD
      }
      if (lowerTitle.includes('交班') || lowerTitle.includes('接班')) {
        return DocumentType.HANDOVER_RECORD
      }
      if (lowerTitle.includes('阶段小结') || lowerTitle.includes('小结')) {
        return DocumentType.STAGE_SUMMARY
      }
      return DocumentType.DAILY_PROGRESS_NOTE
    }

    if (lowerTitle.includes('手术记录') || lowerTitle.includes('手术')) {
      if (lowerTitle.includes('术前小结') || lowerTitle.includes('术前')) {
        return DocumentType.PREOPERATIVE_SUMMARY
      }
      return DocumentType.OPERATION_RECORD
    }

    if (lowerTitle.includes('出院记录') || lowerTitle.includes('出院')) {
      if (lowerTitle.includes('死亡')) {
        return DocumentType.DEATH_RECORD
      }
      return DocumentType.DISCHARGE_RECORD
    }

    const imagingKeys = ['影像', 'ct', 'mri', '核磁', 'x线', 'x光', 'b超', '超声', '扫描']
    const hasImaging = imagingKeys.some(k => lowerTitle.includes(k) || lowerContent.includes(k))
    if (hasImaging || lowerTitle.includes('检查报告') || lowerTitle.includes('报告')) {
      if (hasImaging) {
        return DT.IMAGING_REPORT ?? DocumentType.IMAGING_EXAMINATION
      }
      if (lowerTitle.includes('化验') || lowerTitle.includes('血常规') || lowerTitle.includes('生化') || lowerTitle.includes('实验室')) {
        return DT.LAB_REPORT ?? DocumentType.LABORATORY_TEST
      }
      return DT.OTHER_EXAMINATION ?? DocumentType.SPECIAL_EXAMINATION
    }

    if (lowerTitle.includes('知情同意书') || lowerTitle.includes('同意书')) {
      if (lowerTitle.includes('手术')) {
        return DT.SURGERY_CONSENT ?? DocumentType.OPERATION_RECORD
      }
      if (lowerTitle.includes('麻醉')) {
        return DT.ANESTHESIA_CONSENT ?? DocumentType.ANESTHESIA_RECORD
      }
      if (lowerTitle.includes('输血') || lowerTitle.includes('用血')) {
        return DT.BLOOD_TRANSFUSION_CONSENT ?? DocumentType.LABORATORY_TEST
      }
      return DT.OTHER_CONSENT ?? DocumentType.ORDER_EXECUTION
    }

    if (content) {
      if (lowerContent.includes('主诉') && lowerContent.includes('现病史')) {
        return DocumentType.ADMISSION_RECORD
      }
      if (lowerContent.includes('手术过程') || lowerContent.includes('术中')) {
        return DocumentType.OPERATION_RECORD
      }
      if (lowerContent.includes('出院诊断') || lowerContent.includes('出院医嘱')) {
        return DocumentType.DISCHARGE_RECORD
      }
    }

    return DocumentType.DAILY_PROGRESS_NOTE
  }

  static buildClassificationPrompt(text: string): string {
    return `请判断以下医疗文本属于哪种类型的文书，并给出置信度评分：\n\n文本内容：\n${text.substring(0, 1000)}${text.length > 1000 ? '...' : ''}\n\n请以 JSON 返回：{\n  "type": "文书类型代码",\n  "confidence": 0-1,\n  "title": "推荐标题",\n  "reasoning": "分类理由"\n}`
  }

  static parseClassificationResponse(response: unknown): ClassificationResult {
    try {
      let result: any

      if (typeof response === 'string') {
        const jsonMatch = response.match(/\{[\s\S]*\}/)
        if (!jsonMatch) {
          throw new Error('Unable to find JSON in response')
        }
        result = JSON.parse(jsonMatch[0])
      } else {
        result = response
      }

      if (!result?.type) {
        throw new Error('Missing type field')
      }

      const validTypes = Object.values(DocumentType)
      if (!validTypes.includes(result.type)) {
        result.type = DocumentType.DAILY_PROGRESS_NOTE
      }

      return {
        type: result.type as DocumentType,
        confidence: Math.max(0, Math.min(1, Number(result.confidence ?? 0.5))),
        title: typeof result.title === 'string' ? result.title : '未知文书'
      }
    } catch {
      return {
        type: DocumentType.DAILY_PROGRESS_NOTE,
        confidence: 0.3,
        title: '未知文书'
      }
    }
  }

  static getDocumentTypeName(type: DocumentType): string {
    const typeNames: Partial<Record<DocumentType, string>> = {
      [DocumentType.ADMISSION_RECORD]: '入院记录',
      [DocumentType.FIRST_PROGRESS_NOTE]: '首次病程记录',
      [DocumentType.DAILY_PROGRESS_NOTE]: '日常病程记录',
      [DocumentType.ATTENDING_PROGRESS]: '上级医师查房记录',
      [DocumentType.CONSULTATION_RECORD]: '会诊记录',
      [DocumentType.HANDOVER_RECORD]: '交接班记录',
      [DocumentType.STAGE_SUMMARY]: '阶段小结',
      [DocumentType.OPERATION_RECORD]: '手术记录',
      [DocumentType.PREOPERATIVE_SUMMARY]: '术前小结',
      [DocumentType.DISCHARGE_RECORD]: '出院记录',
      [DocumentType.DEATH_RECORD]: '死亡记录',
      [DocumentType.IMAGING_EXAMINATION]: '影像检查报告',
      [DocumentType.LABORATORY_TEST]: '实验室检查报告',
      [DocumentType.PATHOLOGY_EXAMINATION]: '病理检查报告',
      [DocumentType.SPECIAL_EXAMINATION]: '其他检查报告',
      [DocumentType.ANESTHESIA_RECORD]: '麻醉记录',
      [DocumentType.ORDER_EXECUTION]: '医嘱执行记录'
    }

    return typeNames[type] || '未知文书类型'
  }
}
