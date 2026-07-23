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
  getEditableMedicalRecordDocuments,
  runManualSamplePool,
} from '@/services/manual-case-sample-service'

describe('editable medical-record document normalization', () => {
  beforeEach(() => {
    vi.clearAllMocks()
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
        rule_ids: ['LX0609-001', 'LX0609-002'],
        operation_ref: 'sample-op-safe',
        execution_scope_hash: 'a'.repeat(64),
        deduplicated: true,
      },
    })

    const result = await runManualSamplePool('pool-1', {
      record_ids: ['visit-1'],
      selected_rule_ids: ['LX0609-001', 'LX0609-002'],
      group_by_luxian_family: false,
      validation_mode: 'customer',
      rule_set_key: 'luxian_0609_qc_v1',
    })

    expect(mocks.requestRaw).toHaveBeenCalledWith({
      method: 'POST',
      url: '/api/v1/qc/sample-pools/pool-1/run',
      data: {
        record_ids: ['visit-1'],
        selected_rule_ids: ['LX0609-001', 'LX0609-002'],
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
})
