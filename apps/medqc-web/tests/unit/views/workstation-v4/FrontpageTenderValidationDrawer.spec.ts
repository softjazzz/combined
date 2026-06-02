import { defineComponent, h } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import FrontpageTenderValidationDrawer from '@/views/workstation-v4/components/FrontpageTenderValidationDrawer.vue'
import { frontpageApi } from '@/api/frontpage'

vi.mock('@/api/frontpage', () => ({
  frontpageApi: {
    generateReportDraft: vi.fn(),
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
})
