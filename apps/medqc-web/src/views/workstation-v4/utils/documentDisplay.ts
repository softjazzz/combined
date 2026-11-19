import type { DocItem, DocTreeGroup, DocTreeNode, MaterialDisplay } from '../types'
import { resolveMedicalDocumentGroup, resolveMedicalDocumentTitle } from './medicalDocumentTaxonomy'

export const DOC_TYPE_LABELS: Record<string, string> = {
  admission_record: '入院记录',
  first_course_record: '首次病程记录',
  daily_course_record: '日常病程记录',
  senior_course_record: '上级医师查房记录',
  consultation_record: '会诊记录',
  surgery_record: '手术记录',
  presurg_summary: '术前小结',
  postsurg_firstcourse_record: '术后首次病程记录',
  rescue_record: '抢救记录',
  transfer_in_record: '转入记录',
  transfer_out_record: '转出记录',
  nursing_record: '护理记录',
  discharge_record: '出院记录',
}

export function normalizeDocTitle(value: string | null | undefined): string {
  return String(value || '').trim()
}

export function parseDocSortTime(value: string | null | undefined): number {
  if (!value) return Number.POSITIVE_INFINITY
  const normalized = value.endsWith('Z') ? value : value.replace(' ', 'T')
  const ts = Date.parse(normalized)
  return Number.isFinite(ts) ? ts : Number.POSITIVE_INFINITY
}

export function formatDocSortTime(value: string | null | undefined): string {
  if (!value) return ''
  const normalized = value.endsWith('Z') ? value : value.replace(' ', 'T')
  const date = new Date(normalized)
  if (!Number.isNaN(date.getTime())) {
    const formatter = new Intl.DateTimeFormat('zh-CN', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    })
    const parts = formatter.formatToParts(date)
    const get = (type: Intl.DateTimeFormatPartTypes) =>
      parts.find((part) => part.type === type)?.value || ''
    return `${get('year')}-${get('month')}-${get('day')} ${get('hour')}:${get('minute')}:${get('second')}`
  }
  return value
    .replace('T', ' ')
    .replace(/\.\d+$/, '')
    .replace(/([+-]\d{2}:?\d{2}|Z)$/i, '')
    .trim()
}

export function resolveDocBaseTitle(
  doc: Pick<DocItem, 'document_title' | 'label' | 'type'>,
): string {
  return resolveMedicalDocumentTitle({
    document_title: doc.document_title,
    label: doc.label,
    type: doc.type,
  })
}

export function resolveDocDisplayTitle(
  doc: Pick<
    DocItem,
    | 'document_title'
    | 'label'
    | 'type'
    | 'sort_time'
    | 'doc_type'
    | 'source_table'
    | 'record_time'
    | 'content'
  >,
  includeTime = false,
): string {
  const title = resolveMedicalDocumentTitle(doc)
  const time = formatDocSortTime(doc.sort_time)
  if (includeTime && time) return `${time} ${title}`
  return title
}

/** 只展示已授权 DTO 的来源和选择结果，不重新选择材料。 */
export function resolveMaterialDisplayNotice(doc: MaterialDisplay): string {
  return [
    doc.material_source_label,
    doc.version_id ? `版本：${doc.version_id}` : doc.source_version_key ? `版本：${doc.source_version_key}` : '',
    doc.material_selected === true ? '已选中' : doc.material_selected === false ? '仅展示，未选用' : '',
    doc.material_rule_usable === false ? '规则暂不可用' : '',
    doc.material_notice,
  ].filter(Boolean).join(' · ')
}

export function resolveMaterialScopeNotice(payload: Record<string, unknown>): string {
  const statusLabels: Record<string, string> = {
    AVAILABLE: '材料可用',
    HELD: '状态待核',
    EMPTY_UNCONFIRMED: '暂无可用版本，不能判定未书写',
    NOT_DEPLOYED: '接口未部署',
  }
  for (const key of ['primary_material_status', 'daily_material_status']) {
    const scope = payload[key]
    if (!scope || typeof scope !== 'object') continue
    const notice = 'notice' in scope && typeof scope.notice === 'string' ? scope.notice : ''
    if (key === 'daily_material_status') return notice
    const kinds = 'kinds' in scope && scope.kinds && typeof scope.kinds === 'object' ? scope.kinds : {}
    const entries: Array<[string, unknown]> = Object.entries(kinds)
    const kindNotices = entries.flatMap(([kind, state]) => {
      if (!state || typeof state !== 'object' || !('status' in state) || typeof state.status !== 'string') return []
      const label = statusLabels[state.status] || state.status
      const detail = 'notice' in state && typeof state.notice === 'string' && state.notice ? `（${state.notice}）` : ''
      return [`${DOC_TYPE_LABELS[kind] || kind}：${label}${detail}`]
    })
    const result = [notice, ...kindNotices].filter(Boolean).join('；')
    if (result) return result
  }
  return ''
}

