/**
 * DRG/DIP 数据聚合纯函数
 *
 * 与 Vue/Pinia 解耦，可独立单元测试。
 * 从 CaseRecord[] 聚合出各分析视图需要的指标。
 */

import type { CaseRecord } from '@/types/drg-dataset'
import type {
  AnalysisOverview,
  AnalysisTableItem,
  AnalysisDataResponse,
  AnalysisDimension,
  TrendDataPoint,
  DistributionItem,
} from '@/types/drg-analysis'

// ==================== 工具函数 ====================

/** 安全除法，分母为 0 时返回 fallback */
function safeDivide(numerator: number, denominator: number, fallback = 0): number {
  return denominator === 0 ? fallback : numerator / denominator
}

/** 四舍五入到 N 位小数 */
function round(value: number, decimals = 4): number {
  const factor = 10 ** decimals
  return Math.round(value * factor) / factor
}

/** 从出院日期提取月份 yyyy-MM */
function toMonth(dateStr: string | undefined): string {
  if (!dateStr) return '未知'
  // 兼容 yyyy-MM-dd / yyyy/MM/dd / yyyy-MM-dd HH:mm
  const match = dateStr.match(/(\d{4})[-/](\d{1,2})/)
  if (!match) return '未知'
  return `${match[1]}-${match[2].padStart(2, '0')}`
}

/** 获取记录的层级维度值 */
function getDimensionValue(record: CaseRecord, dimension: AnalysisDimension): string {
  switch (dimension) {
    case 'hospital':
      return '全院'
    case 'department':
      return record.department || '未知科室'
    case 'ward':
      return record.ward || record.department || '未知病区'
    // attending_group 对应 PostEvent 的 chief_group
    case 'drg':
      return record.drg_code || record.dip_code || '未入组'
    case 'person':
      return record.attending_doctor || '未知医师'
    default:
      return record.department || '未知'
  }
}

// ==================== 核心聚合 ====================

/**
 * 计算全局概览指标
 */
export function computeOverview(records: CaseRecord[]): AnalysisOverview {
  const count = records.length
  if (count === 0) {
    return {
      totalCases: 0,
      totalCost: 0,
      totalProfit: 0,
      avgCostRate: 0,
      drgGroupCount: 0,
      cmi: 0,
      lowRiskMortalityRate: 0,
      lowRiskDeathCount: 0,
      lowRiskTotalCount: 0,
      timeConsumptionIndex: 0,
      insuranceProfitLoss: 0,
    }
  }

  // 有权重的病例（用于计算 CMI）
  const withWeight = records.filter((r) => typeof r.weight === 'number' && r.weight > 0)
  const totalWeight = withWeight.reduce((s, r) => s + (r.weight ?? 0), 0)
  const cmi = round(safeDivide(totalWeight, withWeight.length), 4)

  // 有基准支付的病例（用于计算盈亏和费用消耗指数）
  const withPayment = records.filter(
    (r) => typeof r.baseline_payment === 'number' && r.baseline_payment > 0,
  )
  const totalCost = records.reduce((s, r) => s + r.total_cost, 0)
  const totalBaseline = withPayment.reduce((s, r) => s + (r.baseline_payment ?? 0), 0)
  const totalProfit = withPayment.reduce(
    (s, r) => s + ((r.baseline_payment ?? 0) - r.total_cost),
    0,
  )

  // 费用消耗指数 = 实际总费用(有基准支付的) / 基准支付总额
  const costOfPaymentCases = withPayment.reduce((s, r) => s + r.total_cost, 0)
  const avgCostRate = round(safeDivide(costOfPaymentCases, totalBaseline), 4)

  // DRG/DIP 组数
  const drgCodes = new Set(
    records.filter((r) => r.drg_code || r.dip_code).map((r) => r.drg_code || r.dip_code || ''),
  )

  // 时间消耗指数（仅在有 standard_los 时计算）
  const withStdLos = records.filter(
    (r) => typeof r.standard_los === 'number' && r.standard_los > 0 && typeof r.los === 'number',
  )
  let timeConsumptionIndex = 0
  if (withStdLos.length > 0) {
    const avgLos = safeDivide(
      withStdLos.reduce((s, r) => s + (r.los ?? 0), 0),
      withStdLos.length,
    )
    const avgStdLos = safeDivide(
      withStdLos.reduce((s, r) => s + (r.standard_los ?? 0), 0),
      withStdLos.length,
    )
    timeConsumptionIndex = round(safeDivide(avgLos, avgStdLos), 2)
  }

  // 低风险死亡率（仅在有 low_risk_case_flag 时计算）
  const lowRiskCases = records.filter((r) => r.low_risk_case_flag === 1)
  const lowRiskDeaths = lowRiskCases.filter((r) => r.low_risk_death_flag === 1)

  return {
    totalCases: count,
    totalCost: Math.round(totalCost),
    totalProfit: Math.round(totalProfit),
    avgCostRate,
    drgGroupCount: drgCodes.size,
    cmi,
    lowRiskMortalityRate: round(safeDivide(lowRiskDeaths.length, lowRiskCases.length), 4),
    lowRiskDeathCount: lowRiskDeaths.length,
    lowRiskTotalCount: lowRiskCases.length,
    timeConsumptionIndex,
    insuranceProfitLoss: Math.round(totalProfit),
  }
}

/**
 * 按维度聚合明细表
 */
