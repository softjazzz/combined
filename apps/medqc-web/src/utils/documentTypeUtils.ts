/**
 * 文书类型工具函数
 * 提供文书类型的映射、分类和显示功能
 */

import { DocumentType, DocumentCategory } from '@/services/llmService'
import { DocumentCategory as StandardDocumentCategory } from '@/types/medical'

// 兼容不同来源的类型代码，做归一化处理
const KNOWN_TYPES = new Set<string>(Object.values(DocumentType) as unknown as string[])
const TYPE_ALIASES: Record<string, DocumentType> = {
  // 影像检查（统一到旧版：imaging_report）
  'imaging_examination': DocumentType.IMAGING_REPORT,
  'imaging_exam': DocumentType.IMAGING_REPORT,
  'imagingreport': DocumentType.IMAGING_REPORT,
  'imaging_report': DocumentType.IMAGING_REPORT,
  'ct': DocumentType.IMAGING_REPORT,
  'mri': DocumentType.IMAGING_REPORT,
  '核磁': DocumentType.IMAGING_REPORT,
  '磁共振': DocumentType.IMAGING_REPORT,
  'x线': DocumentType.IMAGING_REPORT,
  '影像': DocumentType.IMAGING_REPORT,
  // 实验室检查（统一到旧版：lab_report）
  'laboratory_test': DocumentType.LAB_REPORT,
  'laboratorytest': DocumentType.LAB_REPORT,
  'labtest': DocumentType.LAB_REPORT,
  'lab_report': DocumentType.LAB_REPORT,
  // 其他检查归并到old：other_examination
  'other_examination': DocumentType.OTHER_EXAMINATION,
  // 病理/特殊检查（未单独枚举，归到 other_examination）
  'pathology_examination': DocumentType.OTHER_EXAMINATION,
  'special_examination': DocumentType.OTHER_EXAMINATION,
  // 旧病程/入院/出院等别名归一
  'admission_record_24h_in': DocumentType.ADMISSION_RECORD,
  'admission_record_24h_out': DocumentType.ADMISSION_RECORD,
  'attending_first_progress': DocumentType.ATTENDING_PROGRESS
}

function normalizeType(input: unknown): DocumentType {
  const raw = String(input ?? '').trim()
  const lower = raw.toLowerCase()
  if ((KNOWN_TYPES as Set<string>).has(lower)) {
    return lower as DocumentType
  }
  if (TYPE_ALIASES[lower]) return TYPE_ALIASES[lower]
  return DocumentType.DAILY_PROGRESS_NOTE
}

// 文书类型到中文名称的映射
export const DOCUMENT_TYPE_LABELS: Record<DocumentType, string> = {
  // 入院记录
  [DocumentType.ADMISSION_RECORD]: '入院记录',
  [DocumentType.ADMISSION_RECORD_24H_IN]: '24小时内入院记录',
  [DocumentType.ADMISSION_RECORD_24H_OUT]: '24小时出入院记录',

  // 病程记录
  [DocumentType.FIRST_PROGRESS_NOTE]: '首次病程记录',
  [DocumentType.DAILY_PROGRESS_NOTE]: '日常病程记录',
  [DocumentType.ATTENDING_FIRST_PROGRESS]: '主治医生首次查房记录',
  [DocumentType.ATTENDING_PROGRESS]: '主治医生查房记录',
  [DocumentType.CONSULTATION_RECORD]: '会诊记录',
  [DocumentType.HANDOVER_RECORD]: '接班记录',
  [DocumentType.STAGE_SUMMARY]: '阶段小结',

  // 手术记录
  [DocumentType.OPERATION_RECORD]: '手术记录',
  [DocumentType.PREOPERATIVE_SUMMARY]: '术前小结',

  // 出院记录
  [DocumentType.DISCHARGE_RECORD]: '出院记录',
  [DocumentType.DEATH_RECORD]: '死亡记录',
  [DocumentType.DEATH_CASE_DISCUSSION]: '死亡病例讨论记录',

  // 辅助检查
  [DocumentType.IMAGING_REPORT]: '影像检查报告',
  [DocumentType.LAB_REPORT]: '实验室检查报告',
  [DocumentType.OTHER_EXAMINATION]: '其他检查报告',

  // 知情同意书
  [DocumentType.SURGERY_CONSENT]: '手术知情同意书',
  [DocumentType.ANESTHESIA_CONSENT]: '麻醉知情同意书',
  [DocumentType.BLOOD_TRANSFUSION_CONSENT]: '输血知情同意书',
  [DocumentType.SPECIAL_TREATMENT_CONSENT]: '特殊治疗知情同意书',
  [DocumentType.CRITICAL_ILLNESS_NOTICE]: '病危(重)通知书'
}

