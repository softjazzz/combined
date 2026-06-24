/**
 * 泸州市 DIP 分组引擎
 * 基于泸州市按病种分值（DIP）付费核心和综合病种库
 *
 * DIP 分组逻辑：
 *   1. 主诊断 + 主手术 + 相关手术 → 精确匹配
 *   2. 主诊断 + 主手术 → 标准匹配
 *   3. 仅主诊断（无手术） → 内科保守治疗匹配
 *   4. 均不匹配 → 未入组
 */
import {
  LUZHOU_DIP_CORE_BY_KEY,
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
  /** 离院方式，仅用于模拟输入上下文，当前 DIP 匹配不参与计算 */
  leavingType?: string
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
  /** DIP 分值 */
  score?: number
  /** 病种属性 */
  diseaseAttribute?: string
  /** 基层病种标识 */
  primaryCareFlag?: string
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
    messages.push(`主诊断 ${primaryZd} 不在泸州DIP病种库中`)
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
        const coreEntry = getCoreEntry(key3)
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
          score: coreEntry?.score,
          diseaseAttribute: coreEntry?.diseaseAttribute,
          primaryCareFlag: coreEntry?.primaryCareFlag,
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
          const coreEntry = getCoreEntry(key3)
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
            score: coreEntry?.score,
            diseaseAttribute: coreEntry?.diseaseAttribute,
            primaryCareFlag: coreEntry?.primaryCareFlag,
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
      const coreEntry = getCoreEntry(key2)
      messages.push(`标准匹配: ${primaryZd} + ${mainSs}`)
      return {
        status: '分组成功',
        dipCode,
        dipName: ZD_SS_MAP[key2],
        primaryZd: originalZd || primaryZd,
        primaryZdName,
        matchedSs: mainSs,
        matchType: '诊断+手术',
        score: coreEntry?.score,
        diseaseAttribute: coreEntry?.diseaseAttribute,
        primaryCareFlag: coreEntry?.primaryCareFlag,
        messages,
      }
    }

    // 尝试用其他手术操作匹配
    for (let i = 1; i < ssList.length; i++) {
      const altSs = ssList[i]
      const altKey = `${primaryZd}|${altSs}`
      if (ZD_SS_MAP[altKey]) {
        const dipCode = `${primaryZd}+${altSs}`
        const coreEntry = getCoreEntry(altKey)
        messages.push(`备选手术匹配: ${primaryZd} + ${altSs}（原主手术 ${mainSs} 未匹配）`)
        return {
          status: '分组成功',
          dipCode,
          dipName: ZD_SS_MAP[altKey],
          primaryZd: originalZd || primaryZd,
          primaryZdName,
          matchedSs: altSs,
          matchType: '诊断+手术',
          score: coreEntry?.score,
          diseaseAttribute: coreEntry?.diseaseAttribute,
          primaryCareFlag: coreEntry?.primaryCareFlag,
          messages,
        }
      }
    }

    messages.push(`诊断+手术组合未匹配: ${primaryZd} + ${mainSs}`)
  }

  // Step 3: 纯诊断匹配
  if (ZD_ONLY_MAP[primaryZd]) {
    const dipCode = primaryZd
    const coreEntry = getCoreEntry(primaryZd)
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
      score: coreEntry?.score,
      diseaseAttribute: coreEntry?.diseaseAttribute,
      primaryCareFlag: coreEntry?.primaryCareFlag,
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
 *
 * 背景：DIP 病种库的编码版本（如 K35.2/K35.8）与医保版 ICD 编码
 * （如 K35.000/K35.900）的亚目分类可能不同，直接截断匹配不到。
 * 因此在截断失败后增加"前缀搜索"——按大类前缀（如 K35）在 DIP
 * 有效编码中找所有候选，优先选"未特指/其他"类编码。
 */
function tryFuzzyZdMatch(code: string): string | null {
  const parts = code.split('.')
  if (parts.length < 2) return null

  const prefix = parts[0]
  const suffix = parts[1]

  // 第一轮：逐级截短精确匹配（K35.900 → K35.90 → K35.9 → ...）
  for (let len = suffix.length; len >= 1; len--) {
    const tryCode = `${prefix}.${suffix.substring(0, len)}`
    if (VALID_ZD_CODES.has(tryCode)) {
      return tryCode
    }
  }

  // 第二轮：尝试替换末尾为 x（如 B99.x）
  if (suffix.length >= 1) {
    const tryWithX =
      `${prefix}.${suffix[0]}` + (suffix.length > 1 ? suffix.substring(1).replace(/\d/g, 'x') : '')
    if (VALID_ZD_CODES.has(tryWithX)) {
      return tryWithX
    }
  }

  // 第三轮：前缀搜索 — 用大类前缀在 VALID_ZD_CODES 里找候选
  // 解决 DIP 病种库与医保版 ICD 亚目分类不一致的问题
  const categoryPrefix = `${prefix}.` // 如 "K35."
  const candidates: string[] = []
  for (const zdCode of VALID_ZD_CODES) {
    if (zdCode.startsWith(categoryPrefix)) {
      candidates.push(zdCode)
    }
  }

  if (candidates.length > 0) {
    // 优先选"未特指/其他"类：亚目编号最大的通常是"其他/未特指"
    // 例如 K35.8 = "其他和未特指的急性阑尾炎"
    candidates.sort()
    return candidates[candidates.length - 1]
  }

  return null
}

/** 标准化编码列表 */
function normalizeCodeList(list: string[] | undefined): string[] {
  return (list ?? []).map((item) => item.trim()).filter(Boolean)
}

function getCoreEntry(matchKey: string) {
  return LUZHOU_DIP_CORE_BY_KEY[matchKey]
}

/** 获取 DIP 分组方案信息 */
export function getDipSchemeInfo() {
  return {
    key: 'luzhou_dip_2025',
    label: '泸州市 DIP',
    version: 'CHS-DIP（泸州 2025）',
    totalGroups:
      Object.keys(ZD_SS_MAP).length +
      Object.keys(ZD_SS_REL_MAP).length +
      Object.keys(ZD_ONLY_MAP).length,
    zdCount: VALID_ZD_CODES.size,
  }
}

/** 根据诊断编码获取名称 */
export function getZdName(code: string): string {
  return ZD_NAMES[code] || ''
}
