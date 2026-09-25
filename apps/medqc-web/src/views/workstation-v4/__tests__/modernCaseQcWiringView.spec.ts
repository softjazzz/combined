import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, shallowMount } from '@vue/test-utils'
import { defineComponent, h, nextTick } from 'vue'

// onMounted 里还有列表/通知等异步任务，测试结束必须卸载，避免悬挂的 rejection。
enableAutoUnmount(afterEach)
const apiGet = vi.hoisted(() => vi.fn())
const apiRequest = vi.hoisted(() => vi.fn())
const routeQuery = vi.hoisted(() => ({ value: {} as Record<string, string> }))

vi.mock('@/services/apiService', async () => {
  const actual =
    await vi.importActual<typeof import('@/services/apiService')>('@/services/apiService')
  // 只替换传输层，保留真实 ApiService 的鉴权/错误包装行为。
  actual.apiClient.get = apiGet as never
  actual.apiClient.request = apiRequest as never
  return { ...actual, apiClient: actual.apiClient }
})
vi.mock('vue-router', () => ({
  useRoute: () => ({
    query: routeQuery.value,
    get fullPath() {
      return ''
    },
  }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}))

import WorkstationV4View from '../WorkstationV4View.vue'
import WorkstationV4ListView from '../components/WorkstationV4ListView.vue'

const WORKLIST_KEY = 'worklist:["LX001","P-1","V-1"]'
const LEGACY_KEY = 'LEGACY-1'

/**
 * shallowMount 会把 WorkstationV4DetailView 换成不渲染具名插槽的空壳，
 * 那样「写工作区未渲染」的断言永远是空断言。这里显式渲染三个具名插槽，
 * 让 FrontpageWorkspace / SettlementWorkspace 的真实渲染条件可被证伪。
 */
const DetailViewStub = defineComponent({
  name: 'WorkstationV4DetailView',
  setup(_props, { slots }) {
    return () =>
      h('div', { class: 'detail-view-stub' }, [
        slots.records?.(),
        slots.frontpage?.(),
        slots.settlement?.(),
      ])
  },
})

async function flush() {
  for (let i = 0; i < 3; i += 1) {
    await Promise.resolve()
    await nextTick()
  }
}

function worklistPayload(
  workflowType: 'frontpage' | 'coding' | 'settlement',
  identityStatus: 'unverified' | 'ambiguous' = 'unverified',
) {
  return {
    items: [
      {
        institute_id: 'LX001',
        patient_id: 'P-1',
        visit_id: 'V-1',
        patient_name: '测试患者',
        workflow_type: workflowType,
        identity_status: identityStatus,
      },
    ],
    total: 1,
    total_pages: 1,
    departments: [],
  }
}

function mountView() {
  return shallowMount(WorkstationV4View, {
    global: {
      stubs: {
        // 按组件名替换：渲染三个具名插槽，避免写工作区断言变成空断言。
        'WorkstationV4DetailView': DetailViewStub,
        'a-segmented': true,
        'a-button': true,
        'a-modal': true,
        'a-textarea': true,
        'a-input': true,
        'a-popconfirm': true,
        'a-tooltip': true,
      },
    },
  })
}

/** 快照接口回包必须原样回显请求的 source_key 与三坐标，否则客户端按身份错配拒绝。 */
function mockSnapshotRequest() {
  apiRequest.mockImplementation((config: { params?: Record<string, string> }) => {
    const params = config?.params ?? {}
    return Promise.resolve({
      status: 200,
      data: {
        success: true,
        data: {
          identity_status: 'verified',
          source_key: params.source_key,
          institute_id: params.institute_id,
          patient_id: params.patient_id,
          visit_id: params.visit_id,
          latest_qc_result: null,
          recent_results: [],
          active_defects: [],
          current_result_defects: [],
          latest_notification: null,
        },
      },
    })
  })
}

async function selectOnlyWorklistRow(wrapper: ReturnType<typeof mountView>) {
  const list = wrapper.findComponent(WorkstationV4ListView)
  expect(list.exists()).toBe(true)
  list.vm.$emit('open-record', WORKLIST_KEY)
  await flush()
}

describe('WorkstationV4View 现代只读面板接线（渲染）', () => {
  beforeEach(() => {
    apiGet.mockReset()
    apiRequest.mockReset()
    routeQuery.value = { stage: 'settlement_qc' }
    mockSnapshotRequest()
  })

  function mockWorklist(
    workflowType: 'frontpage' | 'coding' | 'settlement',
    identityStatus: 'unverified' | 'ambiguous' = 'unverified',
    legacyRecords: Array<Record<string, unknown>> = [],
  ) {
    apiGet.mockImplementation((url: string) => {
      const target = String(url)
      if (target.includes('/worklist')) {
        return Promise.resolve({ data: { data: worklistPayload(workflowType, identityStatus) } })
      }
      if (target.includes('/api/v1/frontpage/settings')) {
        return Promise.resolve({
          data: { success: true, data: { settings: { default_preview_tab: 'preview' } } },
        })
      }
      if (target.includes('/api/medical-records/workstation')) {
        return Promise.resolve({
          data: {
            success: true,
            data: { records: legacyRecords, total: legacyRecords.length },
          },
        })
      }
      return Promise.resolve({
        data: { success: true, data: { items: [], total: 0, total_pages: 1, departments: [] } },
      })
    })
  }

  it('工作清单未核实行打开后渲染只读面板，并关闭旧 Assist/首页/结算写入口', async () => {
    mockWorklist('settlement')

    const wrapper = mountView()
    await flush()
    expect(wrapper.find('[data-testid="modern-case-qc-panel"]').exists()).toBe(false)

    await selectOnlyWorklistRow(wrapper)

    const panel = wrapper.find('[data-testid="modern-case-qc-panel"]')
    expect(panel.exists()).toBe(true)
    // 结算工作流必须给出来源切换。
    expect(wrapper.find('[data-testid="modern-case-qc-source-switch"]').exists()).toBe(true)
    // 现代读取必须携带工作清单行的四维身份。
    expect(apiRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        method: 'GET',
        url: '/api/v1/workstation/case-qc/snapshot',
        params: {
          institute_id: 'LX001',
          patient_id: 'P-1',
          visit_id: 'V-1',
          source_key: 'settlement_qc',
        },
      }),
    )
    // 只读面板与旧的写操作工作区互斥。
    expect(wrapper.find('frontpage-workspace-stub').exists()).toBe(false)
    expect(wrapper.find('settlement-workspace-stub').exists()).toBe(false)
    expect(wrapper.find('workstation-v4-assist-view-stub').exists()).toBe(false)
  })

  it('面板与详情在窄屏纵向分区、桌面恢复右侧栏，且两区都允许滚动', async () => {
    mockWorklist('settlement')

    const wrapper = mountView()
    await flush()
    await selectOnlyWorklistRow(wrapper)

    const panel = wrapper.get('[data-testid="modern-case-qc-panel"]')
    const panelClass = panel.attributes('class') ?? ''
    // 窄屏：整行改纵向，面板占满宽度并有高度上限，内部自滚动。
    expect(panelClass).toContain('w-full')
    expect(panelClass).toContain('max-h-[52%]')
    // 桌面：恢复固定宽度侧栏。
    expect(panelClass).toContain('lg:w-[380px]')
    expect(panelClass).toContain('lg:h-full')
    expect(panelClass).toContain('lg:max-h-none')
    // 面板内部滚动容器存在，详情区由自身滚动容器承载。
    expect(panel.find('div.min-h-0.flex-1.overflow-y-auto').exists()).toBe(true)

    const detail = wrapper.find('.detail-view-stub')
    expect(detail.exists()).toBe(true)
    expect(detail.classes()).toContain('min-h-0')
    const row = detail.element.parentElement
    expect(row?.className).toContain('flex-col')
    expect(row?.className).toContain('lg:flex-row')
  })

  it('歧义行仍被阻断，不渲染只读面板，也不放开写入口', async () => {
    mockWorklist('settlement', 'ambiguous')

    const wrapper = mountView()
    await flush()
    await selectOnlyWorklistRow(wrapper)

    expect(wrapper.find('[data-testid="modern-case-qc-panel"]').exists()).toBe(false)
    expect(wrapper.find('settlement-workspace-stub').exists()).toBe(false)
  })

  it('普通旧列表（无工作清单 stage）不触发现代读取', async () => {
    routeQuery.value = {}
    mockWorklist('frontpage')

    const wrapper = mountView()
    await flush()

    expect(wrapper.find('[data-testid="modern-case-qc-panel"]').exists()).toBe(false)
    // 没有工作清单 stage：不请求现代快照，旧列表也不带 identityStatus 的写保护变化。
    expect(apiRequest).not.toHaveBeenCalled()
  })

  it('对照组：非工作清单模式的身份已核实旧病历仍然开放旧写工作区', async () => {
    routeQuery.value = {}
    mockWorklist('frontpage', 'unverified', [
      {
        id: LEGACY_KEY,
        visit_id: 'V-LEGACY',
        patient_id: 'P-LEGACY',
        institute_id: 'LX001',
        patient_name: '旧列表患者',
      },
    ])

    const wrapper = mountView()
    await flush()

    const list = wrapper.findComponent(WorkstationV4ListView)
    list.vm.$emit('open-record', LEGACY_KEY)
    await flush()

    // 证明 stub 具名插槽确实渲染：写工作区在允许时才出现，断言不是空断言。
    expect(wrapper.find('frontpage-workspace-stub').exists()).toBe(true)
    expect(wrapper.find('settlement-workspace-stub').exists()).toBe(true)
    expect(wrapper.find('workstation-v4-assist-view-stub').exists()).toBe(true)
    expect(wrapper.find('[data-testid="modern-case-qc-panel"]').exists()).toBe(false)
    expect(apiRequest).not.toHaveBeenCalled()
  })
})
