import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  listFilterTemplates: vi.fn(),
  createFilterTemplate: vi.fn(),
  updateFilterTemplate: vi.fn(),
  removeFilterTemplate: vi.fn(),
  setOwner: undefined as undefined | ((id: string | null) => void),
}))

vi.mock('@/api/filterTemplates', () => api)
vi.mock('@/stores/auth', async () => {
  const { reactive } = await import('vue')
  const store = reactive<{ user: { id: string } | null }>({ user: { id: 'user-1' } })
  api.setOwner = (id: string | null) => {
    store.user = id ? { id } : null
  }
  return { useAuthStore: () => store }
})

import OutpatientFilterTemplateBar from '@/views/dashboard/records/OutpatientFilterTemplateBar.vue'

enableAutoUnmount(afterEach)

function template(overrides: Record<string, unknown> = {}) {
  return {
    id: 'template-1',
    page_key: 'v5_records_outpatient_emergency',
    name: '本科室本周',
    filters: {
      keyword: '张三',
      dept: '急诊科',
      start_date: '2026-09-21',
      end_date: '2026-09-27',
      date_field: 'visit',
    },
    is_default: false,
    version: 3,
    created_at: '2026-09-27T00:00:00Z',
    updated_at: '2026-09-27T00:00:00Z',
    ...overrides,
  }
}

function mountBar(currentFilters: Record<string, string> = {}) {
  return mount(OutpatientFilterTemplateBar, { props: { currentFilters } })
}

