import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, shallowMount } from '@vue/test-utils'
import { defineComponent, h, nextTick } from 'vue'

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

const LEGACY_KEY = 'LEGACY-1'
const SHEET_PATH = '/api/medical-records/frontpage-sheet/P-LEGACY/V-LEGACY'

/** shallowMount 默认把详情页换成不渲染具名插槽的空壳，这里显式渲染首页工作区插槽。 */
const DetailViewStub = defineComponent({
  name: 'WorkstationV4DetailView',
  setup(_props, { slots }) {
    return () => h('div', { class: 'detail-view-stub' }, [slots.frontpage?.()])
  },
})

const FrontpageWorkspaceStub = defineComponent({
  name: 'FrontpageWorkspace',
  props: {
    canGenerateFrontpage: { type: Boolean, default: true },
    frontpageSheetData: { type: Object, default: null },
    frontpageSheetLoading: { type: Boolean, default: false },
  },
  template: '<div data-testid="frontpage-workspace-stub" />',
})

function mountView() {
  return shallowMount(WorkstationV4View, {
    global: {
      stubs: {
        WorkstationV4DetailView: DetailViewStub,
        FrontpageWorkspace: FrontpageWorkspaceStub,
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

async function flush() {
  for (let i = 0; i < 3; i += 1) {
    await Promise.resolve()
    await nextTick()
  }
}

function legacyRecord(instituteId?: string) {
  return {
    id: LEGACY_KEY,
    visit_id: 'V-LEGACY',
    patient_id: 'P-LEGACY',
    institute_id: instituteId,
    patient_name: '旧列表患者',
    admission_date: '2026-09-01',
    department: '心内科',
    has_frontpage_official: true,
  }
}

function mockApis(records: Array<Record<string, unknown>>, sheetResult: () => Promise<unknown>) {
  apiGet.mockImplementation((url: string) => {
    const target = String(url)
    if (target.includes('/frontpage-sheet/')) return sheetResult()
    if (target.includes('/api/medical-records/workstation')) {
      return Promise.resolve({
        data: { success: true, data: { records, total: records.length } },
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
  apiRequest.mockImplementation(() =>
    Promise.resolve({
      status: 200,
      data: {
        success: true,
        data: { identity_status: 'unverified', latest_qc_result: null, active_defects: [] },
      },
    }),
  )
}

async function openLegacyRecord(wrapper: ReturnType<typeof mountView>) {
  const list = wrapper.findComponent(WorkstationV4ListView)
  expect(list.exists()).toBe(true)
  list.vm.$emit('open-record', LEGACY_KEY)
  await flush()
}

/** 默认取最近一次正式首页请求，便于区分在途旧响应与更正后的新请求。 */
function sheetUrl(): URL {
  const calls = apiGet.mock.calls.filter(([url]) => String(url).includes('/frontpage-sheet/'))
  const call = calls[calls.length - 1]
  expect(call).toBeTruthy()
  return new URL(String(call![0]), 'http://localhost')
}

describe('WorkstationV4View 正式首页消歧参数（渲染）', () => {
  beforeEach(() => {
    apiGet.mockReset()
    apiRequest.mockReset()
    routeQuery.value = {}
    if (!window.localStorage) return
    window.localStorage.clear()
  })

  it('选中行有机构号时以消歧参数请求正式首页，并把正式首页交给工作区', async () => {
    mockApis([legacyRecord('LX-001')], () => Promise.resolve({ data: { basic_info: {} } }))

    const wrapper = mountView()
    await flush()
    await openLegacyRecord(wrapper)

    const url = sheetUrl()
    expect(url.pathname).toBe(SHEET_PATH)
    expect(url.searchParams.get('institute_id')).toBe('LX-001')
    expect(
      wrapper.findComponent(FrontpageWorkspaceStub).props('frontpageSheetData'),
    ).toEqual({ basic_info: {} })
    expect(wrapper.find('[data-testid="frontpage-sheet-error"]').exists()).toBe(false)
  })

  it('选中行没有机构号时不追加查询参数（保持旧调用兼容）', async () => {
    mockApis([legacyRecord(undefined)], () => Promise.resolve({ data: { basic_info: {} } }))

    const wrapper = mountView()
    await flush()
    await openLegacyRecord(wrapper)

    const call = apiGet.mock.calls.find(([url]) => String(url).includes('/frontpage-sheet/'))
    expect(call?.[0]).toBe(SHEET_PATH)
  })

  it('409 归属歧义时留痕并阻断草稿生成', async () => {
    mockApis([legacyRecord('LX-001')], () =>
      Promise.reject({
        response: { status: 409, data: { detail: '病例身份不唯一，请指定机构号' } },
      }),
    )

    const wrapper = mountView()
    await flush()
    await openLegacyRecord(wrapper)

    const alert = wrapper.find('[data-testid="frontpage-sheet-error"]')
    expect(alert.exists()).toBe(true)
    expect(alert.text()).toContain('病例身份不唯一，请指定机构号')
    expect(wrapper.findComponent(FrontpageWorkspaceStub).props('canGenerateFrontpage')).toBe(false)
    expect(
      wrapper.findComponent(FrontpageWorkspaceStub).props('frontpageSheetData'),
    ).toBeNull()
  })

  it('503 服务不可用时同样留痕，不把失败当成“没有正式首页”', async () => {
    mockApis([legacyRecord('LX-001')], () =>
      Promise.reject({
        response: { status: 503, data: { detail: '正式首页服务暂不可用，请稍后重试' } },
      }),
    )

    const wrapper = mountView()
    await flush()
    await openLegacyRecord(wrapper)

    expect(wrapper.find('[data-testid="frontpage-sheet-error"]').text()).toContain(
      '正式首页服务暂不可用',
    )
    expect(wrapper.findComponent(FrontpageWorkspaceStub).props('canGenerateFrontpage')).toBe(false)
  })

  it('404 表示确无正式首页，不显示错误且不阻断草稿生成', async () => {
    mockApis([legacyRecord('LX-001')], () => Promise.reject({ response: { status: 404 } }))

    const wrapper = mountView()
    await flush()
    await openLegacyRecord(wrapper)

    expect(wrapper.find('[data-testid="frontpage-sheet-error"]').exists()).toBe(false)
    expect(wrapper.findComponent(FrontpageWorkspaceStub).props('canGenerateFrontpage')).toBe(true)
  })

  it('同一选中行机构更正后，旧机构在途响应不得覆盖新机构结果', async () => {
    let resolveStaleSheet!: (value: unknown) => void
    const staleSheet = new Promise((resolve) => {
      resolveStaleSheet = resolve
    })
    let sheetCalls = 0
    let records: Array<Record<string, unknown>> = [legacyRecord('LX-OLD')]
    apiGet.mockImplementation((url: string) => {
      const target = String(url)
      if (target.includes('/frontpage-sheet/')) {
        sheetCalls += 1
        if (sheetCalls === 1) return staleSheet
        return Promise.resolve({ data: { basic_info: { age: 2 } } })
      }
      if (target.includes('/api/medical-records/workstation')) {
        return Promise.resolve({
          data: { success: true, data: { records, total: records.length } },
        })
      }
      return Promise.resolve({
        data: { success: true, data: { items: [], total: 0, total_pages: 1, departments: [] } },
      })
    })
    apiRequest.mockImplementation(() =>
      Promise.resolve({ status: 200, data: { success: true, data: {} } }),
    )

    const wrapper = mountView()
    await flush()
    await openLegacyRecord(wrapper)
    expect(sheetUrl().searchParams.get('institute_id')).toBe('LX-OLD')

    // 退回列表后刷新病历池：同一 record id 的机构更正为 LX-NEW（旧列表选中键只含 record id）。
    wrapper.findComponent(DetailViewStub).vm.$emit('back')
    await flush()
    records = [legacyRecord('LX-NEW')]
    // detail 分支下列表组件不存在，必须在退回列表后再驱动它；这里显式断言，避免空 wrapper 报错。
    const list = wrapper.findComponent(WorkstationV4ListView)
    expect(list.exists()).toBe(true)
    list.vm.$emit('clear-filters')
    await flush()

    // 重新打开同一行：选中键不变，但机构已更正为 LX-NEW。
    await openLegacyRecord(wrapper)

    resolveStaleSheet({ data: { basic_info: { age: 1 } } })
    await flush()

    // 旧机构（LX-OLD）的在途响应必须被丢弃：不能落到机构已更正为 LX-NEW 的同一行上。
    expect(
      wrapper.findComponent(FrontpageWorkspaceStub).props('frontpageSheetData'),
    ).toBeNull()

    // 新机构重新加载时以 LX-NEW 消歧，且响应正常落到工作区。
    wrapper.findComponent(FrontpageWorkspaceStub).vm.$emit('reload-frontpage-sheet')
    await flush()
    expect(sheetUrl().searchParams.get('institute_id')).toBe('LX-NEW')
    expect(wrapper.findComponent(FrontpageWorkspaceStub).props('frontpageSheetData')).toEqual({
      basic_info: { age: 2 },
    })
  })
})
