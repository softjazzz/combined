// 质控点与文书大类映射表（可持续扩充）
// 文书大类代码：
// - admission_record 入院记录
// - progress_note 病程记录
// - discharge_record 出院记录
// - operation_record 手术相关记录
// - examination_report 辅助检查
// - consent_form 知情同意书

export type DocumentCategoryCode =
  | 'admission_record'
  | 'progress_note'
  | 'discharge_record'
  | 'operation_record'
  | 'examination_report'
  | 'consent_form'

export type RuleKey = string

interface RuleDocumentLike {
  document_categories?: unknown
  applicable_documents?: unknown
  check_logic?: unknown
  checkLogic?: unknown
  ruleCode?: string
  rule_code?: string
  code?: string
  name?: string
  rule_name?: string
  description?: string
  target_documents?: unknown
  [key: string]: unknown
}

function toRuleDocumentLike(rule: unknown): RuleDocumentLike {
  if (rule && typeof rule === 'object') {
    return rule as RuleDocumentLike
  }
  return {}
}

// 基于“规则名称”或“规则编码”的静态映射
// 备注：优先级低于后端提供的 applicable_documents 字段
export const RULE_TO_CATEGORIES: Record<RuleKey, DocumentCategoryCode[]> = {
  // 样例（来自当前演示环境规则名称）
  现病史完整性检查: ['admission_record'],
  抢救记录详细性检查: ['progress_note'],
  出院记录诊疗经过完整性: ['discharge_record'],
  手术时间记录准确性: ['operation_record'],
  出入量记录一致性: ['operation_record'],
  植入物信息完整性: ['operation_record'],
}

function normalizeCategory(input: unknown): DocumentCategoryCode | undefined {
  if (input && typeof input === 'object') {
    const obj = input as Record<string, unknown>
    const possible = (obj.value ??
      obj.code ??
      obj.category_code ??
      obj.category ??
      obj.label ??
      obj.name) as string | undefined
    if (possible) return normalizeCategory(possible)
  }

  const s = String(input || '').trim()
  if (!s) return undefined
  if (
    s === 'admission_record' ||
    s === 'progress_note' ||
    s === 'discharge_record' ||
    s === 'operation_record' ||
    s === 'examination_report' ||
    s === 'consent_form'
  ) {
    return s as DocumentCategoryCode
  }
  // 支持中文到标准代码的映射
  const zh2code: Record<string, DocumentCategoryCode> = {
    入院记录: 'admission_record',
    入院: 'admission_record',
    病程记录: 'progress_note',
    病程: 'progress_note',
    会诊记录: 'progress_note',
    护理记录: 'progress_note',
    护理文书: 'progress_note',
    护理: 'progress_note',
    医嘱: 'progress_note',
    医嘱记录: 'progress_note',
    输血记录: 'progress_note',
    输血: 'progress_note',
    治疗记录: 'progress_note',
    查房记录: 'progress_note',
    上级医师查房记录: 'progress_note',
    会诊: 'progress_note',
    出院记录: 'discharge_record',
    手术记录: 'operation_record',
    手术相关记录: 'operation_record',
    手术: 'operation_record',
    麻醉记录: 'operation_record',
    辅助检查: 'examination_report',
    检查记录: 'examination_report',
    检验检查: 'examination_report',
    检查: 'examination_report',
    检验: 'examination_report',
    影像: 'examination_report',
    知情同意书: 'consent_form',
    同意书: 'consent_form',
  }
  return zh2code[s]
}

function toCategoryCandidates(inputs: unknown): string[] {
  if (!inputs && inputs !== 0) return []
  if (Array.isArray(inputs)) return inputs
  if (inputs instanceof Set) return Array.from(inputs)
  if (typeof inputs === 'string') {
    const raw = inputs.trim()
    if (!raw) return []
    if ((raw.startsWith('[') && raw.endsWith(']')) || (raw.startsWith('{') && raw.endsWith('}'))) {
      try {
        const parsed = JSON.parse(raw)
        if (Array.isArray(parsed)) return parsed
      } catch {
        // ignore JSON parse errors and fall through to delimiter split
      }
    }
    return raw
      .split(/[\s,;；、/]+/)
      .map((item) => item.trim())
      .filter(Boolean)
  }
  if (typeof inputs === 'object') {
    // 支持Supabase返回的 {value: 'xx'} 或 {applicable_documents: [...]} 等结构
    if ('applicable_documents' in inputs) {
      return toCategoryCandidates((inputs as any).applicable_documents)
    }
    if ('document_categories' in inputs) {
      return toCategoryCandidates((inputs as any).document_categories)
    }
  }
  return []
}

