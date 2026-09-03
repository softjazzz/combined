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
  relatedPersonNames: Set<string>
}

const IDENTIFIER_KEY_EXCLUSIONS = new Set([
  'criterion_id',
  'missing_rule_ids',
  'conflicting_rule_ids',
  'rule_id',
  'rule_ids',
  'rule_set_id',
])

const MEDICAL_IDENTIFIER_KEYS = new Set([
  'accession_number',
  'barcode',
  'bed_no',
  'blood_bag_no',
  'blood_unit_no',
  'case_no',
  'exam_no',
  'id_card_no',
  'identity_no',
  'insurance_no',
  'medical_card_no',
  'order_no',
  'pathology_no',
  'qr_code',
  'report_no',
  'request_no',
  'sample_no',
  'specimen_no',
])

const SECRET_KEYS = new Set([
  'access_key',
  'access_token',
  'api_key',
  'apikey',
  'authorization',
  'client_secret',
  'cookie',
  'credentials',
  'database_password',
  'db_password',
  'jwt',
  'password',
  'passwd',
  'private_key',
  'refresh_token',
  'secret',
  'session_cookie',
  'session_id',
  'session_token',
  'token',
])

const ACCOUNT_KEYS = new Set([
  'account',
  'account_name',
  'database_user',
  'db_user',
  'login_name',
  'user_name',
  'username',
])

const NETWORK_LOCATION_KEYS = new Set([
  'base_url',
  'database_host',
  'endpoint',
  'host',
  'hostname',
  'server_address',
])

const RAW_DOCUMENT_KEYS = new Set([
  'document_content',
  'full_text',
  'medical_record_content',
  'original_content',
  'original_text',
  'raw_content',
  'raw_text',
  'record_content',
  'source_text',
])

const PATIENT_NAME_KEYS = new Set(['patient_name', 'patient_full_name'])
const CLINICIAN_NAME_KEYS = new Set([
  'anesthesiologist_name',
  'author_name',
  'doctor_name',
  'operator_name',
  'physician_name',
  'signer_name',
  'surgeon_name',
])
const RELATED_PERSON_NAME_KEYS = new Set([
  'contact_name',
  'family_name',
  'guardian_name',
  'relative_name',
])

const DIRECT_PERSONAL_DATA_KEYS = new Set([
  'address',
  'contact_address',
  'email',
  'home_address',
  'id_card',
  'identity_card',
  'mobile',
  'mobile_phone',
  'phone',
  'phone_number',
  'telephone',
])

function normalizedKey(value: string): string {
  return value.replace(/([a-z0-9])([A-Z])/gu, '$1_$2').toLowerCase()
}

function isSecretKey(key: string): boolean {
  return (
    SECRET_KEYS.has(key) ||
    [
      '_api_key',
      '_access_token',
      '_refresh_token',
      '_password',
      '_secret',
      '_private_key',
      '_cookie',
    ].some((suffix) => key.endsWith(suffix))
  )
}

function isAccountKey(key: string): boolean {
  return ACCOUNT_KEYS.has(key) || key.endsWith('_username') || key.endsWith('_user')
}

function isNetworkLocationKey(key: string): boolean {
  return (
    NETWORK_LOCATION_KEYS.has(key) ||
    ['_url', '_uri', '_endpoint', '_host', '_hostname', '_server_address'].some((suffix) =>
      key.endsWith(suffix),
    )
  )
}

function isRawDocumentKey(key: string): boolean {
  return (
    RAW_DOCUMENT_KEYS.has(key) ||
    [
      '_record_content',
      '_document_content',
      '_raw_content',
      '_raw_text',
      '_full_text',
      '_source_text',
    ].some((suffix) => key.endsWith(suffix))
  )
}

function identifierCategory(key: string): AliasCategory | null {
  const normalized = normalizedKey(key)
  if (IDENTIFIER_KEY_EXCLUSIONS.has(normalized)) return null
  if (MEDICAL_IDENTIFIER_KEYS.has(normalized)) return '标识'
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

  const relatedPersonPattern =
    /(?:联系人|紧急联系人|监护人|家属姓名|陪护人)[:：]\s*([\p{Script=Han}·]{2,4})/gu
  for (const match of value.matchAll(relatedPersonPattern)) {
    state.relatedPersonNames.add(match[1])
  }
}

function collectNameFromKey(state: SanitizationState, key: string, value: string) {
  const normalized = normalizedKey(key)
  if (PATIENT_NAME_KEYS.has(normalized)) state.patientNames.add(value.trim())
  if (CLINICIAN_NAME_KEYS.has(normalized)) state.clinicianNames.add(value.trim())
  if (RELATED_PERSON_NAME_KEYS.has(normalized)) state.relatedPersonNames.add(value.trim())
}

