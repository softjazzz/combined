import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  getLuxianQcResultAnalysis: vi.fn(),
}))

vi.mock('@/services/luxian-qc-result-analysis-service', () => ({
  getLuxianQcResultAnalysis: mocks.getLuxianQcResultAnalysis,
}))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    user: { is_demo_account: false, roles: ['admin'] },
  }),
}))

import QcRecordResultAnalysisPanel from '@/views/workstation-v4/components/qc/QcRecordResultAnalysisPanel.vue'

function response(ruleId = '') {
  const selected = ruleId ? { rule_id: ruleId, rule_name: '入院记录时限' } : null
  return {
    scope: {
      care_phase: 'inpatient',
      department: null,
      doctor: null,
      rule_id: ruleId || null,
      result_status: null,
      completed_from: null,
      completed_to: null,
    },
    kpis: {
      scoped_record_total: 8,
      ready_record_total: 5,
      unavailable_result_total: 1,
    },
    status_distribution: [
      { status: 'non_compliant', count: 3 },
      { status: 'data_gap', count: 2 },
      { status: 'uncertain', count: 1 },
      { status: 'compliant', count: 12 },
      { status: 'not_applicable', count: 4 },
      { status: 'not_executed', count: 5 },
    ],
    rule_distribution: [
      {
        rule_id: 'LX0609-01-01-01',
        rule_name: '入院记录时限',
        evaluated_count: 5,
        non_compliant_count: 3,
        data_gap_count: 2,
        uncertain_count: 0,
        issue_count: 5,
        department_distribution: [
          {
            department: '重症医学科',
            record_total: 5,
            non_compliant_count: 3,
            data_gap_count: 2,
            uncertain_count: 0,
          },
        ],
      },
    ],
    physician_distribution: [
      {
        physician: '张医生',
        record_total: 5,
        non_compliant_count: 3,
        data_gap_count: 2,
        uncertain_count: 0,
      },
    ],
    selected_rule: selected,
    record_page: {
      page: 1,
      page_size: 20,
      total: selected ? 1 : 0,
      items: selected
        ? [
            {
              record_key: '["H","P","V"]',
              institute_id: 'H',
              patient_id: 'P',
              visit_id: 'V',
              patient_name: '患者甲',
              department: '重症医学科',
              attending_physician: '张医生',
              status: 'non_compliant',
              completed_at: '2026-08-19T08:00:00+00:00',
            },
          ]
        : [],
    },
  }
}

describe('QcRecordResultAnalysisPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getLuxianQcResultAnalysis.mockImplementation((query) =>
      Promise.resolve(response(query.ruleId)),
    )
  })

  it.each(['inpatient', 'discharged'] as const)(
    '按%s范围读取最新 Canonical 分析，且状态导航没有技术异常入口',
    async (carePhase) => {
      const wrapper = mount(QcRecordResultAnalysisPanel, { props: { carePhase } })
      await flushPromises()

      expect(mocks.getLuxianQcResultAnalysis).toHaveBeenCalledWith(
        expect.objectContaining({ carePhase }),
      )
      expect(wrapper.text()).toContain('确定问题')
      expect(wrapper.text()).toContain('资料待核实')
      expect(wrapper.text()).toContain('未执行')
      expect(wrapper.text()).not.toContain('结果校验异常')
      expect(wrapper.findAll('.qc-result-analysis__status-button')).toHaveLength(7)
    },
  )

  it('从质控点选择下钻到病历，并交给既有结果抽屉打开', async () => {
    const wrapper = mount(QcRecordResultAnalysisPanel, { props: { carePhase: 'inpatient' } })
    await flushPromises()

    await wrapper.find('.qc-result-analysis__rule-table tbody tr').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('2026-08-19 16:00')
    expect(mocks.getLuxianQcResultAnalysis).toHaveBeenLastCalledWith(
      expect.objectContaining({ ruleId: 'LX0609-01-01-01' }),
    )
    await wrapper.find('.qc-result-analysis__open').trigger('click')
    expect(wrapper.emitted('open-result')?.[0]).toEqual([
      expect.objectContaining({
        institute_id: 'H',
        patient_id: 'P',
        visit_id: 'V',
        status: 'non_compliant',
      }),
    ])
  })
})