// 文书分类到中文名称的映射
export const DOCUMENT_CATEGORY_LABELS: Record<DocumentCategory, string> = {
  [DocumentCategory.ADMISSION_RECORD]: '入院记录',
  [DocumentCategory.PROGRESS_NOTE]: '病程记录',
  [DocumentCategory.OPERATION_RECORD]: '手术记录',
  [DocumentCategory.DISCHARGE_RECORD]: '出院记录',
  [DocumentCategory.EXAMINATION_REPORT]: '辅助检查',
  [DocumentCategory.CONSENT_FORM]: '知情同意书'
}

// 文书类型到分类的映射
export const DOCUMENT_TYPE_TO_CATEGORY: Record<DocumentType, DocumentCategory> = {
  // 入院记录
  [DocumentType.ADMISSION_RECORD]: DocumentCategory.ADMISSION_RECORD,
  [DocumentType.ADMISSION_RECORD_24H_IN]: DocumentCategory.ADMISSION_RECORD,
  [DocumentType.ADMISSION_RECORD_24H_OUT]: DocumentCategory.ADMISSION_RECORD,

  // 病程记录
  [DocumentType.FIRST_PROGRESS_NOTE]: DocumentCategory.PROGRESS_NOTE,
  [DocumentType.DAILY_PROGRESS_NOTE]: DocumentCategory.PROGRESS_NOTE,
  [DocumentType.ATTENDING_FIRST_PROGRESS]: DocumentCategory.PROGRESS_NOTE,
  [DocumentType.ATTENDING_PROGRESS]: DocumentCategory.PROGRESS_NOTE,
  [DocumentType.CONSULTATION_RECORD]: DocumentCategory.PROGRESS_NOTE,
  [DocumentType.HANDOVER_RECORD]: DocumentCategory.PROGRESS_NOTE,
  [DocumentType.STAGE_SUMMARY]: DocumentCategory.PROGRESS_NOTE,

  // 手术记录
  [DocumentType.OPERATION_RECORD]: DocumentCategory.OPERATION_RECORD,
  [DocumentType.PREOPERATIVE_SUMMARY]: DocumentCategory.OPERATION_RECORD,

  // 出院记录
  [DocumentType.DISCHARGE_RECORD]: DocumentCategory.DISCHARGE_RECORD,
  [DocumentType.DEATH_RECORD]: DocumentCategory.DISCHARGE_RECORD,
  [DocumentType.DEATH_CASE_DISCUSSION]: DocumentCategory.DISCHARGE_RECORD,

  // 辅助检查
  [DocumentType.IMAGING_REPORT]: DocumentCategory.EXAMINATION_REPORT,
  [DocumentType.LAB_REPORT]: DocumentCategory.EXAMINATION_REPORT,
  [DocumentType.OTHER_EXAMINATION]: DocumentCategory.EXAMINATION_REPORT,

  // 知情同意书
  [DocumentType.SURGERY_CONSENT]: DocumentCategory.CONSENT_FORM,
  [DocumentType.ANESTHESIA_CONSENT]: DocumentCategory.CONSENT_FORM,
  [DocumentType.BLOOD_TRANSFUSION_CONSENT]: DocumentCategory.CONSENT_FORM,
  [DocumentType.SPECIAL_TREATMENT_CONSENT]: DocumentCategory.CONSENT_FORM,
  [DocumentType.CRITICAL_ILLNESS_NOTICE]: DocumentCategory.CONSENT_FORM
}

