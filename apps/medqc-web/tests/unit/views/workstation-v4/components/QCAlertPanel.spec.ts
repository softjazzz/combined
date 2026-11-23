import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import QCAlertPanel from '@/views/workstation-v4/components/QCAlertPanel.vue'

const { mockApiPost, mockAxiosPost, mockExecuteQC } = vi.hoisted(() => ({
  mockApiPost: vi.fn(),
  mockAxiosPost: vi.fn(),
  mockExecuteQC: vi.fn(),
}))

vi.mock('@/services/apiService', () => ({
  apiClient: {
    post: mockApiPost,
  },
}))

vi.mock('axios', () => ({
  default: {
    post: mockAxiosPost,
  },
}))

vi.mock('@/services/integrated-qc-engine', () => ({
  integratedQCEngine: {
    executeQualityControl: mockExecuteQC,
  },
}))

vi.mock('@/api/defects', () => ({
  urgeDefect: vi.fn(),
  markDefectRemediated: vi.fn(),
  approveDefect: vi.fn(),
  rejectDefect: vi.fn(),
  exportDefects: vi.fn(),
}))

vi.mock('@/components/layout/workstationConfirmation', () => ({
  useWorkstationConfirmation: () => ({ confirm: vi.fn() }),
}))

describe('QCAlertPanel 使用 apiClient 调用编码质控', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    mockExecuteQC.mockResolvedValue({ ruleResults: [] })
    mockApiPost.mockResolvedValue({
      data: {
        data: {
          rule_issues: [
            {
              severity: 'error',
              dimension: 'format',
              description: 'ICD 编码格式异常',
              suggestion: '修正主诊断编码',
            },
          ],
          llm_issues: [],
        },
      },
    })
  })

  it('通过 apiClient 而非裸 axios 请求编码质控并透传三键标识', async () => {
    const wrapper = mount(QCAlertPanel, {
      props: {
        frontpage: null,
        visitId: 'V-300',
        patientId: 'P-300',
        instituteId: 'H-300',
      },
      global: {
        stubs: {
          'a-badge': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span><slot /></span>' },
          'a-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
          'a-divider': { template: '<span />' },
          'a-dropdown': { template: '<div><slot /></div>' },
          'a-menu': { template: '<div><slot /></div>' },
          'a-menu-item': { template: '<div><slot /></div>' },
          'a-menu-divider': { template: '<hr />' },
        },
      },
    })

    await wrapper.setProps({
      frontpage: { patient_name: '张三', institute_id: 'H-300' },
    })
    await flushPromises()

    expect(mockAxiosPost).not.toHaveBeenCalled()
    expect(mockApiPost).toHaveBeenCalledWith(
      '/api/v1/qc/coding-qc/check',
      {
        institute_id: 'H-300',
        visit_id: 'V-300',
        patient_id: 'P-300',
      },
      expect.objectContaining({ timeout: expect.any(Number) }),
    )

    wrapper.unmount()
  })
})
