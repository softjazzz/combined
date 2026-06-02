import { defineComponent, h } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import FrontpageTenderValidationDrawer from '@/views/workstation-v4/components/FrontpageTenderValidationDrawer.vue'
import { frontpageApi } from '@/api/frontpage'

vi.mock('@/api/frontpage', () => ({
  frontpageApi: {
    generateReportDraft: vi.fn(),
    getDemoVisitPreview: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
  },
}))

const passthroughStub = (name: string, tag = 'div') =>
  defineComponent({
    name,
    setup(_props, { attrs, slots }) {
      return () => h(tag, attrs, slots.default?.())
    },
  })

const DrawerStub = defineComponent({
  name: 'ADrawer',
  props: {
    open: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['update:open'],
  setup(props, { attrs, slots }) {
    return () =>
      h(
        'section',
        {
          ...attrs,
          'data-testid': 'tender-validation-drawer',
          open: String(props.open),
        },
        slots.default?.(),
      )
  },
})

const RadioGroupStub = defineComponent({
  name: 'ARadioGroup',
  props: {
    value: {
      type: String,
      default: 'combined',
    },
  },
  emits: ['update:value'],
  setup(props, { emit }) {
    return () =>
      h(
        'select',
        {
          'data-testid': 'scene-select',
          value: props.value,
          onChange: (event: Event) => {
            emit('update:value', (event.target as HTMLSelectElement).value)
          },
        },
        [
          h('option', { value: 'combined' }, '联合草稿'),
          h('option', { value: 'nhc_frontpage' }, '病案首页'),
          h('option', { value: 'insurance_settlement' }, '医保结算清单'),
        ],
      )
  },
})

const TextareaStub = defineComponent({
  name: 'ATextarea',
  props: {
    value: {
      type: String,
      default: '',
    },
  },
  emits: ['update:value'],
  setup(props, { attrs, emit }) {
    return () =>
      h('textarea', {
        ...attrs,
        'data-testid': 'medical-text',
        value: props.value,
        onInput: (event: Event) => {
          emit('update:value', (event.target as HTMLTextAreaElement).value)
        },
      })
  },
})

const ButtonStub = defineComponent({
  name: 'AButton',
  setup(_props, { attrs, slots }) {
    return () => h('button', attrs, slots.default?.())
  },
})

const ModalStub = defineComponent({
  name: 'AModal',
  props: {
    open: {
      type: Boolean,
      default: false,
    },
  },
  setup(props, { attrs, slots }) {
    return () =>
      props.open
        ? h(
            'section',
            {
              ...attrs,
              'data-testid': 'formatted-preview-modal',
            },
            slots.default?.(),
          )
        : null
  },
})

const TabsStub = defineComponent({
  name: 'ATabs',
  setup(_props, { attrs, slots }) {
    return () => h('div', attrs, slots.default?.())
  },
})

const TabPaneStub = defineComponent({
  name: 'ATabPane',
  setup(_props, { attrs, slots }) {
    return () => h('div', attrs, slots.default?.())
  },
})

const FrontpageSheetStub = defineComponent({
  name: 'FrontpageSheet',
  props: {
    data: {
      type: Object,
      default: () => ({}),
    },
  },
  setup(props) {
    return () =>
      h('div', { 'data-testid': 'frontpage-sheet-stub' }, [
        h('span', String((props.data as any)?.basic?.name || '')),
        h('span', String((props.data as any)?.diagnoses?.[0]?.diagnosis_name || '')),
      ])
  },
})

const SettlementSheetStub = defineComponent({
  name: 'SettlementSheet',
  props: {
    data: {
      type: Object,
      default: () => ({}),
    },
  },
  setup(props) {
    return () =>
      h('div', { 'data-testid': 'settlement-sheet-stub' }, [
        h('span', String((props.data as any)?.patient_name || '')),
        h('span', String((props.data as any)?.total_cost || '')),
      ])
  },
})

function mountDrawer() {
  return mount(FrontpageTenderValidationDrawer, {
    props: {
      open: true,
    },
    global: {
      stubs: {
        ADrawer: DrawerStub,
        AAlert: passthroughStub('AAlert'),
        AForm: passthroughStub('AForm', 'form'),
        AFormItem: passthroughStub('AFormItem'),
        ARadioGroup: RadioGroupStub,
        ARadioButton: passthroughStub('ARadioButton'),
        ATextarea: TextareaStub,
        AButton: ButtonStub,
        ASpin: passthroughStub('ASpin'),
        AEmpty: passthroughStub('AEmpty'),
        ACollapse: passthroughStub('ACollapse'),
        ACollapsePanel: passthroughStub('ACollapsePanel'),
        AModal: ModalStub,
        ATabs: TabsStub,
        ATabPane: TabPaneStub,
        FrontpageSheet: FrontpageSheetStub,
        SettlementSheet: SettlementSheetStub,
      },
    },
  })
}

const baseFrontpageDraft = {
  basic_info: {},
  hospitalization: {},
  diagnoses: {},
  procedures: {},
  other_medical_info: {},
  staff: {},
  costs: {},
  evidence: {},
  confidence: {},
}

async function clickStartValidation(wrapper: ReturnType<typeof mountDrawer>) {
  const startButton = wrapper.findAll('button').find((button) => button.text().includes('开始验证'))
  if (!startButton) {
    throw new Error('开始验证按钮未渲染')
  }
  await startButton.trigger('click')
}

describe('FrontpageTenderValidationDrawer', () => {
  beforeEach(() => {
    vi.mocked(frontpageApi.generateReportDraft).mockReset()
    vi.mocked(frontpageApi.getDemoVisitPreview).mockReset()
    vi.mocked(frontpageApi.getDemoVisitPreview).mockResolvedValue({
      success: true,
      data: {
        visit_id: '1870471',
        patient_id_masked: '00******33',
        patient_name_masked: '李*',
        department: '外二科',
        admission_date: '2026-04-01 09:00:00',
        discharge_date: '2026-04-08 10:00:00',
        document_count: 2,
        document_types: ['入院记录', '手术记录'],
        text_preview: '【入院记录】\n患者因腹痛入院。\n【手术记录】\n行腹腔镜手术。',
      },
    })
  })

  it('renders preset medical record examples', () => {
    const wrapper = mountDrawer()

    expect(wrapper.find('[data-testid="frontpage-demo-presets"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('预置病历示例')
    expect(wrapper.text()).toContain('示例一：内科出院病例')
    expect(wrapper.text()).toContain('示例二：外科手术病例')
    expect(wrapper.text()).toContain('示例三：ICU 呼吸机病例')
    expect(wrapper.text()).toContain('示例四：中医诊断病例')
  })

  it('submits selected scene and medical_text to generate-report-draft', async () => {
    vi.mocked(frontpageApi.generateReportDraft).mockResolvedValue({
      success: true,
      data: {
        scene: 'insurance_settlement',
        frontpage: baseFrontpageDraft,
        settlement: { total_cost: '100.00' },
        coverage: {
          scene: 'insurance_settlement',
          status: 'partial',
          total: 83,
          present: 80,
          partial: 0,
          missing: 3,
          text_extraction: { success: 80, total: 83 },
          settlement_from_frontpage: { success: 66, total: 70 },
          fields: [
            {
              group: '费用信息',
              field: '自付费用',
              path: 'frontpage.costs.self_paid',
              status: 'missing',
              message: '未抽取到自付费用',
            },
          ],
          warnings: ['费用信息-自付费用缺失'],
        },
        warnings: ['费用信息-自付费用缺失'],
      },
    })
    const wrapper = mountDrawer()

    await wrapper.find('[data-testid="scene-select"]').setValue('insurance_settlement')
    await wrapper.find('[data-testid="medical-text"]').setValue('完整病历文本')
    await clickStartValidation(wrapper)
    await flushPromises()

    expect(frontpageApi.generateReportDraft).toHaveBeenCalledWith({
      scene: 'insurance_settlement',
      medical_text: '完整病历文本',
    })
  })

  it('loads preset, shows source summary and submits visit_id with synthetic document', async () => {
    vi.mocked(frontpageApi.generateReportDraft).mockResolvedValue({
      success: true,
      data: {
        scene: 'combined',
        frontpage: baseFrontpageDraft,
        settlement: { total_cost: '52680.80' },
        coverage: {
          scene: 'combined',
          status: 'complete',
          total: 83,
          present: 83,
          partial: 0,
          missing: 0,
          text_extraction: { success: 83, total: 83 },
          settlement_from_frontpage: { success: 70, total: 70 },
          fields: [],
          warnings: [],
        },
        warnings: [],
      },
    })
    const wrapper = mountDrawer()

    await wrapper.find('[data-testid="scene-select"]').setValue('nhc_frontpage')
    await wrapper
      .find('[data-testid="frontpage-demo-preset-demo-surgery-anesthesia"]')
      .trigger('click')
    await flushPromises()

    expect(frontpageApi.getDemoVisitPreview).toHaveBeenCalledWith({
      visit_id: '1870471',
      patient_id: '0000534433',
    })
    expect(wrapper.find('[data-testid="preset-source-summary"]').exists()).toBe(true)
    expect(wrapper.html()).toContain('已加载本机病历示例')
    expect(wrapper.text()).toContain('外二科')
    expect(wrapper.text()).toContain('入院记录')
    expect(wrapper.text()).toContain('手术记录')
    expect(wrapper.find('[data-testid="preset-text-preview"]').text()).toContain('患者因腹痛入院')
    expect(wrapper.find('[data-testid="preset-synthetic-settlement"]').text()).toContain(
      'demo/synthetic 演示补充信息',
    )
    expect(wrapper.find('[data-testid="medical-text"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="medical-text-preset-readonly"]').text()).toContain(
      '后端按 visit_id 读取本机病历全文',
    )

    await clickStartValidation(wrapper)
    await flushPromises()

    expect(frontpageApi.generateReportDraft).toHaveBeenCalledWith(
      expect.objectContaining({
        scene: 'combined',
        visit_id: '1870471',
        patient_id: '0000534433',
        documents: [
          expect.objectContaining({
            type: '演示用医保结算补充信息',
            content: expect.stringContaining('demo/synthetic 演示补充信息'),
            meta: expect.objectContaining({
              source: 'demo/synthetic',
              preset_id: 'demo-surgery-anesthesia',
            }),
          }),
        ],
      }),
    )
    expect(frontpageApi.generateReportDraft).toHaveBeenCalledWith(
      expect.not.objectContaining({
        medical_text: expect.any(String),
      }),
    )
    expect(wrapper.html()).toContain('包含演示用虚拟医保费用数据')
  })

  it('shows friendly fallback when demo preview endpoint is not available', async () => {
    vi.mocked(frontpageApi.getDemoVisitPreview).mockRejectedValue({
      response: { status: 404 },
    })
    const wrapper = mountDrawer()

    await wrapper
      .find('[data-testid="frontpage-demo-preset-demo-surgery-anesthesia"]')
      .trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="preset-source-summary"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('当前后端尚未启用脱敏病历预览接口')
    expect(wrapper.text()).not.toContain('Request failed with status code 404')
    expect(wrapper.find('[data-testid="medical-text-preset-readonly"]').text()).toContain(
      '后端按 visit_id 读取本机病历全文',
    )
  })

  it('renders coverage metrics, warnings and missing fields from response', async () => {
    vi.mocked(frontpageApi.generateReportDraft).mockResolvedValue({
      success: true,
      data: {
        scene: 'combined',
        frontpage: baseFrontpageDraft,
        settlement: { total_cost: '100.00' },
        coverage: {
          scene: 'combined',
          status: 'partial',
          total: 83,
          present: 80,
          partial: 0,
          missing: 3,
          text_extraction: { success: 80, total: 83 },
          settlement_from_frontpage: { success: 66, total: 70 },
          fields: [
            {
              group: '其他住院医疗信息',
              field: 'ICU类型',
              path: 'frontpage.other_medical_info.icu.type',
              status: 'missing',
              message: '未抽取到 ICU 类型',
            },
          ],
          warnings: ['其他住院医疗信息-ICU类型缺失'],
        },
        warnings: ['其他住院医疗信息-ICU类型缺失'],
      },
    })
    const wrapper = mountDrawer()

    await wrapper.find('[data-testid="medical-text"]').setValue('完整病历文本')
    await clickStartValidation(wrapper)
    await flushPromises()

    expect(wrapper.text()).toContain('80/83')
    expect(wrapper.text()).toContain('66/70')
    expect(wrapper.text()).toContain('其他住院医疗信息-ICU类型缺失')
    expect(wrapper.text()).toContain('frontpage.other_medical_info.icu.type')
  })

  it('opens formatted preview modal with official sheet components', async () => {
    vi.mocked(frontpageApi.generateReportDraft).mockResolvedValue({
      success: true,
      data: {
        scene: 'combined',
        frontpage: {
          ...baseFrontpageDraft,
          basic_info: {
            patient_name: '测试患者',
            gender_text: '男',
          },
          hospitalization: {
            hospital_name: '测试医院',
            medical_record_no: 'MR001',
          },
          diagnoses: {
            discharge_main_diagnosis_text: '蛛网膜下腔出血',
            discharge_main_icd: 'I60.900',
          },
        },
        settlement: {
          patient_name: '测试患者',
          total_cost: '100.00',
        },
        coverage: {
          scene: 'combined',
          status: 'complete',
          total: 83,
          present: 83,
          partial: 0,
          missing: 0,
          fields: [],
          warnings: [],
        },
        warnings: [],
      },
    })
    const wrapper = mountDrawer()

    await wrapper.find('[data-testid="medical-text"]').setValue('完整病历文本')
    await clickStartValidation(wrapper)
    await flushPromises()

    expect(wrapper.find('[data-testid="open-formatted-preview"]').exists()).toBe(true)
    await wrapper.find('[data-testid="open-formatted-preview"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="formatted-preview-modal"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="formatted-frontpage-preview"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="formatted-settlement-preview"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="frontpage-sheet-stub"]').text()).toContain('测试患者')
    expect(wrapper.find('[data-testid="frontpage-sheet-stub"]').text()).toContain('蛛网膜下腔出血')
    expect(wrapper.find('[data-testid="settlement-sheet-stub"]').text()).toContain('100.00')
  })
})