// 按分类组织的文书类型
export const DOCUMENT_TYPES_BY_CATEGORY: Record<DocumentCategory, DocumentType[]> = {
  [DocumentCategory.ADMISSION_RECORD]: [
    DocumentType.ADMISSION_RECORD,
    DocumentType.ADMISSION_RECORD_24H_IN,
    DocumentType.ADMISSION_RECORD_24H_OUT
  ],
  [DocumentCategory.PROGRESS_NOTE]: [
    DocumentType.FIRST_PROGRESS_NOTE,
    DocumentType.DAILY_PROGRESS_NOTE,
    DocumentType.ATTENDING_FIRST_PROGRESS,
    DocumentType.ATTENDING_PROGRESS,
    DocumentType.CONSULTATION_RECORD,
    DocumentType.HANDOVER_RECORD,
    DocumentType.STAGE_SUMMARY
  ],
  [DocumentCategory.OPERATION_RECORD]: [
    DocumentType.OPERATION_RECORD,
    DocumentType.PREOPERATIVE_SUMMARY
  ],
  [DocumentCategory.DISCHARGE_RECORD]: [
    DocumentType.DISCHARGE_RECORD,
    DocumentType.DEATH_RECORD,
    DocumentType.DEATH_CASE_DISCUSSION
  ],
  [DocumentCategory.EXAMINATION_REPORT]: [
    DocumentType.IMAGING_REPORT,
    DocumentType.LAB_REPORT,
    DocumentType.OTHER_EXAMINATION
  ],
  [DocumentCategory.CONSENT_FORM]: [
    DocumentType.SURGERY_CONSENT,
    DocumentType.ANESTHESIA_CONSENT,
    DocumentType.BLOOD_TRANSFUSION_CONSENT,
    DocumentType.SPECIAL_TREATMENT_CONSENT,
    DocumentType.CRITICAL_ILLNESS_NOTICE
  ]
}

/**
 * 获取文书类型的中文名称
 */
export function getDocumentTypeLabel(type: DocumentType): string {
  return DOCUMENT_TYPE_LABELS[type] || type
}

/**
 * 获取文书分类的中文名称
 */
export function getDocumentCategoryLabel(category: DocumentCategory): string {
  return DOCUMENT_CATEGORY_LABELS[category] || category
}

/**
 * 根据文书类型获取所属分类
 */
export function getDocumentCategory(type: DocumentType): DocumentCategory {
  const normalized = normalizeType(type)
  return DOCUMENT_TYPE_TO_CATEGORY[normalized] || DocumentCategory.PROGRESS_NOTE
}

/**
 * 获取指定分类下的所有文书类型
 */
export function getDocumentTypesByCategory(category: DocumentCategory): DocumentType[] {
  return DOCUMENT_TYPES_BY_CATEGORY[category] || []
}

/**
 * 获取所有文书类型的选项列表（用于下拉选择）
 */
export function getAllDocumentTypeOptions(): Array<{
  value: DocumentType
  label: string
  category: DocumentCategory
  categoryLabel: string
}> {
  return Object.values(DocumentType).map(type => {
    const normalized = normalizeType(type)
    return {
      value: normalized,
      label: getDocumentTypeLabel(normalized),
      category: getDocumentCategory(normalized),
      categoryLabel: getDocumentCategoryLabel(getDocumentCategory(normalized))
    }
  })
}

/**
 * 获取按分类分组的文书类型选项
 */
export function getGroupedDocumentTypeOptions(): Array<{
  category: DocumentCategory
  categoryLabel: string
  options: Array<{
    value: DocumentType
    label: string
  }>
}> {
  return Object.values(DocumentCategory).map(category => ({
    category,
    categoryLabel: getDocumentCategoryLabel(category),
    options: getDocumentTypesByCategory(category).map(type => {
      const normalized = normalizeType(type)
      return {
        value: normalized,
        label: getDocumentTypeLabel(normalized)
      }
    })
  }))
}

/**
 * 根据文本内容智能推断文书类型
 */
