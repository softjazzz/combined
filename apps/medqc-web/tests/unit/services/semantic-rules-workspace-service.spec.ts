import { describe, expect, it } from 'vitest'
import {
  buildSemanticKpiCards,
  buildSemanticRuleRowActionModel,
  buildSemanticRuleRowStatusModel,
  buildSemanticStatsFromRules,
  buildSemanticWorkspaceQuery,
  filterSemanticRules,
  normalizeSemanticRule,
  parseSemanticWorkspaceQuery,
  toSemanticRulePage,
} from '@/views/workstation-v4/semantic-rules/service'

describe('semantic rules workspace service', () => {
  const seedRules = [
    normalizeSemanticRule({
      rule_id: 'SC-101',
      rule_code: 'SC-101',
      name: '手术记录缺项',
      description: '检查手术记录完整性',
      category: '手术相关记录',
      complexity: '高复杂度',
      defect_level: '严重缺陷',
      applicable_documents: ['operation_record'],
    }),
    normalizeSemanticRule({
      rule_id: 'SC-102',
      rule_code: 'SC-102',
      name: '出院记录缺项',
      description: '检查出院记录完整性',
      category: '(死亡)出院记录',
      complexity: '中复杂度',
      defect_level: '一般缺陷',
      applicable_documents: ['discharge_record'],
    }),
    normalizeSemanticRule({
      rule_id: 'SC-103',
      name: '病程记录缺项',
      description: '检查病程记录完整性',
      category: '病程记录',
      complexity: '低复杂度',
      defect_level: '轻微缺陷',
      applicable_documents: ['progress_note'],
    }),
  ]

  it('应能按关键词与筛选条件过滤规则', () => {
    const byKeyword = filterSemanticRules(seedRules, {
      keyword: '手术',
      complexity: '',
      defectLevel: '',
      documentType: '',
    })
    expect(byKeyword).toHaveLength(1)
    expect(byKeyword[0]?.rule_id).toBe('SC-101')

    const byFilters = filterSemanticRules(seedRules, {
      keyword: '',
      complexity: '中复杂度',
      defectLevel: '一般缺陷',
      documentType: '出院记录',
    })
    expect(byFilters).toHaveLength(1)
    expect(byFilters[0]?.rule_id).toBe('SC-102')
  })

  it('应能分页切片', () => {
    expect(toSemanticRulePage(seedRules, 1, 2).map((item) => item.rule_id)).toEqual([
      'SC-101',
      'SC-102',
    ])
    expect(toSemanticRulePage(seedRules, 2, 2).map((item) => item.rule_id)).toEqual(['SC-103'])
  })

  it('应能解析与构建规则库查询参数', () => {
    const parsed = parseSemanticWorkspaceQuery({
      keyword: '出院',
      page: '2',
      pageSize: '50',
      defectLevel: '严重缺陷',
    })
    expect(parsed).toEqual({
      keyword: '出院',
      complexity: '',
      defectLevel: '严重缺陷',
      documentType: '',
      page: 2,
      pageSize: 50,
    })

    const built = buildSemanticWorkspaceQuery(
      { tab: 'rules' },
      {
        keyword: '手术',
        complexity: '高复杂度',
        defectLevel: '',
        documentType: '',
        page: 1,
        pageSize: 20,
      },
    )
    expect(built).toEqual({
      tab: 'rules',
      keyword: '手术',
      complexity: '高复杂度',
    })
  })

  it('应能回退计算统计分布', () => {
    const stats = buildSemanticStatsFromRules(seedRules, {
      total_rules: 0,
      complexity_distribution: {},
      defect_level_distribution: {},
    })
    expect(stats.total_rules).toBe(3)
    expect(stats.complexity_distribution['高复杂度']).toBe(1)
    expect(stats.defect_level_distribution['轻微缺陷']).toBe(1)
  })

  it('应优先选择可用业务规则编号作为 rule_id', () => {
    const normalized = normalizeSemanticRule({
      id: '22d3f60f-5dd8-40dc-8f00-40aee3d8f509',
      rule_id: '3.1.1',
      rule_code: 'SC-001',
      name: '示例规则',
      description: '',
      category: '入院记录',
      complexity: '低复杂度',
      defect_level: '严重缺陷',
      applicable_documents: ['admission_record'],
    })
    expect(normalized.rule_id).toBe('SC-001')
  })

  it('应生成固定四卡 KPI 展示模型', () => {
    const cards = buildSemanticKpiCards({
      stats: {
        total_rules: 179,
        rule_categories: ['病程记录'],
        complexity_distribution: {},
        defect_level_distribution: {},
      },
      criticalDefectCount: 76,
      riskDensity: '42%',
      lastRefreshedLabel: '18:34',
    })

    expect(cards).toHaveLength(4)
    expect(cards.map((item) => item.key)).toEqual(['total', 'critical', 'density', 'sync'])
    expect(cards.map((item) => item.tone)).toEqual(['brand', 'danger', 'warning', 'safe'])
    expect(cards[0]?.value).toBe('179')
  })

  it('应将行级状态映射为主次状态模型', () => {
    const primaryHighRisk = buildSemanticRuleRowStatusModel(seedRules[0]!)
    expect(primaryHighRisk.primaryLabel).toBe('严重缺陷')
    expect(primaryHighRisk.primaryTone).toBe('danger')
    expect(primaryHighRisk.secondaryLabel).toBe('高复杂度')
    expect(primaryHighRisk.secondaryTone).toBe('danger')

    const primaryLowRisk = buildSemanticRuleRowStatusModel(seedRules[2]!)
    expect(primaryLowRisk.primaryTone).toBe('safe')
    expect(primaryLowRisk.secondaryTone).toBe('neutral')
  })

  it('应固定行级主次操作文案', () => {
    const action = buildSemanticRuleRowActionModel()
    expect(action).toEqual({
      primaryLabel: '查看结果',
      secondaryLabel: '评估',
    })
  })
})
