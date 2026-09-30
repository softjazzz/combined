import { testRecordDocumentTypeOptions } from '@/views/workstation-v4/customer-sample-validation/syntheticCaseBuilder'
import type {
  EditableMedicalRecordDocument,
  ManualTestRecordCreateRequest,
} from '@/views/workstation-v4/customer-sample-validation/types'
import type { CasePurpose, ExpectedStatus } from '@/services/rule-validation-service'

/** 规则验收“新建测试病例”的表单模型与请求构造；不依赖构建器模板，任何规则都可用。 */

export const CASE_TITLE_PREFIX = '【验收测试】'
/** 测试病例之间复制的来源类型；与“真实病历可编辑副本”区分，复制品仍计为合成病例。 */
export const CASE_COPY_SOURCE_TYPE = 'rule_validation_case_copy'

export type DraftDocument = { key: string; type: string; time: string; title: string; content: string }

export type CaseDraft = {
  title: string
  department: string
  mainDiagnosis: string
  admissionTime: string
  dischargeTime: string
  evaluationDate: string
  documents: DraftDocument[]
  expectedStatus: ExpectedStatus
  purpose: CasePurpose
  reason: string
}

const TYPE_VALUES = new Set(testRecordDocumentTypeOptions.map((o) => o.value))
/** 后端落表名 → 构建器文书类型（与 create_customer_test_record 的映射互逆） */
const TABLE_TO_TYPE: Record<string, string> = {
  exam_item_report: 'exam_report',
  labtest_item_report: 'lab_report',
  inpat_nondrug_order: 'medical_order',
}

/** 各规则族通常需要的文书，仅作添加提示，不代表执行器实际读取范围。 */
const FAMILY_DOCUMENTS: Record<string, string[]> = {
  抢救记录: ['rescue_record', 'medical_order'],
  'CT/MRI检查记录': ['exam_report', 'medical_order', 'daily_course_record'],
  病理检查记录: ['exam_report', 'medical_order'],
  微生物培养检查记录: ['lab_report', 'medical_order', 'daily_course_record'],
}

let keySeed = 0
export function newDocumentKey(): string {
  keySeed += 1
  return `doc-${Date.now()}-${keySeed}`
}

export function typeLabel(value: string): string {
  return testRecordDocumentTypeOptions.find((o) => o.value === value)?.label ?? value
}

export function suggestedDocumentTypes(sourceDocument: string): string[] {
  const suggested = FAMILY_DOCUMENTS[sourceDocument] ?? []
  const common = ['daily_course_record', 'admission_record']
  return [...new Set([...suggested, ...common])].filter((t) => TYPE_VALUES.has(t))
}

export function isRuleRelated(type: string, sourceDocument: string): boolean {
  return (FAMILY_DOCUMENTS[sourceDocument] ?? []).includes(type)
}

function pad(n: number) {
  return String(n).padStart(2, '0')
}
export function toLocalDate(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}
export function toLocalDateTime(date: Date): string {
  return `${toLocalDate(date)}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}
/** 接口时间（"2026-07-01 08:00:00" / ISO）→ datetime-local 输入值 */
export function toInputDateTime(value: string | undefined | null): string {
  const text = String(value || '').trim().replace(' ', 'T')
  return /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(text) ? text.slice(0, 16) : ''
}

export function emptyDraft(now = new Date()): CaseDraft {
  const admission = new Date(now.getTime() - 3 * 24 * 60 * 60 * 1000)
  admission.setHours(8, 0, 0, 0)
  return {
    title: '',
    department: '',
    mainDiagnosis: '',
    admissionTime: toLocalDateTime(admission),
    dischargeTime: '',
    evaluationDate: toLocalDate(now),
    documents: [],
    expectedStatus: 'non_compliant',
    purpose: 'development',
    reason: '',
  }
}

export function blankDocument(type: string, time: string): DraftDocument {
  return { key: newDocumentKey(), type, time, title: typeLabel(type), content: '' }
}

/** 复制源病例的文书：只保留能映射到构建器类型的文书，登记/首页等非文书行不带入。 */
export function copyDocuments(documents: EditableMedicalRecordDocument[]): DraftDocument[] {
  return documents
    .map((doc) => {
      const type = TYPE_VALUES.has(doc.document_type)
        ? doc.document_type
        : TABLE_TO_TYPE[doc.source_table ?? ''] ?? (TYPE_VALUES.has(doc.source_table ?? '') ? doc.source_table! : '')
      return type && doc.content?.trim()
        ? { key: newDocumentKey(), type, time: toInputDateTime(doc.record_time), title: doc.title || typeLabel(type), content: doc.content }
        : null
    })
    .filter((doc): doc is DraftDocument => doc !== null)
}

export function stripPrefix(title: string): string {
  return title.startsWith(CASE_TITLE_PREFIX) ? title.slice(CASE_TITLE_PREFIX.length) : title
}

/** 表单校验：返回首个问题，全部通过返回空串。 */
export function validateDraft(draft: CaseDraft): string {
  if (!draft.title.trim()) return '请填写病例标题'
  if (!draft.department.trim()) return '请填写科室'
  if (!draft.admissionTime) return '请填写入院时间'
  if (!draft.evaluationDate) return '请填写评价时间点'
  if (draft.evaluationDate < draft.admissionTime.slice(0, 10)) return '评价时间点不能早于入院日期'
  if (draft.dischargeTime && draft.dischargeTime < draft.admissionTime) return '出院时间不能早于入院时间'
  if (!draft.documents.some((d) => d.content.trim())) return '请至少填写一份有正文的文书'
  if (!draft.reason.trim()) return '请填写人工预期依据'
  return ''
}

export function buildCreatePayload(
  draft: CaseDraft,
  ruleId: string,
  copyFrom?: { itemId: string },
): ManualTestRecordCreateRequest {
  const title = `${CASE_TITLE_PREFIX}${stripPrefix(draft.title.trim())}`
  return {
    case_title: title,
    basic_info: {
      // 合成病例，不写真实患者身份信息
      patient_name: '验收测试患者',
      sex: '男',
      age: 60,
      department: draft.department.trim(),
      admission_time: draft.admissionTime,
      discharge_time: draft.dischargeTime || undefined,
      main_diagnosis: draft.mainDiagnosis.trim() || undefined,
    },
    documents: draft.documents
      .filter((d) => d.content.trim())
      .map((d) => ({
        document_type: d.type,
        title: d.title.trim() || typeLabel(d.type),
        record_time: d.time || undefined,
        content: d.content.trim(),
        enabled: true,
      })),
    selected_rule_ids: [ruleId],
    manual_issue_text: `规则验收测试病例：${ruleId}`,
    evaluation_as_of_date: draft.evaluationDate,
    ...(copyFrom
      ? {
          source: {
            type: CASE_COPY_SOURCE_TYPE,
            source_record_id: copyFrom.itemId,
            source_item_ids: [copyFrom.itemId],
            created_from: 'rule_validation',
          },
        }
      : {}),
  }
}
