/* eslint-disable vue/one-component-per-file */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import SyntheticCaseBuilderView from '@/views/workstation-v4/customer-sample-validation/SyntheticCaseBuilderView.vue'

let capturedBeforeRouteLeave: (() => Promise<boolean> | boolean) | null = null

const {
  message,
  Modal,
  routeQuery,
  routerPush,
  createManualTestMedicalRecord,
  listLuxian0609CustomerRules,
  runManualSamplePool,
} = vi.hoisted(() => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  },
  Modal: {
    confirm: vi.fn(),
  },
  routeQuery: {} as Record<string, string>,
  routerPush: vi.fn(),
  createManualTestMedicalRecord: vi.fn(),
  listLuxian0609CustomerRules: vi.fn(),
  runManualSamplePool: vi.fn(),
}))

vi.mock('ant-design-vue', () => ({
  message,
  Modal,
  DatePicker: defineComponent({
    name: 'ADatePickerStub',
    setup() {
      return () => h('input')
    },
  }),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: routeQuery }),
  useRouter: () => ({ push: routerPush }),
  onBeforeRouteLeave: (guard: () => Promise<boolean> | boolean) => {
    capturedBeforeRouteLeave = guard
  },
}))

vi.mock('@/services/manual-case-sample-service', () => ({
  createManualTestMedicalRecord,
  listLuxian0609CustomerRules,
  runManualSamplePool,
}))

const ButtonStub = defineComponent({
  inheritAttrs: false,
  setup(_, { attrs, slots }) {
    return () => h('button', attrs, slots.default?.())
  },
})

const InputStub = defineComponent({
  props: { value: [String, Number], type: String },
  emits: ['update:value'],
  setup(props, { attrs, emit }) {
    return () =>
      h('input', {
        ...attrs,
        type: props.type || 'text',
        value: props.value ?? '',
        onInput: (e: Event) => emit('update:value', (e.target as HTMLInputElement).value),
      })
  },
})

const TextareaStub = defineComponent({
  props: { value: String },
  emits: ['update:value'],
  setup(props, { attrs, emit }) {
    return () =>
      h('textarea', {
        ...attrs,
        value: props.value ?? '',
        onInput: (e: Event) => emit('update:value', (e.target as HTMLTextAreaElement).value),
      })
  },
})

const passthroughStub = defineComponent({
  inheritAttrs: false,
  setup(_, { attrs, slots }) {
    return () => h('div', attrs, slots.default?.())
  },
})

function mountBuilder() {
  window.localStorage?.setItem('medqc_synthetic_case_builder_guide_seen_v1', 'true')
  return mount(SyntheticCaseBuilderView, {
    global: {
      stubs: {
        MqIcon: true,
        'a-button': ButtonStub,
        'a-input': InputStub,
        'a-input-number': InputStub,
        'a-textarea': TextareaStub,
        'a-select': passthroughStub,
        'a-switch': passthroughStub,
        'a-modal': passthroughStub,
      },
    },
  })
}

