import { describe, expect, it } from 'vitest'
import { resolveMedicalDocumentGroup } from '@/views/workstation-v4/customer-sample-validation/medicalDocumentDisplay'
import { formatDiagnosisSection } from '@/views/workstation-v4/customer-sample-validation/medicalDocumentDisplay'

it('诊断类别与其他诊断分行，保留椎体编号及原有归属', () => {
  expect(
    formatDiagnosisSection(
      '入院记录诊断',
      '诊断类型: 初步诊断 其他诊断: 1.L1椎压缩性骨折 2.L3、L4左侧横突骨折',
    ),
  ).toBe('诊断类型：初步诊断\n其他诊断：\n1.L1椎压缩性骨折\n2.L3、L4左侧横突骨折')
  expect(formatDiagnosisSection('现病史', '数值 1.5 其他诊断: 示例')).toBe(
    '数值 1.5 其他诊断: 示例',
  )
})

describe('medicalDocumentDisplay', () => {
  it('出院前上级医师查房按结构化类型归入病程，出院记录仍归入出院类', () => {
    expect(
      resolveMedicalDocumentGroup({
        document_type: 'senior_course_record',
        group_key: 'course',
        title: '郑瑞清副主任医师出院前查房记录',
        content: '',
      }),
    ).toEqual({ key: 'course.senior', label: '上级医师查房记录', parentKey: 'course' })
    expect(
      resolveMedicalDocumentGroup({
        document_type: 'discharge_record',
        title: '出院记录',
        content: '副主任医师查房后同意出院',
      }),
    ).toEqual({ key: 'discharge', label: '出院与死亡' })
  })
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

  it.each([
    { document_type: 'presurg_discussion', title: '术前讨论记录' },
    { document_type: 'custom_document', title: '术前讨论记录' },
  ])('将术前讨论记录归入手术麻醉分组', (document) => {
    expect(
      resolveMedicalDocumentGroup({
        key: 'presurg-discussion',
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
