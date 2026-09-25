import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))

vi.mock('@/services/apiService', () => ({
  apiClient: { get: mocks.get, post: mocks.post },
  default: {},
}))

import {
  buildFormalFrontpageSheetPath,
  buildFormalFrontpageSheetUrl,
  describeFormalFrontpageSheetError,
  requestFrontpageQc,
} from '@/views/workstation-v2/workstationActions'
import type { PatientRecord } from '@/views/workstation-v2/types'

function buildRecord(overrides: Partial<PatientRecord> = {}): PatientRecord {
  return {
    id: 'internal-record-key',
    visitId: 'visit-1',
    instituteId: 'hospital-1',
    patientId: 'patient-1',
    bedNo: '',
    name: '测试患者',
    sex: '未知',
    age: 0,
    insurance: '',
    department: '',
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

describe('正式首页调用：路径与机构号', () => {
  it('路径段逐段编码，避免被 / ? # 截断', () => {
    expect(buildFormalFrontpageSheetPath('P/1 ?', 'V#2')).toBe(
      '/api/medical-records/frontpage-sheet/P%2F1%20%3F/V%232',
    )
  })

  it('无可信机构号时不追加 institute_id', () => {
    const base = '/api/medical-records/frontpage-sheet/P-1/V-1'
    expect(buildFormalFrontpageSheetUrl('P-1', 'V-1')).toBe(base)
    expect(buildFormalFrontpageSheetUrl('P-1', 'V-1', null)).toBe(base)
    expect(buildFormalFrontpageSheetUrl('P-1', 'V-1', '   ')).toBe(base)
  })

  it('有可信机构号时追加去空格的 institute_id', () => {
    expect(buildFormalFrontpageSheetUrl('P-1', 'V-1', '  hospital-1  ')).toBe(
      '/api/medical-records/frontpage-sheet/P-1/V-1?institute_id=hospital-1',
    )
  })
})

describe('正式首页失败语义', () => {
  it('409 原样返回后端文案，缺文案时给出指定机构号提示', () => {
    expect(
      describeFormalFrontpageSheetError({
        response: { status: 409, data: { detail: '归属不唯一，请指定机构号' } },
      }),
    ).toBe('归属不唯一，请指定机构号')
    expect(describeFormalFrontpageSheetError({ response: { status: 409 } })).toBe(
      '正式首页归属不唯一，请指定机构号后重试',
    )
  })

  it('503 原样返回后端文案，缺文案时给出服务不可用提示', () => {
    expect(
      describeFormalFrontpageSheetError({
        response: { status: 503, data: { detail: '病案数据取数来源不可用，请稍后重试' } },
      }),
    ).toBe('病案数据取数来源不可用，请稍后重试')
    expect(describeFormalFrontpageSheetError({ response: { status: 503 } })).toBe(
      '正式首页服务暂不可用，请稍后重试',
    )
  })

  it('其他状态与网络异常回落到调用方给定的兜底文案', () => {
    expect(describeFormalFrontpageSheetError({ response: { status: 500 } }, '兜底')).toBe('兜底')
    expect(describeFormalFrontpageSheetError(new Error('network'), '兜底')).toBe('兜底')
  })
})

describe('requestFrontpageQc 正式首页质控', () => {
  beforeEach(() => {
    mocks.get.mockReset()
    mocks.post.mockReset()
  })

  it('成功路径：GET 只作门槛，POST 只上送三坐标且不含 frontpage 正文', async () => {
    mocks.get.mockResolvedValue({ data: { basic_info: { patient_name: '甲' } } })
    mocks.post.mockResolvedValue({
      data: {
        data: {
          total_issues: 0,
          errors: 0,
          results: [],
          persistence: { defects_created: 0 },
        },
      },
    })

    await requestFrontpageQc(buildRecord())

    expect(mocks.get).toHaveBeenCalledWith(
      '/api/medical-records/frontpage-sheet/patient-1/visit-1?institute_id=hospital-1',
    )
    expect(mocks.post).toHaveBeenCalledWith('/api/v1/qc/formal-qc/validate', {
      patient_id: 'patient-1',
      visit_id: 'visit-1',
      institute_id: 'hospital-1',
    })
    // 服务端自行重读正式首页：GET 拿到的正文绝不能作为 POST 判定输入。
    const postBody = mocks.post.mock.calls[0][1] as Record<string, unknown>
    expect('frontpage' in postBody).toBe(false)
  })

  it('无机构号时 POST 省略 institute_id，不编造机构', async () => {
    mocks.get.mockResolvedValue({ data: { basic_info: {} } })
    mocks.post.mockResolvedValue({ data: { data: { results: [], persistence: null } } })

    await requestFrontpageQc(buildRecord({ instituteId: undefined }))

    expect(mocks.get).toHaveBeenCalledWith(
      '/api/medical-records/frontpage-sheet/patient-1/visit-1',
    )
    const postBody = mocks.post.mock.calls[0][1] as Record<string, unknown>
    expect(postBody).toEqual({ patient_id: 'patient-1', visit_id: 'visit-1' })
    expect('institute_id' in postBody).toBe(false)
  })

  it('机构号含空白时先去空格再上送', async () => {
    mocks.get.mockResolvedValue({ data: { basic_info: {} } })
    mocks.post.mockResolvedValue({ data: { data: { results: [], persistence: null } } })

    await requestFrontpageQc(buildRecord({ instituteId: '  hospital-9  ' }))

    expect(mocks.post).toHaveBeenCalledWith('/api/v1/qc/formal-qc/validate', {
      patient_id: 'patient-1',
      visit_id: 'visit-1',
      institute_id: 'hospital-9',
    })
  })

  it('缺少 visitId 时用记录主键而非空串拼路径', async () => {
    mocks.get.mockResolvedValue({ data: { basic_info: {} } })
    mocks.post.mockResolvedValue({ data: { data: { results: [], persistence: null } } })

    await requestFrontpageQc(buildRecord({ visitId: undefined }))

    expect(mocks.get).toHaveBeenCalledWith(
      '/api/medical-records/frontpage-sheet/patient-1/internal-record-key?institute_id=hospital-1',
    )
  })

  it('409 归属不唯一：抛出后端文案，且不提交正式质控', async () => {
    mocks.get.mockRejectedValue({
      response: { status: 409, data: { detail: '同名 patient+visit 命中多机构' } },
    })

    await expect(requestFrontpageQc(buildRecord())).rejects.toThrow('同名 patient+visit 命中多机构')
    expect(mocks.post).not.toHaveBeenCalled()
  })

  it('503 首页服务不可用：抛出服务提示，且不提交正式质控', async () => {
    mocks.get.mockRejectedValue({
      response: { status: 503, data: { detail: '病案数据取数来源不可用，请稍后重试' } },
    })

    await expect(requestFrontpageQc(buildRecord())).rejects.toThrow(
      '病案数据取数来源不可用，请稍后重试',
    )
    expect(mocks.post).not.toHaveBeenCalled()
  })

  it('404 无正式首页：失败关闭，不把草稿当正式首页提交', async () => {
    mocks.get.mockRejectedValue({ response: { status: 404, data: { detail: '未找到正式首页' } } })

    await expect(requestFrontpageQc(buildRecord())).rejects.toThrow('读取正式首页数据失败')
    expect(mocks.post).not.toHaveBeenCalled()
  })

  it('200 但空首页：同样失败关闭，不提交正式质控', async () => {
    mocks.get.mockResolvedValue({ data: null })

    await expect(requestFrontpageQc(buildRecord())).rejects.toThrow(
      '未找到正式首页数据，无法执行首页质控',
    )
    expect(mocks.post).not.toHaveBeenCalled()
  })

  it('200 但统一信封缺失：失败关闭，不报成零问题通过', async () => {
    mocks.get.mockResolvedValue({ data: { basic_info: {} } })
    mocks.post.mockResolvedValue({ data: {} })

    await expect(requestFrontpageQc(buildRecord())).rejects.toThrow(
      '首页质控响应异常，无法确认质控结果',
    )
  })

  it('200 但 results 非数组：失败关闭，不报成零问题通过', async () => {
    mocks.get.mockResolvedValue({ data: { basic_info: {} } })
    mocks.post.mockResolvedValue({ data: { data: { results: null } } })

    await expect(requestFrontpageQc(buildRecord())).rejects.toThrow(
      '首页质控响应异常，无法确认质控结果',
    )
  })
})
