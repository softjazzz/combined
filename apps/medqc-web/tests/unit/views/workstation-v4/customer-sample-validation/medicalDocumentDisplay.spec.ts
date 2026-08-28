import { describe, expect, it } from 'vitest'
import { resolveMedicalDocumentGroup } from '@/views/workstation-v4/customer-sample-validation/medicalDocumentDisplay'

describe('medicalDocumentDisplay', () => {
  it.each([
    { document_type: 'presurg_summary', title: '术前小结记录' },
    { document_type: 'custom_document', title: '术前小结' },
  ])('将术前小结归入手术麻醉分组', (document) => {
    expect(
      resolveMedicalDocumentGroup({
        key: 'presurg-summary',
        content: '',
        enabled: true,
        ...document,
      }),
    ).toEqual({ key: 'surgery', label: '手术与麻醉' })
  })

  it('使用同一套目录和规范标题区分上级医师与普通查房', () => {
    expect(
      resolveMedicalDocumentGroup({
        key: 'round-1',
        content: '今日张云海副主任医师查房',
        enabled: true,
        document_type: 'course_record',
      }),
    ).toEqual({ key: 'course.senior', label: '上级医师查房记录', parentKey: 'course' })

    expect(
      resolveMedicalDocumentGroup({
        key: 'round-2',
        content: '今日李方健主治医师查房',
        enabled: true,
        document_type: 'senior_course_record',
      }),
    ).toEqual({ key: 'course.ordinary', label: '普通查房记录', parentKey: 'course' })
  })

  it('为病案首页、首次病程、输血和交接文书提供稳定目录标题', () => {
    expect(resolveMedicalDocumentGroup({ document_type: 'mr' })).toEqual({
      key: 'frontpage',
      label: '病案首页',
    })
    expect(resolveMedicalDocumentGroup({ document_type: 'first_course_record' })).toEqual({
      key: 'admission.first',
      label: '首次病程记录',
      parentKey: 'admission',
    })
    expect(resolveMedicalDocumentGroup({ document_type: 'blood_application' })).toEqual({
      key: 'transfusion',
      label: '输血相关',
    })
    expect(resolveMedicalDocumentGroup({ document_type: 'transfer_in_record' })).toEqual({
      key: 'handoff',
      label: '交接与转科',
    })
  })
})
