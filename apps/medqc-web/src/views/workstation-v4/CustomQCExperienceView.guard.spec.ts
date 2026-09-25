import { flushPromises, shallowMount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import V2View from '../workstation-v2/CustomQCExperienceView.vue'
import V4View from './CustomQCExperienceView.vue'

const state = vi.hoisted(() => ({
  routeQuery: { scene: 'running' },
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

vi.mock('vue-router', async () => {
  const { reactive } = await vi.importActual<typeof import('vue')>('vue')
  state.routeQuery = reactive(state.routeQuery)
  return {
    useRoute: () => ({ query: state.routeQuery }),
    useRouter: () => ({ push: vi.fn() }),
  }
})

vi.mock('ant-design-vue', () => ({ message: { error: state.error, success: vi.fn() } }))

vi.mock('@/api/qcAdmin', () => ({
  getAdminRecordList: state.getAdminRecordList,
  getDepartmentList: state.getDepartmentList,
  getRecordDetail: state.getRecordDetail,
}))

vi.mock('@/services/custom-qc-experience-service', () => ({
  generateCustomQcPrompt: vi.fn(),
  saveCustomQcTestResult: state.saveCustomQcTestResult,
  testCustomQcBatch: state.testCustomQcBatch,
  testCustomQcSingle: state.testCustomQcSingle,
}))

vi.mock('@/services/rules-service', () => ({
  RulesService: { getAllRules: state.getAllRules, createRule: state.createRule },
}))

type GuardView = {
  records: unknown[]
  selectedRecordKeys: string[]
  pagination: { total: number }
  draftRule: { name: string; description: string; prompt_template: string }
  advancedParams: { temperature: number }
  singleResult: unknown | null
  batchResult: unknown | null
  canPublish: boolean
  fetchRecords: () => Promise<void>
  runSelectedTest: () => Promise<void>
  handlePublish: () => Promise<void>
}

const stubs = Object.fromEntries(
  [
    'tag', 'button', 'card', 'input', 'form-item', 'select', 'textarea', 'form',
    'alert', 'input-number', 'range-picker', 'table', 'empty',
  ].map((name) => [`a-${name}`, true]),
)

function render(component: typeof V2View | typeof V4View) {
  return shallowMount(component, { global: { stubs } })
}

async function attemptRunningTest(view: GuardView) {
  view.selectedRecordKeys = ['old-1']
  view.draftRule.name = '病程记录完整性质控'
  view.draftRule.description = '核对每日病程记录是否包含完整处理意见'
  view.draftRule.prompt_template = '核对处理意见'
  await view.runSelectedTest()
  expect(view.canPublish).toBe(false)
  expect(state.getRecordDetail).not.toHaveBeenCalled()
  expect(state.testCustomQcSingle).not.toHaveBeenCalled()
  expect(state.testCustomQcBatch).not.toHaveBeenCalled()
  expect(state.saveCustomQcTestResult).not.toHaveBeenCalled()
}

describe.each([
  ['V2', V2View],
  ['V4', V4View],
])('旧自定义试跑 %s 失败保护', (_version, component) => {
  beforeEach(() => {
    vi.clearAllMocks()
    state.routeQuery.scene = 'running'
    state.getDepartmentList.mockResolvedValue({ success: true, data: [] })
    state.getAllRules.mockResolvedValue([])
    state.getRecordDetail.mockResolvedValue({
      success: true,
      data: { record: { content: '病程记录：今日已复评病情。' } },
    })
    state.testCustomQcSingle.mockResolvedValue({
      success: true,
      data: {
        rule: { name: '病程记录完整性质控', document_type: '病程记录' },
        record: { record_id: 'old-1' },
        result: { is_compliant: true },
      },
    })
    state.getAdminRecordList.mockResolvedValue({
      success: true,
      data: {
        items: [{ id: 'old-1', record_id: 'old-1', status: 'pending', defect_count: 0 }],
        total: 1,
      },
    })
  })

  it.each(['业务失败', '网络异常'])('%s时清空旧候选、选中项及总数', async (reason) => {
    const wrapper = render(component)
    await flushPromises()
    const view = wrapper.vm as unknown as GuardView
    expect(view.records).toHaveLength(1)

    await attemptRunningTest(view)
    if (reason === '业务失败') {
      state.getAdminRecordList.mockResolvedValueOnce({ success: false, message: '旧入口不可用' })
    } else {
      state.getAdminRecordList.mockRejectedValueOnce(new Error('网络异常'))
    }
    await view.fetchRecords()

    expect(view.records).toEqual([])
    expect(view.selectedRecordKeys).toEqual([])
    expect(view.pagination.total).toBe(0)
    expect(view.singleResult).toBeNull()
    expect(view.batchResult).toBeNull()
    expect(view.canPublish).toBe(false)
    wrapper.unmount()
  })

  it('终末场景直接调用试跑函数也不执行或保存', async () => {
    state.routeQuery.scene = 'final'
    const wrapper = render(component)
    await flushPromises()
    const view = wrapper.vm as unknown as GuardView
    view.selectedRecordKeys = ['old-1']
    view.draftRule.name = '出院用药质控规则'
    view.draftRule.description = '检查出院记录中的用药说明是否完整'
    view.draftRule.prompt_template = '检查出院用药说明'
    await nextTick()

    await view.runSelectedTest()

    expect(state.testCustomQcSingle).not.toHaveBeenCalled()
    expect(state.testCustomQcBatch).not.toHaveBeenCalled()
    expect(state.saveCustomQcTestResult).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('切到终末后清除旧试跑证据，直接调用发布也不提交规则', async () => {
    const wrapper = render(component)
    await flushPromises()
    const view = wrapper.vm as unknown as GuardView
    await attemptRunningTest(view)

    state.routeQuery.scene = 'final'
    await nextTick()
    expect(view.singleResult).toBeNull()
    expect(view.batchResult).toBeNull()
    expect(view.canPublish).toBe(false)
    await view.handlePublish()
    expect(state.getAllRules).not.toHaveBeenCalled()
    expect(state.createRule).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('来源未核实时切场景也不查询规则号或创建规则', async () => {
    const wrapper = render(component)
    await flushPromises()
    const view = wrapper.vm as unknown as GuardView
    await attemptRunningTest(view)
    await view.handlePublish()
    expect(state.getAllRules).not.toHaveBeenCalled()

    state.routeQuery.scene = 'final'
    await nextTick()

    expect(state.createRule).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('来源未核实时修改草稿，仍不可发布', async () => {
    const wrapper = render(component)
    await flushPromises()
    const view = wrapper.vm as unknown as GuardView
    await attemptRunningTest(view)

    view.draftRule.description = '改为核对不同的临床事实'
    await nextTick()
    expect(view.canPublish).toBe(false)
    await view.handlePublish()
    expect(state.createRule).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('来源未核实时修改检查逻辑参数，仍不可发布', async () => {
    const wrapper = render(component)
    await flushPromises()
    const view = wrapper.vm as unknown as GuardView
    await attemptRunningTest(view)

    view.advancedParams.temperature = 0.7
    await nextTick()
    expect(view.canPublish).toBe(false)
    await view.handlePublish()
    expect(state.createRule).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('来源未核实时直接调用试跑，不发起请求或保存结果', async () => {
    const wrapper = render(component)
    await flushPromises()
    const view = wrapper.vm as unknown as GuardView
    view.selectedRecordKeys = ['old-1']
    view.draftRule.name = '病程记录完整性质控'
    view.draftRule.description = '核对每日病程记录是否包含完整处理意见'
    view.draftRule.prompt_template = '核对处理意见'

    await view.runSelectedTest()
    await flushPromises()
    expect(state.getRecordDetail).not.toHaveBeenCalled()
    expect(state.testCustomQcSingle).not.toHaveBeenCalled()
    view.draftRule.prompt_template = '改为核对其他条件'
    await nextTick()

    expect(state.saveCustomQcTestResult).not.toHaveBeenCalled()
    expect(view.singleResult).toBeNull()
    wrapper.unmount()
  })

  it('来源未核实时修改草稿也不查询规则号或创建规则', async () => {
    const wrapper = render(component)
    await flushPromises()
    const view = wrapper.vm as unknown as GuardView
    await attemptRunningTest(view)
    await view.handlePublish()
    expect(state.getAllRules).not.toHaveBeenCalled()
    view.draftRule.name = '修改后的规则'
    await nextTick()

    expect(state.createRule).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
