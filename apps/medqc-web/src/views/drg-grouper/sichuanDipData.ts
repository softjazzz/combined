/**
 * DIP 病种库兼容出口
 *
 * 旧分组器从本文件读取 `ZD_ONLY_MAP / ZD_SS_MAP / ZD_SS_REL_MAP`。
 * 当前实际数据切换为泸州市 2025 年 DIP 核心和综合病种库。
 */
export {
  LUZHOU_DIP_COMPREHENSIVE_BY_CODE,
  LUZHOU_DIP_COMPREHENSIVE_DISEASES,
  LUZHOU_DIP_CORE_BY_KEY,
  LUZHOU_DIP_CORE_DISEASES,
  LUZHOU_DIP_DATASET_META,
  VALID_ZD_CODES,
  ZD_NAMES,
  ZD_ONLY_MAP,
  ZD_SS_MAP,
  ZD_SS_REL_MAP,
} from './luzhouDipData'

export type { LuzhouDipComprehensiveDisease, LuzhouDipCoreDisease } from './luzhouDipData'
