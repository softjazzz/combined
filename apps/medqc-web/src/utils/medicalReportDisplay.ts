export type MedicalReportMetadataRow = {
  key: string
  label: string
  value: string
}

type ReportItemLike = {
  item_name?: string
}

type MetadataField = {
  key: string
  label: string
  aliases?: string[]
  showWhenEmpty?: boolean
}

const EXAM_METADATA_FIELDS: MetadataField[] = [
  { key: 'request_dept', label: '科室', showWhenEmpty: true },
  {
    key: 'request_time',
    label: '申请时间',
    aliases: ['request_datetime'],
    showWhenEmpty: true,
  },
  { key: 'schedule_time', label: '预约时间', showWhenEmpty: true },
  { key: 'exam_time', label: '检查时间', showWhenEmpty: true },
  { key: 'report_time', label: '报告时间', aliases: ['report_datetime'], showWhenEmpty: true },
  { key: 'exam_type', label: '检查类型', showWhenEmpty: true },
  { key: 'body_part', label: '检查部位', aliases: ['exam_zone'], showWhenEmpty: true },
  { key: 'exam_item', label: '检查项目', showWhenEmpty: true },
  { key: 'device_information', label: '检查仪器', showWhenEmpty: true },
  { key: 'result_hint', label: '结果提示', showWhenEmpty: true },
  { key: 'performed_dept', label: '执行科室' },
  { key: 'request_physician', label: '申请医师' },
  { key: 'reporter', label: '报告医师' },
  { key: 'verifier', label: '审核医师' },
  { key: 'report_status', label: '报告状态' },
]

const LAB_METADATA_FIELDS: MetadataField[] = [
  { key: 'request_time', label: '申请时间', aliases: ['request_datetime'] },
  { key: 'report_time', label: '报告时间', aliases: ['report_datetime'] },
  { key: 'specimen', label: '标本类型' },
  { key: 'request_dept', label: '申请科室' },
  { key: 'performed_dept', label: '执行科室' },
  { key: 'request_physician', label: '申请医师' },
  { key: 'reporter', label: '报告医师' },
  { key: 'verifier', label: '审核医师' },
]

function textValue(value: unknown): string {
  return String(value ?? '').trim()
}

function resolveMetadataValue(metadata: Record<string, unknown>, field: MetadataField): string {
  for (const key of [field.key, ...(field.aliases || [])]) {
    const value = textValue(metadata[key])
    if (value) return value
  }
  return ''
}

function resolveExamItemNames(items: ReportItemLike[]): string {
  const names = items.map((item) => textValue(item.item_name)).filter(Boolean)
  return [...new Set(names)].join('、')
}

export function buildMedicalReportMetadataRows(
  metadata: Record<string, unknown> | null | undefined,
  reportKind: 'exam' | 'lab',
  reportItems: ReportItemLike[] = [],
): MedicalReportMetadataRow[] {
  const source = metadata || {}
  const fields = reportKind === 'exam' ? EXAM_METADATA_FIELDS : LAB_METADATA_FIELDS

  return fields.flatMap((field) => {
    const metadataValue = resolveMetadataValue(source, field)
    const value =
      field.key === 'exam_item' && !metadataValue
        ? resolveExamItemNames(reportItems)
        : metadataValue
    if (!value && !field.showWhenEmpty) return []
    return [{ key: field.key, label: field.label, value: value || '—' }]
  })
}
