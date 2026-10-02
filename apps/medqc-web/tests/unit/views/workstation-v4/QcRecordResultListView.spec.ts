import { flushPromises, mount } from '@vue/test-utils'
import { Pagination } from 'ant-design-vue'
import { defineComponent, h } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  downloadBlob: vi.fn(),
  exportFilteredLuxian0609RecordResults: vi.fn(),
  getRaw: vi.fn(),
  routerReplace: vi.fn(),
  listFilterTemplates: vi.fn(),
  hasRole: vi.fn(),
  authStore: null as null | {
    user: { id: string; email: string } | null
    userRoles: string[]
    hasRole: ReturnType<typeof vi.fn>
  },
}))
const routeState = vi.hoisted(() => ({
  path: '/workstation-v5/records',
  query: {} as Record<string, string>,
}))

vi.mock('@/services/apiService', () => ({
  ApiService: {
    getRaw: mocks.getRaw,
  },
}))

vi.mock('@/services/sichuan-rule-workspace-service', () => ({
  exportFilteredLuxian0609RecordResults: mocks.exportFilteredLuxian0609RecordResults,
}))

vi.mock('@/views/workstation-v4/customer-sample-validation/batchExport', () => ({
  downloadBlob: mocks.downloadBlob,
}))

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({ replace: mocks.routerReplace }),
}))

vi.mock('@/stores/auth', async () => {
  const { reactive } = await import('vue')
  return {
    useAuthStore: () => {
      if (!mocks.authStore) {
        mocks.authStore = reactive({
          user: { id: 'qc-result-list-test', email: 'qc-result-list-test@example.com' },
          userRoles: ['qc_manager'],
          hasRole: mocks.hasRole,
        })
      }
      return mocks.authStore
    },
  }
})

vi.mock('@/api/filterTemplates', () => ({
  listFilterTemplates: mocks.listFilterTemplates,
  createFilterTemplate: vi.fn(),
  updateFilterTemplate: vi.fn(),
  removeFilterTemplate: vi.fn(),
}))

import QcRecordResultListView from '@/views/workstation-v4/QcRecordResultListView.vue'
import QcRunSelectedControl from '@/views/workstation-v4/components/qc/QcRunSelectedControl.vue'
import QcRecordReviewPreview from '@/views/workstation-v4/components/qc/QcRecordReviewPreview.vue'

const ResultDrawerStub = defineComponent({
  name: 'QCRecordResultComparisonDrawer',
  props: {
    open: { type: Boolean, default: false },
    focus: { type: Object, default: null },
    presentationMode: { type: String, default: 'flat' },
    recordReview: { type: Boolean, default: false },
    hasPrev: { type: Boolean, default: undefined },
    hasNext: { type: Boolean, default: undefined },
    currentIndex: { type: Number, default: undefined },
    totalCount: { type: Number, default: undefined },
    initialDefectPartition: { type: String, default: 'confirmed' },
    initialDefectTarget: { type: Object, default: null },
    rectificationIntent: { type: Number, default: 0 },
    scoreScene: { type: String, default: undefined },
  },
  emits: ['close', 'review-submitted', 'navigate-prev', 'navigate-next', 'qc-completed'],
  setup(props) {
    return () => h('div', { 'data-testid': 'result-drawer-stub', 'data-open': String(props.open) })
  },
})

const DocumentWorkbenchStub = defineComponent({
  name: 'QCRecordCompareWorkbench',
  props: {
    visitId: { type: String, required: true },
    instituteId: { type: String, required: true },
    patientId: { type: String, required: true },
    issues: { type: Array, required: true },
    documentOnly: { type: Boolean, default: false },
  },
  setup() {
    return () => h('div', { 'data-testid': 'document-workbench-stub' })
  },
})

const ResultAnalysisStub = defineComponent({
  name: 'QcRecordResultAnalysisPanel',
  props: { carePhase: { type: String, required: true } },
  emits: ['open-result'],
  setup(_, { emit }) {
    return () =>
      h(
        'button',
        {
          type: 'button',
          'data-testid': 'result-analysis-stub',
          onClick: () =>
            emit('open-result', {
              institute_id: 'H-analysis',
              patient_id: 'P-analysis',
              visit_id: 'V-analysis',
              patient_name: '患者分析',
              department: '康复科',
              completed_at: '2026-08-19T08:00:00+00:00',
            }),
        },
        '分析下钻',
      )
  },
})

const mountedWrappers: Array<{ unmount: () => void }> = []

function response() {
  return {
    data: {
      records: [
        {
          id: 'V-priority',
          record_key: '["H","P","V-priority"]',
          institute_id: 'H',
          patient_id: 'P',
          visit_id: 'V-priority',
          patient_name: '患者甲',
          sex: '女',
          age: 68,
          department: '重症医学科',
          admission_date: '2026-08-09 08:00',
          discharge_date: '2026-08-12 10:00',
          source_state: { status: 'unknown' },
          latest_qc_summary: {
            status: 'ready',
            completed_at: '2026-08-12 11:30',
            status_counts: { non_compliant: 2, data_gap: 1, uncertain: 3 },
          },
        },
        {
          id: 'V-data-gap',
          record_key: '["H","P","V-data-gap"]',
          institute_id: 'H',
          patient_id: 'P',
          visit_id: 'V-data-gap',
          patient_name: '患者乙',
          latest_qc_summary: {
            status: 'ready',
            completed_at: '2026-08-12 11:32',
            status_counts: { data_gap: 2 },
          },
        },
        {
          id: 'V-uncertain',
          record_key: '["H","P","V-uncertain"]',
          institute_id: 'H',
          patient_id: 'P',
          visit_id: 'V-uncertain',
          patient_name: '患者丙',
          latest_qc_summary: { status: 'ready', status_counts: { uncertain: 1 } },
        },
        {
          id: 'V-not-run',
          record_key: '["H","P","V-not-run"]',
          institute_id: 'H',
          patient_id: 'P',
          visit_id: 'V-not-run',
          patient_name: '患者丁',
          latest_qc_summary: { status: 'not_run' },
        },
        {
          id: 'V-technical',
          record_key: '["H","P","V-technical"]',
          institute_id: 'H',
          patient_id: 'P',
          visit_id: 'V-technical',
          patient_name: '患者戊',
          source_state: { status: 'pending' },
          latest_qc_summary: { status: 'technical_error' },
        },
        {
          id: 'missing-triple-coordinate',
          record_key: '["H","P","missing"]',
          visit_id: 'missing',
          patient_name: '不得展示',
        },
      ],
      departments: [{ name: '重症医学科', total: 6 }],
      doctors: [
        { name: '全部主管医师', total: 6 },
        { name: '张医师', total: 3 },
      ],
      total: 6,
      page: 1,
      qc_summary: {
        total_records: 20,
        ready_records: 14,
        status_counts: { non_compliant: 4, data_gap: 5 },
      },
    },
  }
}

function mountView(carePhase: 'inpatient' | 'discharged' = 'inpatient') {
  const wrapper = mount(QcRecordResultListView, {
    attachTo: document.body,
    props: { carePhase },
    global: {
      stubs: {
        'a-modal': true,
        QCRecordResultComparisonDrawer: ResultDrawerStub,
        QCRecordCompareWorkbench: DocumentWorkbenchStub,
        QcRecordResultAnalysisPanel: ResultAnalysisStub,
        QcRecordReviewPreview: true,
      },
    },
  })
  mountedWrappers.push(wrapper)
  return wrapper
}

