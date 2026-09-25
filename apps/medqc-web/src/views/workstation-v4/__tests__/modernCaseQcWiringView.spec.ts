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
          active_defects_has_more: false,
          active_defects_next_offset: null,
          current_result_defects_has_more: false,
          current_result_defects_next_offset: null,
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
          // 分页参数始终随请求发送：初始页固定 0/0/20。
          active_defects_offset: 0,
          current_result_defects_offset: 0,
          defects_limit: 20,
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

// ===== 缺陷分页与加载更多（反例） =====

const MODERN_SNAPSHOT_URL = '/api/v1/workstation/case-qc/snapshot'

/** 合成缺陷条目：字段与后端客户可见投影一致，不含真实患者信息。 */
function defectPayload(prefix: string, count: number, startAt = 1) {
  return Array.from({ length: count }, (_, index) => ({
    id: `${prefix}-${startAt + index}`,
    rule_code: `LX0609-${startAt + index}`,
    rule_name: `${prefix}-item-${startAt + index}`,
    description: `${prefix}-item-${startAt + index}`,
    severity: 'major',
    status: 'open',
  }))
}

/**
 * 现代快照信封：默认带齐四个必填分页元数据字段。
 * 缺字段会被 API 层判为畸形而失败关闭，夹具必须补齐，避免把「没给元数据」当成「已加载完」。
 */
function snapshotEnvelope(params: Record<string, unknown>, data: Record<string, unknown> = {}) {
  return {
    status: 200,
    data: {
      success: true,
      data: {
        identity_status: 'verified',
        source_key: params.source_key,
        institute_id: params.institute_id,
        patient_id: params.patient_id,
        visit_id: params.visit_id,
        latest_qc_result: {
          id: 'result-1',
          rule_set: 'lx0609-v1',
          overall_score: 80,
          grade: 'B',
          defect_count: 3,
          analysis_date: '2026-01-02T00:00:00',
          created_at: '2026-01-02T03:04:05Z',
        },
        recent_results: [],
        active_defects: [],
        current_result_defects: [],
        active_defects_has_more: false,
        active_defects_next_offset: null,
        current_result_defects_has_more: false,
        current_result_defects_next_offset: null,
        latest_notification: null,
        ...data,
      },
    },
  }
}

function snapshotParamsList(): Array<Record<string, unknown>> {
  return apiRequest.mock.calls
    .filter((call) => (call[0] as { url?: string } | undefined)?.url === MODERN_SNAPSHOT_URL)
    .map((call) => (call[0] as { params?: Record<string, unknown> }).params ?? {})
}

function worklistRowPayload(visitId: string, patientId: string) {
  return {
    institute_id: 'LX001',
    patient_id: patientId,
    visit_id: visitId,
    patient_name: `测试患者-${visitId}`,
    workflow_type: 'settlement',
    identity_status: 'unverified',
  }
}