export function normalizeCategories(inputs: unknown): DocumentCategoryCode[] {
  const arr = toCategoryCandidates(inputs)
  const result = new Set<DocumentCategoryCode>()
  for (const v of arr) {
    const n = normalizeCategory(v)
    if (n) result.add(n)
  }
  return Array.from(result)
}

function uniq<T>(arr: T[]): T[] {
  return Array.from(new Set(arr))
}

function includesAny(s: string, keywords: string[]): boolean {
  return keywords.some((k) => s.includes(k))
}

function inferCategoriesFromText(text?: string): DocumentCategoryCode[] {
  const s = String(text || '').trim()
  if (!s) return []

  // 优先级：consent_form > operation_record > discharge > admission > examination_report > progress_note
  const result: DocumentCategoryCode[] = []

  if (includesAny(s, ['同意书', '知情同意'])) result.push('consent_form')

  if (
    includesAny(s, ['手术', '术前', '术后', '术中', '麻醉', '植入物', '术前讨论', '四级手术']) &&
    !result.includes('operation_record')
  ) {
    result.push('operation_record')
  }

  if (includesAny(s, ['出院'])) result.push('discharge_record')

  if (includesAny(s, ['入院', '主诉', '现病史', '既往史', '体格'])) result.push('admission_record')

  if (includesAny(s, ['检查', '检验', '影像', '放射', 'CT', 'MRI', '超声', '报告']))
    result.push('examination_report')

  if (
    includesAny(s, [
      '病程',
      '会诊',
      '抢救',
      '查房',
      '死亡记录',
      '讨论',
      '随访',
      '转科',
      '输血',
      '输血记录',
      '医嘱',
      '医嘱记录',
    ]) &&
    !result.includes('operation_record')
  ) {
    result.push('progress_note')
  }

  return uniq(result)
}

export function lookupRuleCategories(rule: unknown): DocumentCategoryCode[] {
  const ruleObj = toRuleDocumentLike(rule)

  // 0) 首先尝试已归一化的 document_categories（用于服务端直接下发标准代码）
  const embeddedCategories = normalizeCategories(ruleObj.document_categories)
  if (embeddedCategories.length > 0) return embeddedCategories

  // 1) 优先使用后端字段 applicable_documents（若已提供）
  const fromBackend = normalizeCategories(ruleObj.applicable_documents)
  if (fromBackend.length > 0) return fromBackend

  // 1.5) 兼容 check_logic 内嵌的 applicable_documents/document_categories
  const checkLogic = toRuleDocumentLike(ruleObj.check_logic ?? ruleObj.checkLogic)
  const fromCheckLogic = normalizeCategories(
    checkLogic.applicable_documents ??
      checkLogic.document_categories ??
      checkLogic.target_documents,
  )
  if (fromCheckLogic.length > 0) return fromCheckLogic

  // 2) 其次尝试使用规则编码映射
  const codeKey: RuleKey | undefined = ruleObj.ruleCode || ruleObj.rule_code || ruleObj.code
  if (codeKey && RULE_TO_CATEGORIES[codeKey]) return RULE_TO_CATEGORIES[codeKey]

  // 3) 使用规则名称映射
  const nameKey: RuleKey | undefined = ruleObj.name || ruleObj.rule_name
  if (nameKey && RULE_TO_CATEGORIES[nameKey]) return RULE_TO_CATEGORIES[nameKey]

  // 4) 基于名称/描述的启发式关键词推断（兜底）
  const infer = uniq([
    ...inferCategoriesFromText(nameKey),
    ...inferCategoriesFromText(ruleObj.description),
  ])
  if (infer.length > 0) return infer

  return []
}
