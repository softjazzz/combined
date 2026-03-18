import { CC, CCE, MCC, SS_VALID, group_record } from './sichuan2024Grouper'

export interface GrouperInput {
  gender: string
  age: number
  zdList: string[]
  ssList: string[]
  days?: number
  leavingType?: string
  ageDay?: number
  weight?: number
  dept?: string
  icu?: string
}

export interface GrouperResult {
  status: '分组成功' | '未入组'
  mdc?: string
  adrg?: string
  drg?: string
  /** DRG 名称（从引擎 messages 中解析） */
  drgName?: string
  /** ADRG 名称（从 MDC/ADRG 匹配规则中解析） */
  adrgName?: string
  /** 权重值 RW（从引擎 messages 中解析） */
  rw?: number
  messages: string[]
  qcMessages: string[]
}

interface OpenDrgResult {
  status?: string
  mdc?: string
  adrg?: string
  drg?: string
  messages?: string[]
}

/** CHS-DRG 2.0 标准 MDC 名称（来源：四川省2025版DRG付费分组目录） */
const MDC_NAMES: Record<string, string> = {
  'A': '先期分组',
  'B': '神经系统疾病及功能障碍',
  'C': '眼疾病及功能障碍',
  'D': '头颈、耳、鼻、口、咽疾病及功能障碍',
  'E': '呼吸系统疾病及功能障碍',
  'F': '循环系统疾病及功能障碍',
  'G': '消化道疾病及功能障碍',
  'H': '肝、胆、胰疾病及功能障碍',
  'I': '骨骼、肌肉疾病及功能障碍',
  'J': '乳房、皮肤疾病及功能障碍',
  'K': '内分泌、营养、代谢疾病及功能障碍',
  'L': '泌尿系统疾病及功能障碍',
  'M': '男性生殖系统疾病及功能障碍',
  'N': '女性生殖系统疾病及功能障碍',
  'O': '妊娠、分娩及产褥期',
  'P': '新生儿疾病',
  'Q': '血液、免疫疾病及功能障碍',
  'R': '骨髓增生疾病及功能障碍，低分化肿瘤',
  'S': '感染及寄生虫病(全身性或不明确部位的)',
  'T': '精神疾病及功能障碍',
  'U': '酒精/药物使用及其引起的器质性精神功能障碍',
  'V': '创伤、中毒及药物毒性反应',
  'W': '烧伤',
  'X': '影响健康因素及其他就医情况',
  'Y': 'HIV感染疾病及相关操作',
  'Z': '多发严重创伤',
}

export function getMdcName(mdcLetter: string): string {
  return MDC_NAMES[mdcLetter] || `MDC${mdcLetter}`
}

