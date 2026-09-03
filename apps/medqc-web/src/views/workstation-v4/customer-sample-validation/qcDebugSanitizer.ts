const DATE_SHIFT_DAYS = 137

type AliasCategory = '机构' | '患者' | '就诊' | '病历' | '任务' | '文书' | '引用' | '标识'

export interface QcDebugSanitizationHints {
  patientName?: string
}

interface SanitizationState {
  aliases: Map<string, string>
  counters: Map<AliasCategory, number>
  patientNames: Set<string>
  clinicianNames: Set<string>
}

const IDENTIFIER_KEY_EXCLUSIONS = new Set([
  'criterion_id',
  'missing_rule_ids',
  'conflicting_rule_ids',
  'rule_id',
  'rule_ids',
  'rule_set_id',
])

function normalizedKey(value: string): string {
  return value.replace(/([a-z0-9])([A-Z])/gu, '$1_$2').toLowerCase()
}

function identifierCategory(key: string): AliasCategory | null {
  const normalized = normalizedKey(key)
  if (IDENTIFIER_KEY_EXCLUSIONS.has(normalized)) return null
  if (normalized === 'institute_id' || normalized === 'hospital_id') return '机构'
  if (normalized === 'patient_id') return '患者'
  if (normalized === 'visit_id' || normalized === 'inpat_no' || normalized === 'mr_no') {
    return '就诊'
  }
  if (normalized === 'record_id') return '病历'
  if (normalized === 'job_id' || normalized === 'root_job_id') return '任务'
  if (normalized === 'source_ref' || normalized === 'record_ref') return '引用'
  if (normalized.includes('document_id') || normalized.includes('document_ids')) return '文书'
  if (normalized.endsWith('_id') || normalized.endsWith('_ids')) return '标识'
  return null
}

function aliasFor(state: SanitizationState, category: AliasCategory, value: string): string {
  const normalized = value.trim()
  if (!normalized) return ''
  const existing = state.aliases.get(normalized)
  if (existing) return existing
  const next = (state.counters.get(category) || 0) + 1
  state.counters.set(category, next)
  const alias = `${category}-${String(next).padStart(3, '0')}`
  state.aliases.set(normalized, alias)
  return alias
}

function collectNames(state: SanitizationState, value: string) {
  const patientPatterns = [
    /患者(?:姓名)?[:：]?\s*([\p{Script=Han}·]{2,4})(?=[，,；;\s]*(?:性别[:：]?\s*)?[男女])/gu,
    /姓名[:：]\s*([\p{Script=Han}·]{2,4})(?=[，,；;\s]*(?:性别[:：]?\s*)?[男女])/gu,
  ]
  patientPatterns.forEach((pattern) => {
    for (const match of value.matchAll(pattern)) state.patientNames.add(match[1])
  })

  const clinicianPatterns = [
    /(?:医师|医生|护士)(?:签名)?[:：]\s*([\p{Script=Han}·]{2,4})/gu,
    /(?:今日|随|由|请|经|邀请)\s*([\p{Script=Han}·]{2,4})(?=主任医师|副主任医师|主治医师|住院医师|医师|医生|护士)/gu,
    /(?:^|[，,。；;\s])([\p{Script=Han}·]{2,4})(?=医师会诊)/gu,
  ]
  clinicianPatterns.forEach((pattern) => {
    for (const match of value.matchAll(pattern)) state.clinicianNames.add(match[1])
  })
}

function collectSensitiveValues(state: SanitizationState, value: unknown, key = '') {
  if (typeof value === 'string') {
    collectNames(state, value)
    const category = identifierCategory(key)
    if (category) aliasFor(state, category, value)
    return
  }
  if (Array.isArray(value)) {
    const category = identifierCategory(key)
    value.forEach((item) => {
      if (category && typeof item === 'string') aliasFor(state, category, item)
      collectSensitiveValues(state, item, key)
    })
    return
  }
  if (!value || typeof value !== 'object') return
  Object.entries(value as Record<string, unknown>).forEach(([childKey, childValue]) => {
    collectSensitiveValues(state, childValue, childKey)
  })
}