export function aggregateByDimension(
  records: CaseRecord[],
  dimension: AnalysisDimension,
): AnalysisTableItem[] {
  if (records.length === 0) return []

  // 按维度分组
  const groups = new Map<string, CaseRecord[]>()
  for (const r of records) {
    const key = getDimensionValue(r, dimension)
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key)!.push(r)
  }

  // 每组聚合
  const items: AnalysisTableItem[] = []
  let idx = 0
  for (const [name, group] of groups) {
    idx += 1
    const caseCount = group.length
    const totalCost = group.reduce((s, r) => s + r.total_cost, 0)
    const totalBaseline = group.reduce((s, r) => s + (r.baseline_payment ?? 0), 0)
    const profit = totalBaseline - totalCost
    const withWeight = group.filter((r) => typeof r.weight === 'number' && r.weight > 0)
    const cmi = round(
      safeDivide(
        withWeight.reduce((s, r) => s + (r.weight ?? 0), 0),
        withWeight.length,
      ),
      4,
    )
    const costRate = round(safeDivide(totalCost, totalBaseline), 2)

    items.push({
      id: `D${idx}`,
      name,
      caseCount,
      totalRevenue: Math.round(totalBaseline),
      totalCost: Math.round(totalCost),
      profit: Math.round(profit),
      cmi,
      costRate,
    })
  }

  // 按病例数降序
  items.sort((a, b) => b.caseCount - a.caseCount)

  return items
}

/**
 * 按月聚合费用消耗指数趋势
 */
export function computeCostTrends(records: CaseRecord[]): TrendDataPoint[] {
  const groups = new Map<string, CaseRecord[]>()
  for (const r of records) {
    const month = toMonth(r.discharge_date)
    if (month === '未知') continue
    if (!groups.has(month)) groups.set(month, [])
    groups.get(month)!.push(r)
  }

  const result: TrendDataPoint[] = []
  const sortedMonths = [...groups.keys()].sort()

  for (const month of sortedMonths) {
    const group = groups.get(month)!
    const totalCost = group.reduce((s, r) => s + r.total_cost, 0)
    const totalBaseline = group.reduce((s, r) => s + (r.baseline_payment ?? 0), 0)
    result.push({
      date: month,
      value: round(safeDivide(totalCost, totalBaseline), 2),
    })
  }

  return result
}

/**
 * 按月聚合 CMI 趋势
 */
export function computeCmiTrends(records: CaseRecord[]): TrendDataPoint[] {
  const groups = new Map<string, CaseRecord[]>()
  for (const r of records) {
    const month = toMonth(r.discharge_date)
    if (month === '未知') continue
    if (!groups.has(month)) groups.set(month, [])
    groups.get(month)!.push(r)
  }

  const result: TrendDataPoint[] = []
  const sortedMonths = [...groups.keys()].sort()

  for (const month of sortedMonths) {
    const group = groups.get(month)!
    const withWeight = group.filter((r) => typeof r.weight === 'number' && r.weight > 0)
    const totalWeight = withWeight.reduce((s, r) => s + (r.weight ?? 0), 0)
    result.push({
      date: month,
      value: round(safeDivide(totalWeight, withWeight.length), 4),
    })
  }

  return result
}

/**
 * DRG/DIP 分组分布 Top N
 */
export function computeDrgDistribution(records: CaseRecord[], topN = 10): DistributionItem[] {
  const counter = new Map<string, number>()
  for (const r of records) {
    const code = r.drg_code || r.dip_code
    if (!code) continue
    counter.set(code, (counter.get(code) || 0) + 1)
  }

  return [...counter.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, topN)
    .map(([name, value]) => ({ name, value }))
}

/**
 * 费用构成分析
 */
export function computeCostComposition(records: CaseRecord[]): DistributionItem[] {
  let drug = 0
  let material = 0
  let exam = 0
  let treatment = 0
  let other = 0

  for (const r of records) {
    drug += r.drug_fee ?? 0
    material += r.material_fee ?? 0
    exam += r.exam_fee ?? 0
    treatment += r.treatment_fee ?? 0
    // 合并剩余费用
    other += (r.surgery_fee ?? 0) + (r.bed_fee ?? 0) + (r.nursing_fee ?? 0) + (r.other_fee ?? 0)
  }

  const total = drug + material + exam + treatment + other
  if (total === 0) return []

  return [
    { name: '药品费', value: Math.round((drug / total) * 100) },
    { name: '耗材费', value: Math.round((material / total) * 100) },
    { name: '检查费', value: Math.round((exam / total) * 100) },
    { name: '治疗费', value: Math.round((treatment / total) * 100) },
    { name: '其他', value: Math.round((other / total) * 100) },
  ]
}

/**
 * 构建完整的 AnalysisDataResponse（供 api/drg.ts 替代 Mock）
 */
export function buildAnalysisResponse(
  records: CaseRecord[],
  dimension: AnalysisDimension,
): AnalysisDataResponse {
  const overview = computeOverview(records)
  const tableData = aggregateByDimension(records, dimension)

  // 费用消耗指数月度趋势
  const costTrends = computeCostTrends(records)
  // CMI 月度趋势
  const cmiTrends = computeCmiTrends(records)

  // 盈亏月度趋势
  const profitTrends: TrendDataPoint[] = (() => {
    const groups = new Map<string, CaseRecord[]>()
    for (const r of records) {
      const month = toMonth(r.discharge_date)
      if (month === '未知') continue
      if (!groups.has(month)) groups.set(month, [])
      groups.get(month)!.push(r)
    }
    return [...groups.keys()]
      .sort()
      .map((month) => {
        const group = groups.get(month)!
        const profit = group.reduce(
          (s, r) => s + ((r.baseline_payment ?? 0) - r.total_cost),
          0,
        )
        return { date: month, value: Math.round(profit) }
      })
  })()

  return {
    overview,
    trends: {
      cost: costTrends,
      cmi: cmiTrends,
      profit_loss: profitTrends,
    },
    distribution: {
      drg: computeDrgDistribution(records),
      cost: computeCostComposition(records),
    },
    tableData,
  }
}
