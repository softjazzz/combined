export type MedicalDocumentLike = {
  key?: string
  enabled?: boolean
  title?: string
  label?: string
  document_title?: string
  doc_name?: string
  type?: string
  doc_type?: string
  document_type?: string
  source_table?: string
  group_key?: string
  content?: string | null
  sections?: Array<{ text?: string }>
}

export type MedicalDocumentGroupKey =
  | 'frontpage'
  | 'admission'
  | 'admission.record'
  | 'admission.first'
  | 'course'
  | 'course.senior'
  | 'course.ordinary'
  | 'course.other'
  | 'consultation'
  | 'surgery'
  | 'transfusion'
  | 'exam_lab'
  | 'orders'
  | 'discharge'
  | 'handoff'
  | 'other'

export type MedicalDocumentGroup = {
  key: MedicalDocumentGroupKey
  label: string
  parentKey?: 'course' | 'admission'
}

export const MEDICAL_DOCUMENT_GROUP_ORDER: MedicalDocumentGroupKey[] = [
  'frontpage',
  'admission',
  'course',
  'consultation',
  'surgery',
  'transfusion',
  'exam_lab',
  'orders',
  'discharge',
  'handoff',
  'other',
]

export const MEDICAL_DOCUMENT_GROUP_LABELS: Record<MedicalDocumentGroupKey, string> = {
  frontpage: '病案首页',
  admission: '入院与首次病程',
  'admission.record': '入院记录',
  'admission.first': '首次病程记录',
  course: '日常病程与查房',
  'course.senior': '上级医师查房记录',
  'course.ordinary': '普通查房记录',
  'course.other': '其他日常病程记录',
  consultation: '会诊与讨论',
  surgery: '手术与麻醉',
  transfusion: '输血相关',
  exam_lab: '检查与检验',
  orders: '医嘱与用药',
  discharge: '出院与死亡',
  handoff: '交接与转科',
  other: '其他文书',
}

const TYPE_LABELS: Record<string, string> = {
  mr: '病案首页',
  mr_surgery: '病案首页',
  mr_cost: '病案首页',
  admission_record: '入院记录',
  first_course_record: '首次病程记录',
  daily_course_record: '日常病程记录',
  senior_course_record: '上级医师查房记录',
  course_record: '病程记录',
  rescue_record: '抢救记录',
  consultation_record: '会诊记录',
  surgery_record: '手术记录',
  presurg_summary: '术前小结',
  anesthesia_record: '麻醉记录',
  surgery_inform_consent: '手术知情同意书',
  exam_report: '检查报告',
  lab_report: '检验报告',
  pathology_exam_report: '病理检查报告',
  pathology_exam_master: '病理检查申请单',
  blood_application: '输血申请单',
  blood_transfusion_consent: '输血治疗同意书',
  transfusion_record: '输血记录',
  blood_transfusion_record: '输血记录',
  transfusion_evaluation: '输血前后评价记录',
  medical_order: '医嘱',
  inpat_drug_order: '用药医嘱',
  inpat_nondrug_order: '非药物医嘱',
  discharge_record: '出院记录',
  death_record: '死亡记录',
  death_discussion: '死亡病例讨论记录',
  transfer_in_record: '转入记录',
  transfer_out_record: '转出记录',
  physician_handoff: '医师交接记录',
  physician_change_event: '医师变更记录',
}

function normalize(value: unknown): string {
  return String(value || '')
    .trim()
    .toLowerCase()
}

export function medicalDocumentIdentity(document: MedicalDocumentLike): string {
  return [
    document.group_key,
    document.doc_type,
    document.document_type,
    document.type,
    document.source_table,
    document.title,
    document.label,
    document.document_title,
    document.doc_name,
    String(document.content || '').slice(0, 2000),
    ...(document.sections || [])
      .slice(0, 8)
      .map((section) => String(section.text || '').slice(0, 300)),
  ]
    .map(normalize)
    .join(' ')
}

function hasAny(identity: string, patterns: RegExp): boolean {
  return patterns.test(identity)
}

function isSeniorRound(identity: string): boolean {
  const hasOrdinaryRole = hasAny(
    identity,
    /主治医师|住院医师|普通查房|attending[_ -]?round|ordinary[_ -]?round/,
  )
  if (hasOrdinaryRole && !hasAny(identity, /主任医师|副主任医师|上级医师/)) return false
  return hasAny(identity, /主任医师|副主任医师|上级医师|chief[_ -]?round|senior[_ -]?course/)
}

function isOrdinaryRound(identity: string): boolean {
  return hasAny(identity, /主治医师|住院医师|普通查房|attending[_ -]?round|ordinary[_ -]?round/)
}

function isRound(identity: string): boolean {
  return hasAny(identity, /查房|round|ward[_ -]?round|course[_ -]?note/) || isSeniorRound(identity)
}

export function resolveMedicalDocumentGroup(document: MedicalDocumentLike): MedicalDocumentGroup {
  // 正文可能提及其他文书或诊疗事件，先用文书身份决定目录归属。
  const metadata = { ...document, content: undefined, sections: undefined }
  const group = classifyMedicalDocumentGroup(metadata)
  if (group.parentKey === 'course') {
    const identity = medicalDocumentIdentity(document)
    if (isSeniorRound(identity)) {
      return {
        key: 'course.senior',
        label: MEDICAL_DOCUMENT_GROUP_LABELS['course.senior'],
        parentKey: 'course',
      }
    }
    if (isOrdinaryRound(identity)) {
      return {
        key: 'course.ordinary',
        label: MEDICAL_DOCUMENT_GROUP_LABELS['course.ordinary'],
        parentKey: 'course',
      }
    }
  }
  return group.key === 'other' ? classifyMedicalDocumentGroup(document) : group
}

