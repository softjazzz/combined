import { AxiosHeaders, type AxiosResponse } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getRecordDetail, getOutpatientCdmDetail } from '@/api/qcAdmin'
import { ApiService } from '@/services/apiService'

vi.mock('@/services/apiService', () => ({ ApiService: { requestRaw: vi.fn() } }))

function response<T>(data: T): AxiosResponse<T> {
  return {
    data,
    status: 200,
    statusText: 'OK',
    headers: new AxiosHeaders(),
    config: { headers: new AxiosHeaders() },
  }
}

describe('getRecordDetail 质控详情合同', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('CDM详情使用独立入口及完整四坐标，不拼接visit单键旧详情路径', async () => {
    vi.mocked(ApiService.requestRaw).mockResolvedValueOnce(response({ success: true, data: { documents: {} } }))
    await getOutpatientCdmDetail({ institute_id: 'I/1', patient_id: 'P', visit_id: 'V', document_id: 'D' })
    expect(ApiService.requestRaw).toHaveBeenCalledWith({
      method: 'GET', url: '/api/v1/records/outpatient-emergency/cdm-detail',
      params: { source: 'cdm_outpat_record', institute_id: 'I/1', patient_id: 'P', visit_id: 'V', document_id: 'D' },
    })
  })

  it('显式旧病历来源才请求质控详情，并编码旧表主键', async () => {
    const detail = { record_id: 'record-1', defects: [{ id: 'defect-1' }] }
    vi.mocked(ApiService.requestRaw).mockResolvedValueOnce(response({ success: true, data: detail }))

    await expect(getRecordDetail('record/1', 'legacy_medical_records')).resolves.toEqual({
      success: true,
      data: detail,
      message: undefined,
    })
    expect(ApiService.requestRaw).toHaveBeenCalledTimes(1)
    expect(ApiService.requestRaw).toHaveBeenCalledWith({
      method: 'GET',
      url: '/api/v1/records/record%2F1/qc-detail',
      params: { source: 'legacy_medical_records' },
    })
  })

  it('类型边界拒绝不明或 CDM 来源', () => {
    const rejectUnverifiedSource = () => {
      // @ts-expect-error 旧详情必须显式声明旧病历来源
      void getRecordDetail('same-visit')
      // @ts-expect-error CDM 就诊号不能作为旧病历主键查询
      void getRecordDetail('same-visit', 'cdm')
    }
    void rejectUnverifiedSource
    expect(ApiService.requestRaw).not.toHaveBeenCalled()
  })

  it('服务返回失败信封时原样传递失败，不降级到内存单记录', async () => {
    vi.mocked(ApiService.requestRaw).mockResolvedValueOnce(
      response({ success: false, message: '质控详情暂不可用' }),
    )

    await expect(getRecordDetail('record-1', 'legacy_medical_records')).resolves.toEqual({
      success: false,
      data: undefined,
      message: '质控详情暂不可用',
    })
    expect(ApiService.requestRaw).toHaveBeenCalledTimes(1)
    expect(ApiService.requestRaw).toHaveBeenCalledWith({
      method: 'GET',
      url: '/api/v1/records/record-1/qc-detail',
      params: { source: 'legacy_medical_records' },
    })
  })

  it('503 时保留错误提示，不把内存单记录伪装成完整质控详情', async () => {
    vi.mocked(ApiService.requestRaw).mockRejectedValueOnce({
      response: { status: 503, data: { detail: '质控详情数据源不可用' } },
    })

    await expect(getRecordDetail('record-1', 'legacy_medical_records')).resolves.toEqual({
      success: false,
      message: '质控详情数据源不可用',
    })
    expect(ApiService.requestRaw).toHaveBeenCalledTimes(1)
    expect(ApiService.requestRaw).toHaveBeenCalledWith({
      method: 'GET',
      url: '/api/v1/records/record-1/qc-detail',
      params: { source: 'legacy_medical_records' },
    })
  })
})
