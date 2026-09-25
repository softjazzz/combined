import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, shallowMount } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  error: vi.fn(),
  success: vi.fn(),
  info: vi.fn(),
  warning: vi.fn(),
}))

vi.mock('@/services/apiService', () => ({
  apiClient: { get: mocks.get, post: mocks.post },
  default: {},
}))

vi.mock('ant-design-vue', () => ({
  message: {
    error: mocks.error,
    success: mocks.success,
    info: mocks.info,
    warning: mocks.warning,
  },
  Modal: { confirm: vi.fn() },
}))

vi.mock('@/api/defects', () => ({
  urgeDefect: vi.fn(),
  markDefectRemediated: vi.fn(),
  approveDefect: vi.fn(),
  rejectDefect: vi.fn(),
  exportDefects: vi.fn(),
}))

import QCResultTab from '@/views/workstation-v2/components/QCResultTab.vue'

const DRAFT = { basic_info: { patient_name: '草稿姓名' } }
const FORMAL = { basic_info: { patient_name: '正式姓名' } }

function mountTab(props: Record<string, unknown> = {}) {
  return shallowMount(QCResultTab, {
    props: {
      activeTab: 'form',
      patientId: 'patient-1',
      visitId: 'visit-1',
      instituteId: 'hospital-1',
      frontpage: DRAFT,
      ...props,
    },
    global: {
      stubs: {
        'a-button': true,
        'a-spin': true,
        'a-dropdown': true,
        'a-menu': true,
        'a-menu-item': true,
        'a-menu-divider': true,
      },
    },
  })
}

async function runFormQC(wrapper: ReturnType<typeof mountTab>) {
  await (wrapper.vm as unknown as { runFormQC: () => Promise<void> }).runFormQC()
  await flushPromises()
}

type QcRunner = 'runFormQC' | 'runCodingQC' | 'runCostQC' | 'runAllQC'

async function runQc(wrapper: ReturnType<typeof mountTab>, method: QcRunner) {
  await (wrapper.vm as unknown as Record<QcRunner, () => Promise<void>>)[method]()
  await flushPromises()
}

/** 已分析且无问题会渲染绿色空态；未分析态渲染开始分析入口。 */
function expectNotAnalyzed(wrapper: ReturnType<typeof mountTab>) {
  expect(wrapper.find('.qc-empty').exists()).toBe(false)
  expect(wrapper.find('.qc-start').exists()).toBe(true)
}

