/**
 * 文书类型映射表
 * 
 * 用途：
 * 1. 统一管理文书类型的中英文映射关系
 * 2. 数据库存储使用英文代码，前端显示使用中文名称
 * 3. 支持别名匹配，兼容旧数据
 */

export interface DocumentTypeMapping {
  code: string          // 英文代码（数据库存储）
  name: string          // 中文名称（前端显示）
  category: string      // 分类
  aliases: string[]     // 别名列表（用于兼容）
  description?: string  // 描述
}

/**
 * 文书类型映射表
 */
export const DOCUMENT_TYPE_MAPPINGS: Record<string, DocumentTypeMapping> = {
  // ========================================
  // 入院记录类
  // ========================================
  admission_record: {
    code: 'admission_record',
    name: '入院记录',
    category: 'admission',
    aliases: ['入院记录', '入院病历'],
    description: '患者入院时的基本信息、主诉、现病史、既往史、体格检查等记录'
  },
  admission_record_24h_in: {
    code: 'admission_record_24h_in',
    name: '24小时入院记录',
    category: 'admission',
    aliases: ['24小时入院记录', '24h入院记录'],
    description: '入院后24小时内完成的入院记录'
  },
  admission_record_24h_out: {
    code: 'admission_record_24h_out',
    name: '24小时入出院记录',
    category: 'admission',
    aliases: ['24小时入出院记录', '24h入出院记录'],
    description: '入院后24小时内出院的患者记录'
  },

  // ========================================
  // 病程记录类
  // ========================================
  progress_note: {
    code: 'progress_note',
    name: '病程记录',
    category: 'progress',
    aliases: ['病程记录', '病程'],
    description: '住院期间的病情变化、治疗过程、医嘱执行等动态记录'
  },
  first_progress_note: {
    code: 'first_progress_note',
    name: '首次病程记录',
    category: 'progress',
    aliases: ['首次病程记录', '首次病程'],
    description: '入院后首次书写的病程记录'
  },
  daily_progress_note: {
    code: 'daily_progress_note',
    name: '日常病程记录',
    category: 'progress',
    aliases: ['日常病程记录', '日常病程'],
    description: '每日病情变化和诊疗情况记录'
  },
  attending_first_progress: {
    code: 'attending_first_progress',
    name: '上级医师首次查房记录',
    category: 'progress',
    aliases: ['上级医师首次查房记录', '首次查房'],
    description: '上级医师首次查房的记录'
  },
  attending_progress: {
    code: 'attending_progress',
    name: '上级医师查房记录',
    category: 'progress',
    aliases: ['上级医师查房记录', '查房记录'],
    description: '上级医师查房的记录'
  },
  consultation_record: {
    code: 'consultation_record',
    name: '会诊记录',
    category: 'progress',
    aliases: ['会诊记录', '会诊'],
    description: '多学科会诊或专科会诊记录'
  },
  handover_record: {
    code: 'handover_record',
    name: '交接班记录',
    category: 'progress',
    aliases: ['交接班记录', '交班记录'],
    description: '医师交接班时的病情交接记录'
  },
  stage_summary: {
    code: 'stage_summary',
    name: '阶段小结',
    category: 'progress',
    aliases: ['阶段小结', '阶段性小结'],
    description: '住院期间阶段性病情总结'
  },
  transfer_record: {
    code: 'transfer_record',
    name: '转科记录',
    category: 'progress',
    aliases: ['转科记录', '转科'],
    description: '患者转科时的记录'
  },
  difficult_case_discussion: {
    code: 'difficult_case_discussion',
    name: '疑难病例讨论记录',
    category: 'progress',
    aliases: ['疑难病例讨论记录', '疑难病例讨论'],
    description: '疑难病例的多学科讨论记录'
  },

  // ========================================
  // 手术记录类
  // ========================================
  operation_record: {
    code: 'operation_record',
    name: '手术记录',
    category: 'operation',
    aliases: ['手术记录', '手术'],
    description: '手术过程的详细记录'
  },
  preoperative_summary: {
    code: 'preoperative_summary',
    name: '术前小结',
    category: 'operation',
    aliases: ['术前小结', '术前总结'],
    description: '手术前的病情总结和手术指征'
  },
  preoperative_discussion: {
    code: 'preoperative_discussion',
    name: '术前讨论',
    category: 'operation',
    aliases: ['术前讨论', '术前讨论记录'],
    description: '手术前的多学科讨论记录'
  },
  postoperative_first_progress: {
    code: 'postoperative_first_progress',
    name: '术后首次病程记录',
    category: 'operation',
    aliases: ['术后首次病程记录', '术后首程'],
    description: '手术后首次病程记录'
  },
  anesthesia_record: {
    code: 'anesthesia_record',
    name: '麻醉记录',
    category: 'operation',
    aliases: ['麻醉记录', '麻醉'],
    description: '麻醉过程的详细记录'
  },

  // ========================================
  // 出院记录类
  // ========================================
  discharge_record: {
    code: 'discharge_record',
    name: '出院记录',
    category: 'discharge',
    aliases: ['出院记录', '出院病历'],
    description: '患者出院时的诊疗总结、出院诊断、治疗效果等记录'
  },
  discharge_summary: {
    code: 'discharge_summary',
    name: '出院小结',
    category: 'discharge',
    aliases: ['出院小结', '出院总结'],
    description: '出院记录的简化版本'
  },
  death_record: {
    code: 'death_record',
    name: '死亡记录',
    category: 'discharge',
    aliases: ['死亡记录', '死亡病历'],
    description: '患者死亡时的记录'
  },
  death_case_discussion: {
    code: 'death_case_discussion',
    name: '死亡病例讨论记录',
    category: 'discharge',
    aliases: ['死亡病例讨论记录', '死亡讨论'],
    description: '死亡病例的讨论记录'
  },

  // ========================================
  // 检查报告类
  // ========================================
  examination_report: {
    code: 'examination_report',
    name: '检查报告',
    category: 'examination',
    aliases: ['检查报告', '辅助检查'],
    description: '各类辅助检查报告'
  },
  imaging_report: {
    code: 'imaging_report',
    name: '影像学报告',
    category: 'examination',
    aliases: ['影像学报告', '影像报告'],
    description: 'X线、CT、MRI等影像学检查报告'
  },
  lab_report: {
    code: 'lab_report',
    name: '实验室报告',
    category: 'examination',
    aliases: ['实验室报告', '化验报告', '检验报告'],
    description: '血液、尿液等实验室检查报告'
  },
  pathology_report: {
    code: 'pathology_report',
    name: '病理报告',
    category: 'examination',
    aliases: ['病理报告', '病理'],
    description: '病理检查报告'
  },
  other_examination: {
    code: 'other_examination',
    name: '其他检查',
    category: 'examination',
    aliases: ['其他检查'],
    description: '其他辅助检查'
  },

  // ========================================
  // 知情同意书类
  // ========================================
  consent_form: {
    code: 'consent_form',
    name: '知情同意书',
    category: 'consent',
    aliases: ['知情同意书', '同意书'],
    description: '各类知情同意书'
  },
  surgery_consent: {
    code: 'surgery_consent',
    name: '手术知情同意书',
    category: 'consent',
    aliases: ['手术知情同意书', '手术同意书'],
    description: '手术前的知情同意书'
  },
  anesthesia_consent: {
    code: 'anesthesia_consent',
    name: '麻醉知情同意书',
    category: 'consent',
    aliases: ['麻醉知情同意书', '麻醉同意书'],
    description: '麻醉前的知情同意书'
  },
  blood_transfusion_consent: {
    code: 'blood_transfusion_consent',
    name: '输血知情同意书',
    category: 'consent',
    aliases: ['输血知情同意书', '输血同意书'],
    description: '输血前的知情同意书'
  },
  special_treatment_consent: {
    code: 'special_treatment_consent',
    name: '特殊治疗知情同意书',
    category: 'consent',
    aliases: ['特殊治疗知情同意书', '特殊治疗同意书'],
    description: '特殊治疗前的知情同意书'
  },
  critical_illness_notice: {
    code: 'critical_illness_notice',
    name: '病危通知书',
    category: 'consent',
    aliases: ['病危通知书', '病重通知书'],
    description: '病危或病重通知书'
  },

  // ========================================
  // 其他
  // ========================================
  medical_order: {
    code: 'medical_order',
    name: '医嘱记录',
    category: 'other',
    aliases: ['医嘱记录', '医嘱'],
    description: '医嘱记录'
  },
  medication_record: {
    code: 'medication_record',
    name: '用药记录',
    category: 'other',
    aliases: ['用药记录', '用药'],
    description: '用药记录'
  },
  nursing_record: {
    code: 'nursing_record',
    name: '护理记录',
    category: 'other',
    aliases: ['护理记录', '护理'],
    description: '护理记录'
  }
}

