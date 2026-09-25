import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, shallowMount } from '@vue/test-utils'
import { defineComponent, h, nextTick } from 'vue'

// onMounted 里还有列表/快照/通知等异步任务，测试结束必须卸载，避免悬挂的 rejection。
enableAutoUnmount(afterEach)
const apiGet = vi.hoisted(() => vi.fn())
const apiRequest = vi.hoisted(() => vi.fn())
const routeQuery = vi.hoisted(() => ({ value: {} as Record<string, string> }))

vi.mock('@/services/apiService', async () => {
  const actual =
    await vi.importActual<typeof import('@/services/apiService')>('@/services/apiService')
  // 只替换传输层，保留真实 ApiService / apiClient 的鉴权与错误包装行为。
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

const RECORD_A = 'REC-A'
const RECORD_B = 'REC-B'
const SHEET_PATH_A = '/api/medical-records/frontpage-sheet/P-A/REC-A'
const SHEET_PATH_B = '/api/medical-records/frontpage-sheet/P-B/REC-B'

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
        'a-button': true,
        'a-modal': true,
        'a-textarea': true,
        'a-input': true,
        'a-popconfirm': true,
        'a-tooltip': true,
        'a-segmented': true,
      },
    },
  })
}

async function flush() {
  for (let i = 0; i < 4; i += 1) {
    await flushPromises()
    await nextTick()
  }
}

function legacyRecord(id: string, patientId: string, instituteId?: string) {
  return {
    id,
    visit_id: id,
    patient_id: patientId,
    institute_id: instituteId,
    patient_name: `患者-${patientId}`,
    department: '心内科',
    discharge_date: '2026-09-10',
    has_frontpage_official: true,
  }
}

