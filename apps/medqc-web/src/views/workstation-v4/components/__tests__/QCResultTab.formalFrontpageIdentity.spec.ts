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
const CURRENT_SCORE = {
  status: 'scored', score: 83, grade: '乙', veto_hit: false, standard_id: 'frontpage-standard', standard_version_seq: 3,
  standard_updated_at: '2026-10-03T00:00:00Z', rule_set_key: 'frontpage_formal_v1', rule_set_version: '2026-10-03',
  reason_code: null, deductions: [], group_deductions: [], unscored_rule_ids: [],
}

describe('QCResultTab 正式首页身份与失败关闭', () => {
  beforeEach(() => {
    getMock.mockReset()
    postMock.mockReset()
    successMock.mockReset()
    errorMock.mockReset()
  })
  it('本次配置评分独立于旧规则通过率，标准版本从响应搬运', async () => {
    getMock.mockResolvedValue({ data: OFFICIAL_SHEET })
    postMock.mockResolvedValue({ data: { data: { ...FORM_SUCCESS.data.data, pass_rate: 100, scoring: CURRENT_SCORE } } })
    const wrapper = mountFormQc('H1')
    await runFormQC(wrapper)
    expect(wrapper.get('[data-testid="frontpage-current-scoring"]').text()).toContain('83')
    expect(wrapper.text()).toContain('frontpage-standard / 3')
    expect(wrapper.get('[data-testid="frontpage-current-scoring"]').text()).not.toContain('100')
    wrapper.unmount()
  })
  it('旧响应没有scoring时显示未知，重跑立即清旧分且失败不保留旧分', async () => {
    getMock.mockResolvedValue({ data: OFFICIAL_SHEET })
    postMock.mockResolvedValueOnce({ data: { data: { ...FORM_SUCCESS.data.data, scoring: CURRENT_SCORE } } }).mockResolvedValueOnce(FORM_SUCCESS)
    const wrapper = mountFormQc('H1')
    await runFormQC(wrapper)
    const rerun = runFormQC(wrapper)
    await flushPromises()
    await rerun
    expect(wrapper.get('[data-testid="frontpage-current-scoring"]').text()).toContain('未知')
    expect(wrapper.text()).not.toContain('frontpage-standard')
    postMock.mockRejectedValueOnce(new Error('unavailable'))
    await runFormQC(wrapper)
    expect(wrapper.find('[data-testid="frontpage-current-scoring"]').exists()).toBe(false)
    wrapper.unmount()
  })
  it('病例身份变化废弃晚到本次分数', async () => {
    getMock.mockResolvedValue({ data: OFFICIAL_SHEET })
    let done!: (value: unknown) => void
    postMock.mockImplementationOnce(() => new Promise((resolve) => { done = resolve }))
    const wrapper = mountFormQc('H1')
    const pending = runFormQC(wrapper)
    await flushPromises()
    await wrapper.setProps({ patientId: 'patient-2', visitId: 'visit-2' })
    done({ data: { data: { ...FORM_SUCCESS.data.data, scoring: CURRENT_SCORE } } })
    await pending
    expect(wrapper.text()).not.toContain('frontpage-standard')
    wrapper.unmount()
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

  it('正式首页读取成功后才执行 formal-qc，POST 只提交三坐标且不带 frontpage', async () => {
    getMock.mockResolvedValue({ data: OFFICIAL_SHEET })
    postMock.mockResolvedValue(FORM_SUCCESS)
    const wrapper = mountFormQc('hospital-1')

    await runFormQC(wrapper)

    const body = postMock.mock.calls[0][1] as Record<string, unknown>
    expect(body).toEqual({
      patient_id: 'patient-1',
      visit_id: 'visit-1',
      institute_id: 'hospital-1',
    })
    expect(body).not.toHaveProperty('frontpage')
    expect(wrapper.text()).toContain('未发现质控问题')
  })

  it('机构号缺失时 POST 省略 institute_id，不编造机构', async () => {
    getMock.mockResolvedValue({ data: OFFICIAL_SHEET })
    postMock.mockResolvedValue(FORM_SUCCESS)
    const wrapper = mountFormQc('   ')

    await runFormQC(wrapper)

    const body = postMock.mock.calls[0][1] as Record<string, unknown>
    expect(body).toEqual({ patient_id: 'patient-1', visit_id: 'visit-1' })
    expect(body).not.toHaveProperty('institute_id')
    expect(body).not.toHaveProperty('frontpage')
  })

  it('formal-qc 返回 200 但缺少统一数据体时失败关闭，不渲染绿色通过', async () => {
    getMock.mockResolvedValue({ data: OFFICIAL_SHEET })
    postMock.mockResolvedValue({ data: { success: true } })
    const wrapper = mountFormQc('hospital-1')

    await runFormQC(wrapper)

    expect(successMock).not.toHaveBeenCalled()
    expect(errorMock).toHaveBeenCalledWith('首页质控执行失败')
    expect(wrapper.text()).not.toContain('未发现质控问题')
    expect(wrapper.text()).toContain('开始分析')
  })

  it('跨病例迟到响应不得覆盖新病例的 issues 与“已分析”态', async () => {
    getMock.mockResolvedValue({ data: OFFICIAL_SHEET })
    let resolveStale: (value: unknown) => void = () => {}
    const staleResponse = new Promise((resolve) => {
      resolveStale = resolve
    })
    postMock.mockImplementationOnce(() => staleResponse)
    const wrapper = mountFormQc('hospital-1')

    const pending = runFormQC(wrapper)
    await flushPromises()

    // 病例切换：旧请求仍在途，代次已递增。
    await wrapper.setProps({ patientId: 'patient-2', visitId: 'visit-2' })

    resolveStale({
      data: {
        data: {
          results: [{ severity: 'error', message: '旧病例迟到问题', field_name: 'sex' }],
          persistence: {},
          passed: 0,
          total_rules: 1,
        },
      },
    })
    await pending
    await flushPromises()

    expect(wrapper.text()).not.toContain('旧病例迟到问题')
    expect(wrapper.text()).not.toContain('未发现质控问题')
    expect(wrapper.text()).toContain('开始分析')
    expect(successMock).not.toHaveBeenCalled()
  })

  it('跨机构迟到响应不得覆盖新机构的“已分析”态', async () => {
    getMock.mockResolvedValue({ data: OFFICIAL_SHEET })
    let resolveStale: (value: unknown) => void = () => {}
    const staleResponse = new Promise((resolve) => {
      resolveStale = resolve
    })
    postMock.mockImplementationOnce(() => staleResponse)
    const wrapper = mountFormQc('hospital-1')

    const pending = runFormQC(wrapper)
    await flushPromises()

    await wrapper.setProps({ instituteId: 'hospital-2' })

    resolveStale(FORM_SUCCESS)
    await pending
    await flushPromises()

    expect(wrapper.text()).not.toContain('未发现质控问题')
    expect(wrapper.text()).toContain('开始分析')
    expect(successMock).not.toHaveBeenCalled()
  })

  it('正式首页读取成功后才执行 formal-qc 并允许标记已分析（对照组）', async () => {
    getMock.mockResolvedValue({ data: OFFICIAL_SHEET })
    postMock.mockResolvedValue(FORM_SUCCESS)
    const wrapper = mountFormQc('hospital-1')

    await runFormQC(wrapper)

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