export function inferDocumentType(content: string, title?: string): DocumentType {
  const text = (title + ' ' + content).toLowerCase()
  
  // 入院记录
  if (text.includes('入院记录') || text.includes('入院诊断')) {
    if (text.includes('24小时') && text.includes('出院')) {
      return DocumentType.ADMISSION_RECORD_24H_OUT
    } else if (text.includes('24小时')) {
      return DocumentType.ADMISSION_RECORD_24H_IN
    }
    return DocumentType.ADMISSION_RECORD
  }
  
  // 病程记录
  if (text.includes('首次病程') || text.includes('首次查房')) {
    return DocumentType.FIRST_PROGRESS_NOTE
  }
  if (text.includes('主治医生') && text.includes('查房')) {
    if (text.includes('首次')) {
      return DocumentType.ATTENDING_FIRST_PROGRESS
    }
    return DocumentType.ATTENDING_PROGRESS
  }
  if (text.includes('会诊')) {
    return DocumentType.CONSULTATION_RECORD
  }
  if (text.includes('接班') || text.includes('交班')) {
    return DocumentType.HANDOVER_RECORD
  }
  if (text.includes('阶段小结') || text.includes('小结')) {
    return DocumentType.STAGE_SUMMARY
  }
  if (text.includes('病程记录') || text.includes('日常病程')) {
    return DocumentType.DAILY_PROGRESS_NOTE
  }
  
  // 手术记录
  if (text.includes('术前小结') || text.includes('术前讨论')) {
    return DocumentType.PREOPERATIVE_SUMMARY
  }
  if (text.includes('手术记录') || text.includes('手术过程')) {
    return DocumentType.OPERATION_RECORD
  }
  
  // 出院记录
  if (text.includes('死亡记录') || text.includes('死亡证明')) {
    return DocumentType.DEATH_RECORD
  }
  if (text.includes('死亡病例讨论') || text.includes('死亡讨论')) {
    return DocumentType.DEATH_CASE_DISCUSSION
  }
  if (text.includes('出院记录') || text.includes('出院诊断')) {
    return DocumentType.DISCHARGE_RECORD
  }
  
  // 辅助检查
  if (text.includes('影像') || text.includes('ct') || text.includes('mri') || text.includes('x光')) {
    return DocumentType.IMAGING_REPORT
  }
  if (text.includes('化验') || text.includes('血常规') || text.includes('尿常规') || text.includes('实验室')) {
    return DocumentType.LAB_REPORT
  }
  if (text.includes('检查报告') || text.includes('检验报告')) {
    return DocumentType.OTHER_EXAMINATION
  }
  
  // 知情同意书
  if (text.includes('手术知情同意') || text.includes('手术同意书')) {
    return DocumentType.SURGERY_CONSENT
  }
  if (text.includes('麻醉知情同意') || text.includes('麻醉同意书')) {
    return DocumentType.ANESTHESIA_CONSENT
  }
  if (text.includes('输血知情同意') || text.includes('输血同意书')) {
    return DocumentType.BLOOD_TRANSFUSION_CONSENT
  }
  if (text.includes('特殊治疗') && text.includes('同意')) {
    return DocumentType.SPECIAL_TREATMENT_CONSENT
  }
  if (text.includes('病危') || text.includes('病重') || text.includes('通知书')) {
    return DocumentType.CRITICAL_ILLNESS_NOTICE
  }
  
  // 默认返回日常病程记录
  return DocumentType.DAILY_PROGRESS_NOTE
}

/**
 * 验证文书类型是否有效
 */
export function isValidDocumentType(type: string): type is DocumentType {
  return Object.values(DocumentType).includes(type as DocumentType)
}

/**
 * 获取文书类型的颜色标识（用于UI显示）
 */
export function getDocumentTypeColor(type: DocumentType): string {
  const category = getDocumentCategory(type)
  
  switch (category) {
    case DocumentCategory.ADMISSION_RECORD:
      return '#52c41a' // 绿色
    case DocumentCategory.PROGRESS_NOTE:
      return '#1890ff' // 蓝色
    case DocumentCategory.OPERATION_RECORD:
      return '#fa8c16' // 橙色
    case DocumentCategory.DISCHARGE_RECORD:
      return '#722ed1' // 紫色
    case DocumentCategory.EXAMINATION_REPORT:
      return '#722ed1' // 紫色
    case DocumentCategory.CONSENT_FORM:
      return '#13c2c2' // 青色
    default:
      return '#666666' // 灰色
  }
}
