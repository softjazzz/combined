import { describe, expect, it } from 'vitest'

import {
  canGenerateFrontpageDraft,
  canGenerateSettlementDraft,
  getFrontpageDraftDisabledReason,
} from '../frontpageAvailability'
import type { DocItem, PatientRecord } from '../types'

function makeRecord(overrides: Partial<PatientRecord> = {}): PatientRecord {
  return {
    id: 'record-1',
    visitId: 'visit-1',
    patientId: 'patient-1',
    bedNo: '12',
    name: '测试患者',
    sex: '男',
    age: 58,
    insurance: '医保',
    department: '内科',
    admissionDate: '2026-05-01',
    dischargeDate: '',
    days: 3,
    diagnosis: '测试诊断',
    diagnosisCode: 'A00',
    doctor: '张医生',
    status: 'pending',
    ...overrides,
  }
}

function makeDoc(overrides: Partial<DocItem> = {}): DocItem {
  return {
    id: 'doc-1',
    type: 'admission_record',
    label: '入院记录',
    has_content: true,
    content: '患者入院记录正文',
    length: 8,
    ...overrides,
  }
}

describe('frontpageAvailability', () => {
  it('允许在院患者在有 visitId 和可抽取文书时生成 AI 首页草稿', () => {
    const record = makeRecord({ dischargeDate: '' })

    expect(canGenerateFrontpageDraft(record, [makeDoc()])).toBe(true)
    expect(getFrontpageDraftDisabledReason(record, [makeDoc()])).toBe('')
  })

  it('已出院患者仍可生成 AI 首页草稿', () => {
    const record = makeRecord({ dischargeDate: '2026-05-12' })

    expect(canGenerateFrontpageDraft(record, [makeDoc()])).toBe(true)
    expect(getFrontpageDraftDisabledReason(record, [makeDoc()])).toBe('')
  })

  it('未选择病历或无有效病历 ID 时禁用首页草稿生成', () => {
    expect(canGenerateFrontpageDraft(undefined, [makeDoc()])).toBe(false)
    expect(getFrontpageDraftDisabledReason(undefined, [makeDoc()])).toBe('请选择病历后生成首页草稿')

    const recordWithoutId = makeRecord({ id: '', visitId: '' })

    expect(canGenerateFrontpageDraft(recordWithoutId, [makeDoc()])).toBe(false)
    expect(getFrontpageDraftDisabledReason(recordWithoutId, [makeDoc()])).toBe(
      '请选择病历后生成首页草稿',
    )
  })

  it('缺少可抽取文书时禁用首页草稿生成并给出新提示', () => {
    const record = makeRecord({ hasAdmission: false })
    const emptyDoc = makeDoc({ has_content: false, content: null, length: 0 })

    expect(canGenerateFrontpageDraft(record, [emptyDoc])).toBe(false)
    expect(getFrontpageDraftDisabledReason(record, [emptyDoc])).toBe(
      '缺少可抽取文书，暂不能生成首页草稿',
    )
  })

  it('结算清单仍要求患者已出院且无既有正式结算数据', () => {
    expect(canGenerateSettlementDraft(makeRecord({ dischargeDate: '' }), false)).toBe(false)
    expect(canGenerateSettlementDraft(makeRecord({ dischargeDate: '2026-05-12' }), false)).toBe(
      true,
    )
    expect(canGenerateSettlementDraft(makeRecord({ dischargeDate: '2026-05-12' }), true)).toBe(
      false,
    )
  })
})
