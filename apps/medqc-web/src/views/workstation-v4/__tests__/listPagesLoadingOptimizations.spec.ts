import { flushPromises, mount } from '@vue/test-utils'
import { AxiosHeaders } from 'axios'
import { effectScope, reactive } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const routeState = reactive<{ path: string; query: Record<string, string> }>({
  path: '/workstation-v5/records/running',
  query: {},
})

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
}))

vi.mock('@/api/clinicalSources', () => ({
  clinicalSourcesApi: {
    options: vi.fn(),
    configuration: vi.fn(),
    save: vi.fn(),
    check: vi.fn(),
  },
}))

vi.mock('@/services/apiService', () => ({
  ApiService: {
    getRaw: vi.fn(),
    postRaw: vi.fn(),
  },
}))

vi.mock('@/services/sichuan-rule-workspace-service', () => ({
  exportFilteredLuxian0609RecordResults: vi.fn(),
}))

vi.mock('../customer-sample-validation/batchExport', () => ({
  downloadBlob: vi.fn(),
}))

vi.mock('ant-design-vue', () => {
  const Empty = Object.assign(
    {
      name: 'Empty',
      props: ['description', 'image'],
      template: '<div class="empty-stub">{{ description }}</div>',
    },
    { PRESENTED_IMAGE_SIMPLE: 'simple' },
  )
  return {
    Alert: {
      name: 'Alert',
      props: ['message', 'type'],
      template: '<div role="alert">{{ message }}<slot name="action" /></div>',
    },
    Button: {
      name: 'Button',
      emits: ['click'],
      template: '<button type="button" @click="$emit(\'click\')"><slot /></button>',
    },
    Empty,
    Input: {
      name: 'Input',
      props: ['value', 'size'],
      emits: ['update:value', 'pressEnter', 'press-enter', 'change'],
      template:
        '<input :value="value" @input="$emit(\'update:value\', $event.target.value)" @keydown.enter="$emit(\'press-enter\')" />',
    },
    Pagination: { name: 'Pagination', template: '<nav />' },
    RangePicker: { name: 'RangePicker', template: '<div />' },
    Select: {
      name: 'Select',
      props: ['value', 'options'],
      emits: ['update:value', 'change'],
      template: '<select />',
    },
    Spin: { name: 'Spin', template: '<div><slot /></div>' },
  }
})

import { clinicalSourcesApi, type ClinicalSourceSettings } from '@/api/clinicalSources'
import { ApiService } from '@/services/apiService'
import {
  resetClinicalSourceOptionsCache,
  usePatientRecords,
} from '../composables/usePatientRecords'
import ClinicalSourceSettingsPanel from '../components/system-config/ClinicalSourceSettingsPanel.vue'
import WorkstationV4ListView from '../components/WorkstationV4ListView.vue'
import QcRecordResultListView from '../QcRecordResultListView.vue'

const DEFAULT_SOURCES = {
  default_source: 'independent_cdm' as const,
  sources: [{ id: 'independent_cdm' as const, name: '东华CDM', enabled: true }],
}

