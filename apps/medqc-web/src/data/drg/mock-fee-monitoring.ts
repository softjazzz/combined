/**
 * 费用监测模块 Mock 数据
 * 用于费用结构分析、趋势预测等功能
 */

export interface FeeComposition {
    drugFee: number       // 药品费
    examFee: number       // 检查费
    treatmentFee: number  // 治疗费
    materialFee: number   // 材料费
    surgeryFee: number    // 手术费
    bedFee: number        // 床位费
    nursingFee: number    // 护理费
    otherFee: number      // 其他费用
}

export interface FeeTrendPoint {
    day: number           // 住院第几天
    cumulative: number    // 累计费用
    daily: number         // 当日费用
}

export interface HighValueMaterial {
    id: string
    name: string
    category: string      // 分类：支架/起搏器/人工关节等
    quantity: number
    unitPrice: number
    totalPrice: number
    inCatalog: boolean    // 是否在医保目录内
    usedDate: string
}

export interface FeeWarningRecord {
    timestamp: string
    warningLevel: 'normal' | 'attention' | 'warning' | 'critical'
    costRate: number
    actualCost: number
    baselinePayment: number
    message: string
}

/**
 * 生成费用构成数据
 */
export function generateFeeComposition(totalCost: number): FeeComposition {
    // 根据总费用生成合理的费用分布
    const drugRatio = 0.25 + Math.random() * 0.15      // 25-40%
    const materialRatio = 0.20 + Math.random() * 0.15  // 20-35%
    const examRatio = 0.15 + Math.random() * 0.10      // 15-25%
    const surgeryRatio = 0.10 + Math.random() * 0.10   // 10-20%
    const treatmentRatio = 0.08 + Math.random() * 0.07 // 8-15%
    const bedRatio = 0.03 + Math.random() * 0.02       // 3-5%
    const nursingRatio = 0.02 + Math.random() * 0.02   // 2-4%

    const sum = drugRatio + materialRatio + examRatio + surgeryRatio + treatmentRatio + bedRatio + nursingRatio

    return {
        drugFee: Math.round(totalCost * drugRatio / sum),
        materialFee: Math.round(totalCost * materialRatio / sum),
        examFee: Math.round(totalCost * examRatio / sum),
        surgeryFee: Math.round(totalCost * surgeryRatio / sum),
        treatmentFee: Math.round(totalCost * treatmentRatio / sum),
        bedFee: Math.round(totalCost * bedRatio / sum),
        nursingFee: Math.round(totalCost * nursingRatio / sum),
        otherFee: totalCost - Math.round(totalCost * (drugRatio + materialRatio + examRatio + surgeryRatio + treatmentRatio + bedRatio + nursingRatio) / sum)
    }
}

/**
 * 生成费用趋势数据
 */
export function generateFeeTrend(totalCost: number, days: number = 10): FeeTrendPoint[] {
    const trend: FeeTrendPoint[] = []
    let cumulative = 0

    for (let day = 1; day <= days; day++) {
        // 模拟费用增长曲线：前期快速增长（手术日），后期平缓
        let dailyIncrease: number
        if (day === 1) {
            dailyIncrease = totalCost * 0.15 // 入院第一天 15%
        } else if (day === 2 || day === 3) {
            dailyIncrease = totalCost * 0.25 // 手术日及术后第一天 25%
        } else if (day <= 5) {
            dailyIncrease = totalCost * 0.15 // 术后恢复期 15%
        } else {
            dailyIncrease = totalCost * 0.05 // 后期平稳 5%
        }

        cumulative += dailyIncrease
        trend.push({
            day,
            cumulative: Math.min(cumulative, totalCost),
            daily: dailyIncrease
        })
    }

    // 确保最后一天累计费用等于总费用
    if (trend.length > 0) {
        const lastPoint = trend[trend.length - 1]
        lastPoint.cumulative = totalCost
    }

    return trend
}

/**
 * 生成高值耗材数据
 */
export function generateHighValueMaterials(admissionId: string): HighValueMaterial[] {
    const materials: HighValueMaterial[] = []

    // 根据住院号随机生成不同的高值耗材
    const seed = admissionId.charCodeAt(admissionId.length - 1) % 5

    if (seed === 0 || seed === 1) {
        // 心内科场景：冠脉支架
        materials.push({
            id: `${admissionId}-mat-001`,
            name: '药物洗脱冠脉支架',
            category: '心血管介入器材',
            quantity: 2,
            unitPrice: 15800,
            totalPrice: 31600,
            inCatalog: true,
            usedDate: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString()
        })
        materials.push({
            id: `${admissionId}-mat-002`,
            name: '球囊扩张导管',
            category: '心血管介入器材',
            quantity: 1,
            unitPrice: 6500,
            totalPrice: 6500,
            inCatalog: true,
            usedDate: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString()
        })
    } else if (seed === 2) {
        // 骨科场景：人工关节
        materials.push({
            id: `${admissionId}-mat-001`,
            name: '人工髋关节假体',
            category: '骨科植入物',
            quantity: 1,
            unitPrice: 28000,
            totalPrice: 28000,
            inCatalog: true,
            usedDate: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString()
        })
    } else if (seed === 3) {
        // 心脏外科：起搏器
        materials.push({
            id: `${admissionId}-mat-001`,
            name: '双腔心脏起搏器',
            category: '心脏起搏器',
            quantity: 1,
            unitPrice: 45000,
            totalPrice: 45000,
            inCatalog: true,
            usedDate: new Date(Date.now() - 4 * 24 * 60 * 60 * 1000).toISOString()
        })
    }

    return materials
}

/**
 * 生成费用预警记录
 */
export function generateFeeWarningRecords(
    admissionId: string,
    currentCost: number,
    baselinePayment: number | null
): FeeWarningRecord[] {
    if (!baselinePayment) return []

    const records: FeeWarningRecord[] = []
    const days = 8

    for (let day = 1; day <= days; day++) {
        const dayCost = currentCost * (day / days)
        const costRate = (dayCost / baselinePayment) * 100

        let warningLevel: FeeWarningRecord['warningLevel'] = 'normal'
        let message = '费用正常'

        if (costRate >= 120) {
            warningLevel = 'critical'
            message = '费用严重超标，建议立即控费'
        } else if (costRate >= 100) {
            warningLevel = 'warning'
            message = '费用已超付费标准，需关注后续费用'
        } else if (costRate >= 80) {
            warningLevel = 'attention'
            message = '费用接近付费标准，建议控制高值耗材使用'
        }

        records.push({
            timestamp: new Date(Date.now() - (days - day) * 24 * 60 * 60 * 1000).toISOString(),
            warningLevel,
            costRate,
            actualCost: dayCost,
            baselinePayment,
            message
        })
    }

    return records
}

/**
 * 获取费用详情（综合接口）
 */
export function getMockFeeDetails(admissionId: string, totalCost: number, baselinePayment: number | null) {
    return {
        composition: generateFeeComposition(totalCost),
        trend: generateFeeTrend(totalCost),
        highValueMaterials: generateHighValueMaterials(admissionId),
        warningRecords: generateFeeWarningRecords(admissionId, totalCost, baselinePayment)
    }
}
