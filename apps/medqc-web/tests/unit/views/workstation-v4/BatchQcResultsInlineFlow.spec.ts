import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

import { ApiService } from '@/services/apiService'
import * as sichuanService from '@/services/sichuan-rule-workspace-service'
import RecordPoolQcTaskStatusBar from '@/views/workstation-v4/components/workbench/RecordPoolQcTaskStatusBar.vue'
import BatchQcResultsPanel from '@/views/workstation-v4/components/workbench/BatchQcResultsPanel.vue'
import QCRecordResultComparisonDrawer from '@/views/workstation-v4/customer-sample-validation/QCRecordResultComparisonDrawer.vue'
import {
  resolveBatchResultRecords,
  sortBatchResultRecords,
  type BatchResultRecordItem,
} from '@/views/workstation-v4/utils/batchResultViewer'
import type { SichuanBatchJob } from '@/views/workstation-v4/semantic-rules/types'
import type { PatientRecord } from '@/views/workstation-v4/types'

vi.mock('@/composables/useQcResultVisibility', () => ({
  useQcResultVisibility: () => ({
    confirmedResultsOnly: ref(true),
  }),
}))

function makeJob(overrides: Partial<SichuanBatchJob> = {}): SichuanBatchJob {
  return {
    id: 'job-inline-1',
    rule_code: 'luxian_0609_qc_v1',
    rule_name: '泸县0609质控点验证 v1',
    scope: 'all',
    status: 'completed',
    total_records: 2,
    success_count: 2,
    failed_count: 0,
    ...overrides,
  }
}

function makeRecord(overrides: Partial<PatientRecord> = {}): PatientRecord {
  const visitId = overrides.visitId || 'V1001'
  return {
    id: visitId,
    recordKey: overrides.recordKey || `H1::P1::${visitId}`,
    instituteId: overrides.instituteId || 'H1',
    patientId: overrides.patientId || 'P1',
    visitId,
    bedNo: '01',
    name: overrides.name || '张三',
    sex: overrides.sex || '男',
    age: overrides.age ?? 45,
    insurance: '医保',
    department: overrides.department || '呼吸内科',
    admissionDate: '2026-10-01',
    dischargeDate: '',
    hospitalizationStatus: 'inpatient',
    days: 5,
    diagnosis: '肺炎',
    diagnosisCode: 'J18',
    doctor: '李医生',
    status: 'completed',
    ...overrides,
  }
}

function makeBatchItem(overrides: Partial<BatchResultRecordItem> = {}): BatchResultRecordItem {
  return {
    recordKey: 'H1::P1::V1001',
    instituteId: 'H1',
    patientId: 'P1',
    visitId: 'V1001',
    recordId: 'V1001',
    patientName: '张三',
    patientSex: '男',
    patientAge: 45,
    department: '呼吸内科',
    hospitalizationStatus: 'inpatient',
    confirmedIssueCount: 3,
    resultStatus: 'priority',
    resultLabel: '需优先复核',
    issueSummary: '有 3 项确定问题',
    latestQcTime: '2026-11-25 10:00',
    ...overrides,
  }
}

