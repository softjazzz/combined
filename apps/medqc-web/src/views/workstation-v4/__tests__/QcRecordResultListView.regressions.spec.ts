import { flushPromises, mount } from '@vue/test-utils'
import { reactive, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { PatientRecord, QcSummaryLoadState, RecordPoolQcSummary } from '../types'

const routeState = reactive<{ path: string; query: Record<string, string> }>({
  path: '/workstation-v4/running-qc',
  query: {},
})

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
}))

vi.mock('ant-design-vue', () => {
  const Empty = Object.assign(
    { name: 'Empty', props: ['description', 'image'], template: '<div class="empty-stub">{{ description }}</div>' },
    { PRESENTED_IMAGE_SIMPLE: 'simple' },
  )
  return {
    Alert: { name: 'Alert', props: ['message'], template: '<div role="alert">{{ message }}<slot name="action" /></div>' },
    Button: { name: 'Button', template: '<button type="button" @click="$emit(\'click\')"><slot /></button>' },
    Empty,
    Input: { name: 'Input', props: ['value'], template: '<input />' },
    Pagination: { name: 'Pagination', template: '<nav />' },
    RangePicker: { name: 'RangePicker', template: '<div />' },
    Select: { name: 'Select', template: '<select />' },
    Spin: { name: 'Spin', template: '<div><slot /></div>' },
  }
})

const mockRecordsState = {
  sourceId: ref('independent_cdm'),
  allRecords: ref<PatientRecord[]>([]),
  activeDept: ref('全部科室'),
  activeDoctor: ref('全部主管医师'),
  currentPage: ref(1),
  pageSize: ref(15),
  dateField: ref('admission'),
  dateRange: ref(null),
  departments: ref([]),
  fetchData: vi.fn(),
  handlePageChange: vi.fn(),
  loadError: ref(false),
  loading: ref(false),
  qcSummary: ref<RecordPoolQcSummary>({
    totalRecords: 0,
    readyRecords: 0,
    notRunRecords: 0,
    technicalErrorRecords: 0,
    statusCounts: {},
    runningState: 'unknown',
  }),
  qcSummaryState: ref<QcSummaryLoadState>('pending'),
  qcTotalsReady: ref(true),
  refreshData: vi.fn(),
  searchText: ref(''),
  selectHospFilter: vi.fn(),
  serverTotal: ref(0),
}

vi.mock('../composables/usePatientRecords', () => ({
  usePatientRecords: () => mockRecordsState,
}))

vi.mock('@/services/sichuan-rule-workspace-service', () => ({
  exportFilteredLuxian0609RecordResults: vi.fn(),
}))

vi.mock('../customer-sample-validation/batchExport', () => ({
  downloadBlob: vi.fn(),
}))

const analysisMounts = vi.fn()
const previewLoads = vi.fn()

import QcRecordResultListView from '../QcRecordResultListView.vue'

function makeRecord(id: string, latestQcSummary?: PatientRecord['latestQcSummary']): PatientRecord {
  return {
    id,
    recordKey: `H1|P-${id}|V-${id}`,
    instituteId: 'H1',
    patientId: `P-${id}`,
    visitId: `V-${id}`,
    name: `患者${id}`,
    department: '内科',
    bedNo: '1',
    admissionDate: '2026-10-01',
    dischargeDate: '',
    status: 'normal',
    latestQcSummary,
  } as unknown as PatientRecord
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}

const QcRecordResultTableStub = {
  name: 'QcRecordResultTable',
  props: ['rows', 'activeRecordKey', 'selectedRecordKeys'],
  emits: ['open-result', 'open-full', 'open-record', 'update:selectedRecordKeys'],
  template: `
    <div data-testid="table-stub">
      <div v-for="row in rows" :key="row.recordKey" data-testid="table-row" :data-key="row.recordKey">
        {{ row.recordKey }}
      </div>
    </div>
  `,
}

