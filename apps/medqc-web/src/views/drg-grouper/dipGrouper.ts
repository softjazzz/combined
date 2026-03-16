/**
 * 四川省 DIP 分组引擎
 * 基于四川省按病种分值（DIP）付费病种库
 *
 * DIP 分组逻辑：
 *   1. 主诊断 + 主手术 + 相关手术 → 精确匹配
 *   2. 主诊断 + 主手术 → 标准匹配
 *   3. 仅主诊断（无手术） → 内科保守治疗匹配
 *   4. 均不匹配 → 未入组
 */
import {
  ZD_ONLY_MAP,
  ZD_SS_MAP,
  ZD_SS_REL_MAP,
  VALID_ZD_CODES,
  ZD_NAMES,
} from './sichuanDipData'

/** DIP 分组输入 */
export interface DipGrouperInput {
  /** 诊断编码列表（第一个为主诊断） */
  zdList: string[]
  /** 手术操作编码列表（第一个为主手术） */
  ssList: string[]
  /** 性别 1=男, 2=女 */
  gender?: string
  /** 年龄 */
  age?: number
  /** 住院天数 */
  days?: number
}

/** DIP 分组结果 */
export interface DipGrouperResult {
  /** 分组状态 */
  status: '分组成功' | '未入组'
  /** DIP 编码 */
  dipCode?: string
  /** DIP 病种名称 */
  dipName?: string
  /** 主诊断编码 */
  primaryZd?: string
  /** 主诊断名称 */
  primaryZdName?: string
  /** 匹配的主手术编码 */
  matchedSs?: string
  /** 匹配的相关手术编码 */
  matchedRelSs?: string
  /** 匹配方式 */
  matchType?: '诊断+手术+相关手术' | '诊断+手术' | '纯诊断' | string
  /** 分组过程消息 */
  messages: string[]
}

/**
 * 执行 DIP 分组
 */
export function performDipGrouping(input: DipGrouperInput): DipGrouperResult {
  const zdList = normalizeCodeList(input.zdList)
  const ssList = normalizeCodeList(input.ssList)
  const messages: string[] = []

  // Step 0: 验证输入
  if (zdList.length === 0) {
    return { status: '未入组', messages: ['主诊断编码不能为空'] }
  }

  const primaryZd = zdList[0]
  const primaryZdName = ZD_NAMES[primaryZd] || '未知诊断'

  // 验证主诊断是否在病种库中
  if (!VALID_ZD_CODES.has(primaryZd)) {
    messages.push(`主诊断 ${primaryZd} 不在四川DIP病种库中`)
    // 尝试模糊匹配（取前5位/前3位）
    const fuzzyCode = tryFuzzyZdMatch(primaryZd)
    if (fuzzyCode) {
      messages.push(`尝试模糊匹配: ${primaryZd} → ${fuzzyCode}`)
      return performGroupingWithZd(fuzzyCode, ssList, messages, primaryZd)
    }
    return { status: '未入组', primaryZd, primaryZdName, messages }
  }

  return performGroupingWithZd(primaryZd, ssList, messages)
}

/**
 * 使用确定的主诊断执行分组
 */
