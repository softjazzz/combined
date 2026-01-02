
/** 分析维度 */
export type AnalysisDimension = 'hospital' | 'department' | 'doctor' | 'drg'

/** 统计概览数据 */
export interface AnalysisOverview {
    totalCases: number
    totalCost: number
    totalProfit: number
    avgCostRate: number
    drgGroupCount: number
    cmi: number
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
