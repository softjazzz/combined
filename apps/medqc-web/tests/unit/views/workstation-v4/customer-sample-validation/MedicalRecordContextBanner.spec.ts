import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import MedicalRecordContextBanner from '@/views/workstation-v4/customer-sample-validation/MedicalRecordContextBanner.vue'

describe('MedicalRecordContextBanner', () => {
  it('统一患者、科室、病历号和住院时间，质控时间只按显式提供展示', () => {
    const context = {
      label: '样本患者 · 呼吸科 · SAMPLE-11',
      patientName: '样本患者',
      patientSex: '女',
      patientAge: 66,
      admissionTime: '2026-06-01 10:00:00',
      dischargeTime: '2026-06-10 12:00:00',
    }
    const wrapper = mount(MedicalRecordContextBanner, { props: { context } })
    expect(wrapper.findAll('.patient-context-part').map((part) => part.text())).toEqual([
      '样本患者',
      '呼吸科',
      'SAMPLE-11',
    ])
    expect(wrapper.findAll('.patient-context-time-entry').map((entry) => entry.text())).toEqual([
      '入院时间 2026-06-01 10:00:00',
      '出院时间 2026-06-10 12:00:00',
    ])
    expect(wrapper.get('img').attributes('src')).toContain('patient-icon-elder-woman')
    expect(wrapper.find('.customer-record-result-title__qc-time').exists()).toBe(false)
    wrapper.unmount()
  })

  it.each([
    [{ label: '样本', admissionTime: '2026-06-01' }, '入院时间 2026-06-01'],
    [{ label: '样本', dischargeTime: '2026-06-10' }, '出院时间 2026-06-10'],
  ])('只展示已有的住院时间，不补造缺失时间', (context, expected) => {
    const wrapper = mount(MedicalRecordContextBanner, { props: { context } })
    expect(wrapper.get('.customer-record-result-title__context-time').text()).toBe(expected)
    wrapper.unmount()
  })

  it('无上下文时安全回退，显式质控时间保持独立', () => {
    const wrapper = mount(MedicalRecordContextBanner, {
      props: { context: null, qcTimeText: '质控结束时间：2026-10-25' },
    })
    expect(wrapper.text()).toContain('病历原文与质控结果对照')
    expect(wrapper.find('.customer-record-result-title__context-time').exists()).toBe(false)
    expect(wrapper.get('.customer-record-result-title__qc-time').text()).toBe(
      '质控结束时间：2026-10-25',
    )
    wrapper.unmount()
  })
})
