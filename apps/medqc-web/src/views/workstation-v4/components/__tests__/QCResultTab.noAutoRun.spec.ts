import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

// 脚本化客户端：记录请求、返回固定结果，不连接后端也不调用模型
const apiPost = vi.fn()
const apiGet = vi.fn()
vi.mock('@/services/apiService', () => ({
  apiClient: {
    post: (...args: unknown[]) => apiPost(...args),
    get: (...args: unknown[]) => apiGet(...args),
  },
}))
vi.mock('@/components/layout/workstationConfirmation', () => ({
  useWorkstationConfirmation: () => ({ confirm: vi.fn() }),
}))
vi.mock('ant-design-vue', () => ({
  message: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}))

import QCResultTab from '../QCResultTab.vue'

const FRONTPAGE = { patient_name: 'C01', main_diagnosis: '肺炎' }

function mountTab() {
  return mount(QCResultTab, {
    props: {
      frontpage: FRONTPAGE,
      refreshSeed: 0,
      activeTab: 'form',
      visitId: 'C01',
      patientId: 'P-C01',
    },
    global: {
      stubs: {
        // 根元素透传 onClick，无需再手动 emit
        'a-button': { template: '<button><slot /></button>' },
        'a-alert': { props: ['message'], template: '<div v-bind="$attrs">{{ message }}</div>' },
        'a-spin': true,
        'a-dropdown': true,
        'a-menu': true,
        'a-menu-item': true,
        'a-menu-divider': true,
      },
    },
  })
}

describe('QCResultTab 不自动发起质控', () => {
  beforeEach(() => {
    apiPost.mockReset()
    apiGet.mockReset()
    apiGet.mockRejectedValue({ response: { status: 404 } })
    apiPost.mockResolvedValue({ data: { data: { results: [], passed: 1, total_rules: 1 } } })
  })

  it('首页草稿读取或修改（refreshSeed 变化）不发任何质控请求', async () => {
    const wrapper = mountTab()
    await wrapper.setProps({ refreshSeed: 1 })
    await wrapper.setProps({ refreshSeed: 2, frontpage: { ...FRONTPAGE, main_diagnosis: '支气管炎' } })
    await flushPromises()

    expect(apiPost).not.toHaveBeenCalled()
  })

  it('用户点击“开始分析”后才执行首页质控，且只执行当前页签', async () => {
    const wrapper = mountTab()
    const startButton = wrapper.findAll('button').find((btn) => btn.text().includes('开始分析'))
    expect(startButton).toBeTruthy()

    await startButton!.trigger('click')
    await flushPromises()

    const urls = apiPost.mock.calls.map((call) => String(call[0]))
    expect(urls).toEqual(['/api/v1/qc/formal-qc/validate'])
  })

  it('已有结果后首页变更只提示结果过期，不重新质控', async () => {
    const wrapper = mountTab()
    const startButton = wrapper.findAll('button').find((btn) => btn.text().includes('开始分析'))
    await startButton!.trigger('click')
    await flushPromises()
    apiPost.mockClear()

    await wrapper.setProps({ refreshSeed: 1 })
    await flushPromises()

    expect(apiPost).not.toHaveBeenCalled()
    expect(wrapper.find('[data-testid="qc-result-stale"]').exists()).toBe(true)
  })
})