export async function performGrouping(input: GrouperInput): Promise<GrouperResult> {
  const zdList = normalizeCodeList(input.zdList)
  const ssList = normalizeCodeList(input.ssList)
  if (zdList.length === 0) {
    return { status: '未入组', messages: ['主诊断编码不能为空'], qcMessages: [] }
  }

  try {
    const cce = getPrimaryCce(zdList)
    const { mccList, ccList } = collectComplications(zdList, cce)
    const ssValidList = collectValidProcedures(ssList)

    const raw = group_record({
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

    // 在引擎 messages 前面注入预处理详细信息（与 OpenDRG 原版一致）
    const preMessages: string[] = []
    // 1. 排除表
    if (cce) {
      preMessages.push(`主诊断${zdList[0]}排除表${cce}`)
    }
    // 2. 有效手术操作
    if (ssValidList.length > 0) {
      preMessages.push(`以下手术操作有效：${ssValidList.join(' ')}`)
    } else if (ssList.length > 0) {
      preMessages.push(`未找到有效手术操作`)
    }
    // 3. MCC/CC 信息
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

    // 从 messages 中解析 DRG 名称和 RW
    const { drgName, adrgName, rw } = parseDrgDetails(messages, drg, adrg)

    return {
      status: success ? '分组成功' : '未入组',
      mdc,
      adrg,
      drg,
      drgName,
      adrgName,
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
  return (list ?? []).map(item => item.trim()).filter(Boolean)
}

function hasOwn(dict: unknown, key: string): boolean {
  return !!dict && Object.prototype.hasOwnProperty.call(dict, key)
}

function getPrimaryCce(zdList: string[]): string {
  const primary = zdList[0]
  if (!primary || !hasOwn(CCE, primary)) return ''
  return String((CCE as Record<string, string>)[primary] ?? '')
}

function collectComplications(zdList: string[], cce: string): { mccList: string[]; ccList: string[] } {
  const mccList: string[] = []
  const ccList: string[] = []

  for (const zd of zdList) {
    if (hasOwn(MCC, zd) && (cce.length === 0 || String((MCC as Record<string, string>)[zd]) !== cce)) {
      mccList.push(zd)
      continue
    }
    if (hasOwn(CC, zd) && (cce.length === 0 || String((CC as Record<string, string>)[zd]) !== cce)) {
      ccList.push(zd)
    }
  }
  return { mccList, ccList }
}

function collectValidProcedures(ssList: string[]): string[] {
  if (!Array.isArray(SS_VALID)) return []
  return ssList.filter(ss => (SS_VALID as string[]).includes(ss))
}

function normalizeMessages(raw: OpenDrgResult): string[] {
  if (!Array.isArray(raw.messages)) {
    return []
  }
  return raw.messages.map(m => String(m)).filter(Boolean)
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

/** 获取可用的分组方案列表 */
export function getAvailableSchemes() {
  try {
    // Touch once to fail fast if extracted module is broken.
    void group_record
  } catch {
    // Keep API stable even if extraction failed.
  }
  return [
    { key: 'sichuan_2024', label: 'CHS-DRG 2.0（四川）', drgs: 794, adrgs: 252 },
  ]
}

/**
 * 从引擎 messages 中解析 DRG 名称和 RW 权重
 *
 * 引擎 messages 格式示例：
 *   - "主诊断K80.501排除表113"
 *   - "以下手术操作有效：51.8803 51.8701 51.2300"
 *   - "符合MDCH入组条件，匹配规则：主诊断匹配"
 *   - "符合HC1入组条件，匹配规则：主手术匹配"
 *   - "HC15胆总管手术，不伴严重合并症或并发症 2.19"
 */
function parseDrgDetails(
  messages: string[],
  drg?: string,
  adrg?: string,
): { drgName?: string; adrgName?: string; rw?: number } {
  let drgName: string | undefined
  let adrgName: string | undefined
  let rw: number | undefined

  for (const msg of messages) {
    // 最后一条通常是 "HC15胆总管手术，不伴严重合并症或并发症 2.19"
    // 尝试匹配: DRG编码 + 名称 + RW
    if (drg && msg.startsWith(drg)) {
      const rest = msg.slice(drg.length)
      // rest = "胆总管手术，不伴严重合并症或并发症 2.19"
      const rwMatch = rest.match(/\s+([\d.]+)\s*$/)
      if (rwMatch) {
        rw = parseFloat(rwMatch[1])
        drgName = rest.slice(0, rwMatch.index).trim()
      } else {
        drgName = rest.trim()
      }
    }

    // 匹配 ADRG 名称: "符合HC1入组条件，匹配规则：主手术匹配"
    if (adrg && msg.includes(`${adrg}入组条件`)) {
      // 不需要提取名称，ADRG 名称在 DRG 结果中已有
    }
  }

  // 如果上面没解析到，尝试从最后一条 message 直接取
  if (!drgName && messages.length > 0) {
    const last = messages[messages.length - 1]
    // 尝试匹配 "XXXX名称 数字" 格式
    const fullMatch = last.match(/^([A-Z]{2}\d+)(.+?)\s+([\d.]+)\s*$/)
    if (fullMatch) {
      if (!drg || fullMatch[1] === drg) {
        drgName = fullMatch[2].trim()
        rw = parseFloat(fullMatch[3])
      }
    }
  }

  return { drgName, adrgName, rw }
}
