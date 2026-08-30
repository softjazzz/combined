import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  downloadBlob: vi.fn(),
  exportFilteredLuxian0609RecordResults: vi.fn(),
  getRaw: vi.fn(),
}))
const routeState = vi.hoisted(() => ({
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
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    user: { id: 'qc-result-list-test', email: 'qc-result-list-test@example.com' },
  }),
}))

import QcRecordResultListView from '@/views/workstation-v4/QcRecordResultListView.vue'
import QcRunSelectedControl from '@/views/workstation-v4/components/qc/QcRunSelectedControl.vue'

const ResultDrawerStub = defineComponent({
  name: 'QCRecordResultComparisonDrawer',
  props: {
    open: { type: Boolean, default: false },
    focus: { type: Object, default: null },
    presentationMode: { type: String, default: 'flat' },
  },
  emits: ['close'],
  setup(props) {
    return () => h('div', { 'data-testid': 'result-drawer-stub', 'data-open': String(props.open) })
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
  return mount(QcRecordResultListView, {
    props: { carePhase },
    global: {
      stubs: {
        QCRecordResultComparisonDrawer: ResultDrawerStub,
        QcRecordResultAnalysisPanel: ResultAnalysisStub,
      },
    },
  })
}

describe('QcRecordResultListView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.sessionStorage.clear()
    routeState.query = {}
    mocks.getRaw.mockResolvedValue(response())
    mocks.exportFilteredLuxian0609RecordResults.mockResolvedValue({
      success: true,
      data: new Blob(['xlsx']),
    })
  })

  it.each([
    ['inpatient', '运行病历质控', '固定范围：在院', 'admission', '在院病历 · 质控结果'],
    ['discharged', '终末病历质控', '固定范围：已出院', 'discharge', '已出院病历 · 质控结果'],
  ] as const)(
    '固定 %s 服务端范围、保留主标题且不展示范围说明',
    async (carePhase, title, scope, dateField, removedEyebrow) => {
      const wrapper = mountView(carePhase)
      await flushPromises()

      expect(wrapper.text()).toContain(title)
      expect(wrapper.text()).toContain(scope)
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

  it('使用服务端全量汇总，并只展示三坐标和 recordKey 完整的病历行', async () => {
    const wrapper = mountView('inpatient')
    await flushPromises()

    expect(
      wrapper.findAll('.qc-metric-card-strip__card strong').map((item) => item.text()),
    ).toEqual(['20', '14', '4', '5'])
    expect(wrapper.findAll('.qc-metric-card-strip__label').map((item) => item.text())).toEqual([
      '纳入病历',
      '已完成质控',
      '需优先复核',
      '资料待核实',
    ])
    expect(wrapper.findAll('tbody tr[data-record-key]')).toHaveLength(5)
    expect(wrapper.get('.qc-record-result-table__avatar').attributes('alt')).toBe('患者乙头像')
    expect(wrapper.text()).not.toContain('不得展示')
    expect(wrapper.text()).not.toContain('来源未知')
    expect(wrapper.text()).not.toContain('资料完整')
  })

  it('按 Canonical 摘要严格区分临床问题、资料待核实、待判断、未质控和交付异常', async () => {
    const wrapper = mountView('inpatient')
    await flushPromises()

    expect(wrapper.text()).toContain('需优先复核')
    expect(wrapper.text()).toContain('确定问题 2 · 待核实 1 · 待判断 3')
    expect(wrapper.text()).toContain('资料待核实')
    expect(wrapper.text()).toContain('待判断')
    expect(wrapper.text()).toContain('未质控')
    expect(wrapper.text()).toContain('暂无结果')
    expect(wrapper.text()).toContain('结果校验异常')
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
      .findAll('tbody tr[data-record-key] td:nth-child(7)')
      .map((item) => item.text())
    expect(renderedTimes.slice(0, 2)).toEqual(['2026-08-17 16:49', '2026-08-17 16:49'])
    expect(wrapper.text()).toContain('2026-08-09 08:00')
  })

  it('关键词、科室和日期过滤重置为第一页并只使用服务端请求', async () => {
    const wrapper = mountView('discharged')
    await flushPromises()
    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('患者甲')
    await inputs[1].setValue('2026-08-01')
    await inputs[2].setValue('2026-08-10')
    await wrapper.find('select').setValue('重症医学科')
    await flushPromises()

    expect(mocks.getRaw).toHaveBeenLastCalledWith('/api/medical-records/workstation', {
      page: 1,
      page_size: 15,
      date_field: 'discharge',
      dept: '重症医学科',
      keyword: '患者甲',
      start_date: '2026-08-01',
      end_date: '2026-08-10',
      hospital_status: 'discharged',
    })
  })

  it('按当前服务端筛选导出完整终末病历Excel，不使用当前页行拼接', async () => {
    const wrapper = mountView('discharged')
    await flushPromises()
    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('患者甲')
    await inputs[1].setValue('2026-08-01')
    await inputs[2].setValue('2026-08-10')
    await wrapper.find('select').setValue('重症医学科')
    await flushPromises()

    await wrapper.get('[data-testid="qc-result-export-trigger"]').trigger('click')
    await wrapper.get('[data-testid="qc-result-export-filtered"]').trigger('click')
    await flushPromises()

    expect(mocks.exportFilteredLuxian0609RecordResults).toHaveBeenCalledWith({
      scope: 'final',
      department: '重症医学科',
      date_field: 'discharge',
      start_date: '2026-08-01',
      end_date: '2026-08-10',
      keyword: '患者甲',
    })
    expect(mocks.downloadBlob).toHaveBeenCalledWith(expect.any(Blob), '终末病历质控-当前筛选.xlsx')
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
    expect(mocks.downloadBlob).toHaveBeenCalledWith(expect.any(Blob), '终末病历质控-所选1份.xlsx')
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
    await rows[0]!.find('button').trigger('click')

    const drawer = wrapper.getComponent(ResultDrawerStub)
    expect(drawer.props('open')).toBe(true)
    expect(drawer.props('presentationMode')).toBe('grouped')
    expect(drawer.props('focus')).toMatchObject({
      instituteId: 'H-2',
      patientId: 'P-2',
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

  it('未质控病历显示暂无结果并留在当前页，不发起抽屉读取', async () => {
    const wrapper = mountView()
    await flushPromises()

    const notRunRow = wrapper
      .findAll('tbody tr[data-record-key]')
      .find((row) => row.attributes('data-record-key').includes('V-not-run'))!
    expect(notRunRow.find('button').text()).toBe('暂无结果')
    await notRunRow.trigger('click')

    expect(wrapper.get('[role="status"]').text()).toContain('这份病历暂无已保存质控结果')
    expect(wrapper.getComponent(ResultDrawerStub).props('open')).toBe(false)
  })

  it('不展示任务、批量、生成、编码、结算或整改入口，已保存结果在当前页打开分组抽屉', async () => {
    const wrapper = mountView('discharged')
    await flushPromises()
    const text = wrapper.text()

    ;['开始质控', '重新质控', '批量', '生成首页', '编码质控', '结算质控', '整改'].forEach(
      (forbidden) => {
        expect(text).not.toContain(forbidden)
      },
    )
    await wrapper
      .findComponent({ name: 'QcRecordResultTable' })
      .vm.$emit('open-result', '["H","P","V-priority"]')
    expect(wrapper.getComponent(ResultDrawerStub).props('open')).toBe(true)
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
})
