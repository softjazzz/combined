import type {
  ModernCaseQcDefect,
  ModernCaseQcSnapshot,
  ModernCaseQcSnapshotPage,
  ModernCaseQcSourceKey,
} from '@/api/modernCaseQcResult'

/**
 * 现代（三坐标 + 来源）质控只读读取的纯决策层。
 *
 * 职责边界：
 * - 解析当前选中病历（工作清单行优先，工作清单模式下失败关闭）；
 * - 判定是否允许发起现代只读读取，以及读取哪个来源；
 * - 生成包含来源的请求键、判定迟到响应、把失败映射为脱敏文案。
 *
 * 组件与状态由 `WorkstationV4View.vue` 持有；本模块不发请求、不持有状态，
 * 便于用反例覆盖同键阴影、来源切换和迟到响应。
 */

export type ModernCaseQcWorkflowType = 'frontpage' | 'coding' | 'settlement'
export type ModernCaseQcSettlementSource = 'settlement_qc' | 'settlement_generate_qc'

export interface ModernCaseQcStageRecord {
  id?: string
  recordKey?: string
  identityStatus?: 'ambiguous' | 'unverified'
  instituteId?: string
  patientId?: string
  visitId?: string
}

export interface ModernCaseQcWorklistRow {
  workflowType: ModernCaseQcWorkflowType
  identityStatus?: 'ambiguous' | 'unverified'
  instituteId?: string
  patientId?: string
  visitId?: string
}

export interface ModernCaseQcReadTarget {
  workflowType: ModernCaseQcWorkflowType
  sourceKey: ModernCaseQcSourceKey
  instituteId: string
  patientId: string
  visitId: string
}

/**
 * 工作流 → 现代来源的唯一映射。
 * 结算有两条互相独立的来源（settlement_qc / settlement_generate_qc），
 * 由调用方按用户显式切换传入，不做互相回退。
 */
export const MODERN_CASE_QC_SOURCE_BY_WORKFLOW: Record<
  ModernCaseQcWorkflowType,
  ModernCaseQcSourceKey
> = {
  frontpage: 'frontpage_formal_qc',
  coding: 'coding_qc',
  settlement: 'settlement_qc',
}

export const MODERN_SETTLEMENT_SOURCE_OPTIONS: Array<{
  label: string
  value: ModernCaseQcSettlementSource
}> = [
  { label: '结算质控', value: 'settlement_qc' },
  { label: '结算生成质控', value: 'settlement_generate_qc' },
]

function recordKeyOf(record: { id?: string; recordKey?: string } | null | undefined): string {
  return record?.recordKey || record?.id || ''
}

/** 与 api 客户端一致的身份规范：非空字符串，且不含非规范前后空格。 */
export function isUsableModernIdentityValue(value: unknown): value is string {
  return typeof value === 'string' && value !== '' && value === value.trim()
}

/** 仅当选中行存在且身份已核实（无 identityStatus）时才允许旧的写操作工作区。 */
export function allowsLegacyWriteWorkspace(
  record: { identityStatus?: 'ambiguous' | 'unverified' } | null | undefined,
): boolean {
  return Boolean(record) && !record?.identityStatus
}

function resolveFromRecords<T extends { id?: string; recordKey?: string }>(
  selectedKey: string | null,
  stageRecord: T | null,
  allRecords: readonly T[],
): T | null {
  if (!selectedKey) return null
  const fromList = allRecords.find((record) => recordKeyOf(record) === selectedKey)
  if (fromList) return fromList
  return stageRecord && recordKeyOf(stageRecord) === selectedKey ? stageRecord : null
}

/**
 * 解析当前选中的病历。
 *
 * 工作清单模式下失败关闭：只有严格匹配工作清单选中键的工作清单行才是权威行，
 * 绝不回退旧列表。否则同键阴影，或 `useNotifications.openSessionRecord` 只写 selectedId
 * 的路径，都会让旧列表记录抹掉 identityStatus，从而误放开旧 Assist/首页/结算写入口。
 * 非工作清单模式保留旧的按选中键解析。
 */
export function resolveSelectedRecord<T extends { id?: string; recordKey?: string }>(params: {
  isWorklistMode: boolean
  stageSelectedKey: string | null
  fallbackSelectedKey: string | null
  stageRecord: T | null
  allRecords: readonly T[]
}): T | null {
  const { isWorklistMode, stageSelectedKey, fallbackSelectedKey, stageRecord, allRecords } = params
  const stageRecordKey = recordKeyOf(stageRecord)
  if (isWorklistMode) {
    return stageSelectedKey && stageRecord && stageRecordKey === stageSelectedKey ? stageRecord : null
  }
  return resolveFromRecords(stageSelectedKey || fallbackSelectedKey, stageRecord, allRecords)
}

/**
 * 现代只读读取的触发条件。
 * 仅在「详情 + 工作清单」模式下、选中行严格匹配本行且工作流行身份唯一未核实时返回目标；
 * 普通旧列表、歧义行、坐标缺失或同键阴影一律不读取。
 */
