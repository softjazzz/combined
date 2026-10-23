/**
 * 批量质控结果“客户视图”的展示模型（2026-10-23 改版）。
 *
 * 只做装配：状态、结论、证据、建议均来自既有的结果项与文案函数，本模块不重判、不改写临床事实。
 * 病历以客户安全引用 record_ref 分组，可读标识（住院号、科室等）来自结果页身份回查接口。
 */
import type { BatchJobRecordIdentity } from '@/services/sichuan-rule-workspace-service'

export type ReviewStatusKey =
  | 'non_compliant'
  | 'data_gap'
  | 'compliant'
  | 'not_applicable'
  | 'pending'

export const REVIEW_STATUS_ORDER: ReviewStatusKey[] = [
  'non_compliant',
  'data_gap',
  'compliant',
  'not_applicable',
  'pending',
]

export const REVIEW_STATUS_LABELS: Record<ReviewStatusKey, string> = {
  non_compliant: '问题',
  data_gap: '需补资料',
  compliant: '合格',
  not_applicable: '不适用',
  pending: '未完成判定',
}

export const REVIEW_STATUS_TONES: Record<
  ReviewStatusKey,
  'danger' | 'warning' | 'success' | 'neutral'
> = {
  non_compliant: 'danger',
  data_gap: 'warning',
  compliant: 'success',
  not_applicable: 'neutral',
  pending: 'neutral',
}

/** 规则编号第二段为章节号；按章节归入客户熟悉的大类（与 0609 质控点章节一致）。 */
const RULE_CHAPTER_NAMES: Record<string, string> = {
  '01': '入院记录与首次病程',
  '02': '上级医师查房',
  '03': '会诊',
  '04': '手术与麻醉',
  '05': '抗菌药物',
  '06': '检查检验',
  '07': '输血',
  '08': '出院记录',
  '09': '抢救与死亡讨论',
  '10': '交接班、转科与有创操作',
  '11': '知情同意',
  '12': '病程内容',
}

export type ReviewEvidence = { key: string; source: string; time: string; quote: string }

export type ReviewItem = {
  key: string
  ruleCode: string
  title: string
  status: ReviewStatusKey
  chapter: string
  summary: string
  suggestion: string
  evidence: ReviewEvidence[]
}

export type ReviewChapterGroup = { chapter: string; items: ReviewItem[] }

export type ReviewRecord = {
  key: string
  sequence: number
  title: string
  department: string
  inpatientNo: string
  doctor: string
  admissionDate: string
  dischargeDate: string
  counts: Record<ReviewStatusKey, number>
  items: ReviewItem[]
}

export type TopIssueRule = { ruleCode: string; title: string; recordCount: number }

export function reviewStatusOf(canonicalStatus: string): ReviewStatusKey {
  if (canonicalStatus === 'non_compliant' || canonicalStatus === 'ai_suggested_non_compliant') {
    return 'non_compliant'
  }
  if (canonicalStatus === 'data_gap') return 'data_gap'
  if (canonicalStatus === 'compliant' || canonicalStatus === 'ai_suggested_compliant')
    return 'compliant'
  if (canonicalStatus === 'not_applicable') return 'not_applicable'
  return 'pending'
}

export function ruleChapterName(ruleCode: string): string {
  const chapter = String(ruleCode || '').split('-')[1] || ''
  return RULE_CHAPTER_NAMES[chapter] || '其他'
}

/** 质控点名称来自客户原文，去掉末尾标点即可展示。 */
export function cleanRuleTitle(name: string): string {
  return (
    String(name || '')
      .trim()
      .replace(/[；;。，,\s]+$/u, '') || '未命名质控点'
  )
}

function emptyCounts(): Record<ReviewStatusKey, number> {
  return { non_compliant: 0, data_gap: 0, compliant: 0, not_applicable: 0, pending: 0 }
}

function formatDate(value: string): string {
  const text = String(value || '').trim()
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(text)
  return match ? `${match[1]}-${match[2]}-${match[3]}` : text
}

export function buildReviewRecords<T>(
  items: T[],
  options: {
    recordKey: (item: T) => string
    toReviewItem: (item: T) => ReviewItem
    identities: Map<string, BatchJobRecordIdentity>
  },
): ReviewRecord[] {
  const grouped = new Map<string, ReviewItem[]>()
  for (const item of items) {
    const key = options.recordKey(item)
    if (!grouped.has(key)) grouped.set(key, [])
    grouped.get(key)?.push(options.toReviewItem(item))
  }
  const records = Array.from(grouped.entries()).map(([key, reviewItems], index) => {
    const identity = options.identities.get(key)
    const sequence = identity?.sequence || index + 1
    const counts = emptyCounts()
    for (const item of reviewItems) counts[item.status] += 1
    return {
      key,
      sequence,
      title: `病历 ${String(sequence).padStart(2, '0')}`,
      department: identity?.department || '',
      inpatientNo: identity?.inpatient_no || '',
      doctor: identity?.doctor || '',
      admissionDate: formatDate(identity?.admission_date || ''),
      dischargeDate: formatDate(identity?.discharge_date || ''),
      counts,
      items: reviewItems,
    }
  })
  // 问题多的病历排前；同数按任务中的病历顺序。
  return records.sort(
    (left, right) =>
      right.counts.non_compliant - left.counts.non_compliant || left.sequence - right.sequence,
  )
}

/** 同一病历的条目按章节分组，章节按规则编号顺序，组内问题项在前。 */
export function groupByChapter(items: ReviewItem[]): ReviewChapterGroup[] {
  const groups = new Map<string, ReviewItem[]>()
  const sorted = [...items].sort((left, right) => left.ruleCode.localeCompare(right.ruleCode))
  for (const item of sorted) {
    if (!groups.has(item.chapter)) groups.set(item.chapter, [])
    groups.get(item.chapter)?.push(item)
  }
  return Array.from(groups.entries()).map(([chapter, chapterItems]) => ({
    chapter,
    items: chapterItems,
  }))
}

/** 问题最多的质控点：按“涉及几份病历”计数，同一病历同一质控点只计一次。 */
export function buildTopIssueRules(records: ReviewRecord[]): TopIssueRule[] {
  const byRule = new Map<string, { title: string; records: Set<string> }>()
  for (const record of records) {
    for (const item of record.items) {
      if (item.status !== 'non_compliant') continue
      const entry = byRule.get(item.ruleCode) || { title: item.title, records: new Set<string>() }
      entry.records.add(record.key)
      byRule.set(item.ruleCode, entry)
    }
  }
  return Array.from(byRule.entries())
    .map(([ruleCode, entry]) => ({ ruleCode, title: entry.title, recordCount: entry.records.size }))
    .sort(
      (left, right) =>
        right.recordCount - left.recordCount || left.ruleCode.localeCompare(right.ruleCode),
    )
}
