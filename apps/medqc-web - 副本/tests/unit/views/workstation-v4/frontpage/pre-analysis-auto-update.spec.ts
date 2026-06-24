import { mount } from '@vue/test-utils'
import { describe, expect, it, beforeEach, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  getPreGroupingHistory: vi.fn(),
  messageWarning: vi.fn(),
  messageSuccess: vi.fn(),
  messageError: vi.fn(),
}))

vi.mock('@/api/drg', () => ({
  getPreGroupingHistory: mocks.getPreGroupingHistory,
}))

vi.mock('ant-design-vue', () => ({
  message: {
    warning: mocks.messageWarning,
    success: mocks.messageSuccess,
    error: mocks.messageError,
  },
}))

vi.mock('@/utils/auth-token', () => ({
  getAccessToken: vi.fn(() => 'token'),
}))

import PreAnalysisView from '@/views/workstation-v4/frontpage/components/PreAnalysisView.vue'

async function flushPromises() {
  await Promise.resolve()
  await Promise.resolve()
}

describe('PreAnalysisView auto simulation version', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getPreGroupingHistory.mockResolvedValue([
      {
        simulation_id: 'pregrp-ZS-001-2',
        visit_id: 'ZS-001',
        document_id: 'DOC-2',
        version: 2,
        created_at: '2026-06-07T14:00:00Z',
        status: 'simulation',
        read_only: true,
        change_tracking: {
          previous_version: 1,
          current_version: 2,
          needs_regrouping: true,
          reason: 'tracked_input_changed',
          changed_fields: [
            { field: 'pdx_code', previous: 'I25.103', current: 'E11.900' },
            { field: 'total_fee', previous: 12000, current: 13800 },
          ],
        },
      },
    ])
  })

  it('shows latest simulation version and changed fields', async () => {
    const wrapper = mount(PreAnalysisView)
    await flushPromises()

    const versionBlock = wrapper.get('[data-testid="pre-grouping-version"]')
    expect(mocks.getPreGroupingHistory).toHaveBeenCalledWith('ZS-001')
    expect(versionBlock.text()).toContain('自动模拟版本')
    expect(versionBlock.text()).toContain('V2')
    expect(versionBlock.text()).toContain('检测到输入变化')
    expect(versionBlock.text()).toContain('主诊断')
    expect(versionBlock.text()).toContain('费用')
  })
})
