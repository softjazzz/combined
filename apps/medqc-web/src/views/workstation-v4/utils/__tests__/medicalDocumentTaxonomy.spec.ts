import { describe, expect, it } from 'vitest'

import {
  resolveMedicalDocumentGroup,
  resolveMedicalDocumentTitle,
} from '../medicalDocumentTaxonomy'

describe('resolveMedicalDocumentTitle', () => {
  it.each(['CT检查报告', '核磁共振检查报告', '心电图检查报告'])(
    '文书树保留检查报告的明确类型标题：%s',
    (documentTitle) => {
      expect(
        resolveMedicalDocumentTitle({
          document_type: 'exam_item_report',
          source_table: 'exam_item_report',
          document_title: documentTitle,
        }),
      ).toBe(documentTitle)
    },
  )

  it('普通检查报告仍使用既有类型名称', () => {
    expect(
      resolveMedicalDocumentTitle({
        document_type: 'exam_item_report',
        source_table: 'exam_item_report',
        document_title: '检查报告',
      }),
    ).toBe('检查报告')
  })
})

describe('结构化文书类型目录', () => {
  it.each([
    ['diagnosis', 'frontpage', '诊断信息'],
    ['rescue_record', 'course.other', '抢救记录'],
    ['summary_record', 'course.other', '阶段小结'],
    ['diffcase_discussion_record', 'consultation', '疑难病例讨论记录'],
    ['presurg_summary', 'surgery', '术前小结'],
    ['postsurg_firstcourse_record', 'surgery', '术后首次病程记录'],
    ['surgery_safecheck_record', 'surgery', '手术安全核查记录单'],
    ['surgery_application', 'surgery', '手术申请单'],
    ['surgery_risk_assessment', 'surgery', '手术风险评估'],
    ['surgery_inventory_record', 'surgery', '手术物品清点记录'],
    ['preane_surveil_record', 'surgery', '麻醉术前访视记录'],
    ['postane_surveil_record', 'surgery', '麻醉术后访视记录'],
    ['anesthesia_consent', 'surgery', '麻醉知情同意书'],
    ['anesthesia_consent_form', 'surgery', '麻醉知情同意书'],
    ['surgery_inform_consent', 'surgery', '手术知情同意书'],
    ['docpat_commu_record', 'surgery', '医患沟通记录'],
    ['bloodtrans_record', 'transfusion', '输血记录'],
    ['mr_bloodtrans', 'transfusion', '输血首页摘要'],
    ['blood_transfusion_consent', 'transfusion', '输血治疗同意书'],
    ['crisis_value_record', 'exam_lab', '危急值记录'],
    ['inpat_bill_item', 'orders', '住院费用/执行明细'],
    ['handoff_record', 'handoff', '交班记录'],
    ['handover_record', 'handoff', '接班记录'],
    ['physician_change_event', 'handoff', '医师变更记录'],
    ['medical_insurance_settlement', 'frontpage', '医保结算'],
    ['medical_insurance_settlement_cost', 'frontpage', '医保结算明细'],
  ])('%s 使用固定业务目录和中文标题', (documentType, expectedGroup, expectedTitle) => {
    const document = { document_type: documentType, source_table: documentType }
    expect(resolveMedicalDocumentGroup(document).key).toBe(expectedGroup)
    expect(resolveMedicalDocumentTitle(document)).toBe(expectedTitle)
  })

  it('结构化类型优先于正文中出现的其他文书关键词', () => {
    expect(
      resolveMedicalDocumentGroup({
        document_type: 'postane_surveil_record',
        content: '患者出院前已完成会诊并继续输血。',
      }).key,
    ).toBe('surgery')
  })

  it.each([
    ['输血知情同意书', 'transfusion'],
    ['麻醉知情同意书', 'surgery'],
    ['手术知情同意书', 'surgery'],
    ['知情同意书', 'other'],
  ])('通用 consent_form 按明确标题“%s”确定目录', (title, expectedGroup) => {
    expect(resolveMedicalDocumentGroup({ document_type: 'consent_form', title }).key).toBe(
      expectedGroup,
    )
  })

  it.each([
    ['rescue_record', '抢救记录', '副主任医师主持抢救'],
    ['summary_record', '阶段小结', '主治医师审核阶段诊疗计划'],
  ])('%s 不因正文出现医师职称被误判成查房记录', (documentType, title, content) => {
    expect(resolveMedicalDocumentGroup({ document_type: documentType, title, content }).key).toBe(
      'course.other',
    )
  })
})
