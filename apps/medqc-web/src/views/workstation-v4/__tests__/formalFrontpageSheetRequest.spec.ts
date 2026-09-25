import { beforeEach, describe, expect, it, vi } from 'vitest'

const { getMock, postMock } = vi.hoisted(() => ({ getMock: vi.fn(), postMock: vi.fn() }))

vi.mock('@/services/apiService', () => ({
  default: { isAuthenticated: () => true, refreshToken: vi.fn() },
  apiClient: { get: getMock, post: postMock },
}))

import {
  buildFormalFrontpageSheetPath,
  buildFormalFrontpageSheetUrl,
  describeFormalFrontpageSheetError,
  requestFrontpageQc,
} from '../workstationActions'
import type { PatientRecord } from '../types'

const SHEET_PATH = '/api/medical-records/frontpage-sheet/P-1/V-1'

function record(overrides: Partial<PatientRecord> = {}): PatientRecord {
  return {
    id: 'V-1',
    recordKey: 'LX001::P-1::V-1',
    visitId: 'V-1',
    patientId: 'P-1',
    instituteId: 'LX001',
    bedNo: '',
    name: '测试患者',
    sex: '男',
    age: 60,
    insurance: '',
    department: '心内科',
    admissionDate: '',
    dischargeDate: '',
    days: 0,
    diagnosis: '',
    diagnosisCode: '',
    doctor: '',
    status: 'pending',
    ...overrides,
  }
}

describe('正式首页 GET 路径与消歧参数', () => {
  it('路径段逐段编码，patient_id / visit_id 中的分隔符不会截断路由', () => {
    expect(buildFormalFrontpageSheetPath('P/1 2', 'V?3#4')).toBe(
      '/api/medical-records/frontpage-sheet/P%2F1%202/V%3F3%234',
    )
  })

  it.each([undefined, null, '', '   '])('机构号为空（%s）时不编造 institute_id', (instituteId) => {
    const url = buildFormalFrontpageSheetUrl('P-1', 'V-1', instituteId)
    expect(url).toBe(SHEET_PATH)
  })

  it('机构号非空时以 URLSearchParams 编码后仅作为消歧参数', () => {
    const url = buildFormalFrontpageSheetUrl('P-1', 'V-1', ' 机构 A/1&x=2 ')
    const parsed = new URL(url, 'http://localhost')
    expect(parsed.pathname).toBe(SHEET_PATH)
    expect(parsed.searchParams.get('institute_id')).toBe('机构 A/1&x=2')
  })
})

describe('describeFormalFrontpageSheetError 失败语义', () => {
  it('409 原样透出后端 detail', () => {
    expect(
      describeFormalFrontpageSheetError({
        response: { status: 409, data: { detail: '病例身份不唯一，请指定机构号' } },
      }),
    ).toBe('病例身份不唯一，请指定机构号')
  })

  it('409 无 detail 时仍明确提示不确定性', () => {
    expect(describeFormalFrontpageSheetError({ response: { status: 409 } })).toBe(
      '正式首页归属不唯一，请指定机构号后重试',
    )
  })

  it('503 提示服务暂不可用，不退化成“没有正式首页”', () => {
    expect(describeFormalFrontpageSheetError({ response: { status: 503 } })).toBe(
      '正式首页服务暂不可用，请稍后重试',
    )
  })
})

describe('requestFrontpageQc 正式首页读取', () => {
  beforeEach(() => {
    getMock.mockReset()
    postMock.mockReset()
  })

  it('机构号非空时 GET 消歧，POST 只提交三坐标：含 institute_id、不含 frontpage', async () => {
    getMock.mockResolvedValue({ data: { basic_info: {} } })
    postMock.mockResolvedValue({
      data: { success: true, data: { results: [], failed: 0, persistence: { id: 'p-1' } } },
    })

    await requestFrontpageQc(record({ instituteId: '机构 A/1&x=2' }))

    const url = new URL(getMock.mock.calls[0][0] as string, 'http://localhost')
    expect(url.pathname).toBe(SHEET_PATH)
    expect(url.searchParams.get('institute_id')).toBe('机构 A/1&x=2')
    expect(postMock.mock.calls[0][0]).toBe('/api/v1/qc/formal-qc/validate')
    const body = postMock.mock.calls[0][1] as Record<string, unknown>
    expect(body).toEqual({ patient_id: 'P-1', visit_id: 'V-1', institute_id: '机构 A/1&x=2' })
    expect(body).not.toHaveProperty('frontpage')
  })

  it('机构号缺失时 GET 无机构参数，POST 省略 institute_id 且不含 frontpage', async () => {
    getMock.mockResolvedValue({ data: { basic_info: {} } })
    postMock.mockResolvedValue({ data: { success: true, data: { results: [], failed: 0 } } })

    await requestFrontpageQc(record({ instituteId: undefined }))

    expect(getMock).toHaveBeenCalledWith(SHEET_PATH)
    const body = postMock.mock.calls[0][1] as Record<string, unknown>
    expect(body).toEqual({ patient_id: 'P-1', visit_id: 'V-1' })
    expect(body).not.toHaveProperty('frontpage')
    expect(body).not.toHaveProperty('institute_id')
  })

  it('409 归属歧义时原样失败，不再提交正式质控', async () => {
    getMock.mockRejectedValue({
      response: { status: 409, data: { detail: '病例身份不唯一，请指定机构号' } },
    })

    await expect(requestFrontpageQc(record())).rejects.toThrow('病例身份不唯一，请指定机构号')
    expect(postMock).not.toHaveBeenCalled()
  })

  it('503 服务不可用时原样失败，不退化成“无正式首页”', async () => {
    getMock.mockRejectedValue({ response: { status: 503 } })

    await expect(requestFrontpageQc(record())).rejects.toThrow('正式首页服务暂不可用，请稍后重试')
    expect(postMock).not.toHaveBeenCalled()
  })

  it('回包为空时失败关闭，不把空首页当可质控对象', async () => {
    getMock.mockResolvedValue({ data: null })

    await expect(requestFrontpageQc(record())).rejects.toThrow('未找到正式首页数据，无法执行首页质控')
    expect(postMock).not.toHaveBeenCalled()
  })

  it('POST 失败（503）时失败关闭，不产出可当作“已分析”的空结果', async () => {
    getMock.mockResolvedValue({ data: { basic_info: {} } })
    postMock.mockRejectedValue({
      response: { status: 503, data: { detail: '首页质控或结果保存失败，请稍后重试' } },
    })

    await expect(requestFrontpageQc(record())).rejects.toBeDefined()
  })

  it('POST 返回 200 但缺少统一数据体时按失败关闭，不返回零问题结果', async () => {
    getMock.mockResolvedValue({ data: { basic_info: {} } })
    // 服务端自行重新读取首页后异常：success=true 却没有 data 数据体。
    postMock.mockResolvedValue({ data: { success: true } })

    await expect(requestFrontpageQc(record())).rejects.toThrow('首页质控响应缺少统一数据体')
  })

  it('POST 返回 200 但 results 非数组时按失败关闭', async () => {
    getMock.mockResolvedValue({ data: { basic_info: {} } })
    postMock.mockResolvedValue({ data: { success: true, data: { results: { 0: 'x' } } } })

    await expect(requestFrontpageQc(record())).rejects.toThrow('首页质控响应缺少统一数据体')
  })
})
