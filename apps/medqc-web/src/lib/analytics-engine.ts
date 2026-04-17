export type InsightType = 'achievement' | 'warning' | 'opportunity' | 'risk'

export interface TimeRange {
  start: string
  end: string
  granularity: 'day' | 'week' | 'month'
}

export interface AnalyticsInsight {
  title: string
  description: string
  recommendation: string
  type: InsightType
}

function daysBetween(start: string, end: string): number {
  const startTs = new Date(start).getTime()
  const endTs = new Date(end).getTime()
  if (Number.isNaN(startTs) || Number.isNaN(endTs) || endTs < startTs) {
    return 0
  }
  return Math.max(0, Math.floor((endTs - startTs) / (24 * 60 * 60 * 1000)))
}

function buildInsights(range: TimeRange, department?: string): AnalyticsInsight[] {
  const windowDays = daysBetween(range.start, range.end)
  const deptText = department?.trim() ? `（${department}）` : ''

  const insights: AnalyticsInsight[] = [
    {
      title: `质控趋势稳定${deptText}`,
      description: `近 ${windowDays || 1} 天内，关键指标波动处于可控范围。`,
      recommendation: '继续保持规则执行一致性，并关注低频高风险问题。',
      type: 'achievement',
    },
    {
      title: `时效性问题需关注${deptText}`,
      description: '个别记录存在时间节点填写延迟，影响总体及时性评分。',
      recommendation: '建议在交班后 2 小时内完成关键节点补录。',
      type: 'warning',
    },
    {
      title: `结构化提取可继续优化${deptText}`,
      description: '病程长文本存在可结构化字段，适合进一步提升自动抽取准确率。',
      recommendation: '优先对病程与出院记录做模板化字段对齐。',
      type: 'opportunity',
    },
  ]

  if (windowDays > 20) {
    insights.push({
      title: `长周期复盘风险${deptText}`,
      description: '周期拉长后，规则执行偏差可能被累计放大。',
      recommendation: '建议按周生成质量复盘，尽早发现策略漂移。',
      type: 'risk',
    })
  }

  return insights
}

export const analyticsEngine = {
  async generateInsights(range: TimeRange, department?: string): Promise<AnalyticsInsight[]> {
    return buildInsights(range, department)
  },
}
