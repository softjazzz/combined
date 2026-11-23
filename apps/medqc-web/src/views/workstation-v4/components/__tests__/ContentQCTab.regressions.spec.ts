import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { apiGet, apiPost, mockMessage } = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  mockMessage: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
  },
}))

vi.mock('@/services/apiService', () => ({
  apiClient: {
    get: (...args: unknown[]) => apiGet(...args),
    post: (...args: unknown[]) => apiPost(...args),
  },
}))

vi.mock('@/api/qc', () => ({
  evaluateSichuanBundleQC: vi.fn(),
}))

vi.mock('ant-design-vue', () => ({
  message: mockMessage,
}))

import ContentQCTab from '../ContentQCTab.vue'
import { evaluateSichuanBundleQC, type BatchQCEvaluateResponse } from '@/api/qc'

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

const ButtonStub = {
  props: ['disabled', 'loading'],
  template:
    '<button type="button" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
}
const TagStub = { template: '<span class="tag-stub"><slot /></span>' }
const ModalStub = {
  props: ['open', 'title'],
  template: '<section v-if="open" class="modal-stub"><slot /></section>',
}
const TransparentStub = { template: '<div><slot /></div>' }
const iconStub = { template: '<i />' }

function mountTab(propsOverride: Record<string, unknown> = {}) {
  return mount(ContentQCTab, {
    props: {
      instituteId: 'H1',
      patientId: 'P1',
      visitId: 'V1',
      scene: 'final',
      documents: [
        {
          type: 'admission_record',
          label: '入院记录',
          content: '患者因胸痛入院。',
          has_content: true,
          length: 8,
        },
      ],
      ...propsOverride,
    },
    global: {
      stubs: {
        'a-button': ButtonStub,
        'a-tag': TagStub,
        'a-modal': ModalStub,
        'a-radio-button': TransparentStub,
        'a-radio-group': TransparentStub,
        'a-switch': TransparentStub,
        'a-input': TransparentStub,
        'a-select': TransparentStub,
        'a-pagination': TransparentStub,
        'a-spin': true,
        SafetyCertificateOutlined: iconStub,
        ReloadOutlined: iconStub,
        ThunderboltOutlined: iconStub,
        CheckCircleOutlined: iconStub,
        SearchOutlined: iconStub,
      },
    },
  })
}

