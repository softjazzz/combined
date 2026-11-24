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
  inheritAttrs: false,
  setup(_, { attrs, slots }) {
    return () => h('div', attrs, slots.default?.())
  },
})

const AButtonStub = defineComponent({
  inheritAttrs: false,
  setup(_, { attrs, slots }) {
    return () => h('button', attrs, slots.default?.())
  },
})

const AInputStub = defineComponent({
  props: { value: { type: String, default: '' } },
  emits: ['update:value', 'pressEnter'],
  setup(props, { emit }) {
    return () =>
      h('input', {
        class: 'catalog-search-stub',
        value: props.value,
        onInput: (e: Event) => emit('update:value', (e.target as HTMLInputElement).value),
      })
  },
})

const ASelectStub = defineComponent({
  props: { value: { type: String, default: undefined } },
  emits: ['update:value', 'change'],
  setup(props, { attrs, slots }) {
    return () => h('div', { ...attrs, 'data-value': props.value || '' }, slots.default?.())
  },
})

function mountCatalog() {
  return mount(SurgeryProcedureCatalogView, {
    global: {
      stubs: {
        ATable: ATableStub,
        'a-table': ATableStub,
        AButton: AButtonStub,
        'a-button': AButtonStub,
        AInput: AInputStub,
        'a-input': AInputStub,
        ASelect: ASelectStub,
        'a-select': ASelectStub,
        ASelectOption: passthroughStub,
        'a-select-option': passthroughStub,
        AEmpty: passthroughStub,
        'a-empty': passthroughStub,
      },
    },
  })
}

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
    const wrapper = mountCatalog()
    await flushPromises()

    expect(wrapper.text()).toContain('四级手术2337')
    expect(wrapper.text()).toContain('院内绩效分配优先')
    const table = wrapper.findComponent(ATableStub)
    expect(table.props('columns')).toHaveLength(4)
    expect(table.props('scroll')).toEqual({ x: 1020 })
    expect(table.props('tableLayout')).toBe('fixed')
    expect(wrapper.find('.catalog-table-wrap').exists()).toBe(true)
  })

  it('加载失败时退出“目录加载中”状态，展示错误提示与重试按钮', async () => {
    fetchCatalog.mockRejectedValueOnce(new Error('目录接口超时'))
    const wrapper = mountCatalog()
    await flushPromises()

    expect(wrapper.get('[data-testid="catalog-version"]').text()).toBe('目录加载失败')
    expect(wrapper.get('[data-testid="catalog-load-error"]').text()).toContain('目录接口超时')

    await wrapper.get('[data-testid="catalog-retry"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="catalog-version"]').text()).toBe(
      'luxian-surgery-procedure-2025-v1',
    )
    expect(wrapper.find('[data-testid="catalog-load-error"]').exists()).toBe(false)
  })

  it('并发筛选请求按序号防竞态，过期响应不会覆盖新结果', async () => {
    let resolveFirst!: (val: unknown) => void
    const firstPromise = new Promise((resolve) => {
      resolveFirst = resolve
    })
    fetchCatalog
      .mockReturnValueOnce(firstPromise)
      .mockResolvedValueOnce({
        version: 'v-new',
        policy: { level_priority: '', conditional_level_four: '', category_boundary: '' },
        summary: { total: 10, surgery: 8, operation: 2, level_four_surgery: 1 },
        filter_options: { categories: [], levels: [], sources: [] },
        items: [],
        total: 10,
        page: 1,
        page_size: 20,
        total_pages: 1,
      })

    const wrapper = mountCatalog()
    // 触发第二次加载
    await wrapper.get('[data-testid="catalog-summary-all"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="catalog-version"]').text()).toBe('v-new')

    // 旧请求晚到，不应覆盖 v-new
    resolveFirst({
      version: 'v-stale',
      policy: { level_priority: '', conditional_level_four: '', category_boundary: '' },
      summary: { total: 999, surgery: 999, operation: 0, level_four_surgery: 0 },
      filter_options: { categories: [], levels: [], sources: [] },
      items: [],
      total: 999,
      page: 1,
      page_size: 20,
      total_pages: 1,
    })
    await flushPromises()
    expect(wrapper.get('[data-testid="catalog-version"]').text()).toBe('v-new')
  })

  it('输入 keyword 或选择 source 筛选时“目录总数”不高亮 active', async () => {
    const wrapper = mountCatalog()
    await flushPromises()

    const allButton = wrapper.get('[data-testid="catalog-summary-all"]')
    expect(allButton.classes()).toContain('active')

    await wrapper.get('.catalog-search-stub').setValue('血肿')
    expect(allButton.classes()).not.toContain('active')

    await wrapper.get('.catalog-search-stub').setValue('')
    expect(allButton.classes()).toContain('active')

    const sourceSelect = wrapper.findAllComponents(ASelectStub)[2]
    sourceSelect.vm.$emit('update:value', 'hospital_performance')
    await flushPromises()
    expect(allButton.classes()).not.toContain('active')
  })
})