const QcRecordReviewPreviewStub = {
  name: 'QcRecordReviewPreview',
  props: ['row', 'refreshKey'],
  watch: {
    previewSignature: {
      immediate: true,
      handler(val: string) {
        previewLoads(val)
      },
    },
  },
  computed: {
    previewSignature(): string {
      const r = (this as any).row
      return `${r?.recordKey || ''}|${r?.resultStatus || ''}|${(this as any).refreshKey}`
    },
  },
  template: '<div data-testid="preview-stub" :data-refresh-key="refreshKey">{{ row?.recordKey }}</div>',
}

const QcRecordResultAnalysisPanelStub = {
  name: 'QcRecordResultAnalysisPanel',
  props: ['carePhase'],
  mounted() {
    analysisMounts()
  },
  template: '<div data-testid="analysis-stub">analysis</div>',
}

const QcRunSelectedControlStub = {
  name: 'QcRunSelectedControl',
  emits: ['results-updated'],
  template: '<button data-testid="trigger-results-updated" @click="$emit(\'results-updated\')">done</button>',
}

const ComparisonDrawerStub = {
  name: 'QCRecordResultComparisonDrawer',
  props: ['open', 'focus'],
  template: '<div v-if="open" data-testid="comparison-drawer">{{ focus?.visitId }}|{{ focus?.listQcTime || "" }}</div>',
}

function mountView(carePhase: 'inpatient' | 'discharged' = 'inpatient') {
  return mount(QcRecordResultListView, {
    props: { carePhase },
    global: {
      stubs: {
        QcRecordResultTable: QcRecordResultTableStub,
        QcRecordReviewPreview: QcRecordReviewPreviewStub,
        QcRecordResultAnalysisPanel: QcRecordResultAnalysisPanelStub,
        QcRunSelectedControl: QcRunSelectedControlStub,
        QCRecordResultComparisonDrawer: ComparisonDrawerStub,
        CurrentMedicalRecordDrawer: true,
        MqIconTile: true,
        Alert: true,
        Button: { template: '<button type="button" @click="$emit(\'click\')"><slot /></button>' },
        Empty: true,
        Input: true,
        Pagination: true,
        RangePicker: true,
        Select: true,
        Spin: { template: '<div><slot /></div>' },
      },
    },
  })
}