describe('Batch QC inline result viewing flow', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('RecordPoolQcTaskStatusBar emits view-results in inlineResultViewer mode without RouterLink', async () => {
    const job = makeJob({ id: 'job-inline-emit', total_records: 1, success_count: 1 })
    const wrapper = mount(RecordPoolQcTaskStatusBar, {
      props: {
        job,
        autoPoll: false,
        inlineResultViewer: true,
      },
    })

    const trigger = wrapper.get('[data-testid="qc-task-detail-link"]')
    expect(trigger.element.tagName).toBe('BUTTON')
    expect(trigger.text()).toContain('查看本次质控结果')

    await trigger.trigger('click')
    const emitted = wrapper.emitted('view-results')
    expect(emitted).toHaveLength(1)
    expect(emitted?.[0]?.[0]).toMatchObject({ id: 'job-inline-emit' })
    wrapper.unmount()
  })

  it('sortBatchResultRecords places records with more confirmed issues first', () => {
    const sorted = sortBatchResultRecords([
      makeBatchItem({ recordKey: 'k-ok', confirmedIssueCount: 0, resultStatus: 'completed' }),
      makeBatchItem({ recordKey: 'k-two', confirmedIssueCount: 2, resultStatus: 'priority' }),
      makeBatchItem({ recordKey: 'k-five', confirmedIssueCount: 5, resultStatus: 'priority' }),
    ])
    expect(sorted.map((item) => item.recordKey)).toEqual(['k-five', 'k-two', 'k-ok'])
  })

  it('resolveBatchResultRecords hydrates fresh qc-summary and falls back to analytics_job_id when submittedRecords is empty', async () => {
    vi.spyOn(ApiService, 'getRaw').mockResolvedValue({
      data: {
        records: [
          {
            id: 'V2001',
            record_key: 'H1::P2::V2001',
            institute_id: 'H1',
            patient_id: 'P2',
            visit_id: 'V2001',
            patient_name: '王五',
            department: '心内科',
            admission_date: '2026-10-02',
            hospitalization_status: 'inpatient',
          },
          {
            id: 'V2002',
            record_key: 'H1::P3::V2002',
            institute_id: 'H1',
            patient_id: 'P3',
            visit_id: 'V2002',
            patient_name: '赵六',
            department: '骨科',
            admission_date: '2026-10-03',
            hospitalization_status: 'discharged',
            discharge_date: '2026-10-08',
          },
        ],
      },
    } as never)

    vi.spyOn(ApiService, 'postRaw').mockResolvedValue({
      data: {
        records: [
          {
            record_key: 'H1::P2::V2001',
            latest_qc_summary: {
              status: 'ready',
              completed_at: '2026-11-25T10:10:00+08:00',
              status_counts: { non_compliant: 0, compliant: 76 },
            },
          },
          {
            record_key: 'H1::P3::V2002',
            latest_qc_summary: {
              status: 'ready',
              completed_at: '2026-11-25T10:11:00+08:00',
              status_counts: { non_compliant: 4, compliant: 72 },
            },
          },
        ],
      },
    } as never)

    const resolved = await resolveBatchResultRecords({
      job: makeJob({ id: 'job-filter-2', total_records: 2 }),
      sourceId: 'legacy_pg',
      submittedRecords: [],
      currentRecords: [makeRecord({ visitId: 'V9999', recordKey: 'H1::P9::V9999' })],
      confirmedOnly: true,
    })

    expect(resolved.totalCount).toBe(2)
    expect(resolved.issueRecordCount).toBe(1)
    expect(resolved.compliantRecordCount).toBe(1)
    expect(resolved.items.map((item) => item.visitId)).toEqual(['V2002', 'V2001'])
    expect(resolved.items[0].confirmedIssueCount).toBe(4)
  })

  it('BatchQcResultsPanel supports only-issues filtering, opening comparison, and exiting', async () => {
    const items = [
      makeBatchItem({
        recordKey: 'H1::P1::V1',
        visitId: 'V1',
        patientName: '陈一',
        confirmedIssueCount: 4,
        resultStatus: 'priority',
        resultLabel: '需优先复核',
        issueSummary: '有 4 项确定问题',
      }),
      makeBatchItem({
        recordKey: 'H1::P2::V2',
        visitId: 'V2',
        patientName: '林二',
        confirmedIssueCount: 0,
        resultStatus: 'completed',
        resultLabel: '已完成',
        issueSummary: '未发现确定问题',
      }),
    ]

    const wrapper = mount(BatchQcResultsPanel, {
      props: { items },
    })

    expect(wrapper.findAll('[data-testid="batch-qc-result-row"]')).toHaveLength(2)
    expect(wrapper.text()).toContain('共 2 份')
    expect(wrapper.text()).toContain('有问题 1 份')
    expect(wrapper.text()).toContain('未见确定问题 1 份')

    await wrapper.get('[data-testid="batch-qc-results-only-issues"]').trigger('click')
    expect(wrapper.findAll('[data-testid="batch-qc-result-row"]')).toHaveLength(1)
    expect(wrapper.text()).toContain('陈一')
    expect(wrapper.text()).not.toContain('林二')

    await wrapper.get('[data-testid="batch-qc-result-open-btn"]').trigger('click')
    const opened = wrapper.emitted('open-record')
    expect(opened).toHaveLength(1)
    expect(opened?.[0]?.[0]).toMatchObject({
      index: 0,
      item: { visitId: 'V1' },
    })
    expect((opened?.[0]?.[0] as { queue: BatchResultRecordItem[] }).queue).toHaveLength(1)

    await wrapper.get('[data-testid="batch-qc-results-exit"]').trigger('click')
    expect(wrapper.emitted('exit')).toHaveLength(1)
    wrapper.unmount()
  })

  it('QCRecordResultComparisonDrawer renders batch navigator for >= 2 records and emits select-batch-index', async () => {
    vi.spyOn(sichuanService, 'getLatestLuxian0609RecordResult').mockResolvedValue({
      success: true,
      data: {
        state: 'ready',
        job_id: 'job-1',
        record_ref: 'rec_abc',
        items: [],
      },
    } as never)

    const wrapper = mount(QCRecordResultComparisonDrawer, {
      props: {
        open: true,
        loadJobMetadata: false,
        focus: {
          visitId: 'V1',
          instituteId: 'H1',
          patientId: 'P1',
          recordId: 'V1',
          patientName: '陈一',
          label: '陈一 · 呼吸内科 · 住院号 V1',
        },
        batchRecords: [
          { recordKey: 'k1', patientName: '陈一', visitId: 'V1', confirmedIssueCount: 4 },
          { recordKey: 'k2', patientName: '林二', visitId: 'V2', confirmedIssueCount: 2 },
          { recordKey: 'k3', patientName: '周三', visitId: 'V3', confirmedIssueCount: 0 },
        ],
        activeBatchIndex: 0,
      },
      global: {
        stubs: {
          ADrawer: {
            props: ['open'],
            template: '<div v-if="open"><slot name="title" /><slot /></div>',
          },
          AResult: true,
          QCRecordCompareWorkbench: true,
          QcDiagnosticExport: true,
          HospitalLoading: true,
          MedicalRecordContextBanner: true,
          RecordViewCloseIcon: true,
        },
      },
    })
    await flushPromises()

    expect(wrapper.find('[data-testid="comparison-batch-nav"]').exists()).toBe(true)
    const prevBtn = wrapper.get('[data-testid="comparison-batch-prev"]')
    const nextBtn = wrapper.get('[data-testid="comparison-batch-next"]')
    const selectEl = wrapper.get('[data-testid="comparison-batch-select"]')

    expect((prevBtn.element as HTMLButtonElement).disabled).toBe(true)
    expect((nextBtn.element as HTMLButtonElement).disabled).toBe(false)

    await nextBtn.trigger('click')
    expect(wrapper.emitted('select-batch-index')?.[0]).toEqual([1])

    await selectEl.setValue('2')
    expect(wrapper.emitted('select-batch-index')?.[1]).toEqual([2])

    await wrapper.setProps({ batchRecords: [{ recordKey: 'k1', patientName: '陈一', visitId: 'V1' }], activeBatchIndex: 0 })
    expect(wrapper.find('[data-testid="comparison-batch-nav"]').exists()).toBe(false)

    wrapper.unmount()
  })
})