function collectSensitiveValues(state: SanitizationState, value: unknown, key = '') {
  if (typeof value === 'string') {
    collectNames(state, value)
    collectNameFromKey(state, key, value)
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
  state.relatedPersonNames.forEach((name) => {
    result = result.split(name).join('[关联人员已脱敏]')
  })
  result = result
    .replace(
      /-----BEGIN(?: [A-Z]+)? PRIVATE KEY-----[\s\S]*?-----END(?: [A-Z]+)? PRIVATE KEY-----/gu,
      '[访问凭证已脱敏]',
    )
    .replace(/\b(?:Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{8,}/giu, '[访问凭证已脱敏]')
    .replace(/\beyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b/gu, '[访问凭证已脱敏]')
    .replace(
      /\b(?:sk-(?:proj-)?|gh[pousr]_|xox[baprs]-|AKIA|ASIA)[A-Za-z0-9_-]{12,}\b/gu,
      '[访问凭证已脱敏]',
    )
    .replace(
      /((?:api[_-]?key|access[_-]?token|refresh[_-]?token|authorization|password|passwd|client[_-]?secret|cookie|session[_-]?token|token)\s*[:=]\s*)(?:"[^"\n]*"|'[^'\n]*'|[^\s,;，；]+)/giu,
      '$1[访问凭证已脱敏]',
    )
    .replace(/(?<!\d)\d{17}[\dXx](?!\d)/gu, '[身份证号已脱敏]')
    .replace(/(?<!\d)1[3-9]\d{9}(?!\d)/gu, '[电话号码已脱敏]')
    .replace(/(?<!\d)0\d{2,3}-?\d{7,8}(?!\d)/gu, '[电话号码已脱敏]')
    .replace(/(?<!\d)\d{16,19}(?!\d)/gu, '[长数字标识已脱敏]')
    .replace(/[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}/gu, '[邮箱已脱敏]')
    .replace(
      /((?:住址|现住址|户籍地址|联系地址|地址)[:：])\s*[^，,；;\n]{4,80}/gu,
      '$1[地址已脱敏]',
    )
    .replace(/\\\\[^\s\\/]+\\[^\s"'，。；;]+/gu, '[本地路径已脱敏]')
    .replace(/[A-Za-z]:\\[^\s"'，。；;]+/gu, '[本地路径已脱敏]')
    .replace(
      /(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|mssql):\/\/[^\s"')]+/giu,
      '[数据库连接已脱敏]',
    )
    .replace(/(?:https?|wss?):\/\/[^\s"')}]*/giu, '[网络地址已脱敏]')
    .replace(/(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?::\d{1,5})?(?![\d.])/gu, '[网络地址已脱敏]')
    .replace(/(?<![\da-f])(?:[\da-f]{2}:){5}[\da-f]{2}(?![\da-f])/giu, '[设备地址已脱敏]')
    .replace(/(?<![\da-f:])(?:[\da-f]{1,4}:){3,7}[\da-f]{1,4}(?![\da-f:])/giu, '[网络地址已脱敏]')
    .replace(/(^|[\s"'=:：(])\/(?:[A-Za-z0-9._-]+\/)+[A-Za-z0-9._-]+/gu, '$1[本地路径已脱敏]')
    .replace(/(\d{4})-(\d{2})-(\d{2})/gu, (_, year, month, day) =>
      shiftedDate(year, month, day, false),
    )
    .replace(/(\d{4})年(\d{1,2})月(\d{1,2})日/gu, (_, year, month, day) =>
      shiftedDate(year, month, day, true),
    )
  return result
}

function sanitizeValue(state: SanitizationState, value: unknown, key = ''): unknown {
  const normalized = normalizedKey(key)
  if (typeof value === 'boolean' || value === null || value === undefined) return value
  if (isSecretKey(normalized)) return '[访问凭证已脱敏]'
  if (isAccountKey(normalized)) return '[账号已脱敏]'
  if (isNetworkLocationKey(normalized)) return '[网络地址已脱敏]'
  if (DIRECT_PERSONAL_DATA_KEYS.has(normalized)) return '[个人信息已脱敏]'
  if (normalized !== 'field_path' && normalized.endsWith('_path')) {
    return '[本地路径已脱敏]'
  }
  if (isRawDocumentKey(normalized)) return '[完整原始正文已省略]'
  const category = identifierCategory(key)
  if (category && (typeof value === 'number' || typeof value === 'bigint')) {
    return aliasFor(state, category, String(value))
  }
  if (typeof value === 'string') {
    return category ? aliasFor(state, category, value) : sanitizeText(state, value)
  }
  if (Array.isArray(value)) {
    return value.map((item) =>
      category && ['string', 'number', 'bigint'].includes(typeof item)
        ? aliasFor(state, category, String(item))
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
    relatedPersonNames: new Set(),
  }
  if (hints.patientName?.trim()) state.patientNames.add(hints.patientName.trim())
  collectSensitiveValues(state, value)
  return sanitizeValue(state, value) as T
}
