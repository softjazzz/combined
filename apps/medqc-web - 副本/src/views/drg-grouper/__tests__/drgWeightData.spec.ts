import { describe, expect, it } from 'vitest'

import { DRG_WEIGHT_DATASET_META, LOW_RISK_DRG_CODES, getDrgWeightInfo } from '../drgWeightData'

describe('drgWeightData', () => {
  it('读取 2024 绩效监测 DRG 权重数据源', () => {
    expect(DRG_WEIGHT_DATASET_META.groupCount).toBe(654)
    expect(DRG_WEIGHT_DATASET_META.lowRiskCount).toBe(100)

    const info = getDrgWeightInfo('AG19')
    expect(info?.drgName).toBe('非同胞全相合异基因造血干细胞移植')
    expect(info?.weight).toBe(13.65)
    expect(info?.isLowRisk).toBe(false)
  })

  it('保留低风险组标识', () => {
    const info = getDrgWeightInfo('BV39')

    expect(info?.drgName).toBe('头痛')
    expect(info?.weight).toBe(0.42)
    expect(info?.isLowRisk).toBe(true)
    expect(LOW_RISK_DRG_CODES.has('BV39')).toBe(true)
  })
})