function mockApis(
  records: Array<Record<string, unknown>>,
  sheetResult: (url: string) => Promise<unknown>,
) {
  apiGet.mockImplementation((url: string) => {
    const target = String(url)
    if (target.includes('/frontpage-sheet/')) return sheetResult(target)
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
    Promise.resolve({ status: 200, data: { success: true, data: {} } }),
  )
}

async function openRecord(wrapper: ReturnType<typeof mountView>, recordId: string) {
  const list = wrapper.findComponent(WorkstationV4ListView)
  expect(list.exists()).toBe(true)
  list.vm.$emit('open-record', recordId)
  await flush()
}

function sheetCalls(): string[] {
  return apiGet.mock.calls
    .map(([url]) => String(url))
    .filter((url) => url.includes('/frontpage-sheet/'))
}

function sheetUrl(index = 0): URL {
  const call = sheetCalls()[index]
  expect(call).toBeTruthy()
  return new URL(String(call), 'http://localhost')
}

describe('workstation-v2 顶层正式首页读取（渲染）', () => {
  beforeEach(() => {
    apiGet.mockReset()
    apiRequest.mockReset()
    routeQuery.value = {}
    if (!window.localStorage) return
    window.localStorage.clear()
  })

  it('选中行有机构号时以消歧参数请求正式首页，并把正式首页交给工作区', async () => {
    mockApis([legacyRecord(RECORD_A, 'P-A', 'LX-001')], () =>
      Promise.resolve({ data: { basic_info: {} } }),
    )

    const wrapper = mountView()
    await flush()
    await openRecord(wrapper, RECORD_A)

    const url = sheetUrl()
    expect(url.pathname).toBe(SHEET_PATH_A)
    expect(url.searchParams.get('institute_id')).toBe('LX-001')
    expect(wrapper.findComponent(FrontpageWorkspaceStub).props('frontpageSheetData')).toEqual({
      basic_info: {},
    })
    expect(wrapper.find('[data-testid="frontpage-sheet-error"]').exists()).toBe(false)
  })

  it('选中行没有机构号时不追加查询参数，且路径段逐段编码', async () => {
    mockApis([legacyRecord(RECORD_A, 'P-A', undefined)], () =>
      Promise.resolve({ data: { basic_info: {} } }),
    )

    const wrapper = mountView()
    await flush()
    await openRecord(wrapper, RECORD_A)

    expect(sheetCalls()[0]).toBe(SHEET_PATH_A)
  })

  it('409 归属歧义时留痕、阻断草稿生成，且不把失败当成没有正式首页', async () => {
    mockApis([legacyRecord(RECORD_A, 'P-A', 'LX-001')], () =>
      Promise.reject({
        response: { status: 409, data: { detail: '病例身份不唯一，请指定机构号' } },
      }),
    )

    const wrapper = mountView()
    await flush()
    await openRecord(wrapper, RECORD_A)

    const alert = wrapper.find('[data-testid="frontpage-sheet-error"]')
    expect(alert.exists()).toBe(true)
    expect(alert.text()).toContain('病例身份不唯一，请指定机构号')
    expect(wrapper.findComponent(FrontpageWorkspaceStub).props('canGenerateFrontpage')).toBe(false)
    expect(wrapper.findComponent(FrontpageWorkspaceStub).props('frontpageSheetData')).toBeNull()
  })

  it('503 服务不可用时同样留痕，不把失败当成“没有正式首页”', async () => {
    mockApis([legacyRecord(RECORD_A, 'P-A', 'LX-001')], () =>
      Promise.reject({
        response: { status: 503, data: { detail: '正式首页服务暂不可用，请稍后重试' } },
      }),
    )

    const wrapper = mountView()
    await flush()
    await openRecord(wrapper, RECORD_A)

    expect(wrapper.find('[data-testid="frontpage-sheet-error"]').text()).toContain(
      '正式首页服务暂不可用',
    )
    expect(wrapper.findComponent(FrontpageWorkspaceStub).props('canGenerateFrontpage')).toBe(false)
  })

  it('404 表示确无正式首页，不显示错误且不阻断草稿生成', async () => {
    mockApis([legacyRecord(RECORD_A, 'P-A', 'LX-001')], () =>
      Promise.reject({ response: { status: 404 } }),
    )

    const wrapper = mountView()
    await flush()
    await openRecord(wrapper, RECORD_A)

    expect(wrapper.find('[data-testid="frontpage-sheet-error"]').exists()).toBe(false)
    expect(wrapper.findComponent(FrontpageWorkspaceStub).props('canGenerateFrontpage')).toBe(true)
  })

  it('切换选中行后，旧行的首页响应不得覆盖新选中行', async () => {
    let releaseFirst: ((value: unknown) => void) | undefined
    mockApis([legacyRecord(RECORD_A, 'P-A', 'LX-001'), legacyRecord(RECORD_B, 'P-B', 'LX-002')], (url) => {
      if (url.startsWith(SHEET_PATH_A)) {
        return new Promise((resolve) => {
          releaseFirst = resolve
        })
      }
      return Promise.resolve({ data: { basic_info: { from: 'B' } } })
    })

    const wrapper = mountView()
    await flush()
    await openRecord(wrapper, RECORD_A)

    // 第一行首页请求仍挂起时切到下一行，新行请求先完成。
    wrapper.findComponent(DetailViewStub).vm.$emit('next')
    await flush()
    expect(sheetCalls()[1]).toContain(SHEET_PATH_B)
    expect(wrapper.findComponent(FrontpageWorkspaceStub).props('frontpageSheetData')).toEqual({
      basic_info: { from: 'B' },
    })

    // 释放旧响应：它属于上一行，必须被丢弃。
    releaseFirst?.({ data: { basic_info: { from: 'A' } } })
    await flush()

    expect(wrapper.findComponent(FrontpageWorkspaceStub).props('frontpageSheetData')).toEqual({
      basic_info: { from: 'B' },
    })
    expect(wrapper.find('[data-testid="frontpage-sheet-error"]').exists()).toBe(false)
  })

  it('切到无正式首页的选中行时，旧行挂起请求不得遗留 loading', async () => {
    let releaseFirst: ((value: unknown) => void) | undefined
    const recordWithoutOfficial = {
      ...legacyRecord(RECORD_B, 'P-B', 'LX-002'),
      has_frontpage_official: false,
      cdm_frontpage_empty: true,
    }
    mockApis([legacyRecord(RECORD_A, 'P-A', 'LX-001'), recordWithoutOfficial], (url) => {
      if (url.startsWith(SHEET_PATH_A)) {
        return new Promise((resolve) => {
          releaseFirst = resolve
        })
      }
      return Promise.resolve({ data: { basic_info: { from: 'B' } } })
    })

    const wrapper = mountView()
    await flush()
    await openRecord(wrapper, RECORD_A)
    expect(wrapper.findComponent(FrontpageWorkspaceStub).props('frontpageSheetLoading')).toBe(true)

    // 新选中行没有官方首页，不会发起请求；旧行请求仍挂起，不得让 spinner 停留在旧状态。
    wrapper.findComponent(DetailViewStub).vm.$emit('next')
    await flush()
    expect(sheetCalls()).toHaveLength(1)
    expect(wrapper.findComponent(FrontpageWorkspaceStub).props('frontpageSheetLoading')).toBe(false)
    expect(wrapper.findComponent(FrontpageWorkspaceStub).props('frontpageSheetData')).toBeNull()

    // 释放旧行响应：既不能复活 loading，也不能把旧数据还给新选中行。
    releaseFirst?.({ data: { basic_info: { from: 'A' } } })
    await flush()
    expect(wrapper.findComponent(FrontpageWorkspaceStub).props('frontpageSheetLoading')).toBe(false)
    expect(wrapper.findComponent(FrontpageWorkspaceStub).props('frontpageSheetData')).toBeNull()
  })

  it('列表刷新后同一 id 改指另一机构时，旧机构迟到的首页响应必须丢弃', async () => {
    let releaseFirst: ((value: unknown) => void) | undefined
    let listFetchCount = 0
    apiGet.mockImplementation((url: string) => {
      const target = String(url)
      if (target.includes('/frontpage-sheet/')) {
        return new Promise((resolve) => {
          releaseFirst = resolve
        })
      }
      if (target.includes('/api/medical-records/workstation')) {
        listFetchCount += 1
        const records =
          listFetchCount === 1
            ? [legacyRecord(RECORD_A, 'P-A', 'LX-001')]
            : [legacyRecord(RECORD_A, 'P-A', 'LX-002')]
        return Promise.resolve({
          data: { success: true, data: { records, total: records.length } },
        })
      }
      if (target.includes('/api/v1/frontpage/settings')) {
        return Promise.resolve({ data: { success: true, data: { settings: {} } } })
      }
      return Promise.resolve({ data: { success: true, data: {} } })
    })
    apiRequest.mockImplementation(() =>
      Promise.resolve({ status: 200, data: { success: true, data: {} } }),
    )

    const wrapper = mountView()
    await flush()
    await openRecord(wrapper, RECORD_A)
    expect(sheetCalls()).toHaveLength(1)
    expect(sheetUrl().searchParams.get('institute_id')).toBe('LX-001')

    // 回列表翻页触发列表刷新：同一 id 现在属于另一机构，选中行 key 与 patient_id 都没变。
    wrapper.findComponent(DetailViewStub).vm.$emit('back')
    await flush()
    const list = wrapper.findComponent(WorkstationV4ListView)
    expect(list.exists()).toBe(true)
    list.vm.$emit('page-change', 2)
    await flush()
    expect(listFetchCount).toBeGreaterThanOrEqual(2)

    // 重新打开同一 id 不会新发首页请求，因此迟到的旧机构响应若被采用就会直接展示错机构的首页。
    await openRecord(wrapper, RECORD_A)
    expect(sheetCalls()).toHaveLength(1)

    releaseFirst?.({ data: { basic_info: { from: 'LX-001' } } })
    await flush()

    expect(wrapper.findComponent(FrontpageWorkspaceStub).props('frontpageSheetData')).toBeNull()
    expect(wrapper.find('[data-testid="frontpage-sheet-error"]').exists()).toBe(false)
  })
})