export function resolveModernCaseQcReadTarget(params: {
  isDetailMode: boolean
  isWorklistMode: boolean
  stageSelectedKey: string | null
  stageRecord: ModernCaseQcStageRecord | null
  worklistRow: ModernCaseQcWorklistRow | null | undefined
  settlementSourceKey: ModernCaseQcSettlementSource
}): ModernCaseQcReadTarget | null {
  const { isDetailMode, isWorklistMode, stageSelectedKey, stageRecord, worklistRow } = params
  if (!isDetailMode || !isWorklistMode) return null
  if (!stageSelectedKey || !stageRecord) return null
  if (recordKeyOf(stageRecord) !== stageSelectedKey) return null
  // 只有「唯一但未核实」才读取；歧义行不可读取。
  if (stageRecord.identityStatus !== 'unverified') return null
  if (!worklistRow) return null
  // 工作流行与选中行必须同时为唯一未核实；歧义或缺失即视为不能读取。
  if (worklistRow.identityStatus !== 'unverified') return null
  const { instituteId, patientId, visitId } = worklistRow
  if (!isUsableModernIdentityValue(instituteId)) return null
  if (!isUsableModernIdentityValue(patientId)) return null
  if (!isUsableModernIdentityValue(visitId)) return null
  // 选中行与工作流行必须是同一病例；任一坐标不一致即视为同键阴影，不读取。
  if (stageRecord.instituteId !== instituteId) return null
  if (stageRecord.patientId !== patientId) return null
  if (stageRecord.visitId !== visitId) return null
  const sourceKey =
    worklistRow.workflowType === 'settlement'
      ? params.settlementSourceKey
      : MODERN_CASE_QC_SOURCE_BY_WORKFLOW[worklistRow.workflowType]
  if (!sourceKey) return null
  return { workflowType: worklistRow.workflowType, sourceKey, instituteId, patientId, visitId }
}

/** 请求键必须包含来源；用 JSON 编码避免坐标或来源中含分隔符时键碰撞。 */
export function buildModernCaseQcRequestKey(target: ModernCaseQcReadTarget | null): string {
  if (!target) return ''
  return JSON.stringify([target.instituteId, target.patientId, target.visitId, target.sourceKey])
}

/** 迟到响应判定：请求令牌或当前请求键任一变化都必须丢弃。 */
export function isModernCaseQcResponseStale(params: {
  token: number
  currentToken: number
  requestedKey: string
  currentKey: string
}): boolean {
  return params.token !== params.currentToken || params.requestedKey !== params.currentKey
}

/**
 * 失败语义 → 脱敏文案。
 * 传输层状态码在 `error.response.status`（AxiosError），也兼容已归一化的 `error.status`；
 * 界面文案不暴露状态码、连接串、患者三坐标或病例原文。
 */
export function resolveModernCaseQcErrorMessage(error: unknown): string {
  if (error instanceof Error && error.name === 'ModernCaseQcSnapshotError') {
    const code = (error as { code?: unknown }).code
    if (
      code === 'invalid_identity' ||
      code === 'unsupported_source_key' ||
      code === 'identity_unverified' ||
      code === 'identity_mismatch'
    ) {
      return '病例身份未核实，暂不可读取现代质控结果'
    }
    if (code === 'unexpected_status' || code === 'malformed_envelope') {
      return '质控结果暂时不可用'
    }
    return '质控结果读取失败'
  }
  const status =
    (error as { response?: { status?: unknown } } | null)?.response?.status ??
    (error as { status?: unknown } | null)?.status
  if (status === 404) return '未找到该病例的现代质控结果'
  if (status === 403) return '当前账号无权查看该质控结果'
  if (status === 409) return '病例身份不唯一，无法读取质控结果'
  if (status === 422) return '病例身份参数不合法'
  if (status === 502 || status === 503 || status === 504) return '质控结果暂时不可用'
  return '质控结果读取失败'
}

// ===== 缺陷分组分页（纯决策：不持有状态、不发请求） =====

/** 两组缺陷的分组键，与只读面板 `emit('load-more', group)` 的取值一致。 */
export type ModernCaseQcDefectGroup = 'active' | 'current'

export const MODERN_CASE_QC_DEFECT_GROUPS: readonly ModernCaseQcDefectGroup[] = [
  'active',
  'current',
]

/** 某组分页信封的判定结果；ok:false 代表合同不成立，调用方必须失败关闭。 */
export type ModernCaseQcDefectPageEnvelope =
  | { ok: true; hasMore: boolean; nextOffset: number | null }
  | { ok: false }

function defectGroupFieldPrefix(group: ModernCaseQcDefectGroup): string {
  return group === 'active' ? 'active_defects' : 'current_result_defects'
}

/**
 * 解析某组缺陷的分页信封。
 * 与 API 客户端同一口径：两个字段必填，has_more=false 必须严格配 next_offset=null，
 * has_more=true 必须配安全非负整数游标；其余情况（含缺字段）一律 ok:false，
 * 绝不把「没有元数据」当成「已加载完」。
 */
