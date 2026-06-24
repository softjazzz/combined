import { beforeEach, describe, expect, it, vi } from 'vitest'

const postMock = vi.fn()

vi.mock('@/services/apiService', () => ({
  apiClient: {
    post: postMock,
  },
}))

vi.mock('@/utils/api-envelope', () => ({
  unwrapApiEnvelope: vi.fn((payload) => payload?.data ?? payload),
}))

describe('frontpage report api', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('generateReportDraft 使用统一草稿端点并传递场景与病历文本', async () => {
    const { frontpageApi } = await import('@/api/frontpage')
    postMock.mockResolvedValueOnce({
      data: {
        success: true,
        data: {
          scene: 'combined',
          frontpage: {},
          settlement: {},
          coverage: { status: 'partial', total: 1, present: 0, partial: 0, missing: 1 },
        },
      },
    })

    const result = await frontpageApi.generateReportDraft({
      medical_text: '入院记录',
      scene: 'combined',
      patient_id: 'P001',
    })

    expect(postMock).toHaveBeenCalledWith(
      '/api/v1/frontpage/generate-report-draft',
      {
        medical_text: '入院记录',
        scene: 'combined',
        patient_id: 'P001',
      },
      { timeout: 180000 },
    )
    expect(result.data?.scene).toBe('combined')
  })
})
