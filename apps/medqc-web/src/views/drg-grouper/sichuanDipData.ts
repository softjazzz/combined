/**
 * 四川省 DIP 病种库数据
 * 来源：四川省按病种分值（DIP）付费病种库 PDF
 *
 * ⚠️ 占位空壳：原始数据因编码问题产生乱码，已清除。
 *    需要时请从原始 PDF/Excel 重新生成。
 *    DIP 分组引擎（dipGrouper.ts）依赖以下导出，
 *    空数据不影响构建和前端渲染，仅导致分组结果为"未入组"。
 */

/** 纯诊断 → 病种名称（无手术操作的病种） */
export const ZD_ONLY_MAP: Record<string, string> = {}

/** 诊断+手术 → 病种名称 key: "ZD|SS" */
export const ZD_SS_MAP: Record<string, string> = {}

/** 诊断+手术+相关手术 → 病种名称 key: "ZD|SS|REL_SS" */
export const ZD_SS_REL_MAP: Record<string, string> = {}

/** 所有有效的诊断编码集合 */
export const VALID_ZD_CODES: Set<string> = new Set()

/** 诊断编码 → 诊断名称 */
export const ZD_NAMES: Record<string, string> = {}
