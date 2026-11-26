import { describe, expect, it } from 'vitest'
import {
  resolveStageStatus,
  runtimeStatusKey,
  updateBatchRuntimeStatuses,
  updateSingleBatchRuntimeStatus,
} from '@/views/workstation-v4/workstationQueueStatusController'
import type { PatientRecord } from '@/views/workstation-v4/types'

function makeRecord(overrides: Partial<PatientRecord> = {}): PatientRecord {
  return {
    id: 'V-100',
    visitId: 'V-100',
    instituteId: 'H-1',
    patientId: 'P-1',
    bedNo: '',
    name: '测试患者',
    sex: '男',
    age: 40,
    insurance: '',
    department: '内科',
    admissionDate: '',
    dischargeDate: '',
    days: 3,
    diagnosis: '',
    diagnosisCode: '',
    doctor: '',
    status: 'pending',
    ...overrides,
  }
}

describe('workstationQueueStatusController 三键状态隔离', () => {
  it('runtimeStatusKey 生成 stage::instituteId::patientId::visitId 并兼容缺省值与 JSON 三键', () => {
    expect(
      runtimeStatusKey('coding_qc', { instituteId: 'H-1', patientId: 'P-1', visitId: 'V-100' }),
    ).toBe('coding_qc::H-1::P-1::V-100')
    expect(runtimeStatusKey('coding_qc', 'V-100', 'H-1', 'P-1')).toBe('coding_qc::H-1::P-1::V-100')
    expect(runtimeStatusKey('coding_qc', '["H-1","P-1","V-100"]')).toBe(
      'coding_qc::H-1::P-1::V-100',
    )
    expect(runtimeStatusKey('coding_qc', 'V-100')).toBe('coding_qc::::::V-100')
    expect(runtimeStatusKey('', 'V-100')).toBe('default::::::V-100')
  })

  it('不同机构同 visitId 互不串台', () => {
    let statusMap = updateSingleBatchRuntimeStatus(
      {},
      'frontpage_qc',
      { instituteId: 'H-1', patientId: 'P-1', visitId: 'V-100' },
      'running',
    )
    statusMap = updateSingleBatchRuntimeStatus(
      statusMap,
      'frontpage_qc',
      { instituteId: 'H-2', patientId: 'P-2', visitId: 'V-100' },
      'failed',
    )

    expect(
      resolveStageStatus({
        stage: 'frontpage_qc',
        visitId: 'V-100',
        record: makeRecord({ instituteId: 'H-1', patientId: 'P-1', visitId: 'V-100' }),
        fallback: 'pending',
        runtimeStatusMap: statusMap,
      }),
    ).toBe('质控中')

    expect(
      resolveStageStatus({
        stage: 'frontpage_qc',
        visitId: 'V-100',
        record: makeRecord({ instituteId: 'H-2', patientId: 'P-2', visitId: 'V-100' }),
        fallback: 'pending',
        runtimeStatusMap: statusMap,
      }),
    ).toBe('执行失败')

    // 第三个机构同 visitId 未运行，不应误命中 H-1 或 H-2
    expect(
      resolveStageStatus({
        stage: 'frontpage_qc',
        visitId: 'V-100',
        record: makeRecord({ instituteId: 'H-3', patientId: 'P-3', visitId: 'V-100' }),
        fallback: 'pending',
        runtimeStatusMap: statusMap,
      }),
    ).toBe('待首页质控')
  })

  it('兼容缺省仅传 visitId 的旧调用方', () => {
    const statusMap = updateBatchRuntimeStatuses({}, 'frontpage_generate', ['V-200'], 'running')
    expect(statusMap['frontpage_generate::::::V-200']).toBe('running')

    expect(
      resolveStageStatus({
        stage: 'frontpage_generate',
        visitId: 'V-200',
        record: makeRecord({ instituteId: 'H-1', patientId: 'P-1', visitId: 'V-200' }),
        fallback: 'pending',
        runtimeStatusMap: statusMap,
      }),
    ).toBe('生成中')
  })
})
