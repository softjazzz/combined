import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import QCAlertPanel from '../QCAlertPanel.vue'
import { integratedQCEngine } from '@/services/integrated-qc-engine'
import { urgeDefect, markDefectRemediated, approveDefect, rejectDefect, exportDefects } from '@/api/defects'
import axios from 'axios'

vi.mock('@/services/integrated-qc-engine', () => ({
  integratedQCEngine: { executeQualityControl: vi.fn() },
}))

vi.mock('axios', () => ({ default: { post: vi.fn() } }))

vi.mock('@/api/defects', () => ({
  urgeDefect: vi.fn(),
  markDefectRemediated: vi.fn(),
  approveDefect: vi.fn(),
  rejectDefect: vi.fn(),
  exportDefects: vi.fn(),
}))

const ButtonStub = {
  emits: ['click'],
  template: '<button type="button" @click="$emit(\'click\')"><slot /></button>',
}

const SlotStub = { template: '<div><slot /></div>' }

describe('QCAlertPanel 合成问题不能操作持久化缺陷', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(integratedQCEngine.executeQualityControl).mockResolvedValue({
      ruleResults: [
        {
          isCompliant: false,
          ruleName: '首页完整性',
          findings: [
            { severity: 'major', description: '首页缺少必填项', recommendation: '补充首页内容' },
          ],
        },
      ],
    } as Awaited<ReturnType<typeof integratedQCEngine.executeQualityControl>>)
    vi.mocked(axios.post).mockResolvedValue({
      data: {
        data: {
          rule_issues: [
            { severity: 'error', dimension: 'format', description: '编码格式错误' },
          ],
          llm_issues: [
            { severity: 'warning', dimension: 'merge', description: '建议核对合并编码' },
          ],
        },
      },
    })
  })

  it('保留查看和定位动作，但三个来源的合成 ID 均不能操作或导出全局缺陷', async () => {
    const wrapper = mount(QCAlertPanel, {
      props: { frontpage: null, visitId: 'visit-1', patientId: 'patient-1' },
      global: {
        stubs: {
          'a-button': ButtonStub,
          'a-badge': SlotStub,
          'a-tag': SlotStub,
          'a-divider': true,
        },
      },
    })

    await wrapper.setProps({ frontpage: { patient_name: '测试患者' } })
    await flushPromises()
    await wrapper.find('.qc-trigger-btn').trigger('click')

    expect(wrapper.text()).toContain('首页缺少必填项')
    expect(wrapper.text()).toContain('查看详情')
    expect(wrapper.text()).not.toContain('催办')
    expect(wrapper.text()).not.toContain('标记已整改')
    expect(wrapper.text()).not.toContain('审核通过')
    expect(wrapper.text()).not.toContain('审核存疑')
    expect(wrapper.text()).not.toContain('导出')
    expect(wrapper.find('.action-more-btn').exists()).toBe(false)

    await wrapper.find('.issue-actions button').trigger('click')
    expect(wrapper.emitted('action')?.[0]?.[0]).toMatchObject({ id: 'sys-0' })

    await wrapper.findAll('.qc-tab')[1].trigger('click')
    expect(wrapper.text()).toContain('编码格式错误')
    expect(wrapper.text()).toContain('建议核对合并编码')
    expect(wrapper.text()).toContain('修正编码')
    expect(wrapper.findAll('.action-more-btn')).toHaveLength(0)
    expect(wrapper.text()).not.toContain('催办')

    for (const button of wrapper.findAll('.issue-actions button')) {
      if (button.text().includes('忽略')) continue
      await button.trigger('click')
    }
    expect(wrapper.emitted('action')?.map(([issue]) => (issue as { id: string }).id)).toEqual([
      'sys-0',
      'coding-rule-0',
      'coding-llm-1',
    ])
    for (const action of [urgeDefect, markDefectRemediated, approveDefect, rejectDefect, exportDefects]) {
      expect(action).not.toHaveBeenCalled()
    }
    wrapper.unmount()
  })
})