describe('OutpatientFilterTemplateBar', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.listFilterTemplates.mockResolvedValue({ success: true, data: [] })
    api.createFilterTemplate.mockResolvedValue({ success: true, data: template() })
    api.updateFilterTemplate.mockResolvedValue({ success: true, data: template() })
    api.removeFilterTemplate.mockResolvedValue({ success: true, data: { deleted: true } })
    api.setOwner?.('user-1')
  })

  it('只读取门急诊命名空间，并在进入页面时应用有效默认模板', async () => {
    api.listFilterTemplates.mockResolvedValue({
      success: true,
      data: [template({ is_default: true })],
    })
    const wrapper = mountBar()
    await flushPromises()

    expect(api.listFilterTemplates).toHaveBeenCalledWith('v5_records_outpatient_emergency')
    expect(wrapper.emitted('apply')?.at(-1)).toEqual([{
      keyword: '张三',
      department: '急诊科',
      start_date: '2026-09-21',
      end_date: '2026-09-27',
    }])
  })

  it('新建模板只保存页面真实字段，固定使用就诊日期并保持独立 page_key', async () => {
    const wrapper = mountBar({
      keyword: '  李四  ',
      department: '门诊内科',
      start_date: '2026-09-01',
      end_date: '2026-09-02',
    })
    await flushPromises()
    await wrapper.get('[data-testid="outpatient-filter-template-save-as"]').trigger('click')
    await wrapper.get('input[aria-label="门急诊筛选模板名称"]').setValue(' 我的筛选 ')
    await wrapper.get('[data-testid="outpatient-filter-template-form"]').trigger('submit')
    await flushPromises()

    expect(api.createFilterTemplate).toHaveBeenCalledWith({
      page_key: 'v5_records_outpatient_emergency',
      name: '我的筛选',
      filters: {
        keyword: '李四',
        dept: '门诊内科',
        start_date: '2026-09-01',
        end_date: '2026-09-02',
        date_field: 'visit',
      },
      is_default: false,
    })
  })

  it('快捷应用、保存修改和重置均使用当前模板，更新携带 CAS version', async () => {
    api.listFilterTemplates.mockResolvedValue({ success: true, data: [template()] })
    const wrapper = mountBar({ keyword: '已修改' })
    await flushPromises()

    await wrapper.get('[data-testid="outpatient-filter-template-select"]').setValue('template-1')
    expect(wrapper.emitted('apply')?.at(-1)?.[0]).toMatchObject({
      keyword: '张三',
      department: '急诊科',
    })

    await wrapper.setProps({ currentFilters: { keyword: '已修改', department: '急诊科' } })
    await wrapper.get('[data-testid="outpatient-filter-template-update"]').trigger('click')
    await flushPromises()
    expect(api.updateFilterTemplate).toHaveBeenCalledWith('template-1', {
      version: 3,
      filters: {
        keyword: '已修改',
        dept: '急诊科',
        start_date: undefined,
        end_date: undefined,
        date_field: 'visit',
      },
    })

    await wrapper.get('[data-testid="outpatient-filter-template-reset"]').trigger('click')
    expect(wrapper.emitted('apply')?.at(-1)).toEqual([{}])
  })

  it('内容含其他页面字段时失败关闭，不应用为门急诊条件', async () => {
    api.listFilterTemplates.mockResolvedValue({
      success: true,
      data: [template({
        filters: { review_state: ['pending_review'], date_field: 'visit' },
        is_default: true,
      })],
    })
    const wrapper = mountBar()
    await flushPromises()

    expect(wrapper.emitted('apply')).toBeUndefined()
    expect(wrapper.text()).toContain('默认模板内容不可用')
    await wrapper.get('[data-testid="outpatient-filter-template-select"]').setValue('template-1')
    expect(wrapper.text()).toContain('不适用于门急诊筛选')
    expect(wrapper.emitted('apply')).toBeUndefined()
  })

  it('设默认和删除均携带当前版本', async () => {
    api.listFilterTemplates.mockResolvedValue({ success: true, data: [template()] })
    const wrapper = mountBar()
    await flushPromises()
    await wrapper.get('[data-testid="outpatient-filter-template-select"]').setValue('template-1')

    await wrapper.get('[data-testid="outpatient-filter-template-default"]').trigger('click')
    await flushPromises()
    expect(api.updateFilterTemplate).toHaveBeenCalledWith('template-1', {
      version: 3,
      is_default: true,
    })

    await wrapper.get('[data-testid="outpatient-filter-template-delete"]').trigger('click')
    await wrapper.get('[data-testid="outpatient-filter-template-delete-confirm"] button').trigger('click')
    await flushPromises()
    expect(api.removeFilterTemplate).toHaveBeenCalledWith('template-1', 3)
  })

  it('模板服务失败时明确显示不可用，不伪造空模板', async () => {
    api.listFilterTemplates.mockResolvedValue({ success: false, status: 503 })
    const wrapper = mountBar()
    await flushPromises()

    expect(wrapper.text()).toContain('筛选模板暂不可用')
    expect(wrapper.find('[data-testid="outpatient-filter-template-select"]').exists()).toBe(false)
    expect(wrapper.emitted('apply')).toBeUndefined()
  })

  it('账号切换时丢弃旧账号迟到响应并重新读取，退出时清空模板', async () => {
    let resolveOld!: (value: unknown) => void
    const oldRequest = new Promise((resolve) => { resolveOld = resolve })
    api.listFilterTemplates
      .mockReturnValueOnce(oldRequest)
      .mockResolvedValueOnce({ success: true, data: [template({ id: 'user-2-template' })] })
    const wrapper = mountBar()

    api.setOwner?.('user-2')
    await flushPromises()
    expect(api.listFilterTemplates).toHaveBeenCalledTimes(2)
    expect(wrapper.get('[data-testid="outpatient-filter-template-select"]').text()).toContain('本科室本周')

    resolveOld({ success: true, data: [template({ id: 'old-template', name: '旧账号模板' })] })
    await flushPromises()
    expect(wrapper.text()).not.toContain('旧账号模板')

    api.setOwner?.(null)
    await flushPromises()
    expect(wrapper.text()).toContain('暂无模板')
    expect(api.listFilterTemplates).toHaveBeenCalledTimes(2)
  })
})
