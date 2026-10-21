import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  requestRaw: vi.fn(),
}))

vi.mock('@/services/apiService', () => ({
  ApiService: {
    requestRaw: mocks.requestRaw,
  },
}))

import {
  getEditableMedicalRecordDocument,
  getEditableMedicalRecordDocuments,
  previewManualSamplePoolHospitalizationScope,
  runManualSamplePool,
  syncManualSamplePoolRecordsByHospitalization,
} from '@/services/manual-case-sample-service'
import { buildMedicalOrderRow } from '@/views/workstation-v4/customer-sample-validation/medicalOrderDisplay'

describe('editable medical-record document normalization', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('keeps planned end separate from actual stop through list and render', async () => {
    mocks.requestRaw.mockResolvedValue({
      data: {
        documents: [
          {
            doc_key: 'inpat_drug_order::safe-order',
            doc_type: 'inpat_drug_order',
            content: '示例医嘱',
            order_planned_end_time: '2026-09-22T14:00:00+00:00',
            order_stop_time: '2026-09-23 10:00:00',
          },
        ],
      },
    })
    const list = await getEditableMedicalRecordDocuments('safe-visit')
    const document = list.data?.documents[0]
    if (!document) throw new Error('缺少测试医嘱')
    expect(buildMedicalOrderRow(document)).toMatchObject({
      plannedEndTime: '2026-09-22 22:00:00',
      stopTime: '2026-09-23 10:00:00',
    })
    mocks.requestRaw.mockResolvedValue({
      data: {
        content: '示例医嘱',
        render_blocks: [
          {
            block_type: 'order_table',
            rows: [{ planned_end_time: '2026-09-24T00:00:00+08:00' }],
          },
        ],
      },
    })
    const detail = await getEditableMedicalRecordDocument('safe-visit', document)
    if (!detail.data) throw new Error('缺少测试医嘱')
    expect(buildMedicalOrderRow(detail.data)).toMatchObject({
      plannedEndTime: '2026-09-24 00:00:00',
      stopTime: '2026-09-23 10:00:00',
    })
  })

  it('does not interpret planned end or cancellation as actual stop', async () => {
    mocks.requestRaw.mockResolvedValue({
      data: {
        documents: [
          {
            doc_type: 'inpat_nondrug_order',
            content: '示例医嘱',
            planned_end_datetime: '2026-09-22 22:00:00',
            cancel_datetime: '2026-09-21 10:00:00',
          },
        ],
      },
    })
    const list = await getEditableMedicalRecordDocuments('safe-visit')
    const document = list.data?.documents[0]
    if (!document) throw new Error('缺少测试医嘱')
    expect(buildMedicalOrderRow(document)).toMatchObject({
      plannedEndTime: '2026-09-22 22:00:00',
      stopTime: '',
    })
  })

  it('keeps structured order details from the documents API through the table row', async () => {
    mocks.requestRaw.mockResolvedValue({
      data: {
        documents: [
          {
            doc_key: 'inpat_drug_order::safe-order',
            doc_type: 'inpat_drug_order',
            content: '示例药品',
            order_specification: '4g/袋',
            order_dosage: '2袋',
            order_frequency: '每日3次',
            order_route: '口服',
            order_quantity: '12袋',
            order_prescribed_doctor: '示例医师',
          },
        ],
      },
    })
    const result = await getEditableMedicalRecordDocuments('safe-visit')
    const document = result.data?.documents[0]
    expect(document).toBeDefined()
    if (!document) throw new Error('缺少测试医嘱')
    expect(buildMedicalOrderRow(document)).toMatchObject({
      specification: '4g/袋',
      dosage: '2袋',
      frequency: '每日3次',
      route: '口服',
      quantity: '12袋',
      prescribedDoctor: '示例医师',
    })
  })

  it('keeps order details from the render API and retains existing details when absent', async () => {
    const summary = {
      key: 'inpat_drug_order::safe-order',
      document_type: 'inpat_drug_order',
      title: '药品医嘱',
      content: '',
      order_quantity: '12袋',
    }
    mocks.requestRaw.mockResolvedValue({
      data: {
        content: '示例药品',
        render_blocks: [
          {
            block_type: 'order_table',
            rows: [
              {
                specification: '4g/袋',
                dosage: '2袋',
                frequency: '每日3次',
                route: '口服',
                prescribed_doctor: '示例医师',
              },
            ],
          },
        ],
      },
    })
    const result = await getEditableMedicalRecordDocument('safe-visit', summary)
    expect(result.data).toBeDefined()
    if (!result.data) throw new Error('缺少测试医嘱')
    expect(buildMedicalOrderRow(result.data)).toMatchObject({
      specification: '4g/袋',
      dosage: '2袋',
      frequency: '每日3次',
      route: '口服',
      quantity: '12袋',
      prescribedDoctor: '示例医师',
    })
  })

  it('preserves current admission source and explicitly requests current view', async () => {
    const currentRecord = {
      admission_time: '2026-02-02T10:00:00+08:00',
      admission_time_source: 'inpat_registration',
      admission_time_state: 'exact',
    }
    mocks.requestRaw.mockResolvedValue({
      data: { data: { documents: [], current_record: currentRecord } },
    })
    const result = await getEditableMedicalRecordDocuments('visit-1', { source_view: 'current' })
    expect(result.data?.current_record).toEqual(currentRecord)
    expect(mocks.requestRaw).toHaveBeenCalledWith(
      expect.objectContaining({
        params: expect.objectContaining({ source_view: 'current' }),
      }),
    )
  })

  it('keeps summary documents without returning full content', async () => {
    mocks.requestRaw.mockResolvedValue({
      data: {
        documents: [
          {
            doc_key: 'daily_course_record::course-1',
            doc_id: 'course-1',
            doc_type: 'daily_course_record',
            doc_name: '日常病程记录',
            execution_domain: 'course',
            record_time: '2026-08-01 09:00:00',
            has_content: true,
            length: 128,
          },
        ],
      },
    })

    const result = await getEditableMedicalRecordDocuments('visit-1', { view: 'summary' })

    expect(mocks.requestRaw).toHaveBeenCalledWith(
      expect.objectContaining({
        url: '/api/v1/emr/visit-1/documents',
        params: expect.objectContaining({ view: 'summary' }),
      }),
    )
    expect(result.data?.documents).toEqual([
      expect.objectContaining({
        key: 'daily_course_record::course-1',
        source_document_id: 'course-1',
        execution_domain: 'course',
        content: '',
        content_loaded: false,
        has_content: true,
      }),
    ])
  })

  it('loads one selected document through the render endpoint', async () => {
    mocks.requestRaw.mockResolvedValue({
      data: {
        content: '患者今日病情稳定。',
        metadata: {
          doc_key: 'daily_course_record::course-1',
          doc_id: 'course-1',
          document_id: 'course-1',
          doc_type: 'daily_course_record',
          doc_name: '日常病程记录',
          record_time: '2026-08-01 09:00:00',
        },
        render_blocks: [
          {
            block_id: 'daily_course_record::course-1:paragraph:0',
            block_type: 'paragraph',
            title: '病程内容',
            text: '患者今日病情稳定。',
          },
        ],
      },
    })

    const summary = {
      key: 'daily_course_record::course-1',
      source_document_id: 'course-1',
      source_table: 'daily_course_record',
      document_type: 'daily_course_record',
      execution_domain: 'course',
      title: '日常病程记录',
      record_time: '2026-08-01 09:00:00',
      content: '',
      has_content: true,
      content_loaded: false,
    }
    const result = await getEditableMedicalRecordDocument('visit-1', summary, {
      institute_id: 'H1',
      patient_id: 'P1',
      visit_id: 'visit-1',
    })

    expect(mocks.requestRaw).toHaveBeenCalledWith(
      expect.objectContaining({
        url: '/api/v1/emr/visit-1/render',
        params: expect.objectContaining({
          execution_domain: 'course',
          doc_type: 'daily_course_record',
          doc_id: 'course-1',
        }),
      }),
    )
    expect(result.data).toMatchObject({
      key: 'daily_course_record::course-1',
      content: '患者今日病情稳定。',
      content_loaded: true,
      sections: [
        {
          key: 'daily_course_record::course-1:paragraph:0',
          label: '病程内容',
          text: '患者今日病情稳定。',
        },
      ],
    })
  })

  it('uses an order display time when the bundle has no generic record_time', async () => {
    mocks.requestRaw.mockResolvedValue({
      data: {
        documents: [
          {
            doc_key: 'inpat_drug_order::order-1',
            document_type: 'inpat_drug_order',
            document_title: '长期医嘱',
            sort_time: '2025-10-07 08:53:16',
            content: '药品医嘱正文。',
          },
        ],
      },
    })

    const result = await getEditableMedicalRecordDocuments('visit-1')

    expect(result.success).toBe(true)
    expect(result.data?.documents[0]).toMatchObject({
      record_time: '2025-10-07 08:53:16',
      order_start_time: '2025-10-07 08:53:16',
    })
  })

  it('does not use a generic display fallback as non-order document record_time', async () => {
    mocks.requestRaw.mockResolvedValue({
      data: {
        documents: [
          {
            doc_key: 'daily_course_record::course-1',
            document_type: 'daily_course_record',
            document_title: '日常病程记录',
            sort_time: '2025-10-07 08:53:16',
            content: '病程正文。',
          },
        ],
      },
    })

    const result = await getEditableMedicalRecordDocuments('visit-1')

    expect(result.success).toBe(true)
    expect(result.data?.documents[0]?.record_time).toBe('')
  })

  it('uses submit time as display time when non-order document record_time is empty', async () => {
    mocks.requestRaw.mockResolvedValue({
      data: {
        documents: [
          {
            doc_key: 'senior_course_record::round-1',
            document_type: 'senior_course_record',
            document_title: '主任医师查房记录',
            record_time: '',
            submit_datetime: '2026-06-21 17:05:00',
            content: '今日随主任医师查房，患者病情变化记录。',
          },
        ],
      },
    })

    const result = await getEditableMedicalRecordDocuments('visit-1')

    expect(result.success).toBe(true)
    expect(result.data?.documents[0]).toMatchObject({
      record_time: '2026-06-21 17:05:00',
      submit_time: '2026-06-21 17:05:00',
    })
  })

  it('preserves grouped report metadata and items for structured rendering', async () => {
    mocks.requestRaw.mockResolvedValue({
      data: {
        documents: [
          {
            doc_key: 'labtest_item_report::LAB-1',
            document_type: 'labtest_item_report',
            document_title: '血常规检验报告',
            record_time: '2026-02-21 07:45:30',
            content: '检验结果',
            report_metadata: {
              specimen: '外周血',
              report_datetime: '2026-02-21 07:45:30',
            },
            report_items: [
              {
                item_no: '1',
                item_name: '白细胞计数',
                result: '4.95',
                unit: '*10^9/L',
                reference_range: '3.5-9.5',
              },
            ],
          },
        ],
      },
    })

    const result = await getEditableMedicalRecordDocuments('visit-1')

    expect(result.data?.documents[0]).toMatchObject({
      title: '血常规检验报告',
      report_metadata: {
        specimen: '外周血',
        report_datetime: '2026-02-21 07:45:30',
      },
      report_items: [
        {
          item_name: '白细胞计数',
          result: '4.95',
          unit: '*10^9/L',
          reference_range: '3.5-9.5',
        },
      ],
    })
  })

  it('forwards the exact selected validation scope and preserves safe dedupe metadata', async () => {
    mocks.requestRaw.mockResolvedValue({
      data: {
        pool_id: 'pool-1',
        job_id: 'job-1',
        sample_item_count: 1,
        selected_record_count: 1,
        record_count: 1,
        rule_count: 2,
        record_ids: ['visit-1'],
        rule_ids: ['LX0609-01-01-01', 'LX0609-01-02-01'],
        operation_ref: 'sample-op-safe',
        execution_scope_hash: 'a'.repeat(64),
        deduplicated: true,
      },
    })

    const result = await runManualSamplePool('pool-1', {
      sample_item_ids: ['item-1'],
      record_refs: [{ institute_id: 'hospital-1', patient_id: 'patient-1', visit_id: 'visit-1' }],
      selected_rule_ids: ['LX0609-01-01-01', 'LX0609-01-02-01'],
      group_by_luxian_family: false,
      validation_mode: 'customer',
      rule_set_key: 'luxian_0609_qc_v1',
    })

    expect(mocks.requestRaw).toHaveBeenCalledWith({
      method: 'POST',
      url: '/api/v1/qc/sample-pools/pool-1/run',
      data: {
        sample_item_ids: ['item-1'],
        record_refs: [{ institute_id: 'hospital-1', patient_id: 'patient-1', visit_id: 'visit-1' }],
        selected_rule_ids: ['LX0609-01-01-01', 'LX0609-01-02-01'],
        group_by_luxian_family: false,
        validation_mode: 'customer',
        rule_set_key: 'luxian_0609_qc_v1',
      },
      timeout: undefined,
    })
    expect(result.data).toMatchObject({
      operation_ref: 'sample-op-safe',
      execution_scope_hash: 'a'.repeat(64),
      deduplicated: true,
    })
  })

  it('keeps filter-only runs free of record refs and rejects legacy record ids before the API', async () => {
    mocks.requestRaw.mockResolvedValue({ data: { pool_id: 'pool-1', job_id: 'job-1' } })

    await runManualSamplePool('pool-1', {
      validation_mode: 'sc',
      rule_set_key: '',
    })

    expect(mocks.requestRaw).toHaveBeenLastCalledWith(
      expect.objectContaining({
        data: { validation_mode: 'sc', rule_set_key: '' },
      }),
    )

    await expect(
      runManualSamplePool('pool-1', {
        record_ids: ['visit-1'],
        validation_mode: 'sc',
        rule_set_key: '',
      } as never),
    ).rejects.toThrow('record_ids')
    expect(mocks.requestRaw).toHaveBeenCalledTimes(1)
  })

  it('拒绝旧三位 LX0609 规则编号后再发送运行请求', async () => {
    await expect(
      runManualSamplePool('pool-1', {
        selected_rule_ids: ['LX0609-001'],
        validation_mode: 'customer',
        rule_set_key: 'luxian_0609_qc_v1',
      }),
    ).rejects.toThrow('四段式编号')
    expect(mocks.requestRaw).not.toHaveBeenCalled()
  })

  it.each([
    {
      label: 'sample_item_ids only',
      payload: { sample_item_ids: ['item-1'] },
    },
    {
      label: 'record_refs only',
      payload: {
        record_refs: [{ institute_id: 'hospital-1', patient_id: 'patient-1', visit_id: 'visit-1' }],
      },
    },
  ])('rejects partial explicit selection locally: $label', async ({ payload }) => {
    await expect(
      runManualSamplePool('pool-1', {
        ...payload,
        validation_mode: 'sc',
        rule_set_key: '',
      }),
    ).rejects.toThrow('sample_item_ids')

    expect(mocks.requestRaw).not.toHaveBeenCalled()
  })

  it('previews the selected hospitalization scope through the dedicated API', async () => {
    mocks.requestRaw.mockResolvedValue({ data: { counts: { deduplicated: 3 } } })
    const payload = {
      scope_mode: 'active_and_discharged' as const,
      as_of_date: '2026-07-30',
      discharge_start_date: '2026-07-01',
      discharge_end_date: '2026-07-30',
      departments: ['重症医学科（ICU）'],
    }

    await previewManualSamplePoolHospitalizationScope('pool / 1', payload)

    expect(mocks.requestRaw).toHaveBeenCalledWith({
      method: 'POST',
      url: '/api/v1/qc/sample-pools/pool%20%2F%201/hospitalization-scope/preview',
      data: payload,
      timeout: undefined,
    })
  })

  it('starts synchronization with the exact previewed hospitalization scope', async () => {
    mocks.requestRaw.mockResolvedValue({ data: { job_id: 'job-1' } })
    const payload = {
      scope_mode: 'active' as const,
      as_of_date: '2026-07-30',
      departments: [],
    }

    await syncManualSamplePoolRecordsByHospitalization('pool-1', payload)

    expect(mocks.requestRaw).toHaveBeenCalledWith({
      method: 'POST',
      url: '/api/v1/qc/sample-pools/pool-1/sync-by-hospitalization',
      data: payload,
      timeout: undefined,
    })
  })
})

