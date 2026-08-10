import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  requestRaw: vi.fn(),
}))

vi.mock('@/services/apiService', () => ({
  ApiService: {
    requestRaw: mocks.requestRaw,
  },
}))

import { createWorkspaceBatchJob } from '@/services/custom-rule-workspace-service'

describe('custom rule workspace batch service', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.requestRaw.mockResolvedValue({
      data: {
        success: true,
        data: { id: 'job-1', status: 'queued' },
      },
    })
  })

  it('只向批任务接口发送三坐标，不透传兼容ID或病历内容', async () => {
    await createWorkspaceBatchJob({
      draft_id: 'draft-1',
      scope: 'final',
      date_field: 'discharge',
      record_refs: [
        {
          institute_id: 'HOSP-A',
          patient_id: 'PAT-A',
          visit_id: 'VISIT-1',
          patient_name: '不得发送',
          medical_text: '不得发送正文',
        },
      ],
      record_ids: ['legacy-must-not-send'],
    } as never)

    const config = mocks.requestRaw.mock.calls[0][0]
    expect(config.data.record_refs).toEqual([
      { institute_id: 'HOSP-A', patient_id: 'PAT-A', visit_id: 'VISIT-1' },
    ])
    expect(config.data).not.toHaveProperty('record_ids')
    expect(JSON.stringify(config.data)).not.toContain('不得发送')
  })

  it('filter-only批任务不要求record_refs且不发送该字段', async () => {
    await createWorkspaceBatchJob({
      draft_id: 'draft-1',
      scope: 'final',
      department: '重症医学科',
      date_field: 'discharge',
      keyword: '待复核',
    } as never)

    const config = mocks.requestRaw.mock.calls[0][0]
    expect(config.data).toMatchObject({
      draft_id: 'draft-1',
      scope: 'final',
      department: '重症医学科',
      date_field: 'discharge',
      keyword: '待复核',
    })
    expect(config.data).not.toHaveProperty('record_refs')
    expect(config.data).not.toHaveProperty('record_ids')
  })
})
