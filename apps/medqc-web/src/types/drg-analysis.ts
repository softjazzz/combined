
/** 分析维度 - 五级层级 */
export type AnalysisDimension = 'hospital' | 'department' | 'ward' | 'doctor' | 'drg'

/** 统计概览数据 */
export interface AnalysisOverview {
    totalCases: number
    totalCost: number
    totalProfit: number
    avgCostRate: number
    drgGroupCount: number
    cmi: number
    // 低风险死亡率相关
    lowRiskMortalityRate: number  // 低风险死亡率 (%)
    lowRiskDeathCount: number     // 低风险死亡例数
    lowRiskTotalCount: number     // 低风险组总例数
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
    }
    distribution: {
        drg: DistributionItem[]
        cost: DistributionItem[]
    }
    tableData: AnalysisTableItem[]
}