describe('QcRecordResultListView', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    )
    vi.clearAllMocks()
    mocks.authStore = null
    window.sessionStorage.clear()
    window.localStorage.clear()
    routeState.query = {}
    mocks.getRaw.mockResolvedValue(response())
    mocks.routerReplace.mockResolvedValue(undefined)
    mocks.listFilterTemplates.mockResolvedValue({ success: true, data: [] })
    mocks.hasRole.mockReturnValue(false)
    mocks.exportFilteredLuxian0609RecordResults.mockResolvedValue({
      success: true,
      data: new Blob(['xlsx']),
    })
  })

  it('同页查询缺陷明细并按匹配来源打开既有缺陷分区', async () => {
    const wrapper = mountView('inpatient')
    await flushPromises()
    mocks.getRaw.mockResolvedValue({
      data: {
        records: [],
        defects: [
          {
            institute_id: 'H',
            patient_id: 'P',
            visit_id: 'V-manual',
            patient_name: '患者人工',
            department: '内科',
            doctor: '张医师',
            source: 'manual',
            defect_id: 'D1',
            rule_id: 'MANUAL-1',
            rule_name: '人工补充缺陷',
            document: '病程记录',
            description: '缺陷描述',
            status: 'approved',
            occurred_at: '2026-09-30T10:00:00',
          },
        ],
        total: 1,
        page: 1,
      },
    })
    await wrapper.get('[data-testid="qc-result-view-defects"]').trigger('click')
    await flushPromises()

    expect(mocks.getRaw.mock.lastCall?.[1]).toMatchObject({
      result_view: 'defects',
      defect_source: 'all',
      hospital_status: 'inpatient',
    })
    expect(wrapper.text()).toContain('人工补充缺陷')
    expect(wrapper.text()).toContain('共 1 条')
    await wrapper.get('.qc-record-result-list-view__defect-row button').trigger('click')
    const drawer = wrapper.getComponent(ResultDrawerStub)
    expect(drawer.props('initialDefectPartition')).toBe('manual')
    expect(drawer.props('initialDefectTarget')).toEqual({ source: 'manual', defectId: 'D1' })
    expect(drawer.props('rectificationIntent')).toBe(0)
    const buttons = wrapper.findAll('.qc-record-result-list-view__defect-row button')
    await buttons[1].trigger('click')
    expect(drawer.props('rectificationIntent')).toBeGreaterThan(0)
    expect(drawer.props('initialDefectTarget')).toEqual({ source: 'manual', defectId: 'D1' })
    await buttons[0].trigger('click')
    expect(drawer.props('rectificationIntent')).toBe(0)
    expect(drawer.props('focus')).toMatchObject({
      instituteId: 'H',
      patientId: 'P',
      visitId: 'V-manual',
    })
  })

  it('缺陷快捷分区进入请求与URL，切回病历移除分区', async () => {
    const wrapper = mountView('inpatient')
    await flushPromises()
    await wrapper.get('[data-testid="qc-result-view-defects"]').trigger('click')
    await flushPromises()
    expect(mocks.getRaw.mock.lastCall?.[1]).toHaveProperty('defect_workflow', 'pending_work')
    await wrapper.get('[data-testid="quick-filter-clinical_appeal"]').trigger('click')
    await flushPromises()
    expect(mocks.getRaw.mock.lastCall?.[1]).toMatchObject({
      result_view: 'defects',
      defect_workflow: 'clinical_appeal',
    })
    expect(mocks.routerReplace.mock.lastCall?.[0].query).toMatchObject({
      result_view: 'defects',
      defect_workflow: 'clinical_appeal',
    })
    await wrapper.get('[data-testid="qc-result-view-records"]').trigger('click')
    await flushPromises()
    expect(mocks.getRaw.mock.lastCall?.[1]).not.toHaveProperty('defect_workflow')
    expect(mocks.routerReplace.mock.lastCall?.[0].query).not.toHaveProperty('defect_workflow')
  })

  it('从默认审核中进入缺陷默认待处理，并清除病历审核筛选；显式全部再次切换仍保持', async () => {
    mocks.hasRole.mockImplementation((role: string) => role === 'qc_manager')
    const wrapper = mountView('inpatient')
    await flushPromises()
    expect(mocks.getRaw.mock.lastCall?.[1]).toHaveProperty(
      'review_state',
      'pending_review,pending_recheck',
    )
    await wrapper.get('[data-testid="qc-result-view-defects"]').trigger('click')
    await flushPromises()
    expect(mocks.getRaw.mock.lastCall?.[1]).toHaveProperty('defect_workflow', 'pending_work')
    expect(mocks.getRaw.mock.lastCall?.[1]).not.toHaveProperty('review_state')
    await wrapper.get('[data-testid="quick-filter-all"]').trigger('click')
    await flushPromises()
    expect(mocks.routerReplace.mock.lastCall?.[0].query).toHaveProperty('defect_workflow', 'all')
    await wrapper.get('[data-testid="qc-result-view-records"]').trigger('click')
    await flushPromises()
    expect(mocks.getRaw.mock.lastCall?.[1]).toHaveProperty(
      'review_state',
      'pending_review,pending_recheck',
    )
    await wrapper.get('[data-testid="qc-result-view-defects"]').trigger('click')
    await flushPromises()
    expect(mocks.getRaw.mock.lastCall?.[1]).toHaveProperty('defect_workflow', 'all')
  })

  it('显式URL缺陷全部优先于系统默认', async () => {
    routeState.query = { result_view: 'defects', defect_workflow: 'all' }
    const wrapper = mountView('inpatient')
    await flushPromises()
    expect(mocks.getRaw.mock.lastCall?.[1]).toHaveProperty('defect_workflow', 'all')
    expect(wrapper.get('[data-testid="quick-filter-all"]').attributes('aria-pressed')).toBe('true')
  })

  it('用户默认模板优先，切换缺陷不附加待处理组合', async () => {
    mocks.listFilterTemplates.mockResolvedValue({
      success: true,
      data: [
        {
          id: 'default-all',
          page_key: 'v5_records_inpatient',
          name: '本人默认',
          is_default: true,
          version: 1,
          filters: { dept: '内科' },
        },
      ],
    })
    const wrapper = mountView('inpatient')
    await flushPromises()
    await wrapper.get('[data-testid="qc-result-view-defects"]').trigger('click')
    await flushPromises()
    expect(mocks.getRaw.mock.lastCall?.[1]).not.toHaveProperty('defect_workflow')
    expect(mocks.getRaw.mock.lastCall?.[1]).toHaveProperty('dept', '内科')
  })

  it('缺陷owner返回503时显示失败且不伪装成零缺陷', async () => {
    const wrapper = mountView('inpatient')
    await flushPromises()
    mocks.getRaw.mockRejectedValueOnce(new Error('503'))

    await wrapper.get('[data-testid="qc-result-view-defects"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('缺陷数据加载失败，请重试')
    expect(wrapper.text()).not.toContain('当前条件下暂无缺陷')
    expect(wrapper.text()).not.toContain('共 0 条')
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    mountedWrappers
      .splice(0)
      .reverse()
      .forEach((wrapper) => wrapper.unmount())
    document.body.innerHTML = ''
  })

  it.each([
    ['inpatient', '运行病历质控', '固定范围：在院', 'admission', '在院病历 · 质控结果'],
    ['discharged', '已出院病历质控结果', '固定范围：已出院', 'discharge', '已出院病历 · 质控结果'],
  ] as const)(
    '固定 %s 服务端范围、保留主标题且不展示范围说明',
    async (carePhase, title, scope, dateField, removedEyebrow) => {
      const wrapper = mountView(carePhase)
      await flushPromises()

      expect(wrapper.text()).toContain(title)
      if (carePhase === 'discharged') {
        expect(wrapper.get('.qc-record-result-list-view__header').text()).not.toContain('终末')
        // 终末口径 B：已出院列表可发起质控所选，常驻未核验归档提示。
        expect(wrapper.text()).toContain('终末按已出院病历执行，归档状态未核验')
      }
      if (carePhase === 'inpatient') {
        expect(wrapper.get('.review-workbench-scope').text()).toBe('在院')
        expect(wrapper.get('.review-workbench-scope').attributes('title')).toBe(scope)
      } else {
        expect(wrapper.get('.review-workbench-scope').text()).toBe('已出院')
        expect(wrapper.get('.review-workbench-scope').attributes('title')).toBe(scope)
      }
      expect(wrapper.find('.qc-record-result-list-view__header').text()).not.toContain(
        removedEyebrow,
      )
      expect(wrapper.find('.qc-record-result-list-view__header').text()).not.toContain(
        '仅展示当前范围内病历的最新质控结果，不混入其他业务流程。',
      )
      expect(mocks.getRaw).toHaveBeenCalledWith('/api/medical-records/workstation', {
        page: 1,
        page_size: 15,
        date_field: dateField,
        hospital_status: carePhase,
      })
    },
  )

  it('运行和终末页共用复核布局，保留各自日期范围', async () => {
    const wrapper = mountView('inpatient')
    await flushPromises()
    expect(wrapper.classes()).toContain('running-qc-refined')
    expect(
      wrapper.findAll('.qc-record-result-list-view__field-label').map((label) => label.text()),
    ).toEqual([
      '关键词',
      '科室',
      '缺陷来源',
      '缺陷状态',
      '主管医师',
      '入院日期',
      '评分标准',
      '计分状态',
      '评分等级',
      '分数区间',
    ])
    expect(
      wrapper
        .find('.qc-record-result-list-view__filters .qc-record-result-list-view__export-trigger')
        .exists(),
    ).toBe(false)
    expect(wrapper.find('.qc-record-result-list-view__selected-count').exists()).toBe(false)
    await wrapper.get('input[aria-label="选择患者甲"]').setValue(true)
    expect(wrapper.get('.qc-record-result-list-view__selected-count').text()).toBe('已选 1 份')
    await wrapper.get('input[aria-label="选择患者甲"]').setValue(false)
    expect(wrapper.find('.qc-record-result-list-view__selected-count').exists()).toBe(false)

    const finalView = mountView('discharged')
    await flushPromises()
    expect(finalView.classes()).toContain('running-qc-refined')
    expect(finalView.find('.qc-record-result-list-view__list-heading').exists()).toBe(true)
    expect(
      finalView.findAll('.qc-record-result-list-view__field-label').map((label) => label.text()),
    ).toEqual([
      '关键词',
      '科室',
      '缺陷来源',
      '缺陷状态',
      '主管医师',
      '出院日期',
      '评分标准',
      '计分状态',
      '评分等级',
      '分数区间',
    ])
    expect(finalView.getComponent(QcRecordReviewPreview).props('carePhase')).toBe('discharged')
    expect(finalView.findAllComponents(QcRunSelectedControl)).toHaveLength(1)
  })

  it('使用服务端全量汇总，并只展示三坐标和 recordKey 完整的病历行', async () => {
    const wrapper = mountView('inpatient')
    await flushPromises()

    expect(wrapper.findAll('.review-workbench-metrics strong').map((item) => item.text())).toEqual([
      '20',
      '14',
      '4',
      '5',
    ])
    expect(
      wrapper
        .findAll('.review-workbench-metrics > div > span:first-child')
        .map((item) => item.text()),
    ).toEqual(['纳入病历', '已完成质控', '确定问题', '资料待核实'])
    expect(wrapper.findAll('tbody tr[data-record-key]')).toHaveLength(5)
    expect(wrapper.find('.qc-record-result-table__avatar').exists()).toBe(true)
    expect(wrapper.text()).toContain('患者乙')
    expect(wrapper.text()).not.toContain('不得展示')
    expect(wrapper.text()).not.toContain('来源未知')
    expect(wrapper.text()).not.toContain('资料完整')
  })

  it('预览焦点与多选独立，刷新移除原病历后回到有效首行', async () => {
    const wrapper = mountView('inpatient')
    await flushPromises()
    const preview = wrapper.getComponent(QcRecordReviewPreview)
    const firstKey = preview.props('row')!.recordKey
    await wrapper.get('input[aria-label="选择患者甲"]').setValue(true)
    expect(preview.props('row')!.recordKey).toBe(firstKey)
    const target = wrapper
      .findAll('tbody tr[data-record-key]')
      .find((row) => row.attributes('data-record-key').includes('V-priority'))!
    await target.trigger('click')
    expect(preview.props('row')!.visitId).toBe('V-priority')
    expect(wrapper.getComponent(ResultDrawerStub).props('open')).toBe(false)
    const payload = response()
    payload.data.records = payload.data.records.filter((record) => record.visit_id === 'V-data-gap')
    mocks.getRaw.mockResolvedValue(payload)
    await wrapper.get('.qc-record-result-list-view__refresh-button').trigger('click')
    await flushPromises()
    expect(preview.props('row')!.visitId).toBe('V-data-gap')
  })

  it('切换结果分析不销毁运行任务的进度挂载节点', async () => {
    const wrapper = mountView('inpatient')
    await flushPromises()
    const target = wrapper.get('#qc-record-result-task-status-inpatient').element
    await wrapper.get('[data-testid="qc-result-view-analysis"]').trigger('click')
    expect(wrapper.get('#qc-record-result-task-status-inpatient').element).toBe(target)
    await wrapper.get('[data-testid="qc-result-view-records"]').trigger('click')
    expect(wrapper.get('#qc-record-result-task-status-inpatient').element).toBe(target)
    expect(wrapper.findAll('#qc-record-result-task-status-inpatient')).toHaveLength(1)
  })

  it('按 Canonical 摘要严格区分临床问题、资料待核实、待判断、未质控和交付异常', async () => {
    const wrapper = mountView('inpatient')
    await flushPromises()

    expect(wrapper.get('.review-metric--priority').text()).toBe('确定问题4项')
    expect(wrapper.text()).toContain('确定问题 2 · 待核实 1 · 待判断 3')
    expect(wrapper.text()).toContain('资料待核实')
    expect(wrapper.text()).toContain('待判断')
    expect(wrapper.text()).toContain('暂无结果')
    expect(wrapper.text()).toContain('请复核结果交付')
  })

  it('最近质控时间按北京时间展示，且已带时区的时间不重复转换', async () => {
    const payload = response()
    payload.data.records[0]!.latest_qc_summary!.completed_at = '2026-08-17T08:49:00'
    payload.data.records[1]!.latest_qc_summary!.completed_at = '2026-08-17T16:49:00+08:00'
    mocks.getRaw.mockResolvedValue(payload)

    const wrapper = mountView('inpatient')
    await flushPromises()

    const renderedTimes = wrapper
      .findAll('tbody tr[data-record-key] td:nth-child(4)')
      .map((item) => item.text())
    expect(renderedTimes.slice(0, 2)).toEqual(['2026-08-17 16:49', '2026-08-17 16:49'])
    expect(wrapper.getComponent(QcRecordReviewPreview).props('row')?.admissionTime).toBe(
      '2026-08-09 08:00',
    )
  })

  it('关键词、科室、主管医师和日期过滤重置为第一页并只使用服务端请求', async () => {
    const wrapper = mountView('discharged')
    await flushPromises()
    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('患者甲')
    await inputs[1].setValue('2026-08-01')
    await inputs[2].setValue('2026-08-10')
    await wrapper.get('select[aria-label="科室筛选"]').setValue('重症医学科')
    await wrapper.get('select[aria-label="主管医师筛选"]').setValue('张医师')
    await flushPromises()

    expect(mocks.getRaw).toHaveBeenLastCalledWith('/api/medical-records/workstation', {
      page: 1,
      page_size: 15,
      date_field: 'discharge',
      dept: '重症医学科',
      doctor: '张医师',
      keyword: '患者甲',
      start_date: '2026-08-01',
      end_date: '2026-08-10',
      hospital_status: 'discharged',
    })
  })

  it('主管医师选项来自服务端，切换与全部重置均重新请求而不本地过滤', async () => {
    const payload = response()
    payload.data.total = 30
    mocks.getRaw.mockResolvedValue(payload)
    const wrapper = mountView('inpatient')
    await flushPromises()
    const doctorSelect = wrapper.get('select[aria-label="主管医师筛选"]')
    expect(doctorSelect.findAll('option').map((option) => option.text())).toEqual([
      '全部主管医师',
      '张医师',
    ])

    wrapper.getComponent(Pagination).vm.$emit('change', 2, 15)
    await flushPromises()
    expect(mocks.getRaw).toHaveBeenLastCalledWith('/api/medical-records/workstation', {
      page: 2,
      page_size: 15,
      date_field: 'admission',
      hospital_status: 'inpatient',
    })

    await doctorSelect.setValue('张医师')
    await flushPromises()
    expect(mocks.getRaw).toHaveBeenLastCalledWith('/api/medical-records/workstation', {
      page: 1,
      page_size: 15,
      date_field: 'admission',
      doctor: '张医师',
      hospital_status: 'inpatient',
    })
    expect(wrapper.findAll('tbody tr[data-record-key]')).toHaveLength(5)

    await doctorSelect.setValue('全部主管医师')
    await flushPromises()
    expect(mocks.getRaw).toHaveBeenLastCalledWith('/api/medical-records/workstation', {
      page: 1,
      page_size: 15,
      date_field: 'admission',
      hospital_status: 'inpatient',
    })
  })

  it('服务端未提供医生列表时不从当前页病历伪造医生选项', async () => {
    const payload = response()
    payload.data.doctors = []
    mocks.getRaw.mockResolvedValue(payload)
    const wrapper = mountView('inpatient')
    await flushPromises()
    expect(
      wrapper
        .get('select[aria-label="主管医师筛选"]')
        .findAll('option')
        .map((option) => option.text()),
    ).toEqual(['全部主管医师'])
  })

  it('按当前服务端筛选导出已出院病历Excel，不使用当前页行拼接', async () => {
    const wrapper = mountView('discharged')
    await flushPromises()
    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('患者甲')
    await inputs[1].setValue('2026-08-01')
    await inputs[2].setValue('2026-08-10')
    await wrapper.get('select[aria-label="科室筛选"]').setValue('重症医学科')
    await wrapper.get('select[aria-label="主管医师筛选"]').setValue('张医师')
    await flushPromises()

    await wrapper.get('[data-testid="qc-result-export-trigger"]').trigger('click')
    await wrapper.get('[data-testid="qc-result-export-filtered"]').trigger('click')
    await flushPromises()

    expect(mocks.exportFilteredLuxian0609RecordResults).toHaveBeenCalledWith({
      scope: 'final',
      department: '重症医学科',
      doctor: '张医师',
      date_field: 'discharge',
      start_date: '2026-08-01',
      end_date: '2026-08-10',
      keyword: '患者甲',
    })
    expect(mocks.downloadBlob).toHaveBeenCalledWith(
      expect.any(Blob),
      '已出院病历质控-当前筛选.xlsx',
    )
  })

  it('未勾选病历时只禁用导出所选，仍可导出当前筛选结果', async () => {
    const wrapper = mountView('discharged')
    await flushPromises()

    await wrapper.get('[data-testid="qc-result-export-trigger"]').trigger('click')

    expect(wrapper.get('[data-testid="qc-result-export-selected"]').attributes('disabled')).toBe('')
    expect(
      wrapper.get('[data-testid="qc-result-export-filtered"]').attributes('disabled'),
    ).toBeUndefined()
  })

  it('按勾选病历的三坐标精确导出Excel，不回退当前筛选或visitId单键', async () => {
    const wrapper = mountView('discharged')
    await flushPromises()

    await wrapper.get('input[aria-label="选择患者甲"]').setValue(true)
    await wrapper.get('[data-testid="qc-result-export-trigger"]').trigger('click')
    await wrapper.get('[data-testid="qc-result-export-selected"]').trigger('click')
    await flushPromises()

    expect(mocks.exportFilteredLuxian0609RecordResults).toHaveBeenCalledWith({
      scope: 'final',
      date_field: 'discharge',
      record_refs: [
        {
          institute_id: 'H',
          patient_id: 'P',
          visit_id: 'V-priority',
        },
      ],
    })
    expect(mocks.downloadBlob).toHaveBeenCalledWith(expect.any(Blob), '已出院病历质控-所选1份.xlsx')
  })

  it('相同 visitId 的两份病历按 recordKey 定位，并向抽屉传入所选行的完整三坐标', async () => {
    mocks.getRaw.mockResolvedValue({
      data: {
        ...response().data,
        records: [
          {
            id: 'V-shared',
            record_key: '["H-1","P-1","V-shared"]',
            institute_id: 'H-1',
            patient_id: 'P-1',
            visit_id: 'V-shared',
            patient_name: '患者甲',
            department: '重症医学科',
            latest_qc_summary: { status: 'ready', completed_at: '2026-08-09T08:01:02.123456' },
          },
          {
            id: 'V-shared',
            record_key: '["H-2","P-2","V-shared"]',
            institute_id: 'H-2',
            patient_id: 'P-2',
            visit_id: 'V-shared',
            patient_name: '患者乙',
            department: '康复科',
            latest_qc_summary: { status: 'ready', completed_at: '2026-08-09T09:02:03.654321' },
          },
        ],
        total: 2,
      },
    })
    const wrapper = mountView()
    await flushPromises()

    const rows = wrapper.findAll('tbody tr[data-record-key]')
    await rows[1]!.find('button').trigger('click')

    const preview = wrapper.getComponent(QcRecordReviewPreview)
    expect(preview.props('row')).toMatchObject({
      instituteId: 'H-2',
      patientId: 'P-2',
      visitId: 'V-shared',
    })
    expect(wrapper.getComponent(ResultDrawerStub).props('open')).toBe(false)
    preview.vm.$emit('open-full', preview.props('row')!.recordKey)
    await flushPromises()

    const drawer = wrapper.getComponent(ResultDrawerStub)
    expect(drawer.props('open')).toBe(true)
    expect(drawer.props('presentationMode')).toBe('grouped')
    expect(drawer.props('focus')).toMatchObject({
      instituteId: 'H-2',
      patientId: 'P-2',
      patientName: '患者乙',
      visitId: 'V-shared',
      recordId: 'V-shared',
    })
    expect(String((drawer.props('focus') as { label: string }).label)).toContain('患者乙')
    expect(String((drawer.props('focus') as { label: string }).label)).toContain('2026-08-09 17:02')
  })

  it('从首页携带三坐标键进入时按住院号服务端检索，并自动打开该病历质控结果', async () => {
    routeState.query = {
      record_key: '["H","P","V-priority"]',
      visit_id: 'V-priority',
    }

    const wrapper = mountView('discharged')
    await flushPromises()

    expect(mocks.getRaw).toHaveBeenCalledWith('/api/medical-records/workstation', {
      page: 1,
      page_size: 15,
      date_field: 'discharge',
      keyword: 'V-priority',
      hospital_status: 'discharged',
    })
    const drawer = wrapper.getComponent(ResultDrawerStub)
    expect(drawer.props('open')).toBe(true)
    expect(drawer.props('focus')).toMatchObject({
      instituteId: 'H',
      patientId: 'P',
      visitId: 'V-priority',
      recordId: 'V-priority',
    })
  })

  it('未质控病历可按三坐标打开只读文书，不发起质控结果读取', async () => {
    const wrapper = mountView()
    await flushPromises()

    const notRunRow = wrapper
      .findAll('tbody tr[data-record-key]')
      .find((row) => row.attributes('data-record-key').includes('V-not-run'))!
    expect(notRunRow.text()).toContain('暂无结果')
    await notRunRow.trigger('click')

    expect(wrapper.getComponent(QcRecordReviewPreview).props('row')?.resultStatus).toBe('not-run')
    expect(wrapper.getComponent(ResultDrawerStub).props('open')).toBe(false)
    await wrapper.get('[data-testid="open-unchecked-record-documents"]').trigger('click')
    const documents = wrapper.getComponent(DocumentWorkbenchStub)
    expect(documents.props()).toMatchObject({
      visitId: 'V-not-run',
      instituteId: 'H',
      patientId: 'P',
      documentOnly: true,
      issues: [],
    })
    expect(wrapper.getComponent(ResultDrawerStub).props('open')).toBe(false)
  })

  it('身份不完整的病历无法打开只读文书或质控结果', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.find('[data-testid="open-unchecked-record-documents"]').exists()).toBe(false)
    await wrapper.getComponent(QcRecordReviewPreview).vm.$emit('open-full', '["H","P","missing"]')

    expect(wrapper.findComponent(DocumentWorkbenchStub).exists()).toBe(false)
    expect(wrapper.getComponent(ResultDrawerStub).props('open')).toBe(false)
    expect(wrapper.text()).toContain('无法确认当前病历身份')
  })

  it('已保存结果在当前页打开分组抽屉，不混入生成编码结算入口', async () => {
    const wrapper = mountView('discharged')
    await flushPromises()
    const text = wrapper.text()

    ;['开始质控', '重新质控', '生成首页', '编码质控', '结算质控', '整改'].forEach((forbidden) => {
      expect(text).not.toContain(forbidden)
    })
    await wrapper
      .findComponent({ name: 'QcRecordResultTable' })
      .vm.$emit('open-result', '["H","P","V-priority"]')
    expect(wrapper.getComponent(ResultDrawerStub).props('open')).toBe(false)
    expect(wrapper.getComponent(QcRecordReviewPreview).props('row')?.visitId).toBe('V-priority')
    expect(wrapper.find('[data-testid="open-unchecked-record-documents"]').exists()).toBe(false)
    await wrapper
      .getComponent(QcRecordReviewPreview)
      .vm.$emit('open-full', '["H","P","V-priority"]')
    expect(wrapper.getComponent(ResultDrawerStub).props('open')).toBe(true)
    expect(wrapper.findComponent(DocumentWorkbenchStub).exists()).toBe(false)
    expect(wrapper.text()).not.toContain('下一闭环接入')
  })

  it('将勾选病历的完整三坐标交给质控控件，完成后刷新当前结果页', async () => {
    const wrapper = mountView('discharged')
    await flushPromises()
    await wrapper.get('input[aria-label="选择患者甲"]').setValue(true)

    expect(wrapper.getComponent(QcRunSelectedControl).props('recordRefs')).toEqual([
      {
        institute_id: 'H',
        patient_id: 'P',
        visit_id: 'V-priority',
      },
    ])
    const requestsBeforeRefresh = mocks.getRaw.mock.calls.length

    wrapper.getComponent(QcRunSelectedControl).vm.$emit('completed')
    await flushPromises()

    expect(mocks.getRaw.mock.calls.length).toBe(requestsBeforeRefresh + 1)
  })

  it('账号或角色变化立即清空已勾选病历', async () => {
    const wrapper = mountView()
    await flushPromises()
    await wrapper.get('input[aria-label="选择患者甲"]').setValue(true)
    expect(wrapper.getComponent(QcRunSelectedControl).props('selectedCount')).toBe(1)
    if (!mocks.authStore) throw new Error('auth store missing')

    mocks.authStore.userRoles = ['admin']
    await flushPromises()
    expect(wrapper.getComponent(QcRunSelectedControl).props('selectedCount')).toBe(0)

    await wrapper.get('input[aria-label="选择患者甲"]').setValue(true)
    mocks.authStore.user = { id: 'other-user', email: 'other@example.com' }
    await flushPromises()
    expect(wrapper.getComponent(QcRunSelectedControl).props('selectedCount')).toBe(0)
  })

  it('双列表恢复各自列查询，切账号后忽略迟到的旧列查询响应', async () => {
    const wrapper = mountView('inpatient')
    await flushPromises()
    await wrapper.get('[data-testid="column-filter-score"]').setValue('0')
    await wrapper.get('.column-query form').trigger('submit')
    await flushPromises()
    expect(mocks.getRaw.mock.lastCall?.[1]).toHaveProperty('column_filters', '{"score":"0"}')
    await wrapper.get('[data-testid="qc-result-view-defects"]').trigger('click')
    await flushPromises()
    expect(mocks.getRaw.mock.lastCall?.[1]).not.toHaveProperty('column_filters')
    await wrapper.get('[data-testid="column-filter-rule"]').setValue('合成规则')
    await wrapper.get('.column-query form').trigger('submit')
    await flushPromises()
    expect(mocks.getRaw.mock.lastCall?.[1]).toHaveProperty('column_filters', '{"rule":"合成规则"}')
    await wrapper.get('[data-testid="qc-result-view-records"]').trigger('click')
    await flushPromises()
    expect(mocks.getRaw.mock.lastCall?.[1]).toHaveProperty('column_filters', '{"score":"0"}')
    let resolveOld!: (value: ReturnType<typeof response>) => void
    mocks.getRaw.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveOld = resolve
        }),
    )
    await wrapper.get('[data-testid="column-filter-score"]').setValue('99')
    await wrapper.get('.column-query form').trigger('submit')
    if (!mocks.authStore) throw new Error('auth store missing')
    mocks.authStore.user = { id: 'new-user', email: 'new@example.com' }
    await flushPromises()
    expect(mocks.getRaw.mock.lastCall?.[1]).not.toHaveProperty('column_filters')
    const old = response()
    old.data.records[0]!.patient_name = '旧账号迟到病例'
    resolveOld(old)
    await flushPromises()
    expect(wrapper.text()).not.toContain('旧账号迟到病例')
  })

  it('在同一页面切换结果分析，并将下钻病历交给既有结果抽屉', async () => {
    const wrapper = mountView('discharged')
    await flushPromises()

    await wrapper.get('[data-testid="qc-result-view-analysis"]').trigger('click')
    expect(wrapper.find('[data-testid="result-analysis-stub"]').exists()).toBe(true)

    await wrapper.get('[data-testid="result-analysis-stub"]').trigger('click')
    const drawer = wrapper.getComponent(ResultDrawerStub)
    expect(drawer.props('open')).toBe(true)
    expect(drawer.props('focus')).toMatchObject({
      instituteId: 'H-analysis',
      patientId: 'P-analysis',
      visitId: 'V-analysis',
      recordId: 'V-analysis',
    })
  })

  it('ready 行按服务端 review_state 显示审核标签，null 为未知，非 ready 不显示', async () => {
    const payload = response()
    const summaries = payload.data.records.map((record) => record.latest_qc_summary) as Array<
      Record<string, unknown> | undefined
    >
    summaries[0]!.review_state = 'pending_recheck'
    summaries[1]!.review_state = 'approved'
    summaries[2]!.review_state = null
    summaries[3]!.review_state = 'approved'
    summaries[4]!.review_state = 'doubtful'
    mocks.getRaw.mockResolvedValue(payload)

    const wrapper = mountView('inpatient')
    await flushPromises()

    const tagOf = (visitId: string) =>
      wrapper
        .get(`tbody tr[data-record-key='["H","P","${visitId}"]']`)
        .find('[data-testid="qc-record-review-state"]')
    expect(tagOf('V-priority').text()).toBe('待复审')
    expect(tagOf('V-data-gap').text()).toBe('审核通过')
    expect(tagOf('V-uncertain').text()).toBe('审核状态未知')
    expect(tagOf('V-not-run').exists()).toBe(false)
    expect(tagOf('V-technical').exists()).toBe(false)
  })

  it('ready 行显示服务端得分 / 等级与单项否决，unavailable 显示暂不可用，非 ready 不显示', async () => {
    const payload = response() as ReturnType<typeof response> & { data: Record<string, unknown> }
    const summaries = payload.data.records.map((record) => record.latest_qc_summary) as Array<
      Record<string, unknown> | undefined
    >
    summaries[0]!.review_state = 'pending_review'
    summaries[0]!.score_state = {
      status: 'scored',
      score: 86.5,
      grade: '乙',
      veto_hit: false,
      standard_id: 's1',
      reason_code: null,
    }
    summaries[1]!.score_state = {
      status: 'scored',
      score: 95,
      grade: '丙',
      veto_hit: true,
      standard_id: 's1',
      reason_code: null,
    }
    summaries[2]!.score_state = {
      status: 'unavailable',
      score: null,
      grade: null,
      veto_hit: null,
      standard_id: 's1',
      reason_code: 'result_changed',
    }
    payload.data.score_standards = {
      running: {
        status: 'configured',
        standard_id: 's1',
        standard_name: '运行标准',
        standard_updated_at: null,
      },
    }
    mocks.getRaw.mockResolvedValue(payload)

    const wrapper = mountView('inpatient')
    await flushPromises()

    expect(wrapper.findAll('thead th').map((item) => item.text())).toContain('得分 / 等级')
    const cellOf = (visitId: string) =>
      wrapper
        .get(`tbody tr[data-record-key='["H","P","${visitId}"]']`)
        .get('[data-testid="qc-record-score"]')
    expect(cellOf('V-priority').text()).toBe('86.5 / 乙')
    expect(cellOf('V-data-gap').text()).toContain('95 / 丙')
    expect(cellOf('V-data-gap').find('[data-testid="qc-record-score-veto"]').text()).toBe(
      '单项否决',
    )
    expect(cellOf('V-uncertain').text()).toBe('得分暂不可用')
    expect(cellOf('V-not-run').text()).toBe('')
    expect(cellOf('V-technical').text()).toBe('')
    // 审核状态标签不受得分列影响。
    expect(
      wrapper
        .get(`tbody tr[data-record-key='["H","P","V-priority"]']`)
        .get('[data-testid="qc-record-review-state"]')
        .text(),
    ).toBe('待审核')
    expect(wrapper.getComponent(ResultDrawerStub).props('scoreScene')).toBe('running')
  })

  it('场景无默认标准时 ready 行整列显示“未配置评分标准”，终末列表抽屉场景为 final', async () => {
    const payload = response() as ReturnType<typeof response> & { data: Record<string, unknown> }
    const summaries = payload.data.records.map((record) => record.latest_qc_summary) as Array<
      Record<string, unknown> | undefined
    >
    for (const summary of summaries) {
      if (summary?.status === 'ready') {
        summary.score_state = {
          status: 'no_standard',
          score: null,
          grade: null,
          veto_hit: null,
          standard_id: null,
          reason_code: null,
        }
      }
    }
    payload.data.score_standards = {
      final: {
        status: 'no_standard',
        standard_id: null,
        standard_name: null,
        standard_updated_at: null,
      },
    }
    mocks.getRaw.mockResolvedValue(payload)

    const wrapper = mountView('discharged')
    await flushPromises()

    const texts = ['V-priority', 'V-data-gap', 'V-uncertain', 'V-not-run'].map((visitId) =>
      wrapper
        .get(`tbody tr[data-record-key='["H","P","${visitId}"]']`)
        .get('[data-testid="qc-record-score"]')
        .text(),
    )
    expect(texts).toEqual(['未配置评分标准', '未配置评分标准', '未配置评分标准', ''])
    expect(wrapper.text()).not.toContain('0 / ')
    expect(wrapper.getComponent(ResultDrawerStub).props('scoreScene')).toBe('final')
  })

  it('结果抽屉开启病例审核，审核提交确认后重新拉取当前页', async () => {
    mocks.getRaw.mockImplementation((_url: string, params: { page: number }) => {
      const payload = response()
      payload.data.total = 30
      payload.data.page = params.page
      return Promise.resolve(payload)
    })
    const wrapper = mountView('discharged')
    await flushPromises()
    wrapper.getComponent(Pagination).vm.$emit('change', 2, 15)
    await flushPromises()

    const drawer = wrapper.getComponent(ResultDrawerStub)
    expect(drawer.props('recordReview')).toBe(true)
    const requestsBefore = mocks.getRaw.mock.calls.length
    drawer.vm.$emit('review-submitted', {
      instituteId: 'H',
      patientId: 'P',
      visitId: 'V-priority',
      decision: 'approved',
    })
    await flushPromises()

    expect(mocks.getRaw.mock.calls.length).toBe(requestsBefore + 1)
    expect(mocks.getRaw).toHaveBeenLastCalledWith(
      '/api/medical-records/workstation',
      expect.objectContaining({ page: 2 }),
    )
    drawer.vm.$emit('qc-completed', { instituteId: 'H', patientId: 'P', visitId: 'V-priority' })
    await flushPromises()
    expect(mocks.getRaw.mock.calls.length).toBe(requestsBefore + 2)
    expect(mocks.getRaw).toHaveBeenLastCalledWith(
      '/api/medical-records/workstation',
      expect.objectContaining({ page: 2 }),
    )
  })

  describe('抽屉上一个/下一个导航', () => {
    /** 调整顺序：未质控与交付异常夹在两份 ready 病历之间。 */
    function navigationPayload() {
      const payload = response()
      const [priority, dataGap, uncertain, notRun, technical, missing] = payload.data.records
      payload.data.records = [priority, dataGap, notRun, technical, uncertain, missing]
      return payload
    }

    async function openFull(wrapper: ReturnType<typeof mountView>, visitId: string) {
      await wrapper
        .getComponent(QcRecordReviewPreview)
        .vm.$emit('open-full', `["H","P","${visitId}"]`)
      await flushPromises()
    }

    it('只在当前页 ready 行内导航，跳过未质控与交付异常，边界禁用', async () => {
      mocks.getRaw.mockResolvedValue(navigationPayload())
      const wrapper = mountView('discharged')
      await flushPromises()

      // 保持服务端顺序：V-priority、V-data-gap、V-not-run、V-technical、V-uncertain。
      await openFull(wrapper, 'V-priority')
      const drawer = wrapper.getComponent(ResultDrawerStub)
      expect(drawer.props()).toMatchObject({
        hasPrev: false,
        hasNext: true,
        currentIndex: 1,
        totalCount: 3,
      })

      drawer.vm.$emit('navigate-next')
      await flushPromises()
      expect(drawer.props('focus')).toMatchObject({ visitId: 'V-data-gap' })
      expect(drawer.props()).toMatchObject({
        hasPrev: true,
        hasNext: true,
        currentIndex: 2,
        totalCount: 3,
      })

      drawer.vm.$emit('navigate-next')
      await flushPromises()
      expect(drawer.props('open')).toBe(true)
      expect(drawer.props('focus')).toMatchObject({ visitId: 'V-uncertain' })
      expect(drawer.props()).toMatchObject({
        hasPrev: true,
        hasNext: false,
        currentIndex: 3,
        totalCount: 3,
      })
      expect(wrapper.findComponent(DocumentWorkbenchStub).exists()).toBe(false)

      drawer.vm.$emit('navigate-next')
      await flushPromises()
      expect(drawer.props('focus')).toMatchObject({ visitId: 'V-uncertain' })

      drawer.vm.$emit('navigate-prev')
      await flushPromises()
      expect(drawer.props('focus')).toMatchObject({ visitId: 'V-data-gap' })
    })

    it('从分析面板下钻或关闭抽屉后不提供导航', async () => {
      const wrapper = mountView('discharged')
      await flushPromises()
      await wrapper.get('[data-testid="qc-result-view-analysis"]').trigger('click')
      await wrapper.get('[data-testid="result-analysis-stub"]').trigger('click')
      const drawer = wrapper.getComponent(ResultDrawerStub)
      expect(drawer.props('open')).toBe(true)
      expect(drawer.props('hasPrev')).toBeUndefined()
      expect(drawer.props('hasNext')).toBeUndefined()
      expect(drawer.props('currentIndex')).toBeUndefined()
    })

    it('focus 透传入院/出院时间，缺失值不伪造', async () => {
      const wrapper = mountView('discharged')
      await flushPromises()
      await openFull(wrapper, 'V-priority')
      const drawer = wrapper.getComponent(ResultDrawerStub)
      expect(drawer.props('focus')).toMatchObject({
        admissionTime: '2026-08-09 08:00',
        dischargeTime: '2026-08-12 10:00',
      })

      drawer.vm.$emit('navigate-next')
      await flushPromises()
      const focus = drawer.props('focus') as Record<string, unknown>
      expect(focus.visitId).toBe('V-data-gap')
      expect(focus).not.toHaveProperty('admissionTime')
      expect(focus).not.toHaveProperty('dischargeTime')
    })
  })

  describe('审核状态筛选、快捷筛选与 URL 同步', () => {
    function workstationParams() {
      return mocks.getRaw.mock.lastCall?.[1] as Record<string, unknown>
    }

    it('审核角色首次进入（URL 无筛选）默认“审核中”，请求带 review_state 并写入 query', async () => {
      mocks.hasRole.mockImplementation((role: string) => role === 'qc_manager')
      routeState.query = { tab: 'records' }
      mountView('inpatient')
      await flushPromises()

      expect(mocks.listFilterTemplates).toHaveBeenCalledWith('v5_records_inpatient')
      expect(mocks.getRaw).toHaveBeenCalledTimes(1)
      expect(workstationParams()).toEqual({
        page: 1,
        page_size: 15,
        date_field: 'admission',
        hospital_status: 'inpatient',
        review_state: 'pending_review,pending_recheck',
      })
      expect(mocks.routerReplace).toHaveBeenCalledWith({
        query: { tab: 'records', review_state: 'pending_review,pending_recheck' },
      })
    })

    it('导出当前筛选带上列表审核状态筛选，导出所选不带', async () => {
      mocks.hasRole.mockImplementation((role: string) => role === 'qc_manager')
      routeState.query = { review_state: 'pending_review,pending_recheck' }
      const wrapper = mountView('discharged')
      await flushPromises()

      await wrapper.get('[data-testid="qc-result-export-trigger"]').trigger('click')
      await wrapper.get('[data-testid="qc-result-export-filtered"]').trigger('click')
      await flushPromises()
      expect(mocks.exportFilteredLuxian0609RecordResults).toHaveBeenLastCalledWith({
        scope: 'final',
        date_field: 'discharge',
        review_state: ['pending_review', 'pending_recheck'],
      })

      await wrapper.get('input[aria-label="选择患者甲"]').setValue(true)
      await wrapper.get('[data-testid="qc-result-export-trigger"]').trigger('click')
      await wrapper.get('[data-testid="qc-result-export-selected"]').trigger('click')
      await flushPromises()
      const selectedPayload = mocks.exportFilteredLuxian0609RecordResults.mock.lastCall?.[0]
      expect(selectedPayload).toHaveProperty('record_refs')
      expect(selectedPayload).not.toHaveProperty('review_state')
    })

    it('默认模板优先于系统默认', async () => {
      mocks.hasRole.mockImplementation((role: string) => role === 'admin')
      mocks.listFilterTemplates.mockResolvedValue({
        success: true,
        data: [
          {
            id: 'tpl-default',
            page_key: 'v5_records_discharged',
            name: '本科室待复审',
            filters: { dept: '重症医学科', review_state: ['pending_recheck'] },
            is_default: true,
            version: 1,
            created_at: '',
            updated_at: '',
          },
        ],
      })
      mountView('discharged')
      await flushPromises()

      expect(mocks.listFilterTemplates).toHaveBeenCalledWith('v5_records_discharged')
      expect(mocks.getRaw).toHaveBeenCalledTimes(1)
      expect(workstationParams()).toMatchObject({
        dept: '重症医学科',
        review_state: 'pending_recheck',
      })
      expect(mocks.routerReplace).toHaveBeenCalledWith({
        query: { department: '重症医学科', review_state: 'pending_recheck' },
      })
    })

    it('URL 已有筛选参数时以 URL 为准，不套用默认、不改写 query', async () => {
      mocks.hasRole.mockImplementation((role: string) => role === 'qc_manager')
      routeState.query = { review_state: 'approved,bogus', keyword: '患者甲' }
      const wrapper = mountView('inpatient')
      await flushPromises()

      expect(mocks.getRaw).toHaveBeenCalledTimes(1)
      expect(workstationParams()).toMatchObject({ keyword: '患者甲', review_state: 'approved' })
      expect(mocks.routerReplace).not.toHaveBeenCalled()
      expect(
        (wrapper.get('input[aria-label="关键词筛选"]').element as HTMLInputElement).value,
      ).toBe('患者甲')
    })

    it('快捷筛选写入 query 并据此请求第一页，保留其他筛选', async () => {
      mocks.hasRole.mockImplementation((role: string) => role === 'qc_manager')
      routeState.query = { department: '重症医学科' }
      const wrapper = mountView('inpatient')
      await flushPromises()

      await wrapper.get('[data-testid="quick-filter-pending_review"]').trigger('click')
      await flushPromises()
      expect(workstationParams()).toEqual({
        page: 1,
        page_size: 15,
        date_field: 'admission',
        dept: '重症医学科',
        hospital_status: 'inpatient',
        review_state: 'pending_review',
      })
      expect(mocks.routerReplace).toHaveBeenLastCalledWith({
        query: { department: '重症医学科', review_state: 'pending_review' },
      })

      await wrapper.get('[data-testid="quick-filter-all"]').trigger('click')
      await flushPromises()
      expect(workstationParams()).not.toHaveProperty('review_state')
      expect(mocks.routerReplace).toHaveBeenLastCalledWith({
        query: { department: '重症医学科', review_scope: 'all' },
      })
    })

    it('审核角色显式选“全部”写入前端标记 review_scope=all，请求参数不含该键', async () => {
      mocks.hasRole.mockImplementation((role: string) => role === 'qc_manager')
      // 模拟路由：replace 后 query 即为新值。
      mocks.routerReplace.mockImplementation(
        async (location: { query: Record<string, string> }) => {
          routeState.query = location.query
        },
      )
      const wrapper = mountView('inpatient')
      await flushPromises()
      expect(workstationParams()).toMatchObject({ review_state: 'pending_review,pending_recheck' })

      await wrapper.get('[data-testid="quick-filter-all"]').trigger('click')
      await flushPromises()
      expect(mocks.routerReplace).toHaveBeenLastCalledWith({ query: { review_scope: 'all' } })
      expect(workstationParams()).not.toHaveProperty('review_state')
      expect(workstationParams()).not.toHaveProperty('review_scope')

      // 标记存在时手动筛选沿用标记。
      await wrapper.get('select[aria-label="科室筛选"]').setValue('重症医学科')
      await flushPromises()
      expect(mocks.routerReplace).toHaveBeenLastCalledWith({
        query: { department: '重症医学科', review_scope: 'all' },
      })
    })

    it('刷新时 review_scope=all 视为显式范围，保持“全部”，不套系统默认', async () => {
      mocks.hasRole.mockImplementation((role: string) => role === 'qc_manager')
      routeState.query = { review_scope: 'all' }
      window.history.replaceState({}, '', '/workstation-v5/records?review_scope=all')
      const wrapper = mountView('inpatient')
      await flushPromises()
      window.history.replaceState({}, '', '/')

      expect(mocks.getRaw).toHaveBeenCalledTimes(1)
      expect(workstationParams()).toEqual({
        page: 1,
        page_size: 15,
        date_field: 'admission',
        hospital_status: 'inpatient',
      })
      expect(mocks.routerReplace).not.toHaveBeenCalled()
      expect(wrapper.get('[data-testid="quick-filter-all"]').attributes('aria-pressed')).toBe(
        'true',
      )
    })

    it('选其他快捷筛选或重置时移除 review_scope 标记', async () => {
      mocks.hasRole.mockImplementation((role: string) => role === 'qc_manager')
      routeState.query = { review_scope: 'all' }
      const wrapper = mountView('inpatient')
      await flushPromises()

      await wrapper.get('[data-testid="quick-filter-pending_recheck"]').trigger('click')
      await flushPromises()
      expect(mocks.routerReplace).toHaveBeenLastCalledWith({
        query: { review_state: 'pending_recheck' },
      })

      routeState.query = { review_scope: 'all' }
      await wrapper.get('[data-testid="filter-template-reset"]').trigger('click')
      await flushPromises()
      expect(mocks.routerReplace).toHaveBeenLastCalledWith({
        query: { review_state: 'pending_review,pending_recheck' },
      })
      expect(workstationParams()).toMatchObject({ review_state: 'pending_review,pending_recheck' })
    })

    it('手动筛选同样写入 query', async () => {
      const wrapper = mountView('discharged')
      await flushPromises()
      await wrapper.get('select[aria-label="科室筛选"]').setValue('重症医学科')
      await flushPromises()
      expect(mocks.routerReplace).toHaveBeenLastCalledWith({ query: { department: '重症医学科' } })
    })

    it('非审核角色看不到审核快捷筛选，默认“全部”', async () => {
      const wrapper = mountView('inpatient')
      await flushPromises()
      expect(wrapper.find('[data-testid="quick-filter-pending_review"]').exists()).toBe(false)
      expect(wrapper.find('[data-testid="quick-filter-all"]').exists()).toBe(true)
      expect(workstationParams()).not.toHaveProperty('review_state')
    })

    it('模板加载失败不阻塞列表，仅提示模板不可用', async () => {
      mocks.hasRole.mockImplementation((role: string) => role === 'qc_manager')
      mocks.listFilterTemplates.mockResolvedValue({ success: false, status: 503 })
      const wrapper = mountView('inpatient')
      await flushPromises()
      expect(wrapper.text()).toContain('筛选模板暂不可用')
      expect(mocks.getRaw).toHaveBeenCalledTimes(1)
      expect(workstationParams()).toMatchObject({ review_state: 'pending_review,pending_recheck' })
      expect(wrapper.findAll('tbody tr[data-record-key]')).toHaveLength(5)
    })

    it('空结果区分“筛选无结果”与加载失败', async () => {
      mocks.hasRole.mockImplementation((role: string) => role === 'qc_manager')
      const empty = response()
      empty.data.records = []
      empty.data.total = 0
      mocks.getRaw.mockResolvedValue(empty)
      const filtered = mountView('inpatient')
      await flushPromises()
      expect(filtered.text()).toContain('当前筛选条件下暂无病历，可调整筛选或重置')

      mocks.getRaw.mockRejectedValue(new Error('503'))
      const failed = mountView('inpatient')
      await flushPromises()
      expect(failed.text()).toContain('加载失败，请重试')
      expect(failed.text()).not.toContain('当前筛选条件下暂无病历')
    })
  })
})
