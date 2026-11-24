import { flushPromises, mount } from '@vue/test-utils'
import { reactive } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const routeState = reactive<{ fullPath: string; query: Record<string, string> }>({
  fullPath: '/workstation-v5',
  query: {},
})

const routerPush = vi.fn()
const routerReplace = vi.fn()

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({
    push: routerPush,
    replace: routerReplace,
  }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    user: { id: 'u1', roles: ['admin'] },
    isDemoPresentation: false,
  }),
}))

const apiGetMock = vi.fn()
vi.mock('@/services/apiService', () => ({
  ApiService: {
    get: (...args: unknown[]) => apiGetMock(...args),
  },
}))

import QCOverviewView from '../QCOverviewView.vue'

function makeHomePayload(recordsTotal: number) {
  return {
    success: true,
    data: {
      department_options: ['心内科', '呼吸内科'],
      scope: { scene: 'final', generated_at: '2026-11-24T00:00:00Z' },
      clinical_qc: {
        scope: { scene: 'final', generated_at: '2026-11-24T00:00:00Z' },
        kpis: {
          records_total: recordsTotal,
          qc_pending_total: 0,
          qc_completed_total: recordsTotal,
          high_risk_review_total: 0,
          qc_partial_failed_total: 0,
          qc_failed_total: 0,
        },
        conclusion_distribution: [],
        department_breakdown: [],
        physician_breakdown: [],
        priority_records: [],
        data_health: {
          running_task_count: 0,
          technical_error_total: 0,
          last_successful_qc_at: null,
        },
      },
    },
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}

function mountOverview() {
  return mount(QCOverviewView, {
    global: {
      stubs: {
        MqIcon: true,
        MqIconTile: true,
        'a-spin': { template: '<div><slot /></div>' },
        'a-alert': { template: '<div><slot /></div>' },
        'a-empty': { template: '<div><slot /></div>' },
        'a-select': {
          props: ['value'],
          emits: ['update:value'],
          template: '<select :value="value" @change="$emit(\'update:value\', $event.target.value)" />',
        },
        'a-select-option': { template: '<option><slot /></option>' },
        'a-input': {
          props: ['value'],
          emits: ['update:value'],
          template: '<input :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
        },
      },
    },
  })
}

describe('QCOverviewView performance & race guards', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    apiGetMock.mockReset()
    routeState.fullPath = '/workstation-v5'
    routeState.query = {}
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('sends priority_limit=20 without unused legacy hotspot/todo params', async () => {
    apiGetMock.mockResolvedValue(makeHomePayload(12))
    const wrapper = mountOverview()
    await flushPromises()

    expect(apiGetMock).toHaveBeenCalledTimes(1)
    expect(apiGetMock).toHaveBeenCalledWith('/api/v1/workstation/qc-home', {
      department: undefined,
      keyword: undefined,
      priority_limit: 20,
    })
    wrapper.unmount()
  })

  it('cancels stale out-of-order responses and debounces rapid keyword updates', async () => {
    const reqSlow = deferred<ReturnType<typeof makeHomePayload>>()
    const reqFast = deferred<ReturnType<typeof makeHomePayload>>()
    apiGetMock
      .mockResolvedValueOnce(makeHomePayload(12))
      .mockReturnValueOnce(reqSlow.promise)
      .mockReturnValueOnce(reqFast.promise)
      .mockResolvedValueOnce(makeHomePayload(99))

    const wrapper = mountOverview()
    await flushPromises()
    expect(apiGetMock).toHaveBeenCalledTimes(1)

    // Switch department twice quickly: reqSlow (心内科) starts first, reqFast (呼吸内科) starts second
    const select = wrapper.find('select.qc-home-department')
    await select.setValue('心内科')
    await select.setValue('呼吸内科')
    expect(apiGetMock).toHaveBeenCalledTimes(3)
    expect(apiGetMock).toHaveBeenLastCalledWith('/api/v1/workstation/qc-home', {
      department: '呼吸内科',
      keyword: undefined,
      priority_limit: 20,
    })

    // Newer request resolves first with 42 records
    reqFast.resolve(makeHomePayload(42))
    await flushPromises()
    // Older slow request resolves late with 5 records — must be ignored!
    reqSlow.resolve(makeHomePayload(5))
    await flushPromises()
    expect(wrapper.text()).toContain('42')
    expect(wrapper.text()).not.toContain('当前范围 5 份')

    // Rapid keyword mutations debounce for 280ms and emit only 1 request with the latest keyword
    const vm = wrapper.vm as unknown as { keyword: string }
    vm.keyword = '张'
    vi.advanceTimersByTime(100)
    vm.keyword = '张三'
    vi.advanceTimersByTime(100)
    expect(apiGetMock).toHaveBeenCalledTimes(3)

    vi.advanceTimersByTime(200)
    await flushPromises()
    expect(apiGetMock).toHaveBeenCalledTimes(4)
    expect(apiGetMock).toHaveBeenLastCalledWith('/api/v1/workstation/qc-home', {
      department: '呼吸内科',
      keyword: '张三',
      priority_limit: 20,
    })
    wrapper.unmount()
  })
})
