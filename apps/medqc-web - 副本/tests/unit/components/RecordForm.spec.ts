// @ts-nocheck
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import RecordForm from '@/components/medical-records/RecordForm.vue'
import type { MedicalRecord } from '@/types'

vi.mock('ant-design-vue', async () => {
  const actual = await vi.importActual('ant-design-vue')
  return {
    ...actual,
    message: {
      success: vi.fn(),
      error: vi.fn(),
      warning: vi.fn(),
      info: vi.fn(),
    },
  }
})

describe('RecordForm', () => {
  const antdStubs = {
    'a-form': { template: '<form><slot /></form>' },
    'a-form-item': { template: '<div><slot /></div>' },
    'a-input': { template: '<input />' },
    'a-input-number': { template: '<input type="number" />' },
    'a-select': { template: '<select><slot /></select>' },
    'a-select-option': { template: '<option><slot /></option>' },
    'a-date-picker': { template: '<input type="date" />' },
    'a-upload-dragger': { template: '<div><slot /></div>' },
    'a-progress': { template: '<div />' },
    'a-textarea': { template: '<textarea />' },
    'a-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
  }

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  const mockRecord: MedicalRecord = {
    id: 'record-001',
    patient_name: '张三',
    patient_age: 45,
    patient_gender: 'M',
    department: '心内科',
    admission_date: '2024-01-01',
    record_type: 'inpatient',
    content: '患者主诉胸痛3天',
    status: 'pending',
    created_at: '2024-01-01T10:00:00Z',
    updated_at: '2024-01-01T10:00:00Z',
  }

  const findButton = (wrapper: ReturnType<typeof mount>, label: string) =>
    wrapper.findAll('button').find((button) => button.text().includes(label))

  it('renders create mode by default', () => {
    const wrapper = mount(RecordForm, {
      global: { stubs: antdStubs },
    })

    expect(wrapper.text()).toContain('患者基本信息')
    expect(wrapper.text()).toContain('病案内容')
    expect(wrapper.text()).toContain('创建记录')
  })

  it('switches button label in edit mode', () => {
    const wrapper = mount(RecordForm, {
      props: {
        record: mockRecord,
      },
      global: { stubs: antdStubs },
    })

    expect(wrapper.text()).toContain('更新记录')
  })

  it('emits cancel when cancel button is clicked', async () => {
    const wrapper = mount(RecordForm, {
      global: { stubs: antdStubs },
    })
    const cancelButton = findButton(wrapper, '取消')

    expect(cancelButton).toBeTruthy()
    await cancelButton!.trigger('click')

    expect(wrapper.emitted('cancel')).toBeTruthy()
  })

  it('exposes resetForm for parent control', () => {
    const wrapper = mount(RecordForm, {
      global: { stubs: antdStubs },
    })

    expect(typeof wrapper.vm.resetForm).toBe('function')
  })
})
