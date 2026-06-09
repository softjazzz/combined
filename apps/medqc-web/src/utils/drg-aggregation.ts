/**
 * DRG/DIP 数据聚合纯函数
 *
 * 与 Vue/Pinia 解耦，可独立单元测试。
 * 从 CaseRecord[] 聚合出各分析视图需要的指标。
 */

import type { CaseRecord } from '@/types/drg-dataset'
import type {
  CmiTrend,
  DeptCostIndex,
  DrgAlert,
  MonitoringControlTip,
  MonitoringStats,
} from '@/api/panel'
import type {
  AnalysisOverview,
  AnalysisTableItem,
  AnalysisDataResponse,
  AnalysisDimension,
  TrendDataPoint,
  DistributionItem,
} from '@/types/drg-analysis'
import type { FeeMonitoringRow, GroupingStatus } from '@/types/drg-fee'
import type { PaymentMonitoringRow } from '@/data/drg/mock-payment-monitoring'

/** PostEventAnalysisView 的维度定义 */
export type PostEventDimension = 'hospital' | 'department' | 'ward' | 'chief_group' | 'person'

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
    return [...groups.keys()].sort().map((month) => {
      const group = groups.get(month)!
      const profit = group.reduce((s, r) => s + ((r.baseline_payment ?? 0) - r.total_cost), 0)
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

// ==================== FeeMonitoring 映射 ====================

/**
 * 将 CaseRecord[] 映射为 FeeMonitoringRow[]
 *
 * 直接从上传数据生成列表行，不需要三路 API 拼装。
 * FeeMonitoringRow extends CaseFrontPage，这里构造兼容的数据结构。
 */
export function mapCaseRecordsToFeeMonitoringRows(records: CaseRecord[]): FeeMonitoringRow[] {
  return records.map((r, idx) => {
    const actualCost = r.total_cost
    const baselinePayment = r.baseline_payment ?? null
    const hasGroup = !!(r.drg_code || r.dip_code)
    const groupingStatus: GroupingStatus = hasGroup ? 'grouped' : 'ungrouped'

    // 费用消耗率（百分比）
    const costRate =
      baselinePayment && baselinePayment > 0 ? (actualCost / baselinePayment) * 100 : null
    // 盈亏额
    const profitMargin = baselinePayment != null ? baselinePayment - actualCost : null

    // 结算类型推导（与原 composable 逻辑一致）
    let settlementType = '未入组'
    if (hasGroup && typeof costRate === 'number') {
      if (costRate >= 120) settlementType = '费用极高'
      else if (costRate < 50) settlementType = '费用极低'
      else if (typeof profitMargin === 'number' && profitMargin < 0) settlementType = '亏损'
      else settlementType = '正常倍率'
    }

    const isBaseGroup =
      hasGroup && typeof costRate === 'number' ? costRate >= 80 && costRate < 120 : null

    return {
      // CaseFrontPage 兼容字段
      front_page_id: idx + 1,
      admission_id: r.admission_id,
      patient_id: r.admission_id,
      patient_name: r.patient_name || '',
      patient_age: r.age ?? 0,
      patient_gender: r.gender ?? 'M',
      primary_diagnosis_code: r.primary_diagnosis_code ?? '',
      primary_diagnosis_name: r.primary_diagnosis_name ?? '',
      main_procedure_code: r.main_procedure_code,
      main_procedure_name: r.main_procedure_name,
      total_hospital_days: r.los,
      total_cost: r.total_cost,
      coding_status: hasGroup ? 'completed' : 'draft',
      review_status: 'pending',
      created_at: r.admission_date ?? r.discharge_date,
      updated_at: r.discharge_date,

      // FeeMonitoringRow 扩展字段
      grouping: hasGroup
        ? {
            adrg_code: (r.drg_code ?? '').slice(0, 2),
            adrg_name: r.drg_name ?? '',
            drg_code: r.drg_code ?? r.dip_code ?? '',
            drg_name: r.drg_name ?? r.dip_name ?? '',
            weight: r.weight ?? 0,
            baseline_payment: r.baseline_payment ?? 0,
          }
        : null,
      groupingStatus,
      baselinePayment,
      actualCost,
      costRate,
      profitMargin,
      suggestions: [],
      department: r.department,
      admitAt: r.admission_date ?? r.discharge_date,
      dischargeAt: r.discharge_date,
      selfPay: Math.max(0, Math.round(actualCost * 0.01 * 100) / 100),
      isBaseGroup,
      settlementType,
      settlementMethod: hasGroup ? '按DRG付费' : '-',
      ungroupedReason: hasGroup ? '' : r.ungrouped_reason || '主诊断与手术编码不匹配',
      fixSuggestion: hasGroup ? '' : '建议核对主要诊断/主要手术，完善并发症标记后重试入组。',
    } as FeeMonitoringRow
  })
}

// ==================== PaymentMonitoring 映射 ====================

/**
 * 将 CaseRecord[] 映射为 PaymentMonitoringRow[]
 *
 * 用于 workstation-v4 的付费监测页面（PaymentMonitoringView.vue）。
 * 这个组件使用独立的 PaymentMonitoringRow 类型，与 FeeMonitoringRow 不同。
 */
export function mapCaseRecordsToPaymentMonitoringRows(
  records: CaseRecord[],
): PaymentMonitoringRow[] {
  // 科室 key 映射
  const deptKeyMap: Record<string, string> = {
    心内科: 'cardiology',
    心血管内科: 'cardiology',
    心血管内科专业: 'cardiology',
    呼吸内科: 'respiratory',
    呼吸内科专业: 'respiratory',
    神经内科: 'neurology',
    神经内科专业: 'neurology',
    骨科: 'orthopedics',
    骨科专业: 'orthopedics',
    普外科: 'general-surgery',
    普通外科专业: 'general-surgery',
    儿科: 'pediatrics',
  }

  return records
    .filter((r) => r.baseline_payment && r.baseline_payment > 0)
    .map((r, idx) => {
      const deptKey = deptKeyMap[r.department] || r.department.toLowerCase()
      const baselinePayment = r.baseline_payment ?? r.total_cost
      // payment = 模拟医保支付（基准支付 * 支付比例，默认 58%）
      const payment = Math.round(baselinePayment * 0.58)
      const drg = r.drg_code || r.dip_code || '未入组'

      return {
        id: idx + 1,
        caseNo: `#${r.admission_id}`,
        deptKey,
        deptName: r.department,
        drg,
        actualCost: r.total_cost,
        payment,
        baselinePayment,
        weight: r.weight,
        dipScore: r.dip_score,
        ruleHint: r.drg_name || r.dip_name || r.primary_diagnosis_name || '',
        controlTip: '',
      } as PaymentMonitoringRow
    })
}

// ==================== InProcessMonitoring 映射 ====================

function getGroupingCode(record: CaseRecord): string {
  return record.drg_code || record.dip_code || '未入组'
}

function getGroupingName(record: CaseRecord): string {
  return record.drg_name || record.dip_name || record.primary_diagnosis_name || '未知诊断'
}

function inferBaselinePayment(record: CaseRecord): number {
  if (typeof record.baseline_payment === 'number' && record.baseline_payment > 0) {
    return record.baseline_payment
  }
  if (typeof record.insurance_payment === 'number' && record.insurance_payment > 0) {
    return record.insurance_payment
  }
  if (typeof record.dip_score === 'number' && record.dip_score > 0) {
    return Math.round(record.dip_score * 75)
  }
  if (typeof record.weight === 'number' && record.weight > 0) {
    return Math.round(record.weight * 7000)
  }
  return record.total_cost > 0 ? record.total_cost : 1
}

function getCostRatio(record: CaseRecord): number {
  return round(safeDivide(record.total_cost, inferBaselinePayment(record), 1), 2)
}

function getMonitorLevel(record: CaseRecord): DrgAlert['monitor_level'] {
  if (record.ungrouped_reason || (!record.drg_code && !record.dip_code)) return 'warning'
  const ratio = getCostRatio(record)
  if (ratio >= 1.2) return 'critical'
  if (ratio >= 1) return 'warning'
  return 'info'
}

function buildControlTip(record: CaseRecord, ratio: number): string {
  if (record.ungrouped_reason || (!record.drg_code && !record.dip_code)) {
    return `未入组病例：${record.ungrouped_reason || '缺少 DRG/DIP 分组结果'}，建议优先复核主诊断、主要手术和并发症编码。`
  }
  if (ratio >= 1.2) {
    return '费用比超过重点阈值，建议优先复核高值耗材、药品、检查和住院日。'
  }
  if (ratio >= 1) {
    return '费用接近或超过支付标准，建议跟踪费用构成和路径偏差。'
  }
  return '费用处于可控区间，可继续观察。'
}

function toDateLabel(dateStr: string | undefined): string {
  if (!dateStr) return '未知'
  const match = dateStr.match(/(?:\d{4})[-/](\d{1,2})[-/](\d{1,2})/)
  if (!match) return toMonth(dateStr)
  return `${match[1].padStart(2, '0')}-${match[2].padStart(2, '0')}`
}

function buildInProcessAlerts(records: CaseRecord[]): DrgAlert[] {
  return records
    .map<DrgAlert>((record, index) => {
      const baselinePayment = inferBaselinePayment(record)
      const actualCost = record.total_cost
      const ratio = round(safeDivide(actualCost, baselinePayment, 1), 2)
      const monitorLevel = getMonitorLevel(record)
      const paymentGap = Math.round(actualCost - baselinePayment)

      return {
        id: index + 1,
        case_no: `#${record.admission_id}`,
        dept: record.department || '未知科室',
        diagnosis: record.primary_diagnosis_name || getGroupingName(record),
        drg: getGroupingCode(record),
        ratio,
        status: monitorLevel === 'info' ? 'normal' : 'warning',
        los: record.los ?? 0,
        est_cost: actualCost,
        baseline_payment: baselinePayment,
        actual_cost: actualCost,
        payment_gap: paymentGap,
        monitor_level: monitorLevel,
        control_tip: buildControlTip(record, ratio),
      }
    })
    .sort((a, b) => {
      const levelScore = (item: DrgAlert) =>
        item.monitor_level === 'critical' ? 3 : item.monitor_level === 'warning' ? 2 : 1
      return levelScore(b) - levelScore(a) || b.ratio - a.ratio
    })
}

function buildInProcessTrend(records: CaseRecord[]): CmiTrend {
  const groups = new Map<string, CaseRecord[]>()
  for (const record of records) {
    const label = toDateLabel(record.discharge_date || record.admission_date)
    if (!groups.has(label)) groups.set(label, [])
    groups.get(label)!.push(record)
  }

  const labels = [...groups.keys()].sort().slice(-7)
  if (labels.length === 0) {
    return { labels: ['暂无数据'], values: [1], benchmark: 1 }
  }

  return {
    labels,
    values: labels.map((label) => {
      const group = groups.get(label) || []
      return round(
        safeDivide(
          group.reduce((sum, record) => sum + getCostRatio(record), 0),
          group.length,
          1,
        ),
        2,
      )
    }),
    benchmark: 1,
  }
}

function buildInProcessDeptCostIndex(records: CaseRecord[]): DeptCostIndex {
  const groups = new Map<string, CaseRecord[]>()
  for (const record of records) {
    const dept = record.department || '未知科室'
    if (!groups.has(dept)) groups.set(dept, [])
    groups.get(dept)!.push(record)
  }

  const rows = [...groups.entries()]
    .map(([department, group]) => {
      const totalCost = group.reduce((sum, record) => sum + record.total_cost, 0)
      const totalBaseline = group.reduce((sum, record) => sum + inferBaselinePayment(record), 0)
      return {
        department,
        value: round(safeDivide(totalCost, totalBaseline, 1), 2),
      }
    })
    .sort((a, b) => b.value - a.value)
    .slice(0, 8)

  return {
    departments: rows.length ? rows.map((row) => row.department) : ['暂无数据'],
    values: rows.length ? rows.map((row) => row.value) : [1],
    benchmark: 1,
  }
}

function buildInProcessControlTips(
  alerts: DrgAlert[],
  records: CaseRecord[],
): MonitoringControlTip[] {
  const criticalCount = alerts.filter((item) => item.monitor_level === 'critical').length
  const warningCount = alerts.filter((item) => item.monitor_level === 'warning').length
  const ungroupedCount = records.filter((record) => !record.drg_code && !record.dip_code).length

  return [
    {
      title: '高费用病例优先复核',
      indicator: '费用比 ≥ 1.20',
      current_value: `${criticalCount} 例`,
      target_value: '0 例',
      suggestion: '优先核查高值耗材、药品、检查和住院日，降低重点病例费用放大。',
      level: criticalCount > 0 ? 'critical' : 'info',
    },
    {
      title: '边界病例持续跟踪',
      indicator: '1.00 ~ 1.20',
      current_value: `${warningCount} 例`,
      target_value: '稳定在阈值内',
      suggestion: '对照地方付费标准和临床路径提前修正费用偏差。',
      level: warningCount > 0 ? 'warning' : 'info',
    },
    {
      title: '未入组病例补码',
      indicator: 'DRG/DIP 缺失',
      current_value: `${ungroupedCount} 例`,
      target_value: '完成分组',
      suggestion: '补充主诊断、主要手术、并发症和分组结果后再进入正式监控。',
      level: ungroupedCount > 0 ? 'warning' : 'info',
    },
  ]
}

/**
 * 构建 InProcessMonitoringView 所需数据结构（上传数据 adapter）。
 */
export function buildInProcessMonitoringDataset(records: CaseRecord[]): {
  stats: MonitoringStats
  alerts: DrgAlert[]
  cmiTrend: CmiTrend
  costIndex: DeptCostIndex
} {
  const alerts = buildInProcessAlerts(records)
  const criticalCount = alerts.filter((item) => item.monitor_level === 'critical').length
  const warningCount = alerts.filter((item) => item.status === 'warning').length
  const groupedCount = records.filter((record) => record.drg_code || record.dip_code).length

  return {
    stats: {
      total_alerts: records.length,
      severe_alerts: criticalCount,
      pending_suggestions: warningCount,
      today_new: warningCount,
      simulated_groups: groupedCount,
      control_threshold: 1.2,
      mock_scope_note: `基于模板上传数据生成事中监控（${records.length} 例）`,
      control_tips: buildInProcessControlTips(alerts, records),
    },
    alerts,
    cmiTrend: buildInProcessTrend(records),
    costIndex: buildInProcessDeptCostIndex(records),
  }
}

// ==================== PostEvent 映射 ====================

function getPostEventDimensionValue(record: CaseRecord, dimension: PostEventDimension): string {
  switch (dimension) {
    case 'hospital':
      return '全院'
    case 'department':
      return record.department || '未知科室'
    case 'ward':
      return record.ward || record.department || '未知病区'
    case 'chief_group':
      return record.attending_group || '未知医师组'
    case 'person':
      return record.attending_doctor || '未知医师'
    default:
      return record.department || '未知'
  }
}

function aggregatePostEventByDimension(records: CaseRecord[], dimension: PostEventDimension) {
  if (records.length === 0) return []
  const groups = new Map<string, CaseRecord[]>()
  for (const r of records) {
    const key = getPostEventDimensionValue(r, dimension)
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key)!.push(r)
  }

  const rows: Array<Record<string, any>> = []
  for (const [name, group] of groups) {
    const caseCount = group.length
    const totalCost = group.reduce((s, r) => s + r.total_cost, 0)
    const totalBaseline = group.reduce((s, r) => s + (r.baseline_payment ?? 0), 0)
    const totalProfit = totalBaseline - totalCost
    const withWeight = group.filter((r) => typeof r.weight === 'number' && r.weight > 0)
    const avgCmi = round(
      safeDivide(
        withWeight.reduce((s, r) => s + (r.weight ?? 0), 0),
        withWeight.length,
      ),
      4,
    )
    const withLos = group.filter((r) => typeof r.los === 'number')
    const avgLos = round(
      safeDivide(
        withLos.reduce((s, r) => s + (r.los ?? 0), 0),
        withLos.length,
      ),
      1,
    )

    rows.push({
      dept_name: name,
      total_profit: Math.round(totalProfit),
      avg_cmi: avgCmi,
      case_count: caseCount,
      cost_rate: round(safeDivide(totalCost, totalBaseline), 2),
      avg_los: avgLos,
    })
  }

  rows.sort((a, b) => Number(b.case_count || 0) - Number(a.case_count || 0))
  return rows
}

function buildPostEventMonthlyTrends(records: CaseRecord[]) {
  const groups = new Map<string, CaseRecord[]>()
  for (const r of records) {
    const month = toMonth(r.discharge_date)
    if (month === '未知') continue
    if (!groups.has(month)) groups.set(month, [])
    groups.get(month)!.push(r)
  }

  return [...groups.keys()].sort().map((month) => {
    const group = groups.get(month) || []
    const withWeight = group.filter((r) => typeof r.weight === 'number' && r.weight > 0)
    const avgCmi = round(
      safeDivide(
        withWeight.reduce((s, r) => s + (r.weight ?? 0), 0),
        withWeight.length,
      ),
      4,
    )
    return {
      date: month,
      count: group.length,
      avg_cmi: avgCmi,
    }
  })
}

function buildPostEventCostStructure(records: CaseRecord[]) {
  const drug = records.reduce((s, r) => s + (r.drug_fee ?? 0), 0)
  const material = records.reduce((s, r) => s + (r.material_fee ?? 0), 0)
  const exam = records.reduce((s, r) => s + (r.exam_fee ?? 0), 0)
  const treatment = records.reduce((s, r) => s + (r.treatment_fee ?? 0), 0)

  return {
    drug: Math.round(drug),
    material: Math.round(material),
    exam: Math.round(exam),
    treatment: Math.round(treatment),
  }
}

function buildPostEventMdcDistribution(records: CaseRecord[]) {
  const dist = computeDrgDistribution(records, 6)
  if (dist.length > 0) {
    return dist.map((d) => ({ mdc: d.name, count: d.value }))
  }
  const groupedCount = records.filter((r) => r.drg_code || r.dip_code).length
  return [
    { mdc: '已入组', count: groupedCount },
    { mdc: '未入组', count: Math.max(records.length - groupedCount, 0) },
  ]
}

function buildPostEventInsights(
  summary: Record<string, any>,
  dimensionRows: Array<Record<string, any>>,
): string[] {
  const insights: string[] = []
  insights.push(
    `样本共 ${summary.total_records} 例，入组率 ${(Number(summary.grouping_success_rate || 0) * 100).toFixed(2)}%，CMI ${Number(summary.avg_cmi || 0).toFixed(3)}。`,
  )

  const sortedRows = [...dimensionRows].sort(
    (a, b) => Number(a.total_profit || 0) - Number(b.total_profit || 0),
  )
  const topLossRow = sortedRows[0]
  if (topLossRow && Number(topLossRow.total_profit || 0) < 0) {
    insights.push(
      `${topLossRow.dept_name} 医保盈亏为 ${Math.round(topLossRow.total_profit).toLocaleString('zh-CN')} 元，建议优先复核路径外费用。`,
    )
  }

  if (Number(summary.cost_consumption_index || 0) > 1) {
    insights.push('费用消耗指数高于 1，建议重点排查高值耗材与重复检查。')
  } else {
    insights.push('费用消耗指数控制在 1 以内，建议继续监控结构性成本。')
  }

  return insights
}

/**
 * 构建 PostEventAnalysisView 所需 stats 结构（上传数据 adapter）
 */
export function buildPostEventDatasetStats(records: CaseRecord[], dimension: PostEventDimension) {
  const overview = computeOverview(records)
  const groupedCount = records.filter((r) => r.drg_code || r.dip_code).length
  const withWeight = records.filter((r) => typeof r.weight === 'number' && r.weight > 0)
  const withLos = records.filter((r) => typeof r.los === 'number')

  const summary = {
    total_records: records.length,
    drg_count: overview.drgGroupCount,
    grouping_success_rate: safeDivide(groupedCount, records.length),
    avg_cmi: overview.cmi,
    total_weight: round(
      withWeight.reduce((s, r) => s + (r.weight ?? 0), 0),
      2,
    ),
    total_fee: overview.totalCost,
    total_profit: overview.totalProfit,
    insurance_profit: overview.insuranceProfitLoss,
    cost_consumption_index: overview.avgCostRate,
    time_consumption_index: overview.timeConsumptionIndex,
    low_risk_mortality_rate: overview.lowRiskMortalityRate,
    low_risk_death_count: overview.lowRiskDeathCount,
    low_risk_total_count: overview.lowRiskTotalCount,
    avg_length_of_stay: round(
      safeDivide(
        withLos.reduce((s, r) => s + (r.los ?? 0), 0),
        withLos.length,
      ),
      1,
    ),
    avg_inpatient_cost: round(safeDivide(overview.totalCost, records.length), 0),
  }

  const departmentStats = aggregatePostEventByDimension(records, dimension)
  const doctorStats = aggregatePostEventByDimension(
    records,
    dimension === 'person' ? 'person' : 'chief_group',
  )

  return {
    summary,
    mdc_distribution: buildPostEventMdcDistribution(records),
    drg_distribution: computeDrgDistribution(records, 10),
    department_stats: departmentStats,
    doctor_stats: doctorStats,
    daily_trends: buildPostEventMonthlyTrends(records),
    cost_structure: buildPostEventCostStructure(records),
    charts: {},
    ai_insights: buildPostEventInsights(summary, departmentStats),
  }
}
