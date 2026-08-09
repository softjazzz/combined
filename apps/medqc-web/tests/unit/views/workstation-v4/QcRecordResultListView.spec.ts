import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  getRaw: vi.fn(),
}))

vi.mock('@/services/apiService', () => ({
  ApiService: {
    getRaw: mocks.getRaw,
  },
}))

import QcRecordResultListView from '@/views/workstation-v4/QcRecordResultListView.vue'

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

async function flushPromises() {
  await Promise.resolve()
  await Promise.resolve()
}

describe('QcRecordResultListView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getRaw.mockResolvedValue(response())
  })

  it.each([
    ['inpatient', '运行病历质控', '固定范围：在院', 'admission'],
    ['discharged', '终末病历质控', '固定范围：已出院', 'discharge'],
  ] as const)('固定 %s 服务端范围并使用对应时间字段', async (carePhase, title, scope, dateField) => {
    const wrapper = mount(QcRecordResultListView, { props: { carePhase } })
    await flushPromises()

    expect(wrapper.text()).toContain(title)
    expect(wrapper.text()).toContain(scope)
    expect(mocks.getRaw).toHaveBeenCalledWith('/api/medical-records/workstation', {
      params: {
        page: 1,
        page_size: 15,
        date_field: dateField,
        hospital_status: carePhase,
      },
    })
  })

  it('使用服务端全量汇总，并只展示三坐标和 recordKey 完整的病历行', async () => {
    const wrapper = mount(QcRecordResultListView, { props: { carePhase: 'inpatient' } })
    await flushPromises()

    expect(
      wrapper.findAll('.qc-record-result-list-view__metric strong').map((item) => item.text()),
    ).toEqual(['20', '14', '4', '5'])
    expect(wrapper.findAll('tbody tr[data-record-key]')).toHaveLength(5)
    expect(wrapper.text()).not.toContain('不得展示')
    expect(wrapper.text()).toContain('来源未知')
    expect(wrapper.text()).not.toContain('资料完整')
  })

  it('按 Canonical 摘要严格区分临床问题、资料待核实、待判断、未质控和交付异常', async () => {
    const wrapper = mount(QcRecordResultListView, { props: { carePhase: 'inpatient' } })
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

  it('关键词、科室和日期过滤重置为第一页并只使用服务端请求', async () => {
    const wrapper = mount(QcRecordResultListView, { props: { carePhase: 'discharged' } })
    await flushPromises()
    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('患者甲')
    await inputs[1].setValue('2026-08-01')
    await inputs[2].setValue('2026-08-10')
    await wrapper.find('select').setValue('重症医学科')
    await flushPromises()

    expect(mocks.getRaw).toHaveBeenLastCalledWith('/api/medical-records/workstation', {
      params: {
        page: 1,
        page_size: 15,
        date_field: 'discharge',
        dept: '重症医学科',
        keyword: '患者甲',
        start_date: '2026-08-01',
        end_date: '2026-08-10',
        hospital_status: 'discharged',
      },
    })
  })

  it('不展示任务、批量、生成、编码、结算或整改入口，详情仍留待下一闭环', async () => {
    const wrapper = mount(QcRecordResultListView, { props: { carePhase: 'discharged' } })
    await flushPromises()
    const text = wrapper.text()

    ;['开始质控', '重新质控', '批量', '生成首页', '编码质控', '结算质控', '整改'].forEach(
      (forbidden) => {
        expect(text).not.toContain(forbidden)
      },
    )
    await wrapper.findComponent({ name: 'QcRecordResultTable' }).vm.$emit('open-result', '["H","P","V"]')
    expect(wrapper.text()).toContain('质控结果详情将在下一闭环接入')
  })
})