// 与正文页一致，以服务端明确给出的文书类型识别上级查房，保留源标题和文书键。
function isStructuredSeniorRound(doc: Pick<DocItem, 'doc_type' | 'type'>): boolean {
  return (doc.doc_type || doc.type) === 'senior_course_record'
}

export function resolveDocGroupKey(
  doc: Pick<
    DocItem,
    'doc_type' | 'type' | 'source_table' | 'label' | 'document_title' | 'content' | 'group_key'
  >,
): string {
  if (isStructuredSeniorRound(doc)) return 'course.senior'
  return resolveMedicalDocumentGroup(doc).key
}

function buildTreeNodeFromDoc(doc: DocItem): DocTreeNode {
  const id = String(doc.document_id || doc.id || doc.doc_id || doc.label || '')
  const docType = String(doc.doc_type || doc.type || '')
  const docKey = String(doc.doc_key || `${docType}::${id}`)
  return {
    id,
    doc_key: docKey,
    doc_type: docType,
    document_id: String(doc.document_id || doc.id || doc.doc_id || '') || undefined,
    title: isStructuredSeniorRound(doc)
      ? DOC_TYPE_LABELS.senior_course_record
      : resolveDocDisplayTitle(doc),
    record_time: String(doc.record_time || doc.sort_time || ''),
    source_table: String(doc.source_table || ''),
    group_key: String(doc.group_key || ''),
    has_content: Boolean(doc.has_content),
    length: Number(doc.length || 0),
    projection_incomplete: doc.projection_incomplete === true,
    projection_notice: String(doc.projection_notice || '') || undefined,
  }
}

export function buildFallbackTreeFromDocs(docs: DocItem[]): DocTreeGroup[] {
  const groups: Array<{ key: string; label: string }> = [
    { key: 'frontpage', label: '病案首页' },
    { key: 'admission', label: '入院与首次病程' },
    { key: 'course', label: '日常病程与查房' },
    { key: 'consultation', label: '会诊与讨论' },
    { key: 'surgery', label: '手术与麻醉' },
    { key: 'transfusion', label: '输血相关' },
    { key: 'exam_lab', label: '检查与检验' },
    { key: 'orders', label: '医嘱与用药' },
    { key: 'discharge', label: '出院与死亡' },
    { key: 'handoff', label: '交接与转科' },
    { key: 'other', label: '其他文书' },
  ]
  const byGroup = new Map<string, DocTreeNode[]>()
  for (const doc of docs) {
    const node = buildTreeNodeFromDoc(doc)
    const groupKey = resolveDocGroupKey(doc)
    byGroup.set(groupKey, [...(byGroup.get(groupKey) || []), node])
  }
  const nestedGroupOrders: Record<string, string[]> = {
    admission: ['admission.record', 'admission.first'],
    course: ['course.senior', 'course.ordinary', 'course.other'],
  }
  const subgroupLabels: Record<string, string> = {
    'admission.record': '入院记录',
    'admission.first': '首次病程记录',
    'course.senior': '上级医师查房记录',
    'course.ordinary': '普通查房记录',
    'course.other': '其他日常病程记录',
  }
  return groups
    .map(({ key, label }) => {
      const children = byGroup.get(key) || []
      const subgroups = (nestedGroupOrders[key] || [])
        .map((subgroupKey) => {
          const nodes = byGroup.get(subgroupKey) || []
          return {
            key: subgroupKey,
            label: subgroupLabels[subgroupKey],
            count: nodes.length,
            children: nodes,
          }
        })
        .filter((subgroup) => subgroup.count > 0)
      return {
        key,
        label,
        children,
        count: children.length + subgroups.reduce((sum, subgroup) => sum + subgroup.count, 0),
        subgroups,
      }
    })
    .filter((group) => group.count > 0)
}