describe('SyntheticCaseBuilderView (P1-12)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    capturedBeforeRouteLeave = null
    Object.keys(routeQuery).forEach((key) => delete routeQuery[key])
    listLuxian0609CustomerRules.mockResolvedValue({
      success: true,
      data: {
        rules: [
          {
            rule_id: 'LX0609-01-01-01',
            name: '入院记录24小时时限',
            required_documents_label: '入院记录',
          },
          {
            rule_id: 'LX0609-03-01-01',
            name: '会诊执行记录',
            required_documents_label: '会诊记录',
          },
          {
            rule_id: 'LX0609-06-01-05',
            name: 'CT/MRI 阳性结果未分析',
            required_documents_label: '检查报告',
          },
          {
            rule_id: 'LX0609-02-01-04',
            name: '病重查房频次',
            required_documents_label: '病程记录',
          },
        ],
      },
    })
    createManualTestMedicalRecord.mockResolvedValue({
      success: true,
      data: {
        pool: { id: 'customer-created-test-records-v1' },
        visit_id: 'VISIT-1',
        mr_no: 'MR-1',
        item: {
          id: 'ITEM-1',
          matched_institute_id: 'INST-1',
          matched_patient_id: 'PAT-1',
          matched_visit_id: 'VISIT-1',
        },
      },
    })
    runManualSamplePool.mockResolvedValue({
      success: true,
      data: { job_id: 'JOB-1' },
    })
  })

  it('query 传入 ruleFamily=exam_lab 时选中检查检验族，且目录加载后不覆盖用户手动切换的规则族', async () => {
    let resolveCatalog!: (v: unknown) => void
    const catalogDeferred = new Promise((resolve) => {
      resolveCatalog = resolve
    })
    listLuxian0609CustomerRules.mockReturnValueOnce(catalogDeferred)
    routeQuery.ruleFamily = 'exam_lab'

    const wrapper = mountBuilder()
    await flushPromises()

    // 初始选中“检查检验”
    expect(wrapper.find('.synthetic-case-template.is-active').text()).toContain('检查检验')

    // 用户在目录返回前手动切到“会诊质量”
    const consultationBtn = wrapper
      .findAll('.synthetic-case-template')
      .find((btn) => btn.text().includes('会诊质量'))
    await consultationBtn!.trigger('click')
    expect(wrapper.find('.synthetic-case-template.is-active').text()).toContain('会诊质量')

    // 目录迟到返回，不应把规则族覆写回 exam_lab
    resolveCatalog({
      success: true,
      data: {
        rules: [
          { rule_id: 'LX0609-03-01-01', name: '会诊执行记录', required_documents_label: '会诊记录' },
          { rule_id: 'LX0609-06-01-05', name: 'CT/MRI 阳性结果未分析', required_documents_label: '检查报告' },
        ],
      },
    })
    await flushPromises()
    expect(wrapper.find('.synthetic-case-template.is-active').text()).toContain('会诊质量')
  })

  it('左侧文书目录点击切换到步骤2文书页并等待 DOM 更新后滚动到目标文书', async () => {
    routeQuery.ruleIds = 'LX0609-01-01-01'
    const scrollIntoView = vi.fn()
    const wrapper = mountBuilder()
    await flushPromises()

    // 生成病历草稿进入步骤 2（默认 overview tab）
    await wrapper.get('.synthetic-case-generate-button').trigger('click')
    await flushPromises()

    // 进入步骤 3
    const nextBtn = wrapper.findAll('button').find((btn) => btn.text().trim() === '下一步')
    await nextBtn!.trigger('click')
    await flushPromises()
    expect(wrapper.find('.synthetic-case-confirm-card').exists()).toBe(true)

    const getElSpy = vi.spyOn(document, 'getElementById').mockReturnValue({
      scrollIntoView,
    } as unknown as HTMLElement)

    // 在步骤 3 点击左侧文书目录
    const docNavBtn = wrapper.get('.synthetic-case-doc-nav button')
    await docNavBtn.trigger('click')
    await flushPromises()

    expect(wrapper.find('.synthetic-case-doc-list').exists()).toBe(true)
    expect(scrollIntoView).toHaveBeenCalledTimes(1)
    getElSpy.mockRestore()
  })

  it('校验出院时间不能早于入院时间，未保存离开触发守卫，保存后导航跳过守卫且防重复提交', async () => {
    routeQuery.ruleIds = 'LX0609-01-01-01'
    const wrapper = mountBuilder()
    await flushPromises()

    // 未修改时离开守卫直接放行
    expect(await capturedBeforeRouteLeave?.()).toBe(true)

    // 生成草稿后即存在未保存修改
    await wrapper.get('.synthetic-case-generate-button').trigger('click')
    await flushPromises()

    // 触发离开守卫 -> 弹窗确认，用户取消则阻止离开
    Modal.confirm.mockImplementationOnce(({ onCancel }: { onCancel?: () => void }) => onCancel?.())
    expect(await capturedBeforeRouteLeave?.()).toBe(false)
    expect(Modal.confirm).toHaveBeenCalledTimes(1)

    // 设置出院时间早于入院时间 -> 校验拦截
    const dateInputs = wrapper.findAll('input[type="datetime-local"]')
    await dateInputs[0].setValue('2026-06-10T10:00')
    await dateInputs[1].setValue('2026-06-09T08:00')
    const nextBtn = wrapper.findAll('button').find((btn) => btn.text().trim() === '下一步')
    await nextBtn!.trigger('click')
    await flushPromises()

    const saveBtn = wrapper
      .findAll('.synthetic-case-confirm-actions button')
      .find((btn) => btn.text().includes('仅保存测试病历'))
    await saveBtn!.trigger('click')
    await flushPromises()
    expect(message.warning).toHaveBeenCalledWith('出院时间不能早于入院时间')
    expect(createManualTestMedicalRecord).not.toHaveBeenCalled()

    // 修正出院时间，测试保存并验证防重入 + runManualSamplePool 异常兜底 + 导航跳过守卫
    const backEditBtn = wrapper
      .findAll('.synthetic-case-confirm-actions button')
      .find((btn) => btn.text().includes('返回编辑'))
    await backEditBtn!.trigger('click')
    await flushPromises()
    const dateInputs2 = wrapper.findAll('input[type="datetime-local"]')
    await dateInputs2[1].setValue('2026-06-12T08:00')
    const nextBtn2 = wrapper.findAll('button').find((btn) => btn.text().trim() === '下一步')
    await nextBtn2!.trigger('click')
    await flushPromises()

    let resolveCreate!: (v: unknown) => void
    const createDeferred = new Promise((resolve) => {
      resolveCreate = resolve
    })
    createManualTestMedicalRecord.mockReturnValueOnce(createDeferred)
    runManualSamplePool.mockRejectedValueOnce(new Error('质控引擎繁忙'))

    const saveAndRunBtn = wrapper
      .findAll('.synthetic-case-confirm-actions button')
      .find((btn) => btn.text().includes('保存并验证选中质控点'))
    await saveAndRunBtn!.trigger('click')
    await saveAndRunBtn!.trigger('click') // 双击应被守卫拦截
    expect(createManualTestMedicalRecord).toHaveBeenCalledTimes(1)

    resolveCreate({
      success: true,
      data: {
        pool: { id: 'customer-created-test-records-v1' },
        visit_id: 'VISIT-1',
        mr_no: 'MR-1',
        item: {
          id: 'ITEM-1',
          matched_institute_id: 'INST-1',
          matched_patient_id: 'PAT-1',
          matched_visit_id: 'VISIT-1',
        },
      },
    })
    await flushPromises()

    expect(message.warning).toHaveBeenCalledWith('质控引擎繁忙')
    expect(routerPush).toHaveBeenCalledTimes(1)
    // 保存后导航跳过离开守卫
    expect(await capturedBeforeRouteLeave?.()).toBe(true)
  })
})
