import { describe, expect, it } from 'vitest'

import { sanitizeQcDebugPayload } from '../qcDebugSanitizer'

describe('sanitizeQcDebugPayload P0-3 regressions', () => {
  it('does not shred text when patientName, doctor_name, or placeholder names are empty', () => {
    const payload = {
      patientName: '',
      patient_name: '   ',
      doctor_name: '',
      physician_name: '-',
      surgeon_name: '未知',
      contact_name: '未说明',
      family_name: '',
      summary: '入院记录按时完成，未发现缺失项。',
      conclusion: '正常文本不应被插入患者A或医务人员A。',
    }

    const sanitized = sanitizeQcDebugPayload(payload, { patientName: '' })

    expect(sanitized.patientName).toBe('')
    expect(sanitized.doctor_name).toBe('')
    expect(sanitized.summary).toBe('入院记录按时完成，未发现缺失项。')
    expect(sanitized.conclusion).toBe('正常文本不应被插入患者A或医务人员A。')
  })

  it('still redacts real names even when other rows have empty name fields', () => {
    const payload = {
      items: [
        { patientName: '', doctor_name: '', note: '普通说明' },
        { patient_name: '张伟', doctor_name: '王敏', note: '患者张伟由王敏医师查房' },
      ],
    }

    const sanitized = sanitizeQcDebugPayload(payload)

    expect(sanitized.items[0].note).toBe('普通说明')
    expect(sanitized.items[1].patient_name).toBe('患者A')
    expect(sanitized.items[1].doctor_name).toBe('医务人员A')
    expect(sanitized.items[1].note).toBe('患者A由医务人员A医师查房')
  })

  it('preserves LX0916-*, SC-*, and LX0609-* rule IDs under rule identity keys without redacting them to aliases', () => {
    const payload = {
      qc_point_id: 'LX0916-005',
      rule_id: 'SC-026',
      primary_execution_rule_id: 'LX0609-03-01-01',
      rule_ids: ['LX0916-001', 'SC-002', 'LX0609-01-01-01'],
      selected_rule_ids: ['LX0916-005', 'LX0916-015', 'SC-081'],
      scoped_customer_rule_ids: ['LX0916-008', 'LX0609-06-01-04'],
      mapped_rule_ids: ['SC-026', 'SC-048'],
      candidate_rule_ids: ['SC-026', 'LX0916-002'],
      conclusion: '已核查 LX0916-005、SC-026 与 LX0609-03-01-01',
    }

    const sanitized = sanitizeQcDebugPayload(payload)

    expect(sanitized).toEqual(payload)
    expect(JSON.stringify(sanitized)).not.toContain('标识-')
  })

  it('still sanitizes non-rule-id sensitive values inside rule identity fields', () => {
    const sanitized = sanitizeQcDebugPayload({
      qc_point_id: 'LX0916-005 token=secret-value-1234',
      selected_rule_ids: ['LX0916-005', 'SC-026', '患者李庆珍,性别女 token=array-secret-1234'],
    })

    expect(sanitized.selected_rule_ids[0]).toBe('LX0916-005')
    expect(sanitized.selected_rule_ids[1]).toBe('SC-026')
    const serialized = JSON.stringify(sanitized)
    expect(serialized).not.toContain('secret-value-1234')
    expect(serialized).not.toContain('array-secret-1234')
    expect(serialized).not.toContain('李庆珍')
  })

  it('generates clean alphabetic aliases beyond 26 distinct clinician names without ASCII overflow', () => {
    const clinicians = Array.from({ length: 30 }, (_, index) => `医生甲${String(index + 1).padStart(2, '0')}`)
    const payload = {
      records: clinicians.map((name) => ({
        doctor_name: name,
        note: `签名：${name}`,
      })),
    }

    const sanitized = sanitizeQcDebugPayload(payload)
    const aliases = sanitized.records.map((record) => record.doctor_name)

    expect(aliases[0]).toBe('医务人员A')
    expect(aliases[25]).toBe('医务人员Z')
    expect(aliases[26]).toBe('医务人员AA')
    expect(aliases[27]).toBe('医务人员AB')
    expect(aliases[28]).toBe('医务人员AC')
    expect(aliases[29]).toBe('医务人员AD')
    expect(new Set(aliases).size).toBe(30)
    for (const alias of aliases) {
      expect(alias).toMatch(/^医务人员[A-Z]+$/u)
    }
    expect(sanitized.records[26].note).toBe('签名：医务人员AA')
    expect(sanitized.records[29].note).toBe('签名：医务人员AD')
  })
})
