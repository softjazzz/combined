import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import QCResultTab from '../QCResultTab.vue'
import type { WorkstationSnapshotState } from '../../types'

const { getMock, postMock, successMock, errorMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
  postMock: vi.fn(),
  successMock: vi.fn(),
  errorMock: vi.fn(),
}))

vi.mock('@/services/apiService', () => ({
  default: { refreshToken: vi.fn() },
  apiClient: { get: getMock, post: postMock },
}))

vi.mock('ant-design-vue', () => ({
  message: { success: successMock, error: errorMock, info: vi.fn(), warning: vi.fn() },
}))

const ButtonStub = {
  template: '<button type="button" @click="$emit(\'click\')"><slot /></button>',
}

const iconStub = { template: '<i />' }

const SHEET_PATH = '/api/medical-records/frontpage-sheet/patient-1/visit-1'
const FORM_QC_URL = '/api/v1/qc/formal-qc/validate'

type SnapshotStub = Partial<Record<'form' | 'coding' | 'cost', WorkstationSnapshotState>>

function mountFormQc(instituteId?: string | null, snapshotState?: SnapshotStub) {
  return mount(QCResultTab, {
    props: {
      activeTab: 'form',
      patientId: 'patient-1',
      visitId: 'visit-1',
      instituteId,
      // 已存在 AI 抽取草稿：草稿不能替代正式首页成为质控对象。
      frontpage: { sex: '男' },
      ...(snapshotState ? { snapshotState } : {}),
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

async function runFormQC(wrapper: ReturnType<typeof mountFormQc>) {
  await (wrapper.vm as unknown as { runFormQC: () => Promise<void> }).runFormQC()
}

async function runAllQC(wrapper: ReturnType<typeof mountFormQc>) {
  await (wrapper.vm as unknown as { runAllQC: () => Promise<void> }).runAllQC()
}

const OFFICIAL_SHEET = { basic_info: { age: 60 } }
const FORM_SUCCESS = { data: { data: { results: [], persistence: {}, passed: 5, total_rules: 5 } } }

describe('QCResultTab 正式首页身份与失败关闭', () => {
  beforeEach(() => {
    getMock.mockReset()
    postMock.mockReset()
    successMock.mockReset()
    errorMock.mockReset()
  })

  it('instituteId 非空时以 URLSearchParams 编码后作为消歧参数', async () => {
    getMock.mockResolvedValue({ data: OFFICIAL_SHEET })
    postMock.mockResolvedValue(FORM_SUCCESS)
    const wrapper = mountFormQc('机构 A/1&x=2')

    await runFormQC(wrapper)

    const url = new URL(getMock.mock.calls[0][0] as string, 'http://localhost')
    expect(url.pathname).toBe(SHEET_PATH)
    expect(url.searchParams.get('institute_id')).toBe('机构 A/1&x=2')
    expect(postMock.mock.calls[0][0]).toBe(FORM_QC_URL)
  })

  it('instituteId 为空白时保持无机构调用兼容', async () => {
    getMock.mockResolvedValue({ data: OFFICIAL_SHEET })
    postMock.mockResolvedValue(FORM_SUCCESS)
    const wrapper = mountFormQc('   ')

    await runFormQC(wrapper)

    expect(getMock.mock.calls[0][0]).toBe(SHEET_PATH)
    expect(postMock.mock.calls[0][0]).toBe(FORM_QC_URL)
  })

  it('正式首页 409 歧义时就地失败，不提交草稿质控也不显示绿色通过', async () => {
    getMock.mockRejectedValue({
      response: { status: 409, data: { detail: '病例身份不唯一，请指定机构号' } },
    })
    const wrapper = mountFormQc('hospital-1')

    await runFormQC(wrapper)

    expect(postMock).not.toHaveBeenCalled()
    expect(successMock).not.toHaveBeenCalled()
    expect(errorMock).toHaveBeenCalledWith('病例身份不唯一，请指定机构号')
    expect(wrapper.text()).not.toContain('未发现质控问题')
    expect(wrapper.text()).toContain('开始分析')
  })

  it('正式首页 503 时就地失败，提示服务暂不可用', async () => {
    getMock.mockRejectedValue({ response: { status: 503 } })
    const wrapper = mountFormQc('hospital-1')

    await runFormQC(wrapper)

    expect(postMock).not.toHaveBeenCalled()
    expect(errorMock).toHaveBeenCalledWith('正式首页服务暂不可用，请稍后重试')
    expect(wrapper.text()).toContain('开始分析')
  })

  it('正式首页 404 时即使已有 AI 草稿也失败关闭，不用草稿顶替', async () => {
    getMock.mockRejectedValue({ response: { status: 404 } })
    const wrapper = mountFormQc('hospital-1')

    await runFormQC(wrapper)

    expect(postMock).not.toHaveBeenCalled()
    expect(successMock).not.toHaveBeenCalled()
    expect(errorMock).toHaveBeenCalledWith('未找到正式首页数据，无法执行首页质控')
    expect(wrapper.text()).not.toContain('未发现质控问题')
  })

  it('runAllQC 在缺少正式首页时整体失败关闭，不发起任何质控请求', async () => {
    getMock.mockRejectedValue({ response: { status: 404 } })
    const wrapper = mountFormQc('hospital-1')

    await runAllQC(wrapper)

    expect(postMock).not.toHaveBeenCalled()
    expect(errorMock).toHaveBeenCalledWith('未找到正式首页数据，无法执行首页质控')
    expect(wrapper.text()).toContain('开始分析')
    expect(wrapper.text()).not.toContain('未发现质控问题')
  })

  it('正式首页读取成功后才执行 formal-qc 并允许标记已分析', async () => {
    getMock.mockResolvedValue({ data: OFFICIAL_SHEET })
    postMock.mockResolvedValue(FORM_SUCCESS)
    const wrapper = mountFormQc('hospital-1')

    await runFormQC(wrapper)

    expect(postMock.mock.calls[0][1]).toMatchObject({
      patient_id: 'patient-1',
      visit_id: 'visit-1',
      frontpage: OFFICIAL_SHEET,
    })
    expect(wrapper.text()).toContain('未发现质控问题')
  })

  it('同就诊先成功后 409 失败：回到未分析态且自动刷新不再重跑', async () => {
    getMock
      .mockResolvedValueOnce({ data: OFFICIAL_SHEET })
      .mockRejectedValueOnce({
        response: { status: 409, data: { detail: '病例身份不唯一，请指定机构号' } },
      })
    postMock.mockResolvedValue(FORM_SUCCESS)
    const wrapper = mountFormQc('hospital-1')

    await runFormQC(wrapper)
    expect(wrapper.text()).toContain('未发现质控问题')

    await runFormQC(wrapper)
    expect(errorMock).toHaveBeenCalledWith('病例身份不唯一，请指定机构号')
    expect(wrapper.text()).not.toContain('未发现质控问题')
    expect(wrapper.text()).toContain('开始分析')

    const postCallsAfterFailure = postMock.mock.calls.length
    const errorCallsAfterFailure = errorMock.mock.calls.length
    await wrapper.setProps({ refreshSeed: 7 })
    await flushPromises()

    // 失败后正式首页不再标记为可用，自动刷新不得重跑（否则会反复弹错并掩盖失败态）。
    expect(postMock.mock.calls.length).toBe(postCallsAfterFailure)
    expect(errorMock.mock.calls.length).toBe(errorCallsAfterFailure)
  })

  it('已读到正式首页时自动刷新仍会重跑（对照组）', async () => {
    getMock.mockResolvedValue({ data: OFFICIAL_SHEET })
    postMock.mockImplementation((url: string) => {
      const target = String(url)
      if (target.includes('formal-qc/validate')) return Promise.resolve(FORM_SUCCESS)
      if (target.includes('coding-qc/check')) {
        return Promise.resolve({ data: { data: { rule_issues: [], llm_issues: [] } } })
      }
      return Promise.resolve({ data: { results: [], summary: { passed: 0, total: 0 } } })
    })
    const wrapper = mountFormQc('hospital-1')

    await runFormQC(wrapper)
    const postCalls = postMock.mock.calls.length

    await wrapper.setProps({ refreshSeed: 3 })
    await flushPromises()

    expect(postMock.mock.calls.length).toBeGreaterThan(postCalls)
  })

  it.each([
    ['409 归属歧义', { response: { status: 409, data: { detail: '病例身份不唯一，请指定机构号' } } }],
    ['404 无正式首页', { response: { status: 404 } }],
  ])('首页质控失败（%s）时移除旧 form 结果并保留 coding/cost', async (_case, sheetError) => {
    getMock.mockRejectedValue(sheetError)
    const wrapper = mountFormQc('hospital-1', {
      form: {
        analyzed: true,
        issues: [{ id: 'form-old', description: '上一次的首页问题', severity: 'error' }],
      },
      coding: {
        analyzed: true,
        issues: [{ id: 'coding-keep', description: '编码问题', severity: 'warning' }],
      },
      cost: {
        analyzed: true,
        issues: [{ id: 'cost-keep', description: '结算问题', severity: 'info' }],
      },
    })

    await runFormQC(wrapper)

    const emitted = wrapper.emitted('issues-change') ?? []
    const lastPayload = emitted[emitted.length - 1]?.[0] as Array<{ id: string; category: string }>
    expect(lastPayload.some((issue) => issue.category === 'form')).toBe(false)
    expect(lastPayload.map((issue) => issue.id)).toContain('coding-keep')
    expect(lastPayload.map((issue) => issue.id)).toContain('cost-keep')
    expect(wrapper.text()).not.toContain('上一次的首页问题')
  })
})
