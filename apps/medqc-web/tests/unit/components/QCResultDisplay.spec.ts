import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import QCResultDisplay from '@/components/qc/QCResultDisplay.vue'
import type { QCResult } from '@/types/supabase'
import type { QCIssue, QCSuggestion, QCRuleResult } from '@/types/quality-control'

describe('QCResultDisplay', () => {
  const mockIssues: QCIssue[] = [
    {
      id: '1',
      ruleName: '主诉完整性检查',
      ruleId: 'rule-001',
      description: '主诉描述不完整',
      severity: 'major',
      category: '内容完整性',
      location: '主诉',
      suggestion: '请补充完整的主诉信息',
      canAppeal: true
    },
    {
      id: '2',
      ruleName: '诊断一致性检查',
      ruleId: 'rule-002',
      description: '诊断与检查结果不一致',
      severity: 'critical',
      category: '逻辑一致性',
      location: '诊断',
      suggestion: '请核对诊断与检查结果',
      canAppeal: true
    }
  ]

  const mockSuggestions: QCSuggestion[] = [
    {
      id: '1',
      category: '内容改进',
      title: '补充病史信息',
      description: '建议补充患者既往病史',
      priority: 'high',
      actionRequired: true
    },
    {
      id: '2',
      category: '格式规范',
      title: '规范日期格式',
      description: '建议使用标准日期格式',
      priority: 'medium',
      actionRequired: false
    }
  ]

  const mockRuleResults: QCRuleResult[] = [
    {
      ruleId: 'rule-001',
      ruleName: '主诉完整性检查',
      passed: false,
      score: 70,
      maxScore: 100,
      details: '主诉描述不完整',
      executionTime: 120,
      confidence: 0.85
    },
    {
      ruleId: 'rule-002',
      ruleName: '诊断一致性检查',
      passed: true,
      score: 95,
      maxScore: 100,
      details: '诊断与检查结果一致',
      executionTime: 150,
      confidence: 0.92
    }
  ]

  type QCResultDisplayMock = QCResult & {
    overall_score: number
    overall_grade: 'A' | 'B' | 'C'
    analysis_date: string
    rule_results: QCRuleResult[]
  }

  const mockResult: QCResultDisplayMock = {
    id: 'qc-001',
    record_id: 'record-001',
    score: 82,
    grade: 'B',
    overall_score: 82,
    overall_grade: 'B',
    analysis_date: '2024-01-01T10:00:00Z',
    issues: mockIssues,
    suggestions: mockSuggestions,
    summary: '病案存在少量问题',
    raw_analysis: 'raw',
    category_scores: [],
    confidence_score: 0.88,
    rule_version: 'v1',
    analysis_time: '2024-01-01T10:00:00Z',
    reviewer_id: null,
    is_reviewed: false,
    review_notes: '',
    rule_results: mockRuleResults
  }

  it('renders score and grade information', () => {
    const wrapper = mount(QCResultDisplay, {
      props: {
        result: mockResult
      }
    })

    expect(wrapper.text()).toContain('82')
    expect(wrapper.text()).toContain('B级质控')
    expect(wrapper.text()).toContain('良好 - 病案质量较好，存在少量问题')

    const scoreNode = wrapper.find('.text-3xl.font-bold')
    expect(scoreNode.text()).toBe('82')
    expect(scoreNode.classes()).toContain('text-blue-400')
  })

  it('renders issues, suggestions, and rule results', () => {
    const wrapper = mount(QCResultDisplay, {
      props: {
        result: mockResult
      }
    })

    expect(wrapper.text()).toContain('主诉完整性检查')
    expect(wrapper.text()).toContain('诊断一致性检查')
    expect(wrapper.text()).toContain('补充病史信息')
    expect(wrapper.text()).toContain('规范日期格式')
    expect(wrapper.text()).toContain('主诉描述不完整')
    expect(wrapper.text()).toContain('诊断与检查结果一致')
  })

  it('shows issue and suggestion counts', () => {
    const wrapper = mount(QCResultDisplay, {
      props: {
        result: mockResult
      }
    })

    expect(wrapper.text()).toContain('严重问题')
    expect(wrapper.text()).toContain('总问题数')
    expect(wrapper.text()).toContain('2')
    expect(wrapper.text()).toContain('改善建议 (2)')
    expect(wrapper.text()).toContain('规则执行结果')
  })
})
