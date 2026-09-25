import { mount } from '@vue/test-utils'
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
    getMock.mockRejectedValue({ response: { status: 404 } })
    postMock.mockImplementation((url: string) =>
      String(url).includes('/settlement/')
        ? Promise.reject({
            response: { status: 409, data: { detail: '结算清单身份不唯一，请指定机构号' } },
          })
        : Promise.resolve({ data: { data: {} } }),
    )
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
