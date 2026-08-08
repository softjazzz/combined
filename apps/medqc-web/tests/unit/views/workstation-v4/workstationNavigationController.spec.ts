import { describe, expect, it } from 'vitest'

import { findRecordById } from '@/views/workstation-v4/workstationNavigationController'
import type { PatientRecord } from '@/views/workstation-v4/types'

function record(overrides: Partial<PatientRecord>): PatientRecord {
  return {
    id: 'V-100',
    bedNo: '',
    name: '患者',
    sex: '未知',
    age: 0,
    insurance: '',
    department: '内科',
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

describe('workstationNavigationController', () => {
  it('finds the clicked duplicate-visit record by its triple record key', () => {
    const secondKey = '["H-2","P-2","V-100"]'
    const records = [
      record({ recordKey: '["H-1","P-1","V-100"]', name: '患者甲' }),
      record({ recordKey: secondKey, name: '患者乙' }),
    ]

    expect(findRecordById(records, secondKey)?.name).toBe('患者乙')
  })
})