function shiftedDate(
  yearText: string,
  monthText: string,
  dayText: string,
  chinese: boolean,
): string {
  const date = new Date(Date.UTC(Number(yearText), Number(monthText) - 1, Number(dayText)))
  if (Number.isNaN(date.getTime())) {
    return chinese
      ? `${yearText}年${monthText}月${dayText}日`
      : `${yearText}-${monthText}-${dayText}`
  }
  date.setUTCDate(date.getUTCDate() + DATE_SHIFT_DAYS)
  const year = String(date.getUTCFullYear()).padStart(4, '0')
  const month = String(date.getUTCMonth() + 1).padStart(2, '0')
  const day = String(date.getUTCDate()).padStart(2, '0')
  return chinese ? `${year}年${month}月${day}日` : `${year}-${month}-${day}`
}

function replaceKnownValues(value: string, replacements: Map<string, string>): string {
  return Array.from(replacements.entries())
    .filter(([source]) => source.length >= 4)
    .sort(([left], [right]) => right.length - left.length)
    .reduce((result, [source, target]) => result.split(source).join(target), value)
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/gu, '\\$&')
}

function sanitizeText(state: SanitizationState, value: string): string {
  let result = replaceKnownValues(value, state.aliases)
  state.patientNames.forEach((name) => {
    result = result.replace(
      new RegExp(`患者(?:姓名)?[:：]?\\s*${escapeRegExp(name)}`, 'gu'),
      '患者A',
    )
    result = result.split(name).join('患者A')
  })
  let clinicianIndex = 0
  state.clinicianNames.forEach((name) => {
    clinicianIndex += 1
    result = result.split(name).join(`医务人员${String.fromCharCode(64 + clinicianIndex)}`)
  })
  result = result
    .replace(/(?<!\d)\d{17}[\dXx](?!\d)/gu, '[身份证号已脱敏]')
    .replace(/(?<!\d)1[3-9]\d{9}(?!\d)/gu, '[电话号码已脱敏]')
    .replace(/[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}/gu, '[邮箱已脱敏]')
    .replace(
      /((?:住址|现住址|户籍地址|联系地址|地址)[:：])\s*[^，,；;\n]{4,80}/gu,
      '$1[地址已脱敏]',
    )
    .replace(/[A-Za-z]:\\[^\s"'，。；;]+/gu, '[本地路径已脱敏]')
    .replace(/(?:postgres(?:ql)?|mysql):\/\/[^\s"')]+/giu, '[数据库连接已脱敏]')
    .replace(
      /https?:\/\/(?:localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+)[^\s"')}]*/giu,
      '[内网地址已脱敏]',
    )
    .replace(/(\d{4})-(\d{2})-(\d{2})/gu, (_, year, month, day) =>
      shiftedDate(year, month, day, false),
    )
    .replace(/(\d{4})年(\d{1,2})月(\d{1,2})日/gu, (_, year, month, day) =>
      shiftedDate(year, month, day, true),
    )
  return result
}

function sanitizeValue(state: SanitizationState, value: unknown, key = ''): unknown {
  const category = identifierCategory(key)
  if (typeof value === 'string') {
    return category ? aliasFor(state, category, value) : sanitizeText(state, value)
  }
  if (Array.isArray(value)) {
    return value.map((item) =>
      category && typeof item === 'string'
        ? aliasFor(state, category, item)
        : sanitizeValue(state, item, key),
    )
  }
  if (!value || typeof value !== 'object') return value
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>).map(([childKey, childValue]) => [
      childKey,
      sanitizeValue(state, childValue, childKey),
    ]),
  )
}

export function sanitizeQcDebugPayload<T>(value: T, hints: QcDebugSanitizationHints = {}): T {
  const state: SanitizationState = {
    aliases: new Map(),
    counters: new Map(),
    patientNames: new Set(),
    clinicianNames: new Set(),
  }
  if (hints.patientName?.trim()) state.patientNames.add(hints.patientName.trim())
  collectSensitiveValues(state, value)
  return sanitizeValue(state, value) as T
}