function performGroupingWithZd(
  primaryZd: string,
  ssList: string[],
  messages: string[],
  originalZd?: string,
): DipGrouperResult {
  const primaryZdName = ZD_NAMES[primaryZd] || '未知诊断'
  const mainSs = ssList.length > 0 ? ssList[0] : null

  // Step 1: 如果有手术 → 尝试 诊断+手术+相关手术 匹配
  if (mainSs && ssList.length > 1) {
    // 检查所有其他手术编码是否能作为"相关手术"
    for (let i = 1; i < ssList.length; i++) {
      const relSs = ssList[i]
      // 尝试不同的相关手术组合
      const key3 = `${primaryZd}|${mainSs}|${relSs}`
      if (ZD_SS_REL_MAP[key3]) {
        const dipCode = `${primaryZd}+${mainSs}`
        messages.push(`精确匹配: ${primaryZd} + ${mainSs} + 相关手术 ${relSs}`)
        return {
          status: '分组成功',
          dipCode,
          dipName: ZD_SS_REL_MAP[key3],
          primaryZd: originalZd || primaryZd,
          primaryZdName,
          matchedSs: mainSs,
          matchedRelSs: relSs,
          matchType: '诊断+手术+相关手术',
          messages,
        }
      }
    }

    // 尝试多个相关手术的组合 (用+连接)
    for (let i = 1; i < ssList.length; i++) {
      for (let j = i + 1; j <= ssList.length; j++) {
        const relSsCombined = ssList.slice(i, j).join('+')
        const key3 = `${primaryZd}|${mainSs}|${relSsCombined}`
        if (ZD_SS_REL_MAP[key3]) {
          const dipCode = `${primaryZd}+${mainSs}`
          messages.push(`精确匹配: ${primaryZd} + ${mainSs} + 相关手术 ${relSsCombined}`)
          return {
            status: '分组成功',
            dipCode,
            dipName: ZD_SS_REL_MAP[key3],
            primaryZd: originalZd || primaryZd,
            primaryZdName,
            matchedSs: mainSs,
            matchedRelSs: relSsCombined,
            matchType: '诊断+手术+相关手术',
            messages,
          }
        }
      }
    }
  }

  // Step 2: 诊断+主手术 匹配
  if (mainSs) {
    const key2 = `${primaryZd}|${mainSs}`
    if (ZD_SS_MAP[key2]) {
      const dipCode = `${primaryZd}+${mainSs}`
      messages.push(`标准匹配: ${primaryZd} + ${mainSs}`)
      return {
        status: '分组成功',
        dipCode,
        dipName: ZD_SS_MAP[key2],
        primaryZd: originalZd || primaryZd,
        primaryZdName,
        matchedSs: mainSs,
        matchType: '诊断+手术',
        messages,
      }
    }

    // 尝试用其他手术操作匹配
    for (let i = 1; i < ssList.length; i++) {
      const altSs = ssList[i]
      const altKey = `${primaryZd}|${altSs}`
      if (ZD_SS_MAP[altKey]) {
        const dipCode = `${primaryZd}+${altSs}`
        messages.push(`备选手术匹配: ${primaryZd} + ${altSs}（原主手术 ${mainSs} 未匹配）`)
        return {
          status: '分组成功',
          dipCode,
          dipName: ZD_SS_MAP[altKey],
          primaryZd: originalZd || primaryZd,
          primaryZdName,
          matchedSs: altSs,
          matchType: '诊断+手术',
          messages,
        }
      }
    }

    messages.push(`诊断+手术组合未匹配: ${primaryZd} + ${mainSs}`)
  }

  // Step 3: 纯诊断匹配
  if (ZD_ONLY_MAP[primaryZd]) {
    const dipCode = primaryZd
    if (mainSs) {
      messages.push(`手术操作未匹配，回退到纯诊断分组: ${primaryZd}`)
    } else {
      messages.push(`纯诊断分组: ${primaryZd}`)
    }
    return {
      status: '分组成功',
      dipCode,
      dipName: ZD_ONLY_MAP[primaryZd],
      primaryZd: originalZd || primaryZd,
      primaryZdName,
      matchType: '纯诊断',
      messages,
    }
  }

  // Step 4: 未入组
  messages.push(`主诊断 ${primaryZd}（${primaryZdName}）在病种库中存在但无法匹配当前编码组合`)
  return {
    status: '未入组',
    primaryZd: originalZd || primaryZd,
    primaryZdName,
    messages,
  }
}

/**
 * 模糊匹配诊断编码 — 尝试截断编码进行匹配
 */
function tryFuzzyZdMatch(code: string): string | null {
  // 尝试去掉 x 后缀的精确匹配，如 A01.000x001 → A01.0
  // ICD-10 编码格式：X00.0, X00.00, X00.000, X00.000x000
  const parts = code.split('.')
  if (parts.length < 2) return null

  const prefix = parts[0]
  const suffix = parts[1]

  // 尝试逐级截短
  for (let len = suffix.length; len >= 1; len--) {
    const tryCode = `${prefix}.${suffix.substring(0, len)}`
    if (VALID_ZD_CODES.has(tryCode)) {
      return tryCode
    }
  }

  // 尝试替换末尾为 x
  if (suffix.length >= 1) {
    const tryWithX = `${prefix}.${suffix[0]}` + (suffix.length > 1 ? suffix.substring(1).replace(/\d/g, 'x') : '')
    if (VALID_ZD_CODES.has(tryWithX)) {
      return tryWithX
    }
  }

  return null
}

/** 标准化编码列表 */
function normalizeCodeList(list: string[] | undefined): string[] {
  return (list ?? []).map(item => item.trim()).filter(Boolean)
}

/** 获取 DIP 分组方案信息 */
export function getDipSchemeInfo() {
  return {
    key: 'sichuan_dip',
    label: '四川省 DIP',
    version: 'CHS-DIP（四川）',
    totalGroups: Object.keys(ZD_SS_MAP).length + Object.keys(ZD_ONLY_MAP).length,
    zdCount: VALID_ZD_CODES.size,
  }
}

/** 根据诊断编码获取名称 */
export function getZdName(code: string): string {
  return ZD_NAMES[code] || ''
}
