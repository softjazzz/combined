import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

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

const { postMock, getMock, successMock, errorMock } = vi.hoisted(() => ({
  postMock: vi.fn(),
  getMock: vi.fn(),
  successMock: vi.fn(),
  errorMock: vi.fn(),
}))

vi.mock('@/services/apiService', () => ({
  default: { refreshToken: vi.fn() },
  apiClient: { post: postMock, get: getMock },
}))

vi.mock('ant-design-vue', () => ({
  message: { success: successMock, error: errorMock, info: vi.fn(), warning: vi.fn() },
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

const SETTLEMENT_BASE = '/api/medical-records/settlement/patient-1/visit-1'

function mountCostQc(instituteId?: string | null) {
  return mount(QCResultTab, {
    props: {
      activeTab: 'cost',
      patientId: 'patient-1',
      visitId: 'visit-1',
      instituteId,
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

function requestedUrl(index = 0): URL {
  return new URL(postMock.mock.calls[index][0] as string, 'http://localhost')
}

async function runCostQC(wrapper: ReturnType<typeof mountCostQc>) {
  await (wrapper.vm as unknown as { runCostQC: () => Promise<void> }).runCostQC()
}

function mountAllQc() {
  return mount(QCResultTab, {
    props: {
      patientId: 'patient-1',
      visitId: 'visit-1',
      frontpage: { sex: '男' },
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

async function runAllQC(wrapper: ReturnType<typeof mountAllQc>) {
  await (wrapper.vm as unknown as { runAllQC: () => Promise<void> }).runAllQC()
}

describe('QCResultTab 生成式结算质控机构号传递', () => {
  beforeEach(() => {
    postMock.mockReset()
    getMock.mockReset()
    successMock.mockReset()
    errorMock.mockReset()
  })

  it('instituteId 为空白时不拼接 institute_id 查询参数', async () => {
    postMock.mockResolvedValue({ data: { results: [], summary: { passed: 0, total: 0 } } })
    const wrapper = mountCostQc('   ')

    await runCostQC(wrapper)

    expect(postMock).toHaveBeenCalledTimes(1)
    expect(postMock.mock.calls[0][0]).toBe(`${SETTLEMENT_BASE}/qc`)
  })

  it('instituteId 非空时以 URLSearchParams 编码后传递', async () => {
    postMock.mockResolvedValue({ data: { results: [], summary: { passed: 0, total: 0 } } })
    const instituteId = '机构 A/1&x=2'
    const wrapper = mountCostQc(instituteId)

    await runCostQC(wrapper)

    const url = requestedUrl()
    expect(url.pathname).toBe(`${SETTLEMENT_BASE}/qc`)
    expect(url.searchParams.get('institute_id')).toBe(instituteId)
    expect(url.search).toBe(`?${new URLSearchParams({ institute_id: instituteId }).toString()}`)
  })

  it('409 身份歧义就地失败，不回退 /generate/qc，也不产生无病例成功', async () => {
    postMock.mockRejectedValue({
      response: { status: 409, data: { detail: '结算清单身份不唯一，请指定机构号' } },
    })
    const wrapper = mountCostQc('hospital-1')

    await runCostQC(wrapper)

    expect(postMock).toHaveBeenCalledTimes(1)
    const url = requestedUrl()
    expect(url.pathname).toBe(`${SETTLEMENT_BASE}/qc`)
    expect(url.searchParams.get('institute_id')).toBe('hospital-1')
    expect(successMock).not.toHaveBeenCalled()
    expect(errorMock).toHaveBeenCalledWith('结算清单身份不唯一，请指定机构号')
    const emittedIssues = wrapper.emitted('issues-change') ?? []
    for (const [payload] of emittedIssues) {
      expect(payload).toEqual([])
    }
  })

  it('404 无病例时回退 /generate/qc 且保持同一机构号', async () => {
    postMock
      .mockRejectedValueOnce({ response: { status: 404 } })
      .mockResolvedValueOnce({ data: { results: [], summary: { passed: 0, total: 0 } } })
    const wrapper = mountCostQc('hospital-1')

    await runCostQC(wrapper)

    expect(postMock).toHaveBeenCalledTimes(2)
    expect(requestedUrl(0).pathname).toBe(`${SETTLEMENT_BASE}/qc`)
    expect(requestedUrl(1).pathname).toBe(`${SETTLEMENT_BASE}/generate/qc`)
    expect(requestedUrl(1).searchParams.get('institute_id')).toBe('hospital-1')
  })
})

describe('QCResultTab 结算质控失败不得渲染绿色通过', () => {
  beforeEach(() => {
    postMock.mockReset()
    getMock.mockReset()
    successMock.mockReset()
    errorMock.mockReset()
  })

  it('409 身份歧义后控费页签回到未分析态，不显示“未发现质控问题”', async () => {
    postMock.mockRejectedValue({
      response: { status: 409, data: { detail: '结算清单身份不唯一，请指定机构号' } },
    })
    const wrapper = mountCostQc()

    await runCostQC(wrapper)

    expect(wrapper.text()).not.toContain('未发现质控问题')
    expect(wrapper.text()).toContain('开始分析')
  })

  it('503 执行失败后控费页签回到未分析态，不显示“未发现质控问题”', async () => {
    postMock.mockRejectedValue({
      response: { status: 503, data: { detail: '结算清单质控或结果保存失败，请稍后重试' } },
    })
    const wrapper = mountCostQc('hospital-1')

    await runCostQC(wrapper)

    expect(wrapper.text()).not.toContain('未发现质控问题')
    expect(wrapper.text()).toContain('开始分析')
  })

  it('仅当执行成功且无问题时才显示“未发现质控问题”', async () => {
    postMock.mockResolvedValue({ data: { results: [], summary: { passed: 5, total: 5 } } })
    const wrapper = mountCostQc('hospital-1')

    await runCostQC(wrapper)

    expect(wrapper.text()).toContain('未发现质控问题')
  })

  it('runAllQC 中控费 409 失败时三个页签都不显示绿色通过', async () => {
    // 正式首页存在，失败点必须落在控费 409 上（首页读取失败已是另一条独立用例）。
    getMock.mockResolvedValue({ data: { basic_info: {} } })
    postMock.mockImplementation((url: string) => {
      const target = String(url)
      if (target.includes('/settlement/')) {
        return Promise.reject({
          response: { status: 409, data: { detail: '结算清单身份不唯一，请指定机构号' } },
        })
      }
      return target.includes('formal-qc/validate')
        ? Promise.resolve({ data: { data: { results: [], persistence: {}, passed: 5, total_rules: 5 } } })
        : Promise.resolve({ data: { data: { rule_issues: [], llm_issues: [] } } })
    })
    const wrapper = mountAllQc()

    await runAllQC(wrapper)

    const tabs = wrapper.findAll('.qc-result-tab__tab')
    expect(tabs).toHaveLength(3)
    for (const tab of tabs) {
      await tab.trigger('click')
      expect(wrapper.text()).toContain('开始分析')
      expect(wrapper.text()).not.toContain('未发现质控问题')
    }
  })
})

const FORM_QC_URL = '/api/v1/qc/formal-qc/validate'
const CODING_QC_URL = '/api/v1/qc/coding-qc/check'

function mountFormQc() {
  return mount(QCResultTab, {
    props: {
      activeTab: 'form',
      patientId: 'patient-1',
      visitId: 'visit-1',
      frontpage: { sex: '男' },
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

function mountCodingQc() {
  return mount(QCResultTab, {
    props: {
      activeTab: 'coding',
      patientId: 'patient-1',
      visitId: 'visit-1',
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

async function runCodingQC(wrapper: ReturnType<typeof mountCodingQc>) {
  await (wrapper.vm as unknown as { runCodingQC: () => Promise<void> }).runCodingQC()
}

const FORM_SUCCESS = { data: { data: { results: [], persistence: {}, passed: 5, total_rules: 5 } } }
const CODING_SUCCESS = { data: { data: { rule_issues: [], llm_issues: [] } } }

describe('QCResultTab 首页/编码单独执行失败不得渲染绿色通过', () => {
  beforeEach(() => {
    postMock.mockReset()
    getMock.mockReset()
    successMock.mockReset()
    errorMock.mockReset()
    // 正式首页 GET 成功：本组用例验证的是 formal-qc/validate 之后的失败关闭语义。
    getMock.mockResolvedValue({ data: { basic_info: {} } })
  })

  it.each([409, 503])('首页质控 HTTP %s 失败后回到未分析态，不显示“未发现质控问题”', async (status) => {
    postMock.mockRejectedValue({ response: { status, data: { detail: '首页质控执行失败' } } })
    const wrapper = mountFormQc()

    await runFormQC(wrapper)

    expect(postMock).toHaveBeenCalledTimes(1)
    expect(postMock.mock.calls[0][0]).toBe(FORM_QC_URL)
    expect(wrapper.text()).not.toContain('未发现质控问题')
    expect(wrapper.text()).toContain('开始分析')
    expect(successMock).not.toHaveBeenCalled()
    expect(errorMock).toHaveBeenCalledWith('首页质控执行失败')
  })

  it.each([409, 503])('编码质控 HTTP %s 失败后回到未分析态，不显示“未发现质控问题”', async (status) => {
    postMock.mockRejectedValue({ response: { status, data: { detail: '编码质控病例身份无法唯一确定' } } })
    const wrapper = mountCodingQc()

    await runCodingQC(wrapper)

    expect(postMock).toHaveBeenCalledTimes(1)
    expect(postMock.mock.calls[0][0]).toBe(CODING_QC_URL)
    expect(wrapper.text()).not.toContain('未发现质控问题')
    expect(wrapper.text()).toContain('开始分析')
    expect(successMock).not.toHaveBeenCalled()
    expect(errorMock).toHaveBeenCalledWith('编码质控执行失败')
  })

  it('接口 200 但缺少统一数据体时首页质控失败关闭', async () => {
    postMock.mockResolvedValue({ data: { success: true } })
    const wrapper = mountFormQc()

    await runFormQC(wrapper)

    expect(wrapper.text()).not.toContain('未发现质控问题')
    expect(successMock).not.toHaveBeenCalled()
    expect(errorMock).toHaveBeenCalledWith('首页质控执行失败')
  })

  it.each([
    ['缺少 results 数组', { total_rules: 5, passed: 5 }],
    ['results 类型不是数组', { results: { 0: 'x' } }],
  ])('首页质控 200 但 %s 时失败关闭', async (_case, body) => {
    postMock.mockResolvedValue({ data: { data: body } })
    const wrapper = mountFormQc()

    await runFormQC(wrapper)

    expect(wrapper.text()).not.toContain('未发现质控问题')
    expect(wrapper.text()).toContain('开始分析')
    expect(successMock).not.toHaveBeenCalled()
    expect(errorMock).toHaveBeenCalledWith('首页质控执行失败')
  })

  it('接口 200 但缺少统一数据体时编码质控失败关闭', async () => {
    postMock.mockResolvedValue({ data: { success: true } })
    const wrapper = mountCodingQc()

    await runCodingQC(wrapper)

    expect(wrapper.text()).not.toContain('未发现质控问题')
    expect(successMock).not.toHaveBeenCalled()
    expect(errorMock).toHaveBeenCalledWith('编码质控执行失败')
  })

  it.each([
    ['缺少 rule_issues/llm_issues 数组', { total_issues: 0 }],
    ['缺少 llm_issues 数组', { rule_issues: [] }],
    ['rule_issues 类型不是数组', { rule_issues: 'oops', llm_issues: [] }],
  ])('编码质控 200 但 %s 时失败关闭', async (_case, body) => {
    postMock.mockResolvedValue({ data: { data: body } })
    const wrapper = mountCodingQc()

    await runCodingQC(wrapper)

    expect(wrapper.text()).not.toContain('未发现质控问题')
    expect(wrapper.text()).toContain('开始分析')
    expect(successMock).not.toHaveBeenCalled()
    expect(errorMock).toHaveBeenCalledWith('编码质控执行失败')
  })

  it('失败后回到未分析态，可重试并显示“未发现质控问题”', async () => {
    postMock
      .mockRejectedValueOnce({ response: { status: 503, data: { detail: '首页质控执行失败' } } })
      .mockResolvedValueOnce(FORM_SUCCESS)
    const wrapper = mountFormQc()

    await runFormQC(wrapper)
    expect(wrapper.text()).toContain('开始分析')

    await (wrapper.vm as unknown as { startCurrentTab: () => void }).startCurrentTab()
    await flushPromises()

    expect(postMock).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('未发现质控问题')
    expect(successMock).toHaveBeenCalled()
  })

  it('编码质控超时后规则层降级成功，仍标记为已分析', async () => {
    postMock
      .mockRejectedValueOnce({ code: 'ECONNABORTED' })
      .mockResolvedValueOnce(CODING_SUCCESS)
    const wrapper = mountCodingQc()

    await runCodingQC(wrapper)

    expect(postMock).toHaveBeenCalledTimes(2)
    expect(postMock.mock.calls[1][1]).toMatchObject({ skip_llm: true })
    expect(wrapper.text()).toContain('未发现质控问题')
    expect(successMock).toHaveBeenCalled()
    expect(errorMock).not.toHaveBeenCalled()
  })

  it('编码质控超时且降级重试也失败时不得显示绿色通过', async () => {
    postMock
      .mockRejectedValueOnce({ code: 'ECONNABORTED' })
      .mockRejectedValueOnce({ response: { status: 503, data: { detail: '编码质控数据读取失败' } } })
    const wrapper = mountCodingQc()

    await runCodingQC(wrapper)

    expect(postMock).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).not.toContain('未发现质控问题')
    expect(wrapper.text()).toContain('开始分析')
    expect(successMock).not.toHaveBeenCalled()
    expect(errorMock).toHaveBeenCalledWith('编码质控执行失败')
  })

  it('首页质控成功且无问题时仍显示“未发现质控问题”', async () => {
    postMock.mockResolvedValue(FORM_SUCCESS)
    const wrapper = mountFormQc()

    await runFormQC(wrapper)

    expect(wrapper.text()).toContain('未发现质控问题')
  })
})