function makeResponse(data: unknown) {
  return {
    data,
    status: 200,
    statusText: 'OK',
    headers: new AxiosHeaders(),
    config: { headers: new AxiosHeaders() },
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('列表页加载机制优化回归测试', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    resetClinicalSourceOptionsCache()
    routeState.path = '/workstation-v5/records/running'
    routeState.query = {}
    window.history.replaceState({}, '', '/workstation-v5/records/running')
    vi.mocked(clinicalSourcesApi.options).mockResolvedValue(DEFAULT_SOURCES)
    vi.mocked(ApiService.postRaw).mockResolvedValue(
      makeResponse({
        qc_summary: { total_records: 0, ready_records: 0, status_counts: {} },
        records: [],
      }),
    )
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  describe('usePatientRecords', () => {
    it('Stage 1 新请求与作用域销毁时通过 AbortController 取消在途请求，且静默退出不报错', async () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => undefined)
      const capturedSignals: AbortSignal[] = []
      const firstRequest = deferred<ReturnType<typeof makeResponse>>()
      const secondRequest = deferred<ReturnType<typeof makeResponse>>()

      vi.mocked(ApiService.getRaw)
        .mockImplementationOnce((_url, _params, config) => {
          const signal = config?.signal as AbortSignal
          capturedSignals.push(signal)
          signal.addEventListener('abort', () => {
            firstRequest.reject(Object.assign(new Error('canceled'), { code: 'ERR_CANCELED', name: 'CanceledError' }))
          })
          return firstRequest.promise
        })
        .mockImplementationOnce((_url, _params, config) => {
          const signal = config?.signal as AbortSignal
          capturedSignals.push(signal)
          return secondRequest.promise
        })

      const records = usePatientRecords('inpatient')
      const p1 = records.fetchData(1)
      await flushPromises()
      expect(capturedSignals).toHaveLength(1)
      expect(capturedSignals[0].aborted).toBe(false)

      // 发起第二次请求，应立即中止第一次在途请求
      const p2 = records.fetchData(1)
      await flushPromises()
      expect(capturedSignals[0].aborted).toBe(true)
      expect(capturedSignals).toHaveLength(2)
      expect(capturedSignals[1].aborted).toBe(false)
      expect(records.loadError.value).toBe(false)
      expect(records.loading.value).toBe(true)

      secondRequest.resolve(
        makeResponse({
          records: [{ id: 'V2', recordKey: '["I","P2","V2"]', institute_id: 'I', patient_id: 'P2', visit_id: 'V2' }],
          total: 1,
          page: 1,
        }),
      )
      await Promise.all([p1, p2])
      await flushPromises()

      expect(records.loadError.value).toBe(false)
      expect(records.loading.value).toBe(false)
      expect(records.allRecords.value).toHaveLength(1)
      expect(records.allRecords.value[0].visitId).toBe('V2')
      expect(consoleErrorSpy).not.toHaveBeenCalled()

      // onScopeDispose 时同样应中止在途列表请求并静默退出
      const thirdRequest = deferred<ReturnType<typeof makeResponse>>()
      let scopedSignal: AbortSignal | undefined
      vi.mocked(ApiService.getRaw).mockImplementationOnce((_url, _params, config) => {
        scopedSignal = config?.signal as AbortSignal
        scopedSignal.addEventListener('abort', () => {
          thirdRequest.reject(Object.assign(new Error('aborted'), { name: 'AbortError' }))
        })
        return thirdRequest.promise
      })

      const scope = effectScope()
      let scopedRecords!: ReturnType<typeof usePatientRecords>
      scope.run(() => {
        scopedRecords = usePatientRecords('discharged')
      })
      const p3 = scopedRecords.fetchData(1)
      await flushPromises()
      expect(scopedSignal?.aborted).toBe(false)

      scope.stop()
      await p3
      await flushPromises()

      expect(scopedSignal?.aborted).toBe(true)
      expect(scopedRecords.loadError.value).toBe(false)
      expect(consoleErrorSpy).not.toHaveBeenCalled()
    })

    it('clinicalSourcesApi.options() 模块级缓存与在途 Promise 去重，支持 TTL 过期与重置', async () => {
      vi.useFakeTimers()
      vi.setSystemTime(new Date('2026-11-24T00:00:00Z'))

      const optionsDeferred = deferred<typeof DEFAULT_SOURCES>()
      vi.mocked(clinicalSourcesApi.options).mockImplementation(() => optionsDeferred.promise)
      vi.mocked(ApiService.getRaw).mockResolvedValue(makeResponse({ records: [], total: 0, page: 1 }))

      const r1 = usePatientRecords('inpatient')
      const r2 = usePatientRecords('discharged')

      // 并发初始化共享同一在途 Promise
      const p1 = r1.fetchData(1)
      const p2 = r2.fetchData(1)
      expect(clinicalSourcesApi.options).toHaveBeenCalledTimes(1)

      optionsDeferred.resolve(DEFAULT_SOURCES)
      await Promise.all([p1, p2])
      expect(clinicalSourcesApi.options).toHaveBeenCalledTimes(1)

      // 60s TTL 内新实例直接命中缓存
      const r3 = usePatientRecords('all')
      await r3.fetchData(1)
      expect(clinicalSourcesApi.options).toHaveBeenCalledTimes(1)

      // 手动重置缓存后再次请求
      resetClinicalSourceOptionsCache()
      vi.mocked(clinicalSourcesApi.options).mockResolvedValue(DEFAULT_SOURCES)
      const r4 = usePatientRecords('all')
      await r4.fetchData(1)
      expect(clinicalSourcesApi.options).toHaveBeenCalledTimes(2)

      // 超过 60s TTL 后自动过期重新请求
      vi.advanceTimersByTime(60_001)
      const r5 = usePatientRecords('all')
      await r5.fetchData(1)
      expect(clinicalSourcesApi.options).toHaveBeenCalledTimes(3)
    })

    it('首次返回停用源（enabled: false）时不写入缓存，再次重试立即重新请求并成功', async () => {
      vi.spyOn(console, 'error').mockImplementation(() => undefined)
      let attempt = 0
      vi.mocked(clinicalSourcesApi.options).mockImplementation(async () => {
        attempt += 1
        return {
          default_source: 'independent_cdm' as const,
          sources: [{ id: 'independent_cdm' as const, name: '东华CDM', enabled: attempt > 1 }],
        }
      })
      vi.mocked(ApiService.getRaw).mockResolvedValue(
        makeResponse({
          records: [{ id: 'V1', recordKey: '["I","P1","V1"]', institute_id: 'I', patient_id: 'P1', visit_id: 'V1' }],
          total: 1,
          page: 1,
        }),
      )

      const first = usePatientRecords('inpatient')
      await first.fetchData(1)
      expect(first.loadError.value).toBe(true)
      expect(ApiService.getRaw).not.toHaveBeenCalled()
      expect(clinicalSourcesApi.options).toHaveBeenCalledTimes(1)

      // 立即重试（同一 mock 实现、未过 TTL）：因停用响应未缓存，应重新请求并成功
      await first.fetchData(1)
      expect(first.loadError.value).toBe(false)
      expect(first.allRecords.value).toHaveLength(1)
      expect(clinicalSourcesApi.options).toHaveBeenCalledTimes(2)
      expect(ApiService.getRaw).toHaveBeenCalledTimes(1)

      // 成功结果已写入缓存，后续新实例直接复用
      const second = usePatientRecords('discharged')
      await second.fetchData(1)
      expect(clinicalSourcesApi.options).toHaveBeenCalledTimes(2)
    })

    it('保存临床源配置成功后立即清空 options 缓存（含面板保存与保存事件失效）', async () => {
      const settings: ClinicalSourceSettings = {
        version: 1,
        default_source: 'independent_cdm',
        legacy_name: '原来源',
        legacy_enabled: false,
        cdm: {
          name: '东华CDM',
          enabled: true,
          host: 'localhost',
          port: 62997,
          database: 'synthetic',
          username: 'readonly',
        },
      }
      vi.mocked(clinicalSourcesApi.options).mockImplementation(async () => DEFAULT_SOURCES)
      vi.mocked(clinicalSourcesApi.configuration).mockResolvedValue(structuredClone(settings))
      vi.mocked(clinicalSourcesApi.save).mockResolvedValue(structuredClone(settings))
      vi.mocked(ApiService.getRaw).mockResolvedValue(makeResponse({ records: [], total: 0, page: 1 }))

      // 预热缓存并验证命中
      const r1 = usePatientRecords('inpatient')
      await r1.fetchData(1)
      const r2 = usePatientRecords('discharged')
      await r2.fetchData(1)
      expect(clinicalSourcesApi.options).toHaveBeenCalledTimes(1)

      // 通过 ClinicalSourceSettingsPanel 保存配置后，缓存立即失效
      const panel = mount(ClinicalSourceSettingsPanel)
      await flushPromises()
      await panel.get('form').trigger('submit')
      await flushPromises()
      expect(clinicalSourcesApi.save).toHaveBeenCalledTimes(1)
      panel.unmount()

      const r3 = usePatientRecords('all')
      await r3.fetchData(1)
      expect(clinicalSourcesApi.options).toHaveBeenCalledTimes(2)

      // clinicalSourcesApi.save() 派发全局失效事件同样立即清空缓存
      window.dispatchEvent(new Event('medqc:clinical-sources-saved'))
      const r4 = usePatientRecords('all')
      await r4.fetchData(1)
      expect(clinicalSourcesApi.options).toHaveBeenCalledTimes(3)
    })

    it('handlePageChange 复用 qc_summary totals，而 refreshData 与 fetchData(1) 强制刷新 totals', async () => {
      const rec1 = { id: 'V1', recordKey: '["I","P1","V1"]', institute_id: 'I', patient_id: 'P1', visit_id: 'V1' }
      const rec2 = { id: 'V2', recordKey: '["I","P2","V2"]', institute_id: 'I', patient_id: 'P2', visit_id: 'V2' }

      vi.mocked(ApiService.getRaw)
        .mockResolvedValueOnce(makeResponse({ records: [rec1], total: 30, page: 1 }))
        .mockResolvedValueOnce(makeResponse({ records: [rec2], total: 30, page: 2 }))
        .mockResolvedValueOnce(makeResponse({ records: [rec2], total: 30, page: 2 }))
        .mockResolvedValueOnce(makeResponse({ records: [rec1], total: 30, page: 1 }))

      vi.mocked(ApiService.postRaw)
        .mockResolvedValueOnce(
          makeResponse({
            qc_summary: { total_records: 30, ready_records: 5, status_counts: { non_compliant: 2 } },
            records: [{ recordKey: rec1.recordKey, latest_qc_summary: { status: 'ready' } }],
          }),
        )
        .mockResolvedValueOnce(
          makeResponse({
            records: [{ recordKey: rec2.recordKey, latest_qc_summary: { status: 'not_run' } }],
          }),
        )
        .mockResolvedValueOnce(
          makeResponse({
            qc_summary: { total_records: 30, ready_records: 8, status_counts: { non_compliant: 3 } },
            records: [{ recordKey: rec2.recordKey, latest_qc_summary: { status: 'ready' } }],
          }),
        )
        .mockResolvedValueOnce(
          makeResponse({
            qc_summary: { total_records: 30, ready_records: 9, status_counts: { non_compliant: 4 } },
            records: [{ recordKey: rec1.recordKey, latest_qc_summary: { status: 'ready' } }],
          }),
        )

      const records = usePatientRecords('all')
      await records.fetchData(1)
      await flushPromises()
      expect(records.qcSummary.value.readyRecords).toBe(5)

      // 翻页复用 totals（include_totals: false）
      records.handlePageChange(2)
      await flushPromises()
      expect(ApiService.postRaw).toHaveBeenNthCalledWith(
        2,
        '/api/medical-records/workstation/qc-summary',
        { record_keys: [rec2.recordKey], include_totals: false },
        expect.any(Object),
      )
      expect(records.qcSummary.value.readyRecords).toBe(5)

      // refreshData 即使 total 仍是 30 也强制刷新 totals
      await records.refreshData()
      await flushPromises()
      expect(ApiService.postRaw).toHaveBeenNthCalledWith(
        3,
        '/api/medical-records/workstation/qc-summary',
        { record_keys: [rec2.recordKey] },
        expect.any(Object),
      )
      expect(records.qcSummary.value.readyRecords).toBe(8)

      // 重新查询 fetchData(1) 即使 total 仍是 30 也强制刷新 totals
      await records.fetchData(1)
      await flushPromises()
      expect(ApiService.postRaw).toHaveBeenNthCalledWith(
        4,
        '/api/medical-records/workstation/qc-summary',
        { record_keys: [rec1.recordKey] },
        expect.any(Object),
      )
      expect(records.qcSummary.value.readyRecords).toBe(9)
    })
  })

  describe('WorkstationV4ListView 事件分离', () => {
    function mountListView(overrides: Record<string, unknown> = {}) {
      return mount(WorkstationV4ListView, {
        props: {
          activePriorityGroup: 'all',
          priorityGroups: [],
          priorityCardsFiltered: [],
          isStageQueueMode: false,
          searchText: '',
          dateRange: null,
          dateField: 'visit',
          departmentSelectOptions: [{ name: '全部科室', total: 10, warningCount: 0 }],
          doctorSelectOptions: [{ name: '全部主管医师', total: 10 }],
          quickDepartments: [],
          activeDept: '全部科室',
          activeDoctor: '全部主管医师',
          hospFilter: 'all',
          hospOptions: [{ value: 'all', label: '全部病历' }],
          syncScope: 'all',
          inpatientSort: 'default',
          hospitalizationStatusVerifying: false,
          workbenchRows: [],
          selectedWorkbenchKeys: [],
          tableSummaryText: '共 10 份',
          displayLoading: false,
          batchActionLoading: false,
          stageMeta: { batchActionText: '质控', singleActionText: '查看' },
          currentStageFilter: '',
          listRecords: [],
          stageEmptyText: '暂无数据',
          displayServerTotalPages: 2,
          currentPage: 2,
          pageSize: 15,
          displayServerTotal: 20,
          qcScopeTotal: 20,
          qcSummaryState: 'ready',
          loadError: false,
          ...overrides,
        },
        global: {
          stubs: {
            'a-input': {
              props: ['value', 'size'],
              emits: ['update:value', 'press-enter'],
              template:
                '<input data-testid="search-input" :value="value" @keydown.enter="$emit(\'press-enter\')" />',
            },
            'a-button': {
              emits: ['click'],
              template: '<button type="button" @click="$emit(\'click\')"><slot /></button>',
            },
            'a-range-picker': true,
            'a-segmented': true,
            'a-select': true,
            'a-select-option': true,
            BatchTablePanel: {
              name: 'BatchTablePanel',
              emits: ['page-change'],
              template:
                '<button data-testid="pager-next" @click="$emit(\'page-change\', 3, 20)">next</button>',
            },
            RecordPoolQcTaskHistory: true,
            RecordPoolQcTaskStatusBar: true,
            AnalyticsDrilldownBar: true,
            RecordPoolPreviewPanel: true,
            FrontpageTenderValidationDrawer: true,
          },
        },
      })
    }

    it('点击「查询」与搜索框回车发射 search，点击「刷新」与「重试」发射 refresh，分页器发射 page-change', async () => {
      const wrapper = mountListView({
        isStageQueueMode: true,
        currentStageFilter: 'frontpage_generate',
        loadError: true,
      })

      const searchButton = wrapper
        .findAll('button')
        .find((btn) => btn.text().trim() === '查询')
      expect(searchButton).toBeTruthy()
      await searchButton!.trigger('click')

      await wrapper.get('[data-testid="search-input"]').trigger('keydown.enter')

      expect(wrapper.emitted('search')).toHaveLength(2)
      expect(wrapper.emitted('page-change')).toBeUndefined()

      const refreshButton = wrapper
        .findAll('button')
        .find((btn) => btn.text().trim() === '刷新')
      expect(refreshButton).toBeTruthy()
      await refreshButton!.trigger('click')

      const retryButton = wrapper
        .findAll('button')
        .find((btn) => btn.text().trim() === '重试')
      expect(retryButton).toBeTruthy()
      await retryButton!.trigger('click')

      expect(wrapper.emitted('refresh')).toHaveLength(2)
      expect(wrapper.emitted('page-change')).toBeUndefined()

      await wrapper.get('[data-testid="pager-next"]').trigger('click')
      expect(wrapper.emitted('page-change')).toEqual([[3, 20]])

      wrapper.unmount()
    })
  })

  describe('QcRecordResultListView 切换 carePhase', () => {
    it('切换运行病历 ↔ 终末质控时重置筛选条件与 activeView，且只发 1 次列表请求、不残留分析面板双请求', async () => {
      const analysisMounts = vi.fn()
      const analysisCarePhaseUpdates = vi.fn()
      const analysisUnmounts = vi.fn()

      vi.mocked(ApiService.getRaw).mockResolvedValue(
        makeResponse({
          records: [
            {
              id: 'V-1',
              recordKey: '["H1","P1","V-1"]',
              institute_id: 'H1',
              patient_id: 'P1',
              visit_id: 'V-1',
              name: '患者1',
              department: '内科',
              admission_date: '2026-10-01',
            },
          ],
          departments: [
            { name: '全部科室', total: 1 },
            { name: '心内科', total: 1 },
          ],
          total: 1,
          page: 1,
        }),
      )

      const QcRecordResultAnalysisPanelStub = {
        name: 'QcRecordResultAnalysisPanel',
        props: ['carePhase'],
        watch: {
          carePhase() {
            analysisCarePhaseUpdates()
          },
        },
        mounted() {
          analysisMounts()
        },
        unmounted() {
          analysisUnmounts()
        },
        template: '<div data-testid="analysis-stub">{{ carePhase }}</div>',
      }

      const wrapper = mount(QcRecordResultListView, {
        props: { carePhase: 'inpatient' },
        global: {
          stubs: {
            QcRecordResultTable: true,
            QcRecordReviewPreview: true,
            QcRecordResultAnalysisPanel: QcRecordResultAnalysisPanelStub,
            QcRunSelectedControl: true,
            QCRecordResultComparisonDrawer: true,
            CurrentMedicalRecordDrawer: true,
            MqIconTile: true,
          },
        },
      })

      await flushPromises()
      expect(ApiService.getRaw).toHaveBeenCalledTimes(1)
      expect(ApiService.getRaw).toHaveBeenLastCalledWith(
        '/api/medical-records/workstation',
        expect.objectContaining({
          hospital_status: 'inpatient',
          date_field: 'admission',
          page: 1,
        }),
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      )

      // 模拟用户在运行病历页设置了筛选条件、翻到第 2 页，并切到了结果分析视图
      const setupState = (wrapper.vm as unknown as { $: { setupState: Record<string, unknown> } }).$.setupState
      setupState.activeDept = '心内科'
      setupState.activeDoctor = '张医生'
      setupState.searchText = '关键词'
      setupState.dateRange = ['2026-10-01', '2026-10-15']
      setupState.currentPage = 2
      setupState.activeView = 'analysis'
      await flushPromises()

      expect(wrapper.find('[data-testid="analysis-stub"]').exists()).toBe(true)
      expect(analysisMounts).toHaveBeenCalledTimes(1)

      vi.mocked(ApiService.getRaw).mockClear()

      // 切换到终末质控（discharged）
      await wrapper.setProps({ carePhase: 'discharged' })
      await flushPromises()

      // 只发出 1 次列表请求，且所有筛选条件和页码都已复位
      expect(ApiService.getRaw).toHaveBeenCalledTimes(1)
      const [, lastParams] = vi.mocked(ApiService.getRaw).mock.calls[0]
      expect(lastParams).toEqual(
        expect.objectContaining({
          hospital_status: 'discharged',
          date_field: 'discharge',
          page: 1,
          source_id: 'independent_cdm',
          qc_summary_mode: 'deferred',
        }),
      )
      expect(lastParams).not.toHaveProperty('dept')
      expect(lastParams).not.toHaveProperty('doctor')
      expect(lastParams).not.toHaveProperty('keyword')
      expect(lastParams).not.toHaveProperty('start_date')
      expect(lastParams).not.toHaveProperty('end_date')

      // 视图已切回 records，分析面板立即卸载，不因 carePhase 变化触发二次分析请求
      expect(setupState.activeDept).toBe('全部科室')
      expect(setupState.activeDoctor).toBe('全部主管医师')
      expect(setupState.searchText).toBe('')
      expect(setupState.dateRange).toBeNull()
      expect(setupState.currentPage).toBe(1)
      expect(setupState.activeView).toBe('records')
      expect(wrapper.find('[data-testid="analysis-stub"]').exists()).toBe(false)
      expect(analysisUnmounts).toHaveBeenCalledTimes(1)
      expect(analysisCarePhaseUpdates).not.toHaveBeenCalled()

      wrapper.unmount()
    })
  })
})