describe('QcRecordResultListView P2-G2 回归测试', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    routeState.query = {}
    mockRecordsState.sourceId.value = 'independent_cdm'
    mockRecordsState.allRecords.value = []
    mockRecordsState.loading.value = false
    mockRecordsState.loadError.value = false
    mockRecordsState.qcSummaryState.value = 'pending'
    mockRecordsState.serverTotal.value = 0
    mockRecordsState.fetchData.mockResolvedValue(undefined)
  })

  it('摘要回填后保持后端分页顺序，不发生客户端重排跳动，且不产生重复预览刷新', async () => {
    const r1 = makeRecord('1')
    const r2 = makeRecord('2')
    mockRecordsState.fetchData.mockImplementation(async () => {
      mockRecordsState.allRecords.value = [r1, r2]
      mockRecordsState.serverTotal.value = 2
      mockRecordsState.qcSummaryState.value = 'pending'
    })

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.findAll('[data-testid="table-row"]').map((n) => n.attributes('data-key'))).toEqual([
      'H1|P-1|V-1',
      'H1|P-2|V-2',
    ])
    const refreshKeyBeforeSummary = wrapper.get('[data-testid="preview-stub"]').attributes('data-refresh-key')
    expect(refreshKeyBeforeSummary).toBe('0')

    // deferred 摘要回填：r2 质控时间更新于 r1，列表顺序仍应保持 [r1, r2]
    mockRecordsState.allRecords.value = [
      makeRecord('1', {
        status: 'ready',
        completedAt: '2026-10-01T08:00:00+08:00',
        statusCounts: { non_compliant: 1 },
      }),
      makeRecord('2', {
        status: 'ready',
        completedAt: '2026-10-02T12:00:00+08:00',
        statusCounts: { non_compliant: 2 },
      }),
    ]
    mockRecordsState.qcSummaryState.value = 'ready'
    await flushPromises()

    expect(wrapper.findAll('[data-testid="table-row"]').map((n) => n.attributes('data-key'))).toEqual([
      'H1|P-1|V-1',
      'H1|P-2|V-2',
    ])
    // previewRefreshKey 不应因普通摘要回填而额外递增（状态从 unknown -> priority 已由预览组件自身响应一次）
    expect(wrapper.get('[data-testid="preview-stub"]').attributes('data-refresh-key')).toBe('0')

    // 仅当同一选中病历在 ready 状态下原地更新了摘要时间时，才递增 previewRefreshKey
    mockRecordsState.allRecords.value = [
      makeRecord('1', {
        status: 'ready',
        completedAt: '2026-10-03T09:30:00+08:00',
        statusCounts: { non_compliant: 1 },
      }),
      mockRecordsState.allRecords.value[1],
    ]
    await flushPromises()
    expect(wrapper.get('[data-testid="preview-stub"]').attributes('data-refresh-key')).toBe('1')
    wrapper.unmount()
  })

  it('深链 ?record_key= 等待 deferred 摘要落定后再打开抽屉，并在切相或用户交互后取消过期深链', async () => {
    routeState.query = { record_key: 'H1|P-2|V-2', visit_id: 'V-2' }
    mockRecordsState.fetchData.mockImplementation(async () => {
      mockRecordsState.allRecords.value = [makeRecord('1'), makeRecord('2')]
      mockRecordsState.serverTotal.value = 2
      mockRecordsState.qcSummaryState.value = 'pending'
    })

    const wrapper = mountView()
    await flushPromises()

    // 摘要仍在 pending，不应抢跑打开抽屉
    expect(wrapper.find('[data-testid="comparison-drawer"]').exists()).toBe(false)

    // 摘要到达后才打开抽屉并带上质控时间
    mockRecordsState.allRecords.value = [
      makeRecord('1', { status: 'ready', completedAt: '2026-10-01T08:00:00+08:00', statusCounts: {} }),
      makeRecord('2', { status: 'ready', completedAt: '2026-10-02T10:15:00+08:00', statusCounts: { non_compliant: 1 } }),
    ]
    mockRecordsState.qcSummaryState.value = 'ready'
    await flushPromises()

    const drawer = wrapper.get('[data-testid="comparison-drawer"]')
    expect(drawer.text()).toContain('V-2')
    expect(drawer.text()).toContain('2026-10-02 10:15')
    wrapper.unmount()

    // 竞态场景：深链 fetchData 在途时切换 carePhase，晚到结果不得弹窗
    const slowFetch = deferred<void>()
    mockRecordsState.fetchData.mockReturnValueOnce(slowFetch.promise)
    const wrapper2 = mountView('inpatient')
    await wrapper2.setProps({ carePhase: 'discharged' })
    mockRecordsState.allRecords.value = [
      makeRecord('2', { status: 'ready', completedAt: '2026-10-02T10:15:00+08:00', statusCounts: { non_compliant: 1 } }),
    ]
    mockRecordsState.qcSummaryState.value = 'ready'
    slowFetch.resolve(undefined)
    await flushPromises()
    expect(wrapper2.find('[data-testid="comparison-drawer"]').exists()).toBe(false)
    wrapper2.unmount()
  })

  it('@results-updated 同步刷新结果分析视图并刷新病历列表', async () => {
    mockRecordsState.sourceId.value = 'pg_emr'
    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('[data-testid="qc-result-view-analysis"]').trigger('click')
    await flushPromises()
    expect(analysisMounts).toHaveBeenCalledTimes(1)

    await wrapper.get('[data-testid="trigger-results-updated"]').trigger('click')
    await flushPromises()

    expect(mockRecordsState.refreshData).toHaveBeenCalledTimes(1)
    expect(analysisMounts).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })
})