describe('医嘱投影完整性字段规范化', () => {
  it('保留医嘱未完整标志和接口提示', async () => {
    mocks.requestRaw.mockResolvedValue({
      data: {
        documents: [
          {
            key: 'order-projection',
            document_type: 'temporary_order',
            title: '临时医嘱',
            content: '临时医嘱：合成检查项目',
            projection_incomplete: true,
            projection_notice: '已展示700条，仍有更多。',
          },
        ],
      },
    })
    const result = await getEditableMedicalRecordDocuments('synthetic-visit')
    expect(result.data?.documents[0]).toMatchObject({
      projection_incomplete: true,
      projection_notice: '已展示700条，仍有更多。',
    })
  })

  it.each([undefined, false, 'true', 1, null])(
    '未完整标志为 %s 时严格规范化为 false',
    async (flag) => {
      mocks.requestRaw.mockResolvedValue({
        data: {
          documents: [
            {
              key: 'order-complete',
              document_type: 'temporary_order',
              title: '临时医嘱',
              content: '临时医嘱：合成检查项目',
              projection_incomplete: flag,
            },
          ],
        },
      })
      const result = await getEditableMedicalRecordDocuments('synthetic-visit')
      expect(result.data?.documents[0]).toMatchObject({
        projection_incomplete: false,
        projection_notice: '',
      })
    },
  )
})

describe('医嘱投影提示类型规范化', () => {
  it.each([null, false, 700, {}])('非字符串提示 %s 规范化为空字符串', async (notice) => {
    mocks.requestRaw.mockResolvedValue({
      data: {
        documents: [
          {
            key: 'order-notice-type',
            document_type: 'temporary_order',
            title: '临时医嘱',
            content: '临时医嘱：合成检查项目',
            projection_incomplete: true,
            projection_notice: notice,
          },
        ],
      },
    })
    const result = await getEditableMedicalRecordDocuments('synthetic-visit')
    expect(result.data?.documents[0]).toMatchObject({
      projection_incomplete: true,
      projection_notice: '',
    })
  })
})
