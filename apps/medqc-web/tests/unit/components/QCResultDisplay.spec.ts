import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import QCResultDisplay from '@/components/qc/QCResultDisplay.vue'
import type { QCResult, QCIssue, QCSuggestion, QCRuleResult } from '@/types/quality-control'

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

  const mockResult: QCResult = {
    id: 'qc-001',
    recordId: 'record-001',
    overallScore: 82,
    overallGrade: 'B',
    analysisDate: '2024-01-01T10:00:00Z',
    issues: mockIssues,
    suggestions: mockSuggestions,
    ruleResults: mockRuleResults
  }

  describe('组件渲染', () => {
    it('应该正确渲染组件', () => {
      const wrapper = mount(QCResultDisplay, {
        props: {
          result: mockResult
        }
      })

      expect(wrapper.exists()).toBe(true)
      expect(wrapper.find('.qc-result-display').exists()).toBe(true)
    })

    it('应该显示总体评分', () => {
      const wrapper = mount(QCResultDisplay, {
        props: {
          result: mockResult
        }
      })

      expect(wrapper.text()).toContain('82')
      expect(wrapper.text()).toContain('B')
    })
  })

  describe('评分展示', () => {
    it('应该正确显示评分颜色', () => {
      const wrapper = mount(QCResultDisplay, {
        props: {
          result: mockResult
        }
      })

      const scoreColor = wrapper.vm.getScoreColor(82)
      expect(scoreColor).toBe('text-blue-400')
    })

    it('应该正确显示优秀评分颜色', () => {
      const wrapper = mount(QCResultDisplay, {
        props: {
          result: { ...mockResult, overallScore: 95 }
        }
      })

      const scoreColor = wrapper.vm.getScoreColor(95)
      expect(scoreColor).toBe('text-emerald-400')
    })

    it('应该正确显示不及格评分颜色', () => {
      const wrapper = mount(QCResultDisplay, {
        props: {
          result: { ...mockResult, overallScore: 65 }
        }
      })

      const scoreColor = wrapper.vm.getScoreColor(65)
      expect(scoreColor).toBe('text-red-400')
    })
  })

  describe('问题列表', () => {
    it('应该正确显示问题数量', () => {
      const wrapper = mount(QCResultDisplay, {
        props: {
          result: mockResult
        }
      })

      expect(wrapper.vm.totalIssuesCount).toBe(2)
    })

    it('应该正确统计严重问题数量', () => {
      const wrapper = mount(QCResultDisplay, {
        props: {
          result: mockResult
        }
      })

      expect(wrapper.vm.criticalIssuesCount).toBe(2) // major + critical
    })

    it('应该支持问题筛选', async () => {
      const wrapper = mount(QCResultDisplay, {
        props: {
          result: mockResult
        }
      })

      // 筛选严重问题
      wrapper.vm.issueFilter = 'critical'
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.filteredIssues).toHaveLength(1)
      expect(wrapper.vm.filteredIssues[0].severity).toBe('critical')
    })

    it('应该显示所有问题', () => {
      const wrapper = mount(QCResultDisplay, {
        props: {
          result: mockResult
        }
      })

      wrapper.vm.issueFilter = 'all'
      expect(wrapper.vm.filteredIssues).toHaveLength(2)
    })
  })

  describe('严重程度标签', () => {
    it('应该正确显示严重程度标签', () => {
      const wrapper = mount(QCResultDisplay, {
        props: {
          result: mockResult
        }
      })

      expect(wrapper.vm.getSeverityLabel('critical')).toBe('严重')
      expect(wrapper.vm.getSeverityLabel('major')).toBe('重要')
      expect(wrapper.vm.getSeverityLabel('minor')).toBe('轻微')
      expect(wrapper.vm.getSeverityLabel('low')).toBe('提示')
    })

    it('应该正确显示严重程度颜色', () => {
      const wrapper = mount(QCResultDisplay, {
        props: {
          result: mockResult
        }
      })

      expect(wrapper.vm.getSeverityColor('critical')).toBe('red')
      expect(wrapper.vm.getSeverityColor('major')).toBe('orange')
      expect(wrapper.vm.getSeverityColor('minor')).toBe('yellow')
      expect(wrapper.vm.getSeverityColor('low')).toBe('blue')
    })
  })

  describe('建议展示', () => {
    it('应该正确显示建议列表', () => {
      const wrapper = mount(QCResultDisplay, {
        props: {
          result: mockResult
        }
      })

      expect(wrapper.vm.result.suggestions).toHaveLength(2)
      expect(wrapper.vm.result.suggestions[0].title).toBe('补充病史信息')
    })

    it('应该正确显示优先级标签', () => {
      const wrapper = mount(QCResultDisplay, {
        props: {
          result: mockResult
        }
      })

      expect(wrapper.vm.getPriorityLabel('high')).toBe('高优先级')
      expect(wrapper.vm.getPriorityLabel('medium')).toBe('中优先级')
      expect(wrapper.vm.getPriorityLabel('low')).toBe('低优先级')
    })

    it('应该正确显示优先级颜色', () => {
      const wrapper = mount(QCResultDisplay, {
        props: {
          result: mockResult
        }
      })

      expect(wrapper.vm.getPriorityColor('high')).toBe('red')
      expect(wrapper.vm.getPriorityColor('medium')).toBe('orange')
      expect(wrapper.vm.getPriorityColor('low')).toBe('blue')
    })
  })

  describe('规则结果', () => {
    it('应该正确显示规则结果列表', () => {
      const wrapper = mount(QCResultDisplay, {
        props: {
          result: mockResult
        }
      })

      expect(wrapper.vm.result.ruleResults).toHaveLength(2)
    })

    it('应该正确显示规则通过状态', () => {
      const wrapper = mount(QCResultDisplay, {
        props: {
          result: mockResult
        }
      })

      const passedRule = wrapper.vm.result.ruleResults[1]
      const failedRule = wrapper.vm.result.ruleResults[0]

      expect(passedRule.passed).toBe(true)
      expect(failedRule.passed).toBe(false)
    })

    it('应该正确显示规则评分', () => {
      const wrapper = mount(QCResultDisplay, {
        props: {
          result: mockResult
        }
      })

      expect(wrapper.vm.result.ruleResults[0].score).toBe(70)
      expect(wrapper.vm.result.ruleResults[1].score).toBe(95)
    })
  })

  describe('用户交互', () => {
    it('应该触发高亮问题事件', async () => {
      const wrapper = mount(QCResultDisplay, {
        props: {
          result: mockResult
        }
      })

      wrapper.vm.$emit('highlight-issue', mockIssues[0])

      expect(wrapper.emitted('highlight-issue')).toBeTruthy()
      expect(wrapper.emitted('highlight-issue')?.[0][0]).toEqual(mockIssues[0])
    })
  })

  describe('等级展示', () => {
    it('应该正确显示等级颜色', () => {
      const wrapper = mount(QCResultDisplay, {
        props: {
          result: mockResult
        }
      })

      expect(wrapper.vm.getGradeColor('A')).toBe('green')
      expect(wrapper.vm.getGradeColor('B')).toBe('blue')
      expect(wrapper.vm.getGradeColor('C')).toBe('orange')
      expect(wrapper.vm.getGradeColor('D')).toBe('red')
    })

    it('应该正确显示评分描述', () => {
      const wrapper = mount(QCResultDisplay, {
        props: {
          result: mockResult
        }
      })

      const description = wrapper.vm.getScoreDescription(82)
      expect(description).toContain('良好')
    })
  })
})

