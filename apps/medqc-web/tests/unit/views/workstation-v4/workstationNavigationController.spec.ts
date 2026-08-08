import { ref } from 'vue'
import { describe, expect, it } from 'vitest'

import {
  createDetailNavigation,
  findRecordById,
} from '@/views/workstation-v4/workstationNavigationController'
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

  it('navigates from the second duplicate-visit record by triple record key', () => {
    const records = [
      record({ recordKey: '["H-1","P-1","V-100"]', name: '患者甲' }),
      record({ recordKey: '["H-2","P-2","V-100"]', name: '患者乙' }),
    ]
    const selected = ref(records[1])
    const opened: PatientRecord[] = []
    const navigation = createDetailNavigation({
      getSelectedRecord: () => selected.value,
      getFilteredRecords: () => records,
      openRecord: (nextRecord) => opened.push(nextRecord),
      backToList: () => undefined,
      clearPanels: () => undefined,
    })

    expect(navigation.currentRecordIndex.value).toBe(1)

    navigation.goToPrevRecord()

    expect(opened).toEqual([records[0]])
  })
})
