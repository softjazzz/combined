import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import DetailHeader from '@/views/workstation-v4/components/DetailHeader.vue'
import type { PatientRecord } from '@/views/workstation-v4/types'

const record: PatientRecord = {
  id: 'VISIT-001',
  visitId: 'VISIT-001',
  bedNo: '12',
  name: '患者A',
  sex: '女',
  age: 54,
  insurance: '医保',
  department: '普通外科',
  admissionDate: '2026-06-20',
  dischargeDate: '2026-06-26',
  dischargeDatetime: '2026-06-26 08:31:00',
  days: 6,
  diagnosis: '',
  diagnosisCode: '',
  doctor: '医生A',
  status: 'completed',
}

describe('DetailHeader', () => {
  it('directly displays the full discharge datetime while retaining the date field', () => {
    const wrapper = mount(DetailHeader, {
      props: {
        record,
        currentIndex: 0,
        totalCount: 1,
        generating: false,
        hasDraft: false,
        canGenerate: false,
        disabledReason: '',
      },
      global: {
        stubs: {
          AButton: { template: '<button><slot name="icon" /><slot /></button>' },
          ATooltip: { template: '<span><slot /></span>' },
        },
      },
    })

    expect(wrapper.text()).toContain('出院时间 2026-06-26 08:31:00')
    expect(record.dischargeDate).toBe('2026-06-26')
  })
})
