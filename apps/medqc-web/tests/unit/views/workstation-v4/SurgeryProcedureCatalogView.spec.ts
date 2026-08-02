/* eslint-disable vue/one-component-per-file */
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SurgeryProcedureCatalogView from '@/views/workstation-v4/components/SurgeryProcedureCatalogView.vue'

const { fetchCatalog, routerPush, message } = vi.hoisted(() => ({
  fetchCatalog: vi.fn(),
  routerPush: vi.fn(),
  message: { error: vi.fn() },
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: routerPush }),
}))

vi.mock('ant-design-vue', () => ({ message }))

vi.mock('@/views/workstation-v4/surgery-catalog/service', () => ({
  fetchSurgeryProcedureCatalog: fetchCatalog,
}))

const ATableStub = defineComponent({
  name: 'ATableStub',
  props: {
    columns: { type: Array, default: () => [] },
    dataSource: { type: Array, default: () => [] },
    scroll: { type: Object, default: () => ({}) },
    tableLayout: { type: String, default: '' },
  },
  setup(props) {
    return () => h('div', { class: 'table-stub' }, `${props.dataSource.length} rows`)
  },
})

const passthroughStub = defineComponent({
  setup(_, { slots }) {
    return () => h('div', slots.default?.())
  },
})

describe('SurgeryProcedureCatalogView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    fetchCatalog.mockResolvedValue({
      version: 'luxian-surgery-procedure-2025-v1',
      policy: {
        level_priority: '院内绩效分配优先于2025年国家临床版手术分级目录',
        conditional_level_four: '条件四级按四级手术执行',
        category_boundary: '治疗性操作、诊断性操作和介入治疗不按手术触发',
      },
      summary: { total: 6509, surgery: 5947, operation: 562, level_four_surgery: 2337 },
      filter_options: {
        categories: ['手术', '治疗性操作'],
        levels: ['四级', '三级', '二级', '一级'],
        sources: [{ value: 'hospital_performance', label: '院内绩效分配' }],
      },
      items: [
        {
          code: '01.2408',
          name: '颅内血肿清除术',
          category: '手术',
          effective_level: '四级',
          raw_level: '院内四级',
          source: 'hospital_performance',
          source_label: '院内绩效分配',
        },
      ],
      total: 6509,
      page: 1,
      page_size: 20,
      total_pages: 326,
    })
  })

  it('使用全宽固定布局展示四列目录并保留客户口径说明', async () => {
    const wrapper = mount(SurgeryProcedureCatalogView, {
      global: {
        stubs: {
          ATable: ATableStub,
          'a-table': ATableStub,
          AButton: passthroughStub,
          'a-button': passthroughStub,
          AInput: passthroughStub,
          'a-input': passthroughStub,
          ASelect: passthroughStub,
          'a-select': passthroughStub,
          ASelectOption: passthroughStub,
          'a-select-option': passthroughStub,
          AEmpty: passthroughStub,
          'a-empty': passthroughStub,
        },
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('四级手术2337')
    expect(wrapper.text()).toContain('院内绩效分配优先')
    const table = wrapper.findComponent(ATableStub)
    expect(table.props('columns')).toHaveLength(4)
    expect(table.props('scroll')).toEqual({ x: 1020 })
    expect(table.props('tableLayout')).toBe('fixed')
    expect(wrapper.find('.catalog-table-wrap').exists()).toBe(true)
  })
})
