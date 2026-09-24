import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import QCResultTab from '../QCResultTab.vue'
import {
  approveDefect,
  exportDefects,
  markDefectRemediated,
  rejectDefect,
  urgeDefect,
} from '@/api/defects'

vi.mock('@/api/defects', () => ({
  approveDefect: vi.fn(),
  markDefectRemediated: vi.fn(),
  rejectDefect: vi.fn(),
  urgeDefect: vi.fn(),
  exportDefects: vi.fn(),
}))

const ButtonStub = {
  template: '<button type="button" @click="$emit(\'click\')"><slot /></button>',
}

const iconStub = { template: '<i />' }

function mountReport(activeTab: 'form' | 'coding' | 'cost') {
  return mount(QCResultTab, {
    props: {
      activeTab,
      patientId: 'patient-1',
      visitId: 'visit-1',
      snapshotState: {
        form: {
          analyzed: true,
          issues: [{ id: 'form-1', description: '首页问题', severity: 'error' }],
        },
        coding: {
          analyzed: true,
          issues: [{ id: 'coding-rule-1', description: '编码问题', severity: 'warning' }],
        },
        cost: {
          analyzed: true,
          issues: [{ id: '550e8400-e29b-41d4-a716-446655440000', description: '结算问题' }],
        },
      },
    },
    global: {
      stubs: {
        'a-button': ButtonStub,
        'a-spin': true,
        CheckCircleOutlined: iconStub,
      },
    },
  })
}

describe('QCResultTab 报告问题服务端操作保护', () => {
  it.each(['form', 'coding', 'cost'] as const)('%s 报告问题只保留本地查看动作', async (tab) => {
    const wrapper = mountReport(tab)

    expect(wrapper.text()).toContain('定位字段')
    expect(wrapper.text()).toContain('文书依据')
    expect(wrapper.text()).not.toContain('操作')
    expect(wrapper.text()).not.toContain('标记已整改')
    expect(wrapper.text()).not.toContain('审核通过')
    expect(wrapper.text()).not.toContain('导出')

    const issueButtons = wrapper.findAll('.qc-issue__action-bar button')
    expect(issueButtons).toHaveLength(3)
    for (const button of issueButtons) await button.trigger('click')
    expect(wrapper.emitted('locate-field')).toHaveLength(1)
    expect(wrapper.emitted('jump-evidence')).toHaveLength(1)
    expect(urgeDefect).not.toHaveBeenCalled()
    expect(markDefectRemediated).not.toHaveBeenCalled()
    expect(approveDefect).not.toHaveBeenCalled()
    expect(rejectDefect).not.toHaveBeenCalled()
    expect(exportDefects).not.toHaveBeenCalled()
    expect(wrapper.text()).not.toContain('已整改')
    expect(wrapper.text()).not.toContain('审核通过')
  })
})
