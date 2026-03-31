// @ts-nocheck
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import RecordList from '@/components/medical-records/RecordList.vue'
import type { MedicalRecord } from '@/types/medical-records'

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  },
}))

describe('RecordList', () => {
  const antdStubs = {
    'a-input-search': { template: '<input />' },
    'a-select': { template: '<select><slot /></select>' },
    'a-select-option': { template: '<option><slot /></option>' },
    'a-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
    'a-dropdown': { template: '<div><slot /><slot name="overlay" /></div>' },
    'a-menu': { template: '<div><slot /></div>' },
    'a-menu-item': { template: '<div><slot /></div>' },
    'a-menu-divider': { template: '<hr />' },
    'a-tooltip': { template: '<div><slot /></div>' },
    'a-tag': { template: '<span><slot /></span>' },
    'a-table': {
      props: ['dataSource'],
      template:
        '<div><div v-for="item in dataSource" :key="item.id">{{ item.patient_name }} {{ item.qc_score }}</div></div>',
    },
  }

  const mockRecords: MedicalRecord[] = [
    {
      id: '1',
      patient_name: '张三',
      patient_age: 45,
      patient_gender: 'M',
      department: '心内科',
      admission_date: '2024-01-01',
      record_type: 'inpatient',
      content: '患者主诉胸痛3天...',
      status: 'pending',
      created_at: '2024-01-01T10:00:00Z',
      updated_at: '2024-01-01T10:00:00Z',
      qc_score: 85,
    },
    {
      id: '2',
      patient_name: '李四',
      patient_age: 32,
      patient_gender: 'F',
      department: '神经内科',
      admission_date: '2024-01-02',
      record_type: 'outpatient',
      content: '患者主诉头痛2天...',
      status: 'completed',
      created_at: '2024-01-02T10:00:00Z',
      updated_at: '2024-01-02T10:00:00Z',
      qc_score: 92,
      qc_grade: 'A',
    },
  ]

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the table shell', () => {
    const wrapper = mount(RecordList, {
      props: {
        loading: false,
      },
      global: { stubs: antdStubs },
    })

    expect(wrapper.find('.medical-records-table').exists()).toBe(true)
  })

  it('shows updated records after calling exposed method', async () => {
    const wrapper = mount(RecordList, {
      global: { stubs: antdStubs },
    })

    wrapper.vm.updateRecords(mockRecords)
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('张三')
    expect(wrapper.text()).toContain('李四')
    expect(wrapper.text()).toContain('85')
    expect(wrapper.text()).toContain('92')
  })

  it('emits search when refresh is triggered', () => {
    const wrapper = mount(RecordList, {
      global: { stubs: antdStubs },
    })

    wrapper.vm.refresh()

    expect(wrapper.emitted('search')).toBeTruthy()
  })

  it('updates the displayed total after pagination changes', async () => {
    const wrapper = mount(RecordList, {
      global: { stubs: antdStubs },
    })

    wrapper.vm.updatePagination({
      page: 2,
      pageSize: 20,
      total: 50,
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.text().replace(/\s+/g, '')).toContain('共50条记录')
  })

  it('exposes clearSelection for parent control', () => {
    const wrapper = mount(RecordList, {
      global: { stubs: antdStubs },
    })

    expect(typeof wrapper.vm.clearSelection).toBe('function')
  })
})
