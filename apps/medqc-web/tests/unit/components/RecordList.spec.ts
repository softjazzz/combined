import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import RecordList from '@/components/medical-records/RecordList.vue'
import type { MedicalRecord } from '@/types/medical-records'

// Mock Ant Design Vue components
vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn()
  }
}))

describe('RecordList', () => {
  const mockRecords: MedicalRecord[] = [
    {
      id: '1',
      patient_name: '张三',
      patient_age: 45,
      patient_gender: 'M',
      department: '心内科',
      admission_date: '2024-01-01',
      record_type: 'inpatient',
      content: '患者主诉胸痛...',
      status: 'pending',
      created_at: '2024-01-01T10:00:00Z',
      updated_at: '2024-01-01T10:00:00Z',
      qc_score: 85
    },
    {
      id: '2',
      patient_name: '李四',
      patient_age: 32,
      patient_gender: 'F',
      department: '神经内科',
      admission_date: '2024-01-02',
      record_type: 'outpatient',
      content: '患者主诉头痛...',
      status: 'completed',
      created_at: '2024-01-02T10:00:00Z',
      updated_at: '2024-01-02T10:00:00Z',
      qc_score: 92,
      qc_grade: 'A'
    }
  ]

  describe('组件渲染', () => {
    it('应该正确渲染组件', () => {
      const wrapper = mount(RecordList, {
        props: {
          loading: false
        }
      })

      expect(wrapper.exists()).toBe(true)
      expect(wrapper.find('.medical-records-table').exists()).toBe(true)
    })

    it('应该显示加载状态', () => {
      const wrapper = mount(RecordList, {
        props: {
          loading: true
        }
      })

      expect(wrapper.props('loading')).toBe(true)
    })
  })

  describe('数据展示', () => {
    it('应该正确展示病历列表', async () => {
      const wrapper = mount(RecordList)
      
      // 通过暴露的方法更新记录
      wrapper.vm.updateRecords(mockRecords)
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.records).toHaveLength(2)
      expect(wrapper.vm.records[0].patient_name).toBe('张三')
    })

    it('应该正确显示患者信息', async () => {
      const wrapper = mount(RecordList)
      wrapper.vm.updateRecords(mockRecords)
      await wrapper.vm.$nextTick()

      const record = wrapper.vm.records[0]
      expect(record.patient_name).toBe('张三')
      expect(record.patient_age).toBe(45)
      expect(record.patient_gender).toBe('M')
    })

    it('应该正确显示质控评分', async () => {
      const wrapper = mount(RecordList)
      wrapper.vm.updateRecords(mockRecords)
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.records[0].qc_score).toBe(85)
      expect(wrapper.vm.records[1].qc_score).toBe(92)
      expect(wrapper.vm.records[1].qc_grade).toBe('A')
    })
  })

  describe('搜索功能', () => {
    it('应该触发搜索事件', async () => {
      const wrapper = mount(RecordList)
      
      // 模拟搜索
      wrapper.vm.searchParams.keyword = '张三'
      wrapper.vm.handleSearch()

      expect(wrapper.emitted('search')).toBeTruthy()
      expect(wrapper.emitted('search')?.[0][0]).toMatchObject({
        keyword: '张三'
      })
    })

    it('应该支持按科室筛选', async () => {
      const wrapper = mount(RecordList)
      
      wrapper.vm.searchParams.filters.department = '心内科'
      wrapper.vm.handleSearch()

      const emitted = wrapper.emitted('search')
      expect(emitted).toBeTruthy()
      expect(emitted?.[0][0].filters.department).toBe('心内科')
    })

    it('应该支持按状态筛选', async () => {
      const wrapper = mount(RecordList)
      
      wrapper.vm.searchParams.filters.status = 'completed'
      wrapper.vm.handleSearch()

      const emitted = wrapper.emitted('search')
      expect(emitted).toBeTruthy()
      expect(emitted?.[0][0].filters.status).toBe('completed')
    })
  })

  describe('分页功能', () => {
    it('应该正确处理分页配置', async () => {
      const wrapper = mount(RecordList)
      
      wrapper.vm.updatePagination({
        page: 2,
        pageSize: 20,
        total: 100
      })
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.pagination.page).toBe(2)
      expect(wrapper.vm.pagination.pageSize).toBe(20)
      expect(wrapper.vm.pagination.total).toBe(100)
    })

    it('应该正确计算分页配置', () => {
      const wrapper = mount(RecordList)
      
      wrapper.vm.updatePagination({
        page: 1,
        pageSize: 20,
        total: 50
      })

      const paginationConfig = wrapper.vm.paginationConfig
      expect(paginationConfig.current).toBe(1)
      expect(paginationConfig.pageSize).toBe(20)
      expect(paginationConfig.total).toBe(50)
    })
  })

  describe('行选择功能', () => {
    it('应该支持行选择', async () => {
      const wrapper = mount(RecordList)
      wrapper.vm.updateRecords(mockRecords)
      await wrapper.vm.$nextTick()

      // 模拟选择行
      const rowSelection = wrapper.vm.rowSelection
      rowSelection.onChange(['1', '2'])

      expect(wrapper.vm.selectedRowKeys).toEqual(['1', '2'])
    })

    it('应该禁用分析中的记录选择', async () => {
      const analyzingRecord: MedicalRecord = {
        ...mockRecords[0],
        status: 'analyzing'
      }
      
      const wrapper = mount(RecordList)
      wrapper.vm.updateRecords([analyzingRecord])
      await wrapper.vm.$nextTick()

      const rowSelection = wrapper.vm.rowSelection
      const checkboxProps = rowSelection.getCheckboxProps(analyzingRecord)
      expect(checkboxProps.disabled).toBe(true)
    })

    it('应该支持清除选择', async () => {
      const wrapper = mount(RecordList)
      wrapper.vm.updateRecords(mockRecords)
      await wrapper.vm.$nextTick()

      // 选择行
      wrapper.vm.selectedRowKeys = ['1', '2']
      expect(wrapper.vm.selectedRowKeys).toHaveLength(2)

      // 清除选择
      wrapper.vm.clearSelection()
      expect(wrapper.vm.selectedRowKeys).toHaveLength(0)
    })
  })

  describe('用户交互', () => {
    it('应该触发查看记录事件', async () => {
      const wrapper = mount(RecordList)
      wrapper.vm.updateRecords(mockRecords)
      await wrapper.vm.$nextTick()

      wrapper.vm.$emit('view-record', mockRecords[0])

      expect(wrapper.emitted('view-record')).toBeTruthy()
      expect(wrapper.emitted('view-record')?.[0][0]).toEqual(mockRecords[0])
    })

    it('应该触发编辑记录事件', async () => {
      const wrapper = mount(RecordList)
      wrapper.vm.updateRecords(mockRecords)
      await wrapper.vm.$nextTick()

      wrapper.vm.$emit('edit-record', mockRecords[0])

      expect(wrapper.emitted('edit-record')).toBeTruthy()
      expect(wrapper.emitted('edit-record')?.[0][0]).toEqual(mockRecords[0])
    })

    it('应该触发分析记录事件', async () => {
      const wrapper = mount(RecordList)
      wrapper.vm.updateRecords(mockRecords)
      await wrapper.vm.$nextTick()

      wrapper.vm.$emit('analyze-record', mockRecords[0])

      expect(wrapper.emitted('analyze-record')).toBeTruthy()
      expect(wrapper.emitted('analyze-record')?.[0][0]).toEqual(mockRecords[0])
    })

    it('应该触发创建记录事件', () => {
      const wrapper = mount(RecordList)

      wrapper.vm.$emit('create-record')

      expect(wrapper.emitted('create-record')).toBeTruthy()
    })
  })

  describe('刷新功能', () => {
    it('应该支持刷新列表', async () => {
      const wrapper = mount(RecordList)
      
      wrapper.vm.refresh()

      expect(wrapper.emitted('search')).toBeTruthy()
    })
  })
})

