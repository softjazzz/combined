import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { apiPost, apiGet, mockMessage } = vi.hoisted(() => ({
  apiPost: vi.fn(),
  apiGet: vi.fn(),
  mockMessage: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}))
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
  message: mockMessage,
}))

import QCResultTab from '../QCResultTab.vue'

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

function mountTab(propsOverride: Record<string, unknown> = {}) {
  return mount(QCResultTab, {
    props: {
      frontpage: { patient_name: '患者A' },
      refreshSeed: 0,
      activeTab: 'form',
      visitId: 'V-A',
      patientId: 'P-A',
      ...propsOverride,
    },
    global: {
      stubs: {
        'a-button': { template: '<button type="button"><slot /></button>' },
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

describe('QCResultTab P1-G4 跨患者切换竞态防护', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiGet.mockRejectedValue({ response: { status: 404 } })
  })

  it('首页质控请求在途时切换患者，患者 A 晚到结果不会回写到患者 B 面板', async () => {
    const reqA = deferred<any>()
    apiPost.mockReturnValueOnce(reqA.promise)

    const wrapper = mountTab({ activeTab: 'form', patientId: 'P-A', visitId: 'V-A' })
    const startBtn = wrapper.findAll('button').find((btn) => btn.text().includes('开始分析'))
    await startBtn!.trigger('click')

    // 切换到患者 B
    await wrapper.setProps({
      patientId: 'P-B',
      visitId: 'V-B',
      frontpage: { patient_name: '患者B' },
    })
    await flushPromises()

    // 患者 A 的晚到响应返回
    reqA.resolve({
      data: {
        data: {
          results: [{ severity: 'error', category: '首页质控', message: '患者A首页缺失' }],
          passed: 0,
          total_rules: 1,
          persistence: { defects_created: 1 },
        },
      },
    })
    await flushPromises()

    expect(wrapper.text()).not.toContain('患者A首页缺失')
    expect(wrapper.text()).toContain('开始分析')
    expect(wrapper.emitted('persistence-finished')).toBeFalsy()
    expect(mockMessage.success).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('编码质控超时降级期间切换患者，不发起降级重试也不提示过期消息', async () => {
    const reqA = deferred<any>()
    apiPost.mockReturnValueOnce(reqA.promise)

    const wrapper = mountTab({ activeTab: 'coding', patientId: 'P-A', visitId: 'V-A' })
    const startBtn = wrapper.findAll('button').find((btn) => btn.text().includes('开始分析'))
    await startBtn!.trigger('click')
    expect(apiPost).toHaveBeenCalledTimes(1)

    await wrapper.setProps({ patientId: 'P-B', visitId: 'V-B' })
    await flushPromises()

    reqA.reject({ code: 'ECONNABORTED', message: 'timeout of 30000ms exceeded' })
    await flushPromises()

    // 不应触发 skip_llm 降级二次请求，也不应污染患者 B
    expect(apiPost).toHaveBeenCalledTimes(1)
    expect(mockMessage.info).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('开始分析')
    wrapper.unmount()
  })

  it('同一患者连续触发两次请求时，仅最后一次请求结果生效', async () => {
    const first = deferred<any>()
    const second = deferred<any>()
    apiPost.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)

    const wrapper = mountTab({ activeTab: 'coding', patientId: 'P-A', visitId: 'V-A' })
    const vm = wrapper.vm as unknown as { runCodingQC: () => Promise<void> }

    const p1 = vm.runCodingQC()
    const p2 = vm.runCodingQC()

    second.resolve({
      data: {
        data: {
          rule_issues: [{ severity: 'error', dimension: 'format', description: '最新编码问题' }],
          llm_issues: [],
        },
      },
    })
    await p2
    await flushPromises()
    expect(wrapper.text()).toContain('最新编码问题')

    first.resolve({
      data: {
        data: {
          rule_issues: [{ severity: 'error', dimension: 'format', description: '过期编码问题' }],
          llm_issues: [],
        },
      },
    })
    await p1
    await flushPromises()

    expect(wrapper.text()).toContain('最新编码问题')
    expect(wrapper.text()).not.toContain('过期编码问题')
    wrapper.unmount()
  })
})
