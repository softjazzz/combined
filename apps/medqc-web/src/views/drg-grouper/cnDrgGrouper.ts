/**
 * CN-DRG 绩效监测分组器包装。
 *
 * CN-DRG 绩效监测复用 CHS-DRG 四川 2.0 分组路径，
 * 并叠加官方 Excel 生成的 2024 绩效监测 DRG 权重与低风险组列表。
 */
import {
  performGrouping as performChsDrgGrouping,
  getMdcName,
  type GrouperInput,
  type GrouperResult,
} from './drgGrouper'

export { getMdcName }
export type { GrouperInput, GrouperResult }

const CN_DRG_PERFORMANCE_NOTICE =
  'CN-DRG 绩效监测：复用 CHS-DRG 四川 2.0 分组路径，叠加 2024 绩效监测 DRG 权重与低风险组列表。'

/** CN-DRG 绩效监测分组 */
export async function performGrouping(input: GrouperInput): Promise<GrouperResult> {
  const result = await performChsDrgGrouping(input)

  return {
    ...result,
    messages: [CN_DRG_PERFORMANCE_NOTICE, ...result.messages],
    weightSource:
      result.weightSource ||
      (result.status === '分组成功'
        ? '2024年度三级公立医院绩效监测DRG权重和低风险组列表'
        : result.weightSource),
  }
}

/** 方案信息 */
export function getSchemeInfo() {
  return { key: 'cn_drg_performance', label: 'CN-DRG 绩效监测' }
}
