import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({ post: vi.fn() }))

vi.mock('@/services/apiService', () => ({
  apiClient: { post: mocks.post },
  default: {},
}))

import { requestCodingQc } from '@/views/workstation-v4/workstationActions'
import type { PatientRecord } from '@/views/workstation-v4/types'

const record: PatientRecord = {
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
}

describe('编码质控病例身份', () => {
  beforeEach(() => {
    mocks.post.mockReset()
    mocks.post.mockResolvedValue({ data: { data: { total_issues: 0, errors: 0 } } })
  })

  it('请求携带机构、患者和真实就诊号', async () => {
    await requestCodingQc(record)

    expect(mocks.post).toHaveBeenCalledWith('/api/v1/qc/coding-qc/check', {
      institute_id: 'hospital-1',
      patient_id: 'patient-1',
      visit_id: 'visit-1',
    })
  })
})
