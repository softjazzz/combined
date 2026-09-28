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
  createDraftBasicInfo,
  createWorkspaceBatchJob,
  getDraftBasicInfo,
  getDraftBasicInfoOptions,
  updateDraftBasicInfo,
} from '@/services/custom-rule-workspace-service'

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

describe('custom rule draft basic info service', () => {
  const draft = {
    id: 'draft-1', rule_code: 'CUSTOM-001', status: 'draft', updated_at: '2026-09-28T12:00:00Z',
    name: '新规则', category: '诊疗规范', rule_type: '规范性', document_type: 'discharge_record',
  }
  const payload = { name: '新规则', category: '诊疗规范', rule_type: '规范性', document_type: 'discharge_record' }

  beforeEach(() => vi.clearAllMocks())

  it('读取文书选项时拒绝重复或错型值', async () => {
    mocks.requestRaw.mockResolvedValueOnce({ data: { success: true, data: { documents: [
      { value: 'discharge_record', label: '出院记录' },
      { value: 'discharge_record', label: '出院记录副本' },
    ] } } })
    expect(await getDraftBasicInfoOptions()).toMatchObject({ success: false })

    mocks.requestRaw.mockResolvedValueOnce({ data: { success: true, data: { documents: [{ value: 'admission_record', label: '入院记录' }] } } })
    expect(await getDraftBasicInfoOptions()).toEqual({
      success: true, data: { documents: [{ value: 'admission_record', label: '入院记录' }] },
    })
  })

  it('回读只接受请求id对应的draft且updated_at可解析', async () => {
    mocks.requestRaw.mockResolvedValueOnce({ data: { success: true, data: draft } })
    expect(await getDraftBasicInfo('draft-1')).toEqual({ success: true, data: draft })
    mocks.requestRaw.mockResolvedValueOnce({ data: { success: true, data: { ...draft, id: 'other' } } })
    expect(await getDraftBasicInfo('draft-1')).toMatchObject({ success: false })
    mocks.requestRaw.mockResolvedValueOnce({ data: { success: true, data: { ...draft, updated_at: 'not-a-date' } } })
    expect(await getDraftBasicInfo('draft-1')).toMatchObject({ success: false })
  })

  it('创建只发送四项基础信息并核对可确认回执', async () => {
    mocks.requestRaw.mockResolvedValue({ data: { success: true, data: draft } })
    expect(await createDraftBasicInfo(payload)).toEqual({ success: true, data: draft, resultUnknown: false, conflict: false })
    expect(mocks.requestRaw).toHaveBeenCalledWith({
      method: 'POST', url: '/api/v1/custom-qc/workspace/draft-basic-info', data: payload,
    })
  })

  it.each([401, 403, 404, 409, 422])('HTTP %s是明确拒绝而非未知结果', async (status) => {
    mocks.requestRaw.mockRejectedValue({ response: { status, data: { detail: '请求被拒绝' } } })
    expect(await createDraftBasicInfo(payload)).toMatchObject({
      success: false, resultUnknown: false, conflict: status === 409,
    })
  })

  it.each([500, 503, undefined])('HTTP %s或无响应时禁止盲目重试', async (status) => {
    mocks.requestRaw.mockRejectedValue(status ? { response: { status } } : new Error('timeout'))
    const result = await createDraftBasicInfo(payload)
    expect(result).toMatchObject({ success: false, resultUnknown: true })
    if (result.success === false) expect(result.message).toContain('勿盲目重试')
  })

  it('PATCH携带CAS且其他草稿回执标记未知', async () => {
    mocks.requestRaw.mockResolvedValueOnce({ data: { success: true, data: draft } })
    await updateDraftBasicInfo('draft-1', { ...payload, expected_updated_at: draft.updated_at })
    expect(mocks.requestRaw).toHaveBeenCalledWith({
      method: 'PATCH', url: '/api/v1/custom-qc/workspace/draft-basic-info/draft-1',
      data: { ...payload, expected_updated_at: draft.updated_at },
    })
    mocks.requestRaw.mockResolvedValueOnce({ data: { success: true, data: { ...draft, id: 'other' } } })
    expect(await updateDraftBasicInfo('draft-1', { ...payload, expected_updated_at: draft.updated_at })).toMatchObject({
      success: false, resultUnknown: true,
    })
  })
})