describe('ContentQCTab P1-G4 & P2-G2 回归测试', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('按需拉取完整文书与逐文书回退均走统一认证 apiClient，且无规则/全不适用时不硬编码 100%', async () => {
    apiGet.mockResolvedValue({
      data: {
        data: {
          documents: [
            {
              type: 'admission_record',
              label: '入院记录',
              has_content: true,
              content: '完整入院记录正文',
              length: 8,
            },
          ],
        },
      },
    })
    vi.mocked(evaluateSichuanBundleQC).mockRejectedValue(new Error('bundle unavailable'))
    apiPost.mockResolvedValue({
      data: {
        success: true,
        data: {
          status: 'success',
          evaluation_summary: { total_rules: 0, compliance_rate: null, issues_found: 0 },
          evaluation_results: [],
        },
      },
    })

    const wrapper = mountTab({
      documents: [
        {
          type: 'admission_record',
          label: '入院记录',
          has_content: true,
          content: null,
          length: 8,
        },
      ],
    })

    await wrapper.find('.content-qc-tab__header-action').trigger('click')
    await flushPromises()

    expect(apiGet).toHaveBeenCalledWith(
      '/api/v1/emr/V1/documents',
      expect.objectContaining({
        params: expect.objectContaining({ patient_id: 'P1', institute_id: 'H1', visit_id: 'V1', view: 'full' }),
      }),
    )
    expect(apiPost).toHaveBeenCalledWith(
      '/api/v1/qc/sichuan/evaluate',
      expect.objectContaining({ document_id: 'P1-V1-admission_record' }),
      expect.any(Object),
    )
    expect(wrapper.find('.summary-card__progress').text()).toBe('--')
    expect(wrapper.text()).not.toContain('100%')

    // 全不适用规则在逐文书回退下同样显示“无适用项”而非 100%
    apiPost.mockResolvedValueOnce({
      data: {
        success: true,
        data: {
          status: 'success',
          evaluation_summary: { total_rules: 1, compliance_rate: null, issues_found: 0 },
          evaluation_results: [
            {
              rule_id: 'SC-NA-1',
              rule_name: '仅手术患者适用',
              status: 'not_applicable',
              findings: '非手术病历不适用',
            },
          ],
        },
      },
    })
    await wrapper.find('.content-qc-tab__header-action').trigger('click')
    await flushPromises()
    expect(wrapper.find('.summary-card__progress').text()).toBe('无适用项')
    expect(wrapper.text()).not.toContain('100%')
    wrapper.unmount()
  })

  it('防重入保护：分析进行中重复点击不会发起第二次请求', async () => {
    const req = deferred<BatchQCEvaluateResponse>()
    vi.mocked(evaluateSichuanBundleQC).mockReturnValue(req.promise)

    const wrapper = mountTab()
    const trigger = wrapper.find('.content-qc-tab__header-action')
    await trigger.trigger('click')
    await trigger.trigger('click')
    expect(evaluateSichuanBundleQC).toHaveBeenCalledTimes(1)

    req.resolve({
      success: true,
      data: {
        document_id: 'H1-P1-V1',
        evaluation_summary: { total_rules: 1, compliance_rate: 100, issues_found: 0 },
        evaluation_results: [],
      },
    })
    await flushPromises()
    wrapper.unmount()
  })

  it('跨患者切换丢弃患者 A 晚到响应，且不触发回退或污染患者 B 面板', async () => {
    const reqA = deferred<BatchQCEvaluateResponse>()
    vi.mocked(evaluateSichuanBundleQC).mockReturnValueOnce(reqA.promise)

    const wrapper = mountTab({ patientId: 'P1', visitId: 'V1', instituteId: 'H1' })
    await wrapper.find('.content-qc-tab__header-action').trigger('click')

    // 切换到患者 B
    await wrapper.setProps({ patientId: 'P2', visitId: 'V2', instituteId: 'H1' })
    await flushPromises()

    // 患者 A 晚到响应返回
    reqA.resolve({
      success: true,
      data: {
        document_id: 'H1-P1-V1',
        evaluation_summary: { total_rules: 2, compliance_rate: 50, issues_found: 1 },
        evaluation_results: [
          {
            rule_id: 'SC-A1',
            rule_name: '患者A缺陷',
            status: 'non_compliant',
            is_compliant: false,
            findings: '患者A专属问题',
          },
        ],
      },
    })
    await flushPromises()

    expect(wrapper.text()).not.toContain('患者A专属问题')
    expect(wrapper.find('.content-qc-tab__empty').exists()).toBe(true)
    expect(apiPost).not.toHaveBeenCalled()

    // 患者 B 启动后又切到患者 C，患者 B 的 Bundle 失败也不能回退污染患者 C
    const reqB = deferred<BatchQCEvaluateResponse>()
    vi.mocked(evaluateSichuanBundleQC).mockReturnValueOnce(reqB.promise)
    await wrapper.find('.content-qc-tab__header-action').trigger('click')
    await wrapper.setProps({ patientId: 'P3', visitId: 'V3', instituteId: 'H1' })
    reqB.reject(new Error('network error'))
    await flushPromises()
    expect(apiPost).not.toHaveBeenCalled()
    expect(wrapper.find('.content-qc-tab__empty').exists()).toBe(true)
    wrapper.unmount()
  })

  it('状态分组筛选芯片与 STATUS_LABEL_MAP 文案完全对齐并真正过滤明细', async () => {
    vi.mocked(evaluateSichuanBundleQC).mockResolvedValue({
      success: true,
      data: {
        document_id: 'H1-P1-V1',
        evaluation_summary: { total_rules: 4, compliance_rate: 50, issues_found: 2 },
        evaluation_results: [
          {
            rule_id: 'R-NON',
            rule_name: '规则不合规',
            status: 'non_compliant',
            is_compliant: false,
            findings: '结论-不合规',
          },
          {
            rule_id: 'R-UNC',
            rule_name: '规则AI判断',
            status: 'uncertain',
            is_compliant: false,
            findings: '结论-AI判断',
          },
          {
            rule_id: 'R-GAP',
            rule_name: '规则数据不足',
            status: 'data_gap' as unknown as 'uncertain',
            is_compliant: false,
            findings: '结论-数据不足',
          },
          {
            rule_id: 'R-OK',
            rule_name: '规则合规',
            status: 'compliant',
            is_compliant: true,
            findings: '结论-合规',
          },
        ],
      },
    })

    const wrapper = mountTab()
    await wrapper.find('.content-qc-tab__header-action').trigger('click')
    await flushPromises()

    const findChip = (label: string) =>
      wrapper.findAll('.group-chip').find((chip) => chip.find('.group-chip__label').text() === label)

    const aiChip = findChip('AI判断')
    expect(aiChip).toBeTruthy()
    await aiChip!.trigger('click')
    await flushPromises()
    let cards = wrapper.findAll('.issue-card')
    expect(cards).toHaveLength(1)
    expect(cards[0].text()).toContain('结论-AI判断')

    const gapChip = findChip('数据不足')
    expect(gapChip).toBeTruthy()
    await gapChip!.trigger('click')
    await flushPromises()
    cards = wrapper.findAll('.issue-card')
    expect(cards).toHaveLength(1)
    expect(cards[0].text()).toContain('结论-数据不足')

    const okChip = findChip('合规')
    expect(okChip).toBeTruthy()
    await okChip!.trigger('click')
    await flushPromises()
    cards = wrapper.findAll('.issue-card')
    expect(cards).toHaveLength(1)
    expect(cards[0].text()).toContain('结论-合规')

    // 再次点击当前芯片取消筛选，恢复问题视图
    await okChip!.trigger('click')
    await flushPromises()
    cards = wrapper.findAll('.issue-card')
    expect(cards).toHaveLength(3)
    wrapper.unmount()
  })
})