export function readModernCaseQcDefectPageEnvelope(
  snapshot: ModernCaseQcSnapshot,
  group: ModernCaseQcDefectGroup,
): ModernCaseQcDefectPageEnvelope {
  const envelope = snapshot as unknown as Record<string, unknown>
  const prefix = defectGroupFieldPrefix(group)
  const hasMore = envelope[`${prefix}_has_more`]
  const nextOffset = envelope[`${prefix}_next_offset`]
  if (typeof hasMore !== 'boolean') return { ok: false }
  if (!hasMore) {
    // 严格 null：undefined（缺字段）同样视为合同不成立，不允许绕过失败关闭。
    if (nextOffset !== null) return { ok: false }
    return { ok: true, hasMore: false, nextOffset: null }
  }
  if (typeof nextOffset !== 'number' || !Number.isSafeInteger(nextOffset) || nextOffset < 0) {
    return { ok: false }
  }
  return { ok: true, hasMore: true, nextOffset }
}

/** 两组信封任一不成立即视为响应不完整：界面按失败关闭处理，不落地截断快照。 */
export function hasModernCaseQcDefectPageEnvelopes(snapshot: ModernCaseQcSnapshot): boolean {
  return MODERN_CASE_QC_DEFECT_GROUPS.every(
    (group) => readModernCaseQcDefectPageEnvelope(snapshot, group).ok,
  )
}

/**
 * 分页请求只带目标组的 offset：另一组按默认第 1 页返回，
 * 不会被用来覆盖该组已加载的后续页。
 */
export function buildModernCaseQcDefectPageRequest(params: {
  group: ModernCaseQcDefectGroup
  offset: number
  limit: number
}): ModernCaseQcSnapshotPage {
  return params.group === 'active'
    ? { active_defects_offset: params.offset, defects_limit: params.limit }
    : { current_result_defects_offset: params.offset, defects_limit: params.limit }
}

/** 已落地快照的最新结果标识：结果变化时两组分页都不得再拼接旧页。 */
export function latestModernCaseQcResultIdOf(snapshot: ModernCaseQcSnapshot | null): string {
  const record = snapshot?.latest_qc_result
  if (!record) return ''
  const raw = record.id ?? record.result_id
  return typeof raw === 'string' ? raw.trim() : ''
}

/**
 * 迟到分页响应判定：请求令牌/请求键变化，或期间已有别的结果落地，都必须丢弃。
 * 结果变化时不能用该响应直接替换快照——它带的是旧 offset，会跳过新结果的第一页。
 */
export function isModernCaseQcDefectPageResponseStale(params: {
  token: number
  currentToken: number
  requestedKey: string
  currentKey: string
  requestedResultId: string
  loadedResultId: string
}): boolean {
  if (params.requestedResultId !== params.loadedResultId) return true
  return isModernCaseQcResponseStale(params)
}

function modernCaseQcDefectIdentityOf(defect: ModernCaseQcDefect): string {
  const raw = defect?.id
  return typeof raw === 'string' ? raw.trim() : ''
}

/**
 * 稳定去重拼接：保持已有顺序，后到的重复 id 丢弃。
 * 并发写入导致同一缺陷落到两页时不会重复渲染、不会撞 key；无 id 的条目无法判等，一律保留。
 */
export function mergeModernCaseQcDefectItems(
  existing: readonly ModernCaseQcDefect[],
  incoming: readonly ModernCaseQcDefect[],
): ModernCaseQcDefect[] {
  const seen = new Set<string>()
  const merged: ModernCaseQcDefect[] = []
  for (const defect of existing) {
    const id = modernCaseQcDefectIdentityOf(defect)
    if (id !== '') seen.add(id)
    merged.push(defect)
  }
  for (const defect of incoming) {
    const id = modernCaseQcDefectIdentityOf(defect)
    if (id !== '') {
      if (seen.has(id)) continue
      seen.add(id)
    }
    merged.push(defect)
  }
  return merged
}

/**
 * 拼接某组缺陷的下一页：只改写该组数组与该组信封，另一组已加载页保持原样。
 * 返回 null 表示该响应信封不成立，调用方按「加载更多失败」处理，不拼接也不宣称已加载完。
 */
export function mergeModernCaseQcDefectPage(params: {
  group: ModernCaseQcDefectGroup
  current: ModernCaseQcSnapshot
  incoming: ModernCaseQcSnapshot
}): ModernCaseQcSnapshot | null {
  const envelope = readModernCaseQcDefectPageEnvelope(params.incoming, params.group)
  if (!envelope.ok) return null
  if (params.group === 'active') {
    return {
      ...params.current,
      active_defects: mergeModernCaseQcDefectItems(
        params.current.active_defects,
        params.incoming.active_defects,
      ),
      active_defects_has_more: envelope.hasMore,
      active_defects_next_offset: envelope.nextOffset,
    }
  }
  return {
    ...params.current,
    current_result_defects: mergeModernCaseQcDefectItems(
      params.current.current_result_defects,
      params.incoming.current_result_defects,
    ),
    current_result_defects_has_more: envelope.hasMore,
    current_result_defects_next_offset: envelope.nextOffset,
  }
}
