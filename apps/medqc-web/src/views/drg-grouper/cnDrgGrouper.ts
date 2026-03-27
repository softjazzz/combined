/**
 * CN-DRG 2023 绩效监测版 分组器包装
 * 与 drgGrouper.ts 接口完全相同，底层使用 cnDrg2023Grouper.js 引擎
 */
import { CN_DRG_INFO } from './cnDrg2023Data'
import type { GrouperInput, GrouperResult } from './drgGrouper'
import { getMdcName } from './drgGrouper'

export { getMdcName }
export type { GrouperInput, GrouperResult }

type CnDrgEngine = typeof import('./cnDrg2023Grouper')
let cnDrgEnginePromise: Promise<CnDrgEngine> | null = null

async function loadCnDrgEngine() {
  if (!cnDrgEnginePromise) {
    cnDrgEnginePromise = import('./cnDrg2023Grouper')
  }
  return cnDrgEnginePromise
}

interface OpenDrgResult {
  status?: string
  mdc?: string
  adrg?: string
  drg?: string
  messages?: string[]
}

/** CN-DRG 分组 */
export async function performGrouping(input: GrouperInput): Promise<GrouperResult> {
  const zdList = normalizeCodeList(input.zdList)
  const ssList = normalizeCodeList(input.ssList)
  if (zdList.length === 0) {
    return { status: '未入组', messages: ['主诊断编码不能为空'], qcMessages: [] }
  }

  try {
    const engine = await loadCnDrgEngine()
    const cce = getPrimaryCce(engine, zdList)
    const { mccList, ccList } = collectComplications(engine, zdList, cce)
    const ssValidList = collectValidProcedures(engine, ssList)

    const raw = engine.group_record({
      Index: 'WEB',
      gender: input.gender,
      age: Number.isFinite(input.age) ? Number(input.age) : 0,
      ageDay: Number.isFinite(input.ageDay) ? Number(input.ageDay) : 0,
      weight: Number.isFinite(input.weight) ? Number(input.weight) : 0,
      dept: input.dept ?? '',
      inHospitalTime: Number.isFinite(input.days) ? Number(input.days) : 0,
      leavingType: input.leavingType ?? '1',
      zdList,
      ssList,
      remark: '',
      icu: input.icu ?? '',
      cce,
      mccList,
      ccList,
      ssValidList,
    }) as OpenDrgResult

    // 注入预处理信息
    const preMessages: string[] = []
    if (cce) {
      preMessages.push(`主诊断${zdList[0]}排除表${cce}`)
    }
    if (ssValidList.length > 0) {
      preMessages.push(`以下手术操作有效：${ssValidList.join(' ')}`)
    } else if (ssList.length > 0) {
      preMessages.push(`未找到有效手术操作`)
    }
    if (mccList.length > 0) {
      preMessages.push(`严重合并症(MCC)：${mccList.join(' ')}`)
    }
    if (ccList.length > 0) {
      preMessages.push(`合并症/并发症(CC)：${ccList.join(' ')}`)
    }
    if (mccList.length === 0 && ccList.length === 0 && zdList.length > 1) {
      preMessages.push(`未检出 MCC/CC 合并症或并发症`)
    }

    const engineMessages = normalizeMessages(raw)
    const messages = [...preMessages, ...engineMessages]
    const qcMessages: string[] = []
    if (raw.status === '歧义病案') {
      qcMessages.push('该病例被标记为歧义病案，请人工复核。')
    }

    const mdc = normalizeMdc(raw.mdc)
    const adrg = normalizeAdrg(raw.adrg)
    const drg = normalizeDrg(raw.drg)
    const success = raw.status === '分组成功' && !!drg

    if (!messages.length) {
      messages.push(success ? '分组成功' : raw.status || '无法入组')
    }

    // 从 CN_DRG_INFO 数据表直接查表获取 DRG 名称和 RW
    let drgName: string | undefined
    let rw: number | undefined
    if (drg && CN_DRG_INFO[drg]) {
      drgName = CN_DRG_INFO[drg].name
      rw = CN_DRG_INFO[drg].rw
      // 将 DRG 名称和 RW 追加到 messages 末尾（与 OpenDRG 网站展示一致）
      messages.push(`${drg}${drgName} ${rw}`)
    }

    return {
      status: success ? '分组成功' : '未入组',
      mdc,
      adrg,
      drg,
      drgName,
      rw,
      messages,
      qcMessages,
    }
  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error)
    return {
      status: '未入组',
      messages: [`分组引擎执行失败: ${msg}`],
      qcMessages: [],
    }
  }
}

function normalizeCodeList(list: string[] | undefined): string[] {
  return (list ?? []).map((item) => item.trim()).filter(Boolean)
}
function hasOwn(dict: unknown, key: string): boolean {
  return !!dict && Object.prototype.hasOwnProperty.call(dict, key)
}
function getPrimaryCce(engine: CnDrgEngine, zdList: string[]): string {
  const primary = zdList[0]
  if (!primary || !hasOwn(engine.CCE, primary)) return ''
  return String((engine.CCE as Record<string, string>)[primary] ?? '')
}
function collectComplications(engine: CnDrgEngine, zdList: string[], cce: string) {
  const mccList: string[] = []
  const ccList: string[] = []
  for (const zd of zdList) {
    if (
      hasOwn(engine.MCC, zd) &&
      (cce.length === 0 || String((engine.MCC as Record<string, string>)[zd]) !== cce)
    ) {
      mccList.push(zd)
      continue
    }
    if (
      hasOwn(engine.CC, zd) &&
      (cce.length === 0 || String((engine.CC as Record<string, string>)[zd]) !== cce)
    ) {
      ccList.push(zd)
    }
  }
  return { mccList, ccList }
}
function collectValidProcedures(engine: CnDrgEngine, ssList: string[]): string[] {
  if (!Array.isArray(engine.SS_VALID)) return []
  return ssList.filter((ss) => (engine.SS_VALID as string[]).includes(ss))
}
function normalizeMessages(raw: OpenDrgResult): string[] {
  if (!Array.isArray(raw.messages)) return []
  return raw.messages.map((m) => String(m)).filter(Boolean)
}
function normalizeMdc(mdc: string | undefined): string | undefined {
  if (!mdc) return undefined
  const match = /^MDC([A-Z])$/.exec(mdc)
  if (match) return match[1]
  if (/^[A-Z]$/.test(mdc)) return mdc
  return undefined
}
function normalizeAdrg(adrg: string | undefined): string | undefined {
  if (!adrg || adrg === '00' || adrg === 'QY') return undefined
  return adrg
}
function normalizeDrg(drg: string | undefined): string | undefined {
  if (!drg || drg === '0000') return undefined
  return drg
}

/** 方案信息 */
export function getSchemeInfo() {
  return { key: 'cn_drg_2023', label: 'CN-DRG 2023 绩效监测版' }
}
