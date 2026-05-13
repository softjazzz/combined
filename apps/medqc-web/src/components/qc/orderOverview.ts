export type OrderFilter =
  | 'all'
  | 'long'
  | 'temp'
  | 'drug'
  | 'exam_lab'
  | 'procedure_care'
  | 'discharge_admin'
  | 'other'

export type OrderCategory = 'drug' | 'exam_lab' | 'procedure_care' | 'discharge_admin' | 'other'

export type OrderType = 'long' | 'temp' | 'unknown'

export interface OrderSourceField {
  source_field?: string
  raw_value_preview?: string
  used?: boolean
}

export interface OrderDocLike {
  doc_key: string
  doc_type: string
  doc_name: string
  content: string
  document_title?: string
  sort_time?: string
  record_time?: string
  source_table?: string
  group_key?: string
  source_fields?: OrderSourceField[]
}

export interface OrderRow {
  key: string
  sourceDocKey: string
  blockKey: string
  orderType: OrderType
  orderTypeLabel: string
  category: OrderCategory
  categoryLabel: string
  content: string
  time: string
  startTime: string
  stopTime: string
  status: string
  doctor: string
  doseUsage: string
  searchText: string
}

export const ORDER_FILTER_LABELS: Record<OrderFilter, string> = {
  all: '全部',
  long: '长期',
  temp: '临时',
  drug: '药品',
  exam_lab: '检验检查',
  procedure_care: '处置护理',
  discharge_admin: '出院行政',
  other: '其他',
}

export function safeOrderText(value: unknown): string {
  return String(value || '').trim()
}

function formatOrderDate(value?: string): string {
  const raw = safeOrderText(value)
  if (!raw) return ''
  const normalized = raw.endsWith('Z') ? raw : raw.replace(' ', 'T')
  const date = new Date(normalized)
  if (!Number.isNaN(date.getTime())) {
    const formatter = new Intl.DateTimeFormat('zh-CN', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    })
    const parts = formatter.formatToParts(date)
    const get = (type: Intl.DateTimeFormatPartTypes) =>
      parts.find((part) => part.type === type)?.value || ''
    return `${get('year')}-${get('month')}-${get('day')} ${get('hour')}:${get('minute')}`
  }
  return raw.slice(0, 16)
}

export function isOrderDoc(
  doc?: Pick<
    OrderDocLike,
    'doc_type' | 'source_table' | 'group_key' | 'document_title' | 'doc_name'
  > | null,
): boolean {
  if (!doc) return false
  if (safeOrderText(doc.group_key) === 'orders') return true
  const probe = [doc.doc_type, doc.source_table, doc.document_title, doc.doc_name]
    .map((item) => safeOrderText(item).toLowerCase())
    .join(' ')
  return probe.includes('order') || probe.includes('医嘱')
}

export function buildSourceFieldMap(doc: Pick<OrderDocLike, 'source_fields'>): Map<string, string> {
  const fields = new Map<string, string>()
  for (const field of doc.source_fields || []) {
    const key = safeOrderText(field?.source_field).toLowerCase()
    const value = safeOrderText(field?.raw_value_preview)
    if (key && value) fields.set(key, value)
  }
  return fields
}

export function pickFieldValue(fields: Map<string, string>, keys: string[]): string {
  for (const key of keys) {
    const value = fields.get(key.toLowerCase())
    if (value) return value
  }
  return ''
}

export function inferOrderTypeFromText(text: string): OrderType {
  if (/临时医嘱|临嘱|临时/u.test(text)) return 'temp'
  if (/长期医嘱|长嘱|长期/u.test(text)) return 'long'
  return 'unknown'
}

function hasExplicitDrugField(fields: Map<string, string>): boolean {
  return [
    'drug_name',
    'medicine_name',
    'medication_name',
    'drug_code',
    'medicine_code',
    '药品名称',
  ].some((key) => Boolean(fields.get(key.toLowerCase())))
}

function hasDoseFrequencyUsage(fields: Map<string, string>, text: string): boolean {
  const hasDose = Boolean(
    pickFieldValue(fields, ['dosage', 'dose', 'single_dose', '一次剂量', '剂量']),
  )
  const hasFrequency = Boolean(pickFieldValue(fields, ['frequency', 'freq', '频次']))
  const hasUsage = Boolean(
    pickFieldValue(fields, ['usage', 'route', 'administration_route', '用法', '途径']),
  )
  if ((hasDose && hasFrequency) || (hasDose && hasUsage) || (hasFrequency && hasUsage)) {
    return true
  }
  return /(\d+(\.\d+)?\s?(mg|g|ml|iu|u|片|粒|支|瓶|袋|丸|贴|滴|喷|枚|单位))|(\b(qd|bid|tid|qid|q[0-9]+h|st|qn|prn)\b)|口服|静滴|静脉|肌注|皮下|外用|雾化吸入|舌下含服/iu.test(
    text,
  )
}

