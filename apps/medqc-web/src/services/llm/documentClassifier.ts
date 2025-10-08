/**
 * 文档分类器 - 负责医疗文书的智能分类
 */

import { DocumentType, ClassificationResult } from '@/types/medical'

export class DocumentClassifier {
  /**
   * 基于标题和内容的规则分类（增强版）
   */
  static classifyByTitle(title: string, content?: string): DocumentType {
    const lowerTitle = title.toLowerCase()
    const lowerContent = content?.toLowerCase() || ''

    // 入院记录类
    if (lowerTitle.includes('入院记录') || lowerTitle.includes('入院病历')) {
      if (lowerTitle.includes('24小时内') || lowerTitle.includes('24h内')) {
        return DocumentType.ADMISSION_RECORD_24H_IN
      }
      if (lowerTitle.includes('24小时出入院') || lowerTitle.includes('24h出入院')) {
        return DocumentType.ADMISSION_RECORD_24H_OUT
      }
      return DocumentType.ADMISSION_RECORD
    }

    // 病程记录类
    if (lowerTitle.includes('病程记录') || lowerTitle.includes('病程')) {
      if (lowerTitle.includes('首次') || lowerTitle.includes('首程')) {
        return DocumentType.FIRST_PROGRESS_NOTE
      }
      if (lowerTitle.includes('主治医师') || lowerTitle.includes('主治医生')) {
        if (lowerTitle.includes('首次') || lowerTitle.includes('首程')) {
          return DocumentType.ATTENDING_FIRST_PROGRESS
        }
        return DocumentType.ATTENDING_PROGRESS
      }
      if (lowerTitle.includes('会诊')) {
        return DocumentType.CONSULTATION_RECORD
      }
      if (lowerTitle.includes('接班') || lowerTitle.includes('交班')) {
        return DocumentType.HANDOVER_RECORD
      }
      if (lowerTitle.includes('阶段小结') || lowerTitle.includes('小结')) {
        return DocumentType.STAGE_SUMMARY
      }
      return DocumentType.DAILY_PROGRESS_NOTE
    }

    // 手术记录类
    if (lowerTitle.includes('手术记录') || lowerTitle.includes('手术')) {
      if (lowerTitle.includes('术前小结') || lowerTitle.includes('术前')) {
        return DocumentType.PREOPERATIVE_SUMMARY
      }
      return DocumentType.OPERATION_RECORD
    }

    // 出院记录类
    if (lowerTitle.includes('出院记录') || lowerTitle.includes('出院')) {
      if (lowerTitle.includes('死亡')) {
        if (lowerTitle.includes('讨论')) {
          return DocumentType.DEATH_CASE_DISCUSSION
        }
        return DocumentType.DEATH_RECORD
      }
      return DocumentType.DISCHARGE_RECORD
    }

    // 检查报告类（更鲁棒：标题或内容出现影像关键词即归为影像检查）
    const imagingKeys = ['影像', 'ct', 'mri', '核磁', '磁共振', 'x线', 'x光', 'b超', '超声', '检查记录', '扫描', '计算机断层']
    const hasImaging = imagingKeys.some(k => lowerTitle.includes(k) || lowerContent.includes(k))
    if (hasImaging || lowerTitle.includes('检查报告') || lowerTitle.includes('报告')) {
      if (hasImaging) {
        return DocumentType.IMAGING_REPORT
      }
      if (lowerTitle.includes('化验') || lowerTitle.includes('血常规') ||
          lowerTitle.includes('生化') || lowerTitle.includes('实验室')) {
        return DocumentType.LAB_REPORT
      }
      return DocumentType.OTHER_EXAMINATION
    }

    // 知情同意书类
    if (lowerTitle.includes('知情同意书') || lowerTitle.includes('同意书')) {
      if (lowerTitle.includes('手术')) {
        return DocumentType.SURGERY_CONSENT
      }
      if (lowerTitle.includes('麻醉')) {
        return DocumentType.ANESTHESIA_CONSENT
      }
      if (lowerTitle.includes('输血') || lowerTitle.includes('用血')) {
        return DocumentType.BLOOD_TRANSFUSION_CONSENT
      }
      if (lowerTitle.includes('特殊治疗') || lowerTitle.includes('特殊检查')) {
        return DocumentType.SPECIAL_TREATMENT_CONSENT
      }
      return DocumentType.OTHER_CONSENT
    }

    // 基于内容的二次判断
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

    // 默认返回日常病程记录
    return DocumentType.DAILY_PROGRESS_NOTE
  }

  /**
   * 构建分类提示词
   */
  static buildClassificationPrompt(text: string): string {
    return `请判断以下医疗文本属于哪种类型的文书，并给出置信度评分：

文本内容：
${text.substring(0, 1000)}${text.length > 1000 ? '...' : ''}

请从以下类型中选择最合适的一种：
1. admission_record - 入院记录
2. first_progress_note - 首次病程记录
3. daily_progress_note - 日常病程记录
4. attending_progress - 主治医生查房记录
5. consultation_record - 会诊记录
6. operation_record - 手术记录
7. discharge_record - 出院记录
8. imaging_report - 影像检查报告
9. lab_report - 实验室检查报告
10. surgery_consent - 手术知情同意书

请以JSON格式返回结果：
{
  "type": "文书类型代码",
  "confidence": 置信度(0-1之间的数字),
  "title": "推荐的文书标题",
  "reasoning": "分类理由"
}`
  }

  /**
   * 解析分类响应
   */
  static parseClassificationResponse(response: unknown): ClassificationResult {
    try {
      let result: unknown

      if (typeof response === 'string') {
        // 尝试提取JSON部分
        const jsonMatch = response.match(/\{[\s\S]*\}/)
        if (jsonMatch) {
          result = JSON.parse(jsonMatch[0])
        } else {
          throw new Error('无法找到JSON格式的响应')
        }
      } else {
        result = response
      }

      // 验证必需字段
      if (!result.type) {
        throw new Error('响应中缺少type字段')
      }

      // 验证文档类型是否有效
      const validTypes = Object.values(DocumentType)
      if (!validTypes.includes(result.type)) {
        console.warn(`未知的文档类型: ${result.type}，使用默认类型`)
        result.type = DocumentType.DAILY_PROGRESS_NOTE
      }

      return {
        type: result.type as DocumentType,
        confidence: Math.max(0, Math.min(1, result.confidence || 0.5)),
        title: result.title || '未知文书'
      }
    } catch (error) {
      console.error('解析分类响应失败:', error)
      return {
        type: DocumentType.DAILY_PROGRESS_NOTE,
        confidence: 0.3,
        title: '未知文书'
      }
    }
  }

  /**
   * 获取文档类型的中文名称
   */
  static getDocumentTypeName(type: DocumentType): string {
    const typeNames: Record<DocumentType, string> = {
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
      [DocumentType.DEATH_CASE_DISCUSSION]: '死亡病例讨论记录',
      [DocumentType.IMAGING_REPORT]: '影像检查报告',
      [DocumentType.LAB_REPORT]: '实验室检查报告',
      [DocumentType.OTHER_EXAMINATION]: '其他检查报告',
      [DocumentType.SURGERY_CONSENT]: '手术知情同意书',
      [DocumentType.ANESTHESIA_CONSENT]: '麻醉知情同意书',
      [DocumentType.BLOOD_TRANSFUSION_CONSENT]: '输血知情同意书',
      [DocumentType.SPECIAL_TREATMENT_CONSENT]: '特殊治疗知情同意书',
      [DocumentType.OTHER_CONSENT]: '其他知情同意书'
    }

    return typeNames[type] || '未知文书类型'
  }
}
