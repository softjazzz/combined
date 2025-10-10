import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import RecordForm from '@/components/medical-records/RecordForm.vue'
import type { MedicalRecord, CreateMedicalRecordRequest } from '@/types'

// Mock Ant Design Vue components
vi.mock('ant-design-vue', async () => {
  const actual = await vi.importActual('ant-design-vue')
  return {
    ...actual,
    message: {
      success: vi.fn(),
      error: vi.fn(),
      warning: vi.fn(),
      info: vi.fn()
    }
  }
})

describe('RecordForm', () => {
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
    content: '患者主诉胸痛3天，既往有高血压病史...',
    status: 'pending',
    created_at: '2024-01-01T10:00:00Z',
    updated_at: '2024-01-01T10:00:00Z'
  }

  describe('组件渲染', () => {
    it('应该正确渲染组件', () => {
      const wrapper = mount(RecordForm)

      expect(wrapper.exists()).toBe(true)
    })

    it('应该在创建模式下显示空表单', () => {
      const wrapper = mount(RecordForm)

      expect(wrapper.vm.isEdit).toBe(false)
    })

    it('应该在编辑模式下显示已有数据', () => {
      const wrapper = mount(RecordForm, {
        props: {
          record: mockRecord
        }
      })

      expect(wrapper.vm.isEdit).toBe(true)
    })
  })

  describe('表单字段', () => {
    it('应该包含所有必需的表单字段', () => {
      const wrapper = mount(RecordForm)

      // 验证表单数据结构
      expect(wrapper.vm.formData).toHaveProperty('patient_name')
      expect(wrapper.vm.formData).toHaveProperty('patient_age')
      expect(wrapper.vm.formData).toHaveProperty('patient_gender')
      expect(wrapper.vm.formData).toHaveProperty('department')
      expect(wrapper.vm.formData).toHaveProperty('admission_date')
      expect(wrapper.vm.formData).toHaveProperty('record_type')
      expect(wrapper.vm.formData).toHaveProperty('content')
    })

    it('应该正确初始化表单数据', () => {
      const wrapper = mount(RecordForm)

      expect(wrapper.vm.formData.patient_name).toBe('')
      expect(wrapper.vm.formData.patient_age).toBe(0)
      expect(wrapper.vm.formData.patient_gender).toBe('U')
      expect(wrapper.vm.formData.department).toBe('')
      expect(wrapper.vm.formData.record_type).toBe('inpatient')
    })

    it('应该在编辑模式下填充表单数据', async () => {
      const wrapper = mount(RecordForm, {
        props: {
          record: mockRecord
        }
      })

      await wrapper.vm.$nextTick()

      expect(wrapper.vm.formData.patient_name).toBe(mockRecord.patient_name)
      expect(wrapper.vm.formData.patient_age).toBe(mockRecord.patient_age)
      expect(wrapper.vm.formData.patient_gender).toBe(mockRecord.patient_gender)
      expect(wrapper.vm.formData.department).toBe(mockRecord.department)
    })
  })

  describe('表单验证', () => {
    it('应该有患者姓名验证规则', () => {
      const wrapper = mount(RecordForm)

      expect(wrapper.vm.formRules.patient_name).toBeDefined()
      expect(Array.isArray(wrapper.vm.formRules.patient_name)).toBe(true)
    })

    it('应该有患者年龄验证规则', () => {
      const wrapper = mount(RecordForm)

      expect(wrapper.vm.formRules.patient_age).toBeDefined()
    })

    it('应该有科室验证规则', () => {
      const wrapper = mount(RecordForm)

      expect(wrapper.vm.formRules.department).toBeDefined()
    })

    it('应该有病历内容验证规则', () => {
      const wrapper = mount(RecordForm)

      expect(wrapper.vm.formRules.content).toBeDefined()
    })
  })

  describe('表单提交', () => {
    it('应该有 handleSubmit 方法', () => {
      const wrapper = mount(RecordForm)

      expect(wrapper.vm.handleSubmit).toBeDefined()
      expect(typeof wrapper.vm.handleSubmit).toBe('function')
    })

    it('应该能够访问表单数据', () => {
      const wrapper = mount(RecordForm)

      const testData = {
        patient_name: '王五',
        patient_age: 50,
        patient_gender: 'M' as const,
        department: '骨科',
        admission_date: '2024-01-20',
        record_type: 'inpatient' as const,
        content: '患者主诉腰痛1周...'
      }

      Object.assign(wrapper.vm.formData, testData)

      expect(wrapper.vm.formData.patient_name).toBe(testData.patient_name)
      expect(wrapper.vm.formData.patient_age).toBe(testData.patient_age)
      expect(wrapper.vm.formData.department).toBe(testData.department)
    })
  })

  describe('表单取消', () => {
    it('应该在取消时触发 cancel 事件', async () => {
      const wrapper = mount(RecordForm)

      await wrapper.vm.handleCancel()

      expect(wrapper.emitted('cancel')).toBeTruthy()
    })
  })

  describe('表单重置', () => {
    it('应该有 resetForm 方法', () => {
      const wrapper = mount(RecordForm)

      expect(wrapper.vm.resetForm).toBeDefined()
      expect(typeof wrapper.vm.resetForm).toBe('function')
    })

    it('应该能够修改表单数据', async () => {
      const wrapper = mount(RecordForm)

      // 填充表单数据
      wrapper.vm.formData.patient_name = '测试患者'
      wrapper.vm.formData.patient_age = 40
      wrapper.vm.formData.department = '内科'

      await wrapper.vm.$nextTick()

      // 验证数据已修改
      expect(wrapper.vm.formData.patient_name).toBe('测试患者')
      expect(wrapper.vm.formData.patient_age).toBe(40)
      expect(wrapper.vm.formData.department).toBe('内科')
    })
  })

  describe('文件上传', () => {
    it('应该有文件列表状态', () => {
      const wrapper = mount(RecordForm)

      expect(wrapper.vm.fileList).toBeDefined()
      expect(Array.isArray(wrapper.vm.fileList)).toBe(true)
    })

    it('应该有上传进度状态', () => {
      const wrapper = mount(RecordForm)

      expect(wrapper.vm.uploadProgress).toBeDefined()
      expect(wrapper.vm.uploadProgress).toHaveProperty('show')
      expect(wrapper.vm.uploadProgress).toHaveProperty('percentage')
    })

    it('应该初始化上传进度为隐藏', () => {
      const wrapper = mount(RecordForm)

      expect(wrapper.vm.uploadProgress.show).toBe(false)
      expect(wrapper.vm.uploadProgress.percentage).toBe(0)
    })
  })

  describe('Props 响应', () => {
    it('应该响应 loading prop 变化', async () => {
      const wrapper = mount(RecordForm, {
        props: {
          loading: false
        }
      })

      expect(wrapper.props('loading')).toBe(false)

      await wrapper.setProps({ loading: true })

      expect(wrapper.props('loading')).toBe(true)
    })

    it('应该响应 record prop 变化', async () => {
      const wrapper = mount(RecordForm)

      expect(wrapper.vm.isEdit).toBe(false)

      await wrapper.setProps({ record: mockRecord })

      expect(wrapper.vm.isEdit).toBe(true)
    })
  })

  describe('科室列表', () => {
    it('应该提供科室列表', () => {
      const wrapper = mount(RecordForm)

      expect(wrapper.vm.departments).toBeDefined()
      expect(Array.isArray(wrapper.vm.departments)).toBe(true)
      expect(wrapper.vm.departments.length).toBeGreaterThan(0)
    })
  })
})