export function inferOrderCategory(
  content: string,
  fields: Map<string, string> = new Map(),
): OrderCategory {
  const text = safeOrderText(content)
  const compact = text.replace(/\s+/g, '')

  if (/今日出院|明日出院|准予出院|办理出院|出院带药|出院|转科|转院|请假/u.test(compact)) {
    return 'discharge_admin'
  }
  if (
    /测定|检查|检验|抗体|抗原|CT|MRI|DR|X线|彩超|超声|心电图|病理|培养|尿常规|血常规|肝功|肾功|电解质|凝血|血糖/u.test(
      compact,
    )
  ) {
    return 'exam_lab'
  }
  if (
    /护理|换药|清创|吸氧|导尿|雾化|会诊|手术|处置|治疗|康复|理疗|穿刺|冲洗|引流|监测|测血压|测血糖|备皮/u.test(
      compact,
    )
  ) {
    return 'procedure_care'
  }
  if (
    hasExplicitDrugField(fields) ||
    hasDoseFrequencyUsage(fields, compact) ||
    /药品|用药|片|针|注射液|胶囊|颗粒|丸|口服液|乳膏|软膏|贴膏|滴眼液|滴鼻液|栓|散剂|溶液/u.test(
      compact,
    )
  ) {
    return 'drug'
  }
  return 'other'
}

export function formatOrderTypeLabel(type: OrderType): string {
  if (type === 'long') return '长期'
  if (type === 'temp') return '临时'
  return '未标记'
}

export function formatOrderCategoryLabel(category: OrderCategory): string {
  return ORDER_FILTER_LABELS[category]
}

export function normalizeOrderRow(doc: OrderDocLike, index: number): OrderRow {
  const fields = buildSourceFieldMap(doc)
  const title = safeOrderText(doc.document_title || doc.doc_name)
  const content =
    pickFieldValue(fields, [
      'order_name',
      'order_text',
      'order_content',
      'order_item_name',
      'item_name',
      'name',
      'prescription_name',
      'drug_name',
      'medicine_name',
    ]) ||
    title ||
    safeOrderText(doc.content) ||
    '未命名医嘱'
  const typeProbe = [
    pickFieldValue(fields, ['order_type', 'order_class', 'type', 'class']),
    doc.doc_type,
    doc.source_table,
    title,
    doc.content,
  ].join(' ')
  const orderType = inferOrderTypeFromText(typeProbe)
  const category = inferOrderCategory(content, fields)
  const startTime = formatOrderDate(
    pickFieldValue(fields, [
      'start_time',
      'start_datetime',
      'prescribed_datetime',
      'order_time',
      'record_time',
      'create_time',
    ]) ||
      doc.record_time ||
      doc.sort_time,
  )
  const stopTime = formatOrderDate(
    pickFieldValue(fields, ['stop_time', 'stop_datetime', 'end_time', 'end_datetime']),
  )
  const doseUsage = [
    pickFieldValue(fields, ['dosage', 'dose', 'single_dose', '一次剂量', '剂量']),
    pickFieldValue(fields, ['frequency', 'freq', '频次']),
    pickFieldValue(fields, ['usage', 'route', 'administration_route', '用法', '途径']),
  ]
    .filter(Boolean)
    .join(' / ')
  const status = pickFieldValue(fields, ['order_status', 'status', 'execute_status'])
  const doctor = pickFieldValue(fields, [
    'doctor',
    'doctor_name',
    'prescriber',
    'prescribed_by',
    'submitter',
    'last_modifier',
  ])
  const searchText = [
    content,
    typeProbe,
    doc.source_table,
    doc.doc_type,
    startTime,
    stopTime,
    doseUsage,
    status,
    doctor,
  ].join(' ')
  const key = `${doc.doc_key}::order-${index}`
  return {
    key,
    sourceDocKey: doc.doc_key,
    blockKey: `order-row-${index}`,
    orderType,
    orderTypeLabel: formatOrderTypeLabel(orderType),
    category,
    categoryLabel: formatOrderCategoryLabel(category),
    content,
    time: startTime,
    startTime,
    stopTime,
    status,
    doctor,
    doseUsage,
    searchText,
  }
}
