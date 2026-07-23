import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  requestRaw: vi.fn(),
}))

vi.mock('@/services/apiService', () => ({
  ApiService: {
    requestRaw: mocks.requestRaw,
  },
}))

import { getEditableMedicalRecordDocuments } from '@/services/manual-case-sample-service'

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
})