// 分页断言要看面板内部 DOM，所以显式取消面板的自动 stub，其余子组件仍走默认替换。
function mountViewWithPanel() {
  return shallowMount(WorkstationV4View, {
    global: {
      stubs: {
        'WorkstationV4DetailView': DetailViewStub,
        'ModernCaseQcReadOnlyPanel': false,
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

describe('WorkstationV4View 缺陷分页（渲染反例）', () => {
  beforeEach(() => {
    apiGet.mockReset()
    apiRequest.mockReset()
    routeQuery.value = { stage: 'settlement_qc' }
  })

  // 分页用例统一真渲染面板，才能断言面板内部 DOM；同名遮蔽模块级 mountView。
  const mountView = mountViewWithPanel

  function mockStageWorklist(rows: Array<Record<string, unknown>>) {
    apiGet.mockImplementation((url: string) => {
      const target = String(url)
      if (target.includes('/worklist')) {
        return Promise.resolve({
          data: { data: { items: rows, total: rows.length, total_pages: 1, departments: [] } },
        })
      }
      if (target.includes('/api/v1/frontpage/settings')) {
        return Promise.resolve({
          data: { success: true, data: { settings: { default_preview_tab: 'preview' } } },
        })
      }
      return Promise.resolve({
        data: { success: true, data: { items: [], total: 0, total_pages: 1, departments: [] } },
      })
    })
  }

  it('初始快照按 0/0/20 默认分页读取，计数写「已加载」且只有有更多的组出现加载更多', async () => {
    mockStageWorklist([worklistRowPayload('V-1', 'P-1')])
    apiRequest.mockImplementation((config: { params?: Record<string, unknown> }) => {
      const params = config?.params ?? {}
      if (Number(params.active_defects_offset ?? 0) > 0) {
        return Promise.resolve(
          snapshotEnvelope(params, {
            active_defects: defectPayload('active', 5, 21),
            active_defects_has_more: false,
            active_defects_next_offset: null,
            current_result_defects: defectPayload('current', 1),
          }),
        )
      }
      return Promise.resolve(
        snapshotEnvelope(params, {
          active_defects: defectPayload('active', 20),
          active_defects_has_more: true,
          active_defects_next_offset: 20,
          current_result_defects: defectPayload('current', 1),
          current_result_defects_has_more: false,
        }),
      )
    })

    const wrapper = mountViewWithPanel()
    await flush()
    await selectOnlyWorklistRow(wrapper)

    expect(snapshotParamsList()[0]).toMatchObject({
      active_defects_offset: 0,
      current_result_defects_offset: 0,
      defects_limit: 20,
    })
    expect(wrapper.get('[data-role="active-defects-count"]').text()).toContain('已加载 20 项')
    expect(wrapper.find('[data-role="load-more-active"]').exists()).toBe(true)
    expect(wrapper.find('[data-role="load-more-current"]').exists()).toBe(false)
  })

  it('加载更多按组追加，只带目标组 offset，且响应不会覆盖另一组已加载页', async () => {
    mockStageWorklist([worklistRowPayload('V-1', 'P-1')])
    apiRequest.mockImplementation((config: { params?: Record<string, unknown> }) => {
      const params = config?.params ?? {}
      if (Number(params.active_defects_offset ?? 0) > 0) {
        return Promise.resolve(
          snapshotEnvelope(params, {
            active_defects: defectPayload('active', 5, 21),
            active_defects_has_more: false,
            active_defects_next_offset: null,
            // 响应携带的是「本次结果缺陷」第 1 页，不得用它覆盖已加载页。
            current_result_defects: defectPayload('current-fresh', 1),
          }),
        )
      }
      return Promise.resolve(
        snapshotEnvelope(params, {
          active_defects: defectPayload('active', 20),
          active_defects_has_more: true,
          active_defects_next_offset: 20,
          current_result_defects: defectPayload('current', 2),
        }),
      )
    })

    const wrapper = mountView()
    await flush()
    await selectOnlyWorklistRow(wrapper)
    await wrapper.get('[data-role="load-more-active"]').trigger('click')
    await flush()

    expect(snapshotParamsList().at(-1)).toMatchObject({
      active_defects_offset: 20,
      current_result_defects_offset: 0,
      defects_limit: 20,
    })
    expect(wrapper.get('[data-role="active-defects-count"]').text()).toContain('已加载 25 项')
    const activeText = wrapper.get('[data-section="active-defects"]').text()
    expect(activeText).toContain('active-item-1')
    expect(activeText).toContain('active-item-25')
    const currentText = wrapper.get('[data-section="current-result-defects"]').text()
    expect(currentText).toContain('current-item-1')
    expect(currentText).not.toContain('current-fresh-item-1')
  })

  it('加载更多失败保留已加载条目并提示重试，绝不显示「无缺陷」空态', async () => {
    mockStageWorklist([worklistRowPayload('V-1', 'P-1')])
    apiRequest.mockImplementation((config: { params?: Record<string, unknown> }) => {
      const params = config?.params ?? {}
      if (Number(params.active_defects_offset ?? 0) > 0) {
        return Promise.reject(Object.assign(new Error('page failed'), { status: 503 }))
      }
      return Promise.resolve(
        snapshotEnvelope(params, {
          active_defects: defectPayload('active', 20),
          active_defects_has_more: true,
          active_defects_next_offset: 20,
        }),
      )
    })

    const wrapper = mountView()
    await flush()
    await selectOnlyWorklistRow(wrapper)
    await wrapper.get('[data-role="load-more-active"]').trigger('click')
    await flush()

    const activeSection = wrapper.get('[data-section="active-defects"]')
    expect(activeSection.text()).not.toContain('暂无未关闭缺陷')
    expect(activeSection.text()).toContain('已加载 20 项')
    expect(activeSection.text()).toContain('active-item-20')
    expect(wrapper.find('[data-role="load-more-active-error"]').exists()).toBe(true)
    expect(wrapper.get('[data-role="load-more-active"]').text()).toContain('重新加载')
  })

  it('切换病例后，上一例迟到的加载更多响应不覆盖新快照', async () => {
    mockStageWorklist([worklistRowPayload('V-1', 'P-1'), worklistRowPayload('V-2', 'P-2')])
    const pending: Array<{ params: Record<string, unknown>; resolve: (value: unknown) => void }> = []
    apiRequest.mockImplementation((config: { params?: Record<string, unknown> }) => {
      const params = config?.params ?? {}
      if (params.visit_id === 'V-1') {
        if (Number(params.active_defects_offset ?? 0) > 0) {
          return new Promise<unknown>((resolve) => {
            pending.push({ params, resolve })
          })
        }
        return Promise.resolve(
          snapshotEnvelope(params, {
            active_defects: defectPayload('a1', 20),
            active_defects_has_more: true,
            active_defects_next_offset: 20,
          }),
        )
      }
      return Promise.resolve(
        snapshotEnvelope(params, {
          active_defects: defectPayload('b1', 3),
          active_defects_has_more: false,
          active_defects_next_offset: null,
        }),
      )
    })

    const wrapper = mountView()
    await flush()
    wrapper.findComponent(WorkstationV4ListView).vm.$emit('open-record', WORKLIST_KEY)
    await flush()
    await wrapper.get('[data-role="load-more-active"]').trigger('click')
    await flush()

    // 详情模式下列表已卸载：先用详情返回回到列表，再打开第二例。
    wrapper.findComponent(DetailViewStub).vm.$emit('back')
    await flush()
    wrapper
      .findComponent(WorkstationV4ListView)
      .vm.$emit('open-record', 'worklist:["LX001","P-2","V-2"]')
    await flush()
    expect(wrapper.get('[data-role="active-defects-count"]').text()).toContain('已加载 3 项')

    // 旧例迟到页此刻才返回，必须被丢弃。
    expect(pending).toHaveLength(1)
    pending[0].resolve(
      snapshotEnvelope(pending[0].params, {
        active_defects: defectPayload('a2', 5, 21),
        active_defects_has_more: false,
        active_defects_next_offset: null,
      }),
    )
    await flush()

    expect(wrapper.get('[data-role="active-defects-count"]').text()).toContain('已加载 3 项')
    expect(wrapper.get('[data-section="active-defects"]').text()).not.toContain('a2-item-21')
  })

  it('加载更多返回的新结果 id 变化时改用默认 offset 0 重取，不跳过第一条新结果缺陷', async () => {
    mockStageWorklist([worklistRowPayload('V-1', 'P-1')])
    let snapshotCallIndex = 0
    const resultTwo = {
      id: 'result-2',
      rule_set: 'lx0609-v1',
      overall_score: 70,
      grade: 'C',
      defect_count: 2,
      analysis_date: '2026-01-03T00:00:00',
      created_at: '2026-01-03T01:00:00Z',
    }
    apiRequest.mockImplementation((config: { params?: Record<string, unknown> }) => {
      const params = config?.params ?? {}
      snapshotCallIndex += 1
      if (snapshotCallIndex === 1) {
        return Promise.resolve(
          snapshotEnvelope(params, {
            active_defects: defectPayload('old', 20),
            active_defects_has_more: true,
            active_defects_next_offset: 20,
          }),
        )
      }
      if (snapshotCallIndex === 2) {
        // 服务端已切到新结果，但本次请求仍是旧 offset 的加载更多页。
        return Promise.resolve(
          snapshotEnvelope(params, {
            latest_qc_result: resultTwo,
            active_defects: defectPayload('new', 5, 21),
            active_defects_has_more: false,
            active_defects_next_offset: null,
          }),
        )
      }
      return Promise.resolve(
        snapshotEnvelope(params, {
          latest_qc_result: resultTwo,
          active_defects: defectPayload('new', 2),
          active_defects_has_more: false,
          active_defects_next_offset: null,
        }),
      )
    })

    const wrapper = mountView()
    await flush()
    await selectOnlyWorklistRow(wrapper)
    await wrapper.get('[data-role="load-more-active"]').trigger('click')
    await flush()

    // 必须出现二次「默认 offset 0」请求。
    expect(snapshotCallIndex).toBeGreaterThanOrEqual(3)
    expect(snapshotParamsList()[2]).toMatchObject({
      active_defects_offset: 0,
      current_result_defects_offset: 0,
      defects_limit: 20,
    })
    const activeText = wrapper.get('[data-section="active-defects"]').text()
    // 第一条新结果缺陷不能被跳过，旧 offset 那一页也不能拼接进来。
    expect(activeText).toContain('new-item-1')
    expect(activeText).not.toContain('new-item-21')
    expect(activeText).not.toContain('old-item-1')
  })

  it('初始响应缺少分页元数据时按错误态处理，绝不显示为已加载完/无缺陷', async () => {
    mockStageWorklist([worklistRowPayload('V-1', 'P-1')])
    apiRequest.mockImplementation((config: { params?: Record<string, unknown> }) => {
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

    const wrapper = mountView()
    await flush()
    await selectOnlyWorklistRow(wrapper)

    expect(wrapper.find('[data-role="error"]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('暂无已核验质控结果')
    expect(wrapper.find('[data-role="load-more-active"]').exists()).toBe(false)
  })
})
