import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import SettlementSheet from '../SettlementSheet.vue'

describe('SettlementSheet', () => {
  it('renders generated settlement fields in official sheet layout', () => {
    const wrapper = mount(SettlementSheet, {
      props: {
        data: {
          designated_medical_institution: '示例医院',
          institution_code: 'HOSP001',
          settlement_status: '结算草稿',
          insurance_no: 'INS-001',
          mr_no: 'MR-001',
          hospital_duration: '24',
          diagnoses: [
            {
              diagnosis_type: '门急诊诊断',
              diagnosis_name: '急性支气管炎',
              diagnosis_code: 'J20.9',
            },
            {
              diagnosis_type: '出院主要诊断',
              diagnosis_name: '肺炎',
              diagnosis_code: 'J18.9',
              admission_condition: '入院时已存在',
            },
            {
              diagnosis_type: '出院中医诊断',
              diagnosis_name: '咳嗽病',
              diagnosis_code: 'BNF010',
              admission_condition: '入院时已存在',
            },
          ],
          surgeries: [
            {
              surgery_name: '腹腔镜胆囊切除术',
              surgery_code: '51.2300',
              surgery_date: '2026-01-06',
              surgeon: '王医生',
              surgeon_code: 'SUR001',
              incision_grade: 'I/甲',
              anesthesia_method: '全身麻醉',
              anesthesiologist: '李麻醉',
              anesthesiologist_code: 'ANE001',
            },
          ],
          surgery_code_cnt: '1',
          ventilator_usetime: '49.5',
          icu_records: [
            {
              icu_type: 'ICU',
              icu_enter_time: '2026-01-05 10:30:00',
              icu_leave_time: '2026-01-07 12:00:00',
              icu_total_hours: '49.5',
            },
          ],
          blood_unit: 'mL',
          attending_physician: '赵主任',
          attending_physician_code: 'DOC001',
          total_cost: '10000',
          insurance_fund_pay: '8800',
          out_of_pocket_advance: '1200',
          out_of_pocket_amount: '1200',
          cash_payment_amount: '1200',
          western_medicine_fee: '1200',
          surgery_treatment_fee: '3000',
          other_fee: '300',
          medical_insurance_recorder: '医保办填报员',
        },
      },
    })

    const text = wrapper.text()
    expect(text).toContain('定点医疗机构名称示例医院')
    expect(text).toContain('定点医疗机构代码HOSP001')
    expect(text).toContain('医保编号INS-001')
    expect(text).toContain('病案号MR-001')
    expect(text).toContain('实际住院24天')
    expect(text).toContain('疾病代码J20.9')
    expect(text).toContain('肺炎')
    expect(text).toContain('J18.9')
    expect(text).toContain('咳嗽病')
    expect(text).toContain('BNF010')
    expect(text).toContain('腹腔镜胆囊切除术')
    expect(text).toContain('51.2300')
    expect(text).toContain('李麻醉')
    expect(text).toContain('ANE001')
    expect(text).toContain('手术及操作代码计数1')
    expect(text).toContain('呼吸机使用时间2天1小时30分钟')
    expect(text).toContain('ICU')
    expect(text).toContain('49.5')
    expect(text).toContain('输血计量单位mL')
    expect(text).toContain('主诊医师代码*DOC001')
    expect(text).toContain('医疗机构填报人医保办填报员')
    expect(text).toContain('医保统筹基金支付')
    expect(text).toContain('8800.00')
    expect(text).toContain('个人自付1200.00')
    expect(text).toContain('个人现金支付1200.00')
    expect(text).toContain('西药费')
    expect(text).toContain('手术治疗费')
    expect(text).toContain('其他费用')
  })

  it('does not use hospital name as institution code fallback', () => {
    const wrapper = mount(SettlementSheet, {
      props: {
        data: {
          designated_medical_institution: '未知医院',
          diagnoses: [],
        },
      },
    })

    expect(wrapper.text()).toContain('定点医疗机构名称未知医院')
    expect(wrapper.text()).not.toContain('定点医疗机构代码未知医院')
  })
})
