import { flushPromises, shallowMount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import V2View from '@/views/workstation-v2/CustomQCExperienceView.vue'
import V4View from '@/views/workstation-v4/CustomQCExperienceView.vue'

const mocks = vi.hoisted(() => ({
  getAdminRecordList: vi.fn(),
  getDepartmentList: vi.fn(),
  getRecordDetail: vi.fn(),
  testCustomQcSingle: vi.fn(),
  testCustomQcBatch: vi.fn(),
  saveCustomQcTestResult: vi.fn(),
  getAllRules: vi.fn(),
  createRule: vi.fn(),
  error: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: { scene: 'running' } }),
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('ant-design-vue', () => ({ message: { error: mocks.error, success: vi.fn() } }))

vi.mock('@/api/qcAdmin', () => ({
  getAdminRecordList: mocks.getAdminRecordList,
  getDepartmentList: mocks.getDepartmentList,
  getRecordDetail: mocks.getRecordDetail,
}))

vi.mock('@/services/custom-qc-experience-service', () => ({
  generateCustomQcPrompt: vi.fn(),
  saveCustomQcTestResult: mocks.saveCustomQcTestResult,
  testCustomQcBatch: mocks.testCustomQcBatch,
  testCustomQcSingle: mocks.testCustomQcSingle,
}))

vi.mock('@/services/rules-service', () => ({
  RulesService: { getAllRules: mocks.getAllRules, createRule: mocks.createRule },
}))

type TestView = {
  selectedRecordKeys: string[]
  draftRule: { name: string; description: string; prompt_template: string }
  canRunTest: boolean
  canPublish: boolean
  runSelectedTest: () => Promise<void>
  runDirectSingle: (record: { id: string; record_id: string }) => Promise<void>
  handlePublish: () => Promise<void>
}

const tableStub = defineComponent({
  props: { dataSource: { type: Array, default: () => [] } },
  setup(props, { slots }) {
    return () => h('div', { class: 'candidate-table' },
      props.dataSource.flatMap((record) => ['status', 'defect_count', 'action'].map((key) =>
        h('div', { class: `candidate-${key}` }, slots.bodyCell?.({ column: { key }, record })),
      )),
    )
  },
})

const stubs = {
  ...Object.fromEntries(
    [
      'tag', 'button', 'card', 'input', 'form-item', 'select', 'textarea', 'form',
      'alert', 'input-number', 'range-picker', 'table', 'empty',
    ].map((name) => [`a-${name}`, true]),
  ),
  'a-table': tableStub,
}

describe.each([
  ['V2', V2View],
  ['V4', V4View],
])('自定义试跑 %s 旧详情来源保护', (_version, component) => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getDepartmentList.mockResolvedValue({ success: true, data: [] })
    mocks.getAllRules.mockResolvedValue([])
    mocks.getAdminRecordList.mockResolvedValue({
      success: true,
      data: {
        items: [{ id: 'row-key', record_id: 'shared-visit', status: 'pending' }],
        total: 1,
      },
    })
    mocks.getRecordDetail.mockResolvedValue({
      success: true,
      data: { record: { content: '其他患者的病历正文' } },
    })
  })

  it('列表就诊号不被送入旧详情，失败时不执行或保存', async () => {
    const wrapper = shallowMount(component, { global: { stubs, renderStubDefaultSlot: true } })
    await flushPromises()
    const view = wrapper.vm as unknown as TestView
    view.selectedRecordKeys = ['shared-visit']
    view.draftRule.name = '病程记录完整性质控'
    view.draftRule.description = '核对每日病程记录是否包含完整处理意见'
    view.draftRule.prompt_template = '核对处理意见'

    await view.runSelectedTest()

    expect(mocks.getRecordDetail).not.toHaveBeenCalled()
    expect(mocks.testCustomQcSingle).not.toHaveBeenCalled()
    expect(mocks.testCustomQcBatch).not.toHaveBeenCalled()
    expect(mocks.saveCustomQcTestResult).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it.each(['passed', 'completed'])('旧 %s 状态不显示为已核实，单条试跑和发布均关闭', async (status) => {
    mocks.getAdminRecordList.mockResolvedValue({
      success: true,
      data: {
        items: [{ id: 'legacy-1', record_id: 'shared-visit', status, defect_count: 7 }],
        total: 1,
      },
    })
    const wrapper = shallowMount(component, { global: { stubs, renderStubDefaultSlot: true } })
    await flushPromises()
    const view = wrapper.vm as unknown as TestView
    view.selectedRecordKeys = ['shared-visit']
    view.draftRule.name = '病程记录完整性质控'
    view.draftRule.description = '核对每日病程记录是否包含完整处理意见'
    view.draftRule.prompt_template = '核对处理意见'
    await flushPromises()

    expect(wrapper.find('.candidate-status').text()).toBe('质控关联待核实')
    expect(wrapper.find('.candidate-defect_count').text()).toBe('-')
    expect(wrapper.find('.candidate-action a-button-stub').attributes('disabled')).toBeDefined()
    expect(view.canRunTest).toBe(false)
    expect(view.canPublish).toBe(false)
    await view.runDirectSingle({ id: 'legacy-1', record_id: 'shared-visit' })
    await view.handlePublish()
    expect(mocks.getRecordDetail).not.toHaveBeenCalled()
    expect(mocks.testCustomQcSingle).not.toHaveBeenCalled()
    expect(mocks.createRule).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
