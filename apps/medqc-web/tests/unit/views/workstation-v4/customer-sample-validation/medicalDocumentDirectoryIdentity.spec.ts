import { describe, expect, it } from 'vitest'
import { resolveMedicalDocumentGroup } from '@/views/workstation-v4/utils/medicalDocumentTaxonomy'

describe('完整文书目录身份优先', () => {
  it.each([
    ['senior_course_record', '上级医师查房记录', 'course.senior'],
    ['consultation_record', '会诊记录', 'consultation'],
    ['discharge_record', '出院记录', 'discharge'],
    ['inpat_drug_order', '用药医嘱', 'orders'],
  ])('%s 不因正文提到入院而改变分组', (document_type, title, key) => {
    expect(
      resolveMedicalDocumentGroup({
        document_type,
        title,
        content: '患者入院后检查，手术后会诊，继续用药。',
        sections: [{ text: '入院时间：2026-02-02 10:00:00' }],
      }).key,
    ).toBe(key)
  })

  it('普通病程仍可由正文医师角色细分查房', () => {
    expect(
      resolveMedicalDocumentGroup({
        document_type: 'daily_course_record',
        content: '入院后今日副主任医师查房。',
      }).key,
    ).toBe('course.senior')
  })
})