describe('QCResultTab 首页质控只认正式首页', () => {
  beforeEach(() => {
    mocks.get.mockReset()
    mocks.post.mockReset()
    mocks.error.mockReset()
    mocks.success.mockReset()
    mocks.info.mockReset()
    mocks.warning.mockReset()
  })

  it('读取到正式首页时带机构号请求，并把正式首页（而非草稿）提交正式质控', async () => {
    mocks.get.mockResolvedValue({ data: FORMAL })
    mocks.post.mockResolvedValue({
      data: { data: { results: [], passed: 12, total_rules: 12, persistence: null } },
    })

    const wrapper = mountTab()
    await runFormQC(wrapper)

    expect(mocks.get).toHaveBeenCalledWith(
      '/api/medical-records/frontpage-sheet/patient-1/visit-1?institute_id=hospital-1',
    )
    expect(mocks.post).toHaveBeenCalledWith('/api/v1/qc/formal-qc/validate', {
      patient_id: 'patient-1',
      visit_id: 'visit-1',
      frontpage: FORMAL,
    }, { timeout: 30000 })
    expect(mocks.error).not.toHaveBeenCalled()
  })

  it('409 归属不唯一：不提交正式质控，提示后端原因', async () => {
    mocks.get.mockRejectedValue({
      response: { status: 409, data: { detail: '正式首页归属不唯一，请指定机构号' } },
    })

    const wrapper = mountTab()
    await runFormQC(wrapper)

    expect(mocks.post).not.toHaveBeenCalled()
    expect(mocks.error).toHaveBeenCalledWith('正式首页归属不唯一，请指定机构号')
  })

  it('503 首页服务不可用：不提交正式质控，提示服务不可用', async () => {
    mocks.get.mockRejectedValue({
      response: { status: 503, data: { detail: '病案数据取数来源不可用，请稍后重试' } },
    })

    const wrapper = mountTab()
    await runFormQC(wrapper)

    expect(mocks.post).not.toHaveBeenCalled()
    expect(mocks.error).toHaveBeenCalledWith('病案数据取数来源不可用，请稍后重试')
  })

  it('404 无正式首页：失败关闭，绝不用草稿顶替正式首页', async () => {
    mocks.get.mockRejectedValue({ response: { status: 404, data: { detail: '未找到' } } })

    const wrapper = mountTab()
    await runFormQC(wrapper)

    expect(mocks.post).not.toHaveBeenCalled()
    expect(mocks.error).toHaveBeenCalledWith('读取正式首页数据失败')
  })

  it('缺少就诊标识：不发请求，也不提交正式质控', async () => {
    const wrapper = mountTab({ visitId: null })
    await runFormQC(wrapper)

    expect(mocks.get).not.toHaveBeenCalled()
    expect(mocks.post).not.toHaveBeenCalled()
    expect(mocks.error).toHaveBeenCalledWith('缺少患者或就诊标识，无法读取正式首页')
  })

  it('患者号含特殊字符时逐段编码', async () => {
    mocks.get.mockResolvedValue({ data: FORMAL })
    mocks.post.mockResolvedValue({ data: { data: { results: [], persistence: null } } })

    const wrapper = mountTab({ patientId: 'P/1 ?' })
    await runFormQC(wrapper)

    expect(mocks.get).toHaveBeenCalledWith(
      '/api/medical-records/frontpage-sheet/P%2F1%20%3F/visit-1?institute_id=hospital-1',
    )
  })

  it('全部质控：正式首页不可读时跳过首页段，仍跑编码/控费，且不报"全部完成"', async () => {
    mocks.get.mockRejectedValue({ response: { status: 404, data: { detail: '未找到' } } })
    mocks.post.mockImplementation((url: string) => {
      if (url.includes('coding-qc/check')) {
        return Promise.resolve({ data: { data: { rule_issues: [], llm_issues: [], persistence: null } } })
      }
      if (url.includes('settlement')) {
        return Promise.resolve({ data: { results: [], summary: { passed: 0, total: 0 } } })
      }
      return Promise.resolve({ data: { data: {} } })
    })

    const wrapper = mountTab()
    await (wrapper.vm as unknown as { runAllQC: () => Promise<void> }).runAllQC()
    await flushPromises()

    const formalQcCalls = mocks.post.mock.calls.filter(([url]) =>
      String(url).includes('formal-qc/validate'),
    )
    expect(formalQcCalls).toHaveLength(0)
    expect(mocks.post.mock.calls.some(([url]) => String(url).includes('coding-qc/check'))).toBe(
      true,
    )
    expect(mocks.post.mock.calls.some(([url]) => String(url).includes('settlement'))).toBe(true)
    expect(mocks.success).not.toHaveBeenCalledWith('全部质控执行完成，结果已保存')
    expect(mocks.warning).toHaveBeenCalledWith('读取正式首页数据失败')
  })

  it('F2 首页质控 POST 失败：清掉旧 form 结果且不标记已分析', async () => {
    mocks.get.mockResolvedValue({ data: FORMAL })
    mocks.post.mockRejectedValue({ response: { status: 500, data: { detail: 'engine down' } } })

    const wrapper = mountTab({
      snapshotState: {
        form: {
          analyzed: true,
          issues: [
            { id: 'stale-1', category: '首页质控', severity: 'error', description: '上一次的旧问题' },
          ],
        },
      },
    })
    await runQc(wrapper, 'runFormQC')

    expect(mocks.error).toHaveBeenCalledWith('首页质控执行失败')
    expect(mocks.success).not.toHaveBeenCalled()
    expectNotAnalyzed(wrapper)
    const emissions = wrapper.emitted('issues-change') as unknown[][]
    const lastPayload = emissions.at(-1)?.[0] as Array<{ category: string }>
    expect(lastPayload.some((issue) => issue.category === 'form')).toBe(false)
  })

  it('F3 全部质控整体抛错：编码与控费都必须回到未分析态', async () => {
    mocks.get.mockResolvedValue({ data: FORMAL })
    mocks.post.mockImplementation((url: string) => {
      if (url.includes('coding-qc/check')) {
        return Promise.resolve({
          data: { data: { rule_issues: [], llm_issues: [], persistence: null } },
        })
      }
      if (url.includes('settlement')) {
        return Promise.reject({ response: { status: 500 } })
      }
      return Promise.resolve({ data: { data: { results: [], persistence: null } } })
    })

    const wrapper = mountTab({ activeTab: 'coding' })
    await runQc(wrapper, 'runAllQC')

    expect(mocks.error).toHaveBeenCalledWith('全部质控执行失败')
    expectNotAnalyzed(wrapper)
    await wrapper.setProps({ activeTab: 'cost' })
    expectNotAnalyzed(wrapper)
  })

  it('F3 单跑编码后端失败：不再伪装成未发现问题', async () => {
    mocks.post.mockRejectedValue({ response: { status: 500 } })

    const wrapper = mountTab({ activeTab: 'coding' })
    await runQc(wrapper, 'runCodingQC')

    expect(mocks.error).toHaveBeenCalledWith('编码质控执行失败')
    expect(mocks.success).not.toHaveBeenCalled()
    expectNotAnalyzed(wrapper)
  })

  it('F3 单跑控费失败：失败关闭且不标记已分析', async () => {
    mocks.post.mockRejectedValue({ response: { status: 500 } })

    const wrapper = mountTab({ activeTab: 'cost' })
    await runQc(wrapper, 'runCostQC')

    expect(mocks.error).toHaveBeenCalledWith('控费监测执行失败')
    expect(mocks.success).not.toHaveBeenCalled()
    expectNotAnalyzed(wrapper)
  })

  it('HTTP 200 但首页质控数据体缺失时不显示零问题通过', async () => {
    mocks.get.mockResolvedValue({ data: FORMAL })
    mocks.post.mockResolvedValue({ data: {} })

    const wrapper = mountTab()
    await runQc(wrapper, 'runFormQC')

    expect(mocks.error).toHaveBeenCalledWith('首页质控执行失败')
    expectNotAnalyzed(wrapper)
  })

  it('HTTP 200 但编码质控 issues 缺失时不显示零问题通过', async () => {
    mocks.post.mockResolvedValue({ data: { data: {} } })

    const wrapper = mountTab({ activeTab: 'coding' })
    await runQc(wrapper, 'runCodingQC')

    expect(mocks.error).toHaveBeenCalledWith('编码质控执行失败')
    expectNotAnalyzed(wrapper)
  })

  it('F4 读到正式首页后 refreshSeed 仍会自动重跑（闸门只拦失败态）', async () => {
    mocks.get.mockResolvedValue({ data: FORMAL })
    mocks.post.mockResolvedValue({
      data: { data: { results: [], persistence: null, rule_issues: [], llm_issues: [] } },
    })

    const wrapper = mountTab()
    await runQc(wrapper, 'runFormQC')
    const getCallsAfterSuccess = mocks.get.mock.calls.length

    await wrapper.setProps({ refreshSeed: 1 })
    await flushPromises()

    expect(mocks.get.mock.calls.length).toBeGreaterThan(getCallsAfterSuccess)
  })

  it('F4 正式源读取失败后 refreshSeed 不再自动重跑或反复告警', async () => {
    mocks.get.mockRejectedValue({
      response: { status: 409, data: { detail: '正式首页归属不唯一' } },
    })
    mocks.post.mockResolvedValue({ data: { data: { results: [], persistence: null } } })

    const wrapper = mountTab()
    await runQc(wrapper, 'runFormQC')
    expect(mocks.error).toHaveBeenCalledTimes(1)
    const getCalls = mocks.get.mock.calls.length
    const postCalls = mocks.post.mock.calls.length

    await wrapper.setProps({ refreshSeed: 1 })
    await wrapper.setProps({ refreshSeed: 2 })
    await flushPromises()

    expect(mocks.get.mock.calls.length).toBe(getCalls)
    expect(mocks.post.mock.calls.length).toBe(postCalls)
    expect(mocks.error).toHaveBeenCalledTimes(1)
  })

  it('F4 由可用转失败后立即降级：后续 refreshSeed 不再自动重跑', async () => {
    mocks.get.mockResolvedValueOnce({ data: FORMAL })
    mocks.get.mockRejectedValue({
      response: { status: 503, data: { detail: '病案数据取数来源不可用，请稍后重试' } },
    })
    mocks.post.mockResolvedValue({ data: { data: { results: [], persistence: null } } })

    const wrapper = mountTab()
    await runQc(wrapper, 'runFormQC')
    await runQc(wrapper, 'runFormQC')
    const getCalls = mocks.get.mock.calls.length

    await wrapper.setProps({ refreshSeed: 1 })
    await flushPromises()

    expect(mocks.get.mock.calls.length).toBe(getCalls)
  })
})
