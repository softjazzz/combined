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

  it('rejects a bare id shared across patients or institutes', () => {
    const records = [
      record({ instituteId: 'H-1', patientId: 'P-1', visitId: 'V-100' }),
      record({ instituteId: 'H-1', patientId: 'P-2', visitId: 'V-100' }),
      record({ instituteId: 'H-2', patientId: 'P-1', visitId: 'V-100' }),
    ]
    expect(findRecordById(records, 'V-100')).toBeUndefined()
    expect(findRecordById(records, '["H-2","P-1","V-100"]')).toBe(records[2])
  })

  it('matches a unique legacy id or visit number', () => {
    const legacy = record({ id: 'LEGACY-1', visitId: 'V-100' })
    expect(findRecordById([legacy], 'LEGACY-1')).toBe(legacy)
    expect(findRecordById([legacy], 'V-100')).toBe(legacy)
  })

  it('does not reinterpret an unmatched complete key as a bare id', () => {
    const requestedKey = '["H-2","P-2","V-100"]'
    const records = [record({ id: requestedKey, visitId: 'V-100' })]
    expect(findRecordById(records, requestedKey)).toBeUndefined()
  })

  it('does not reinterpret a malformed case key as a bare id', () => {
    const requestedKey = '["H-2","P-2","V-100"'
    const records = [record({ id: requestedKey })]
    expect(findRecordById(records, requestedKey)).toBeUndefined()
  })

  it('stops detail navigation when a bare selection becomes ambiguous', () => {
    const records = [
      record({ instituteId: 'H-1' }),
      record({ instituteId: 'H-2' }),
      record({ id: 'V-200' }),
    ]
    const opened: PatientRecord[] = []
    const navigation = createDetailNavigation({
      getSelectedRecord: () => record({}),
      getFilteredRecords: () => records,
      openRecord: (nextRecord) => opened.push(nextRecord),
      backToList: () => undefined,
      clearPanels: () => undefined,
    })

    expect(navigation.currentRecordIndex.value).toBe(-1)
    navigation.goToPrevRecord()
    navigation.goToNextRecord()
    expect(opened).toEqual([])
  })

  it('keeps detail navigation in the source of the selected record', () => {
    const selected = record({
      sourceId: 'independent_cdm',
      instituteId: 'H-1',
      patientId: 'P-1',
      visitId: 'V-100',
      recordKey: '["H-1","P-1","V-100"]',
    })
    const differentSource = record({ ...selected, id: 'V-200', sourceId: 'legacy_pg' })
    const next = record({
      sourceId: 'independent_cdm',
      instituteId: 'H-2',
      patientId: 'P-2',
      visitId: 'V-100',
      recordKey: '["H-2","P-2","V-100"]',
    })
    const opened: PatientRecord[] = []
    const navigation = createDetailNavigation({
      getSelectedRecord: () => selected,
      getFilteredRecords: () => [selected, differentSource, next],
      openRecord: (nextRecord) => opened.push(nextRecord),
      backToList: () => undefined,
      clearPanels: () => undefined,
    })

    navigation.goToNextRecord()
    expect(opened).toEqual([next])
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