function classifyMedicalDocumentGroup(document: MedicalDocumentLike): MedicalDocumentGroup {
  const identity = medicalDocumentIdentity(document)
  const type = normalize(document.doc_type || document.document_type || document.type)

  if (hasAny(identity, /病案首页|frontpage|(?:^|[\s._-])mr(?:[\s._-]|$)/)) {
    return { key: 'frontpage', label: MEDICAL_DOCUMENT_GROUP_LABELS.frontpage }
  }
  if (hasAny(identity, /first_course|首次病程/)) {
    return {
      key: 'admission.first',
      label: MEDICAL_DOCUMENT_GROUP_LABELS['admission.first'],
      parentKey: 'admission',
    }
  }
  if (hasAny(identity, /admission|入院记录|入院/)) {
    return {
      key: 'admission.record',
      label: MEDICAL_DOCUMENT_GROUP_LABELS['admission.record'],
      parentKey: 'admission',
    }
  }
  if (hasAny(identity, /consult|会诊|讨论/)) {
    return { key: 'consultation', label: MEDICAL_DOCUMENT_GROUP_LABELS.consultation }
  }
  if (hasAny(identity, /surgery|operation|anesth|手术|术前小结|麻醉/)) {
    return { key: 'surgery', label: MEDICAL_DOCUMENT_GROUP_LABELS.surgery }
  }
  if (hasAny(identity, /transfus|blood_|blood\b|输血/)) {
    return { key: 'transfusion', label: MEDICAL_DOCUMENT_GROUP_LABELS.transfusion }
  }
  if (hasAny(identity, /order|医嘱|用药/)) {
    return { key: 'orders', label: MEDICAL_DOCUMENT_GROUP_LABELS.orders }
  }
  if (hasAny(identity, /exam|lab|pathology|检查|检验|病理/)) {
    return { key: 'exam_lab', label: MEDICAL_DOCUMENT_GROUP_LABELS.exam_lab }
  }
  if (hasAny(identity, /discharge|terminal|death|出院|死亡/)) {
    return { key: 'discharge', label: MEDICAL_DOCUMENT_GROUP_LABELS.discharge }
  }
  if (hasAny(identity, /handoff|transfer|交接|转入|转出|医师变更/)) {
    return { key: 'handoff', label: MEDICAL_DOCUMENT_GROUP_LABELS.handoff }
  }
  if (isRound(identity)) {
    if (isOrdinaryRound(identity) && !isSeniorRound(identity)) {
      return {
        key: 'course.ordinary',
        label: MEDICAL_DOCUMENT_GROUP_LABELS['course.ordinary'],
        parentKey: 'course',
      }
    }
    if (isSeniorRound(identity)) {
      return {
        key: 'course.senior',
        label: MEDICAL_DOCUMENT_GROUP_LABELS['course.senior'],
        parentKey: 'course',
      }
    }
    return {
      key: 'course.other',
      label: MEDICAL_DOCUMENT_GROUP_LABELS['course.other'],
      parentKey: 'course',
    }
  }
  if (hasAny(identity, /daily|course|病程|抢救/)) {
    return {
      key: 'course.other',
      label: MEDICAL_DOCUMENT_GROUP_LABELS['course.other'],
      parentKey: 'course',
    }
  }
  if (type.includes('course')) {
    return {
      key: 'course.other',
      label: MEDICAL_DOCUMENT_GROUP_LABELS['course.other'],
      parentKey: 'course',
    }
  }
  return { key: 'other', label: MEDICAL_DOCUMENT_GROUP_LABELS.other }
}

export function resolveMedicalDocumentTypeLabel(
  document: MedicalDocumentLike | string | null | undefined,
): string {
  const source: MedicalDocumentLike =
    typeof document === 'string' ? { title: document } : document || {}
  const values = [
    source.doc_type,
    source.document_type,
    source.type,
    source.source_table,
    source.title,
    source.label,
    source.document_title,
    source.doc_name,
  ]
    .map(normalize)
    .filter(Boolean)
  for (const value of values) {
    if (TYPE_LABELS[value]) return TYPE_LABELS[value]
    const matched = Object.keys(TYPE_LABELS)
      .sort((left, right) => right.length - left.length)
      .find((key) => value.includes(key))
    if (matched) return TYPE_LABELS[matched]
  }
  const rawTitle = String(
    source.title || source.label || source.document_title || source.doc_name || '',
  ).trim()
  if (/[\u3400-\u9fff]/u.test(rawTitle)) return rawTitle
  return ''
}

export function resolveMedicalDocumentTitle(document: MedicalDocumentLike): string {
  const group = resolveMedicalDocumentGroup(document)
  if (group.key === 'course.senior') return MEDICAL_DOCUMENT_GROUP_LABELS['course.senior']
  if (group.key === 'course.ordinary') {
    const identity = medicalDocumentIdentity(document)
    if (/主治医师/.test(identity)) return '主治医师查房记录'
    if (/住院医师/.test(identity)) return '住院医师查房记录'
    return MEDICAL_DOCUMENT_GROUP_LABELS['course.ordinary']
  }
  if (group.key === 'course.other') {
    const typed = resolveMedicalDocumentTypeLabel(document)
    return typed || MEDICAL_DOCUMENT_GROUP_LABELS['course.other']
  }
  return (
    resolveMedicalDocumentTypeLabel(document) ||
    (/[\u3400-\u9fff]/u.test(String(document.title || ''))
      ? String(document.title || '').trim()
      : '') ||
    (/[\u3400-\u9fff]/u.test(String(document.label || ''))
      ? String(document.label || '').trim()
      : '') ||
    '未命名文书'
  )
}
