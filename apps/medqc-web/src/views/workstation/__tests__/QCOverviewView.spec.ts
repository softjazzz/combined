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
    user: { id: 'u1', roles: ['admin'], is_demo_account: false },
    userRoles: ['admin'],
  }),
}))

const apiGetMock = vi.fn()
vi.mock('@/services/apiService', () => ({
  ApiService: {
    get: (...args: unknown[]) => apiGetMock(...args),
  },
}))

import QCOverviewView from '../QCOverviewView.vue'

function makeHomePayload(
  recordsTotal: number,
  options?: { departmentOptions?: string[]; department?: string | null },
) {
  const scope = {
    hospital_scope: 'all',
    department: options?.department ?? null,
    scene: 'final',
    rule_set_key: 'luxian_0609_qc_v1',
    rule_set_version: 'v1',
    generated_at: '2026-11-24T00:00:00Z',
  }
  return {
    success: true,
    data: {
      department_options: options?.departmentOptions ?? ['心内科', '呼吸内科'],
      scope,
      clinical_qc: {
        scope,
        kpis: {
          records_total: recordsTotal,
          qc_pending_total: 0,
          qc_completed_total: recordsTotal,
          high_risk_review_total: 0,
          qc_partial_failed_total: 0,
          qc_failed_total: 0,
        },
        canonical_status_counts: {},
        department_distribution: [],
        physician_distribution: [],
        priority_items: [],
        rule_family_distribution: [],
        trend: null,
        comparison: null,
        data_health: {
          source_sync_status: 'unknown',
          source_error_total: 0,
          running_task_total: null,
          running_task_state: 'unknown',
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

  it('sends priority_limit=20 with AbortSignal and without unused legacy hotspot/todo params', async () => {
    apiGetMock.mockResolvedValue(makeHomePayload(12))
    const wrapper = mountOverview()
    await flushPromises()

    expect(apiGetMock).toHaveBeenCalledTimes(1)
    expect(apiGetMock).toHaveBeenCalledWith(
      '/api/v1/workstation/qc-home',
      {
        department: undefined,
        keyword: undefined,
        priority_limit: 20,
      },
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    wrapper.unmount()
  })

  it('aborts superseded requests, ignores stale out-of-order responses, and debounces rapid keyword updates', async () => {
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
    const slowSignal = (apiGetMock.mock.calls[1][2] as { signal: AbortSignal }).signal
    expect(slowSignal.aborted).toBe(false)

    await select.setValue('呼吸内科')
    const fastSignal = (apiGetMock.mock.calls[2][2] as { signal: AbortSignal }).signal
    expect(slowSignal.aborted).toBe(true)
    expect(fastSignal.aborted).toBe(false)
    expect(apiGetMock).toHaveBeenCalledTimes(3)
    expect(apiGetMock).toHaveBeenLastCalledWith(
      '/api/v1/workstation/qc-home',
      {
        department: '呼吸内科',
        keyword: undefined,
        priority_limit: 20,
      },
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )

    // Newer request resolves first with 42 records
    reqFast.resolve(makeHomePayload(42, { departmentOptions: ['呼吸内科'], department: '呼吸内科' }))
    await flushPromises()
    // Older slow request resolves late with 5 records — must be ignored!
    reqSlow.resolve(makeHomePayload(5, { departmentOptions: ['心内科'], department: '心内科' }))
    await flushPromises()
    expect(wrapper.text()).toContain('42')
    expect(wrapper.text()).not.toContain('当前范围 5 份')
    // Cached full-scope department options are preserved when backend returns single-department slice
    const optionValues = wrapper
      .findAll('select.qc-home-department option')
      .map((node) => node.attributes('value'))
    expect(optionValues).toEqual(['all', '心内科', '呼吸内科'])

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
    expect(apiGetMock).toHaveBeenLastCalledWith(
      '/api/v1/workstation/qc-home',
      {
        department: '呼吸内科',
        keyword: '张三',
        priority_limit: 20,
      },
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    wrapper.unmount()
  })

  it('aborts in-flight request on unmount and disables refresh while loading', async () => {
    const pending = deferred<ReturnType<typeof makeHomePayload>>()
    apiGetMock.mockReturnValueOnce(pending.promise)
    routeState.query = { department: '骨科' }

    const wrapper = mountOverview()
    const signal = (apiGetMock.mock.calls[0][2] as { signal: AbortSignal }).signal
    expect(signal.aborted).toBe(false)

    // Toolbar stays visible because departmentFilter !== 'all', and refresh button is disabled while loading
    const refreshButton = wrapper.get('[aria-label="刷新首页数据"]')
    expect((refreshButton.element as HTMLButtonElement).disabled).toBe(true)

    wrapper.unmount()
    expect(signal.aborted).toBe(true)
  })

  it('keeps toolbar rendered on loadError with fallback department option so users can recover', async () => {
    routeState.query = { department: '未返回科室', keyword: '异常关键字' }
    apiGetMock.mockResolvedValueOnce({ success: false, error: 'server error', data: null })

    const wrapper = mountOverview()
    await flushPromises()

    expect(wrapper.find('[data-testid="home-load-error"]').exists()).toBe(true)
    expect(wrapper.find('.qc-home-toolbar').exists()).toBe(true)
    expect(wrapper.find('[aria-label="清除关键词"]').exists()).toBe(true)
    const select = wrapper.get('select.qc-home-department')
    expect((select.element as HTMLSelectElement).value).toBe('未返回科室')
    expect(select.findAll('option').map((o) => o.attributes('value'))).toContain('未返回科室')
    expect((wrapper.get('[aria-label="刷新首页数据"]').element as HTMLButtonElement).disabled).toBe(false)
    wrapper.unmount()
  })

  it('formats naive UTC timestamps into Asia/Shanghai without host-timezone shift', async () => {
    const payload = makeHomePayload(12)
    payload.data.clinical_qc.scope.generated_at = '2026-08-08 01:20:00'
    payload.data.clinical_qc.data_health.last_successful_qc_at = '2026-08-08T01:20:00'
    apiGetMock.mockResolvedValueOnce(payload)

    const wrapper = mountOverview()
    await flushPromises()

    expect(wrapper.get('.qc-home-toolbar__time').text()).toContain('2026-08-08 09:20')
    expect(wrapper.get('[data-testid="data-health"]').text()).toContain('2026-08-08 09:20')
    wrapper.unmount()
  })

  it('keeps dashboard visible with .is-refreshing during in-place refresh instead of flashing home-loading', async () => {
    const refreshDeferred = deferred<ReturnType<typeof makeHomePayload>>()
    apiGetMock
      .mockResolvedValueOnce(makeHomePayload(12))
      .mockReturnValueOnce(refreshDeferred.promise)

    const wrapper = mountOverview()
    // Cold load renders centered home-loading
    expect(wrapper.find('[data-testid="home-loading"]').exists()).toBe(true)
    await flushPromises()
    expect(wrapper.find('[data-testid="home-loading"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="home-overview"]').exists()).toBe(true)

    // Subsequent department change keeps dashboard mounted and marks .is-refreshing
    await wrapper.get('select.qc-home-department').setValue('心内科')
    expect(wrapper.find('[data-testid="home-loading"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="home-overview"]').exists()).toBe(true)
    expect(wrapper.get('.qc-home-body').classes()).toContain('is-refreshing')
    expect(wrapper.get('[aria-label="刷新首页数据"]').classes()).toContain('is-refreshing')

    refreshDeferred.resolve(makeHomePayload(7, { department: '心内科' }))
    await flushPromises()
    expect(wrapper.get('.qc-home-body').classes()).not.toContain('is-refreshing')
    expect(wrapper.text()).toContain('7')
    wrapper.unmount()
  })
})