/**
 * 根据中文名称获取英文代码
 * @param name 中文名称或别名
 * @returns 英文代码，如果找不到则返回原值
 */
export function getDocumentTypeCode(name: string): string {
  // 先尝试精确匹配
  for (const [code, mapping] of Object.entries(DOCUMENT_TYPE_MAPPINGS)) {
    if (mapping.name === name || mapping.aliases.includes(name)) {
      return code
    }
  }
  
  // 如果已经是英文代码，直接返回
  if (DOCUMENT_TYPE_MAPPINGS[name]) {
    return name
  }
  
  // 找不到，返回原值
  return name
}

/**
 * 根据英文代码获取中文名称
 * @param code 英文代码
 * @returns 中文名称，如果找不到则返回原值
 */
export function getDocumentTypeName(code: string): string {
  return DOCUMENT_TYPE_MAPPINGS[code]?.name || code
}

/**
 * 获取用于规则匹配的标准基础代码
 * 例如：first_progress_note -> progress_note
 */
export function getDocumentBaseCode(codeOrName: string): string {
  const code = getDocumentTypeCode(codeOrName)
  const mapping = DOCUMENT_TYPE_MAPPINGS[code]
  if (!mapping) return code

  switch (mapping.category) {
    case 'progress':
      return 'progress_note'
    case 'admission':
      return 'admission_record'
    case 'discharge':
      return 'discharge_record'
    case 'operation':
      return 'operation_record'
    case 'examination':
      return 'examination_report'
    case 'other':
      // 其他类保留常见基础类型；未知的返回自身
      if (code === 'medical_order' || code === 'medication_record') return code
      return code
    default:
      return code
  }
}

/**
 * 获取所有用于匹配的代码集合：精确代码 + 基础代码（去重）
 */
export function getDocumentMatchCodes(codeOrName: string): string[] {
  const code = getDocumentTypeCode(codeOrName)
  const base = getDocumentBaseCode(code)
  return Array.from(new Set([code, base]))
}

/**
 * 获取所有文书类型代码列表
 * @returns 文书类型代码数组
 */
export function getAllDocumentTypeCodes(): string[] {
  return Object.keys(DOCUMENT_TYPE_MAPPINGS)
}

/**
 * 根据分类获取文书类型列表
 * @param category 分类名称
 * @returns 该分类下的文书类型映射数组
 */
export function getDocumentTypesByCategory(category: string): DocumentTypeMapping[] {
  return Object.values(DOCUMENT_TYPE_MAPPINGS).filter(
    mapping => mapping.category === category
  )
}

/**
 * 文书分类映射
 */
export const DOCUMENT_CATEGORIES = {
  admission: '入院记录',
  progress: '病程记录',
  operation: '手术记录',
  discharge: '出院记录',
  examination: '检查报告',
  consent: '知情同意书',
  other: '其他'
} as const

