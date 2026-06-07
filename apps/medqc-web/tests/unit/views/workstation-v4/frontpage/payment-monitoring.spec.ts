import { mount } from '@vue/test-utils'
import { describe, expect, it, beforeEach, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  simulatePaymentMonitoring: vi.fn(),
  messageSuccess: vi.fn(),
  messageWarning: vi.fn(),
}))

vi.mock('@/api/drg', () => ({
  simulatePaymentMonitoring: mocks.simulatePaymentMonitoring,
}))

vi.mock('echarts', () => ({
  init: vi.fn(() => ({
    setOption: vi.fn(),
    dispose: vi.fn(),
  })),
}))

vi.mock('@/stores/drgDataset', () => ({
  useDrgDatasetStore: () => ({
    hasUploadedData: false,
    records: [],
  }),
}))

vi.mock('@/utils/drgMockMode', () => ({
  isDrgMockModeEnabled: vi.fn(() => false),
  onDrgMockModeChange: vi.fn(() => vi.fn()),
}))

vi.mock('@/utils/drgMockExport', () => ({
  exportDrgMockReport: vi.fn(),
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: mocks.messageSuccess,
    warning: mocks.messageWarning,
  },
}))

import PaymentMonitoringView from '@/views/workstation-v4/frontpage/components/PaymentMonitoringView.vue'

async function flushPromises() {
  await Promise.resolve()
  await Promise.resolve()
}

const simpleStub = {
  template: '<div><slot /><slot name="overlay" /></div>',
}

describe('PaymentMonitoringView backend simulation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.simulatePaymentMonitoring.mockResolvedValue({
      result_type: 'payment_monitoring',
      config_version_id: 'published-default',
      overview: {
        case_count: 1,
        actual_cost: 10000,
        expected_payment: 12000,
        profit_loss: 2000,
        payment_rate: 120,
        loss_case_count: 0,
        base_group: 1,
        high_cost_group: 0,
        low_cost_group: 0,
      },
      records: [
        {
          case_id: 'CASE-1',
          department: '心内科',
          group_code: 'DRG-A',
          group_name: '冠心病组',
          actual_cost: 10000,
          expected_payment: 12000,
          cost_ratio: 0.83,
          risk_level: 'low',
        },
      ],
      cost_control_hints: [],
      safety_warning: '付费监测为模拟测算，不写入正式医保结算清单或正式 DRG/DIP 结果。',
      writes_formal_tables: false,
    })
  })

  it('loads backend simulation and shows simulated data scope', async () => {
    const wrapper = mount(PaymentMonitoringView, {
      global: {
        mocks: {
          $router: { back: vi.fn() },
        },
        stubs: {
          DatasetUploadPanel: simpleStub,
          'a-select': simpleStub,
          'a-select-option': simpleStub,
          'a-dropdown': simpleStub,
          'a-menu': simpleStub,
          'a-menu-item': simpleStub,
          'a-segmented': simpleStub,
          'a-tag': simpleStub,
          ArrowLeftOutlined: simpleStub,
          DollarOutlined: simpleStub,
          PayCircleOutlined: simpleStub,
          RiseOutlined: simpleStub,
          FallOutlined: simpleStub,
          DownloadOutlined: simpleStub,
          FileExcelOutlined: simpleStub,
          FilePdfOutlined: simpleStub,
          FileWordOutlined: simpleStub,
        },
      },
    })

    await flushPromises()

    expect(mocks.simulatePaymentMonitoring).toHaveBeenCalled()
    expect(wrapper.text()).toContain('后端模拟')
    expect(wrapper.text()).toContain('CASE-1')
    expect(wrapper.text()).toContain('冠心病组')
    expect(wrapper.text()).toContain('不写入正式医保结算清单')
  })
})
