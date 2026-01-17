import type { AnalysisDimension, AnalysisDataResponse } from '@/types/drg-analysis'

export const mockAnalysisData = (dimension: AnalysisDimension): AnalysisDataResponse => {
    // 基础数据
    const baseOverview = {
        totalCases: 1250,
        totalCost: 15850000,
        totalProfit: 1620000,
        avgCostRate: 0.95,
        drgGroupCount: 42,
        cmi: 1.8523,
        lowRiskMortalityRate: 0.8,
        lowRiskDeathCount: 5,
        lowRiskTotalCount: 625
    }

    // 趋势模拟
    const trends = {
        cost: [
            { date: '2024-01', value: 0.92 },
            { date: '2024-02', value: 0.94 },
            { date: '2024-03', value: 0.91 },
            { date: '2024-04', value: 0.98 },
            { date: '2024-05', value: 0.95 },
            { date: '2024-06', value: 0.93 }
        ],
        cmi: [
            { date: '2024-01', value: 1.75 },
            { date: '2024-02', value: 1.78 },
            { date: '2024-03', value: 1.80 },
            { date: '2024-04', value: 1.82 },
            { date: '2024-05', value: 1.84 },
            { date: '2024-06', value: 1.85 }
        ]
    }

    // 分布模拟
    const distribution = {
        drg: [
            { name: '循环系统疾病', value: 35 },
            { name: '呼吸系统疾病', value: 25 },
            { name: '消化系统疾病', value: 20 },
            { name: '神经系统疾病', value: 15 },
            { name: '其他', value: 5 }
        ],
        cost: [
            { name: '药品费', value: 30 },
            { name: '耗材费', value: 25 },
            { name: '检查费', value: 20 },
            { name: '手术费', value: 15 },
            { name: '护理费', value: 10 }
        ]
    }

    // 表格数据模拟
    const tableData = Array.from({ length: 15 }).map((_, index) => ({
        id: `ITEM_${index + 1}`,
        name: dimension === 'department' ? `科室 ${index + 1}` :
            dimension === 'doctor' ? `医生 ${index + 1}` :
                dimension === 'drg' ? `DRG组 ${index + 1}` : `项目 ${index + 1}`,
        caseCount: Math.floor(Math.random() * 100) + 10,
        totalRevenue: Math.floor(Math.random() * 1000000) + 100000,
        totalCost: Math.floor(Math.random() * 900000) + 90000,
        profit: Math.floor(Math.random() * 200000) - 50000,
        cmi: Number((1 + Math.random()).toFixed(4)),
        costRate: Number((0.8 + Math.random() * 0.4).toFixed(4))
    }))

    return {
        overview: baseOverview,
        trends,
        distribution,
        tableData
    }
}
