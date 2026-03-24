/** 分析维度 - 五级层级 */
export type AnalysisDimension = 'hospital' | 'department' | 'ward' | 'doctor' | 'drg'
export type AnalysisRequiredLevel =
  | 'hospital'
  | 'department'
  | 'ward'
  | 'attending_group'
  | 'person'

/** 统计概览数据 */
export interface AnalysisOverview {
  totalCases: number
  totalCost: number
  totalProfit: number
  avgCostRate: number
  drgGroupCount: number
  cmi: number
  // 低风险死亡率相关
  lowRiskMortalityRate: number // 低风险死亡率 (%)
  lowRiskDeathCount: number // 低风险死亡例数
  lowRiskTotalCount: number // 低风险组总例数
  timeConsumptionIndex: number // 时间消耗指数
  insuranceProfitLoss: number // 医保盈亏
}

/** 趋势数据点 */
export interface TrendDataPoint {
  date: string
  value: number
  label?: string
}

/** 分布数据点 */
export interface DistributionItem {
  name: string
  value: number
  percentage?: number
}

/** 详细分析表格项 */
export interface AnalysisTableItem {
  id: string
  name: string // 科室名/医生名/DRG组名
  caseCount: number
  totalRevenue: number
  totalCost: number
  profit: number
  cmi?: number
  costRate: number
}

/** 分析数据响应 */
export interface AnalysisDataResponse {
  overview: AnalysisOverview
  trends: {
    cost: TrendDataPoint[]
    cmi: TrendDataPoint[]
    time?: TrendDataPoint[]
    profit_loss?: TrendDataPoint[]
  }
  distribution: {
    drg: DistributionItem[]
    cost: DistributionItem[]
  }
  tableData: AnalysisTableItem[]
  levels?: Record<AnalysisRequiredLevel, { items: AnalysisTableItem[] }>
  kpis?: {
    drg_dip_group_count: number
    cmi: number
    cost_consumption_index: number
    time_consumption_index: number
    low_risk_mortality_rate: number
    avg_los: number
    avg_cost: number
    insurance_profit_loss: number
  }
  profitability?: {
    by_department: Array<Record<string, any>>
    by_diagnosis_group: Array<Record<string, any>>
    by_doctor: Array<Record<string, any>>
    reason_breakdown: {
      drug: number
      material: number
      exam: number
      treatment: number
      other: number
    }
  }
  export_payload?: Record<string, any>
  conclusions?: string[]
}
