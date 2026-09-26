import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  hasRole: vi.fn(),
  listFilterTemplates: vi.fn(),
  createFilterTemplate: vi.fn(),
  updateFilterTemplate: vi.fn(),
  removeFilterTemplate: vi.fn(),
}))

vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ hasRole: mocks.hasRole }) }))
vi.mock('@/api/filterTemplates', () => ({
  listFilterTemplates: mocks.listFilterTemplates,
  createFilterTemplate: mocks.createFilterTemplate,
  updateFilterTemplate: mocks.updateFilterTemplate,
  removeFilterTemplate: mocks.removeFilterTemplate,
}))

import RecordFilterTemplateBar from '@/views/workstation-v4/components/qc/RecordFilterTemplateBar.vue'
import type { RecordFilterSnapshot } from '@/views/workstation-v4/composables/recordFilterQuery'

function template(overrides: Record<string, unknown> = {}) {
  return {
    id: 'tpl-1',
    page_key: 'v5_records_inpatient',
    name: '本科室待审核',
    filters: { dept: '心内科', review_state: ['pending_review'], date_field: 'admission' },
    is_default: false,
    version: 2,
    created_at: '2026-09-27T00:00:00Z',
    updated_at: '2026-09-27T00:00:00Z',
    ...overrides,
  }
}

function mountBar(
  options: { currentFilters?: RecordFilterSnapshot; resolveInitialFilters?: boolean } = {},
) {
  return mount(RecordFilterTemplateBar, {
    props: {
      pageKey: 'v5_records_inpatient',
      currentFilters: options.currentFilters ?? {},
      resolveInitialFilters: options.resolveInitialFilters ?? false,
    },
  })
}

function setReviewer(isReviewer: boolean) {
  mocks.hasRole.mockImplementation((role: string) =>
    isReviewer ? role === 'qc_manager' : role === 'doctor',
  )
}

function selectValue(wrapper: ReturnType<typeof mountBar>): string {
  return (wrapper.get('[data-testid="filter-template-select"]').element as HTMLSelectElement).value
}

async function selectTemplate(wrapper: ReturnType<typeof mountBar>, id: string) {
  await wrapper.get('[data-testid="filter-template-select"]').setValue(id)
  await flushPromises()
}

describe('RecordFilterTemplateBar', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setReviewer(true)
    mocks.listFilterTemplates.mockResolvedValue({ success: true, data: [] })
  })

  it('审核角色可见全部快捷筛选，非审核角色只见“全部”', async () => {
    const reviewer = mountBar()
    await flushPromises()
    expect(reviewer.findAll('[role="group"][aria-label="快捷筛选"] button').map((b) => b.text()))
      .toEqual(['全部', '待审核', '待复审', '审核中'])

    setReviewer(false)
    const doctor = mountBar()
    await flushPromises()
    expect(doctor.findAll('[role="group"][aria-label="快捷筛选"] button').map((b) => b.text()))
      .toEqual(['全部'])
  })

  it('快捷筛选只改审核状态并保留其他筛选，按当前筛选高亮', async () => {
    const wrapper = mountBar({ currentFilters: { dept: '心内科', review_state: ['pending_recheck'] } })
    await flushPromises()
    expect(wrapper.get('[data-testid="quick-filter-pending_recheck"]').attributes('aria-pressed')).toBe('true')

    await wrapper.get('[data-testid="quick-filter-reviewing"]').trigger('click')
    expect(wrapper.emitted('apply')?.at(-1)).toEqual([
      { dept: '心内科', review_state: ['pending_review', 'pending_recheck'] },
      false,
    ])
    // 审核角色显式选“全部”：要求父组件写入前端标记 review_scope=all。
    await wrapper.get('[data-testid="quick-filter-all"]').trigger('click')
    expect(wrapper.emitted('apply')?.at(-1)).toEqual([{ dept: '心内科' }, true])
  })

  it('非审核角色点“全部”不写显式标记', async () => {
    setReviewer(false)
    const wrapper = mountBar({ currentFilters: { review_state: ['approved'] } })
    await flushPromises()
    await wrapper.get('[data-testid="quick-filter-all"]').trigger('click')
    expect(wrapper.emitted('apply')?.at(-1)).toEqual([{}, false])
  })

  it.each([
    [true, { review_state: ['pending_review', 'pending_recheck'] }],
    [false, {}],
  ])('无默认模板时系统默认：审核角色=%s', async (isReviewer, expected) => {
    setReviewer(isReviewer)
    const wrapper = mountBar({ resolveInitialFilters: true })
    await flushPromises()
    expect(wrapper.emitted('apply')).toEqual([[expected, false]])
  })

  it('默认模板优先于系统默认，并只取本页筛选键', async () => {
    mocks.listFilterTemplates.mockResolvedValue({
      success: true,
      data: [template({ is_default: true })],
    })
    const wrapper = mountBar({ resolveInitialFilters: true })
    await flushPromises()
    expect(wrapper.emitted('apply')).toEqual([
      [{ dept: '心内科', review_state: ['pending_review'] }, false],
    ])
    expect(selectValue(wrapper)).toBe('tpl-1')
    expect(wrapper.text()).toContain('本科室待审核（默认）')
  })

  it('模板内容不可用（filters=null）时不当作空筛选应用，默认模板回退系统默认', async () => {
    mocks.listFilterTemplates.mockResolvedValue({
      success: true,
      data: [template({ is_default: true, filters: null })],
    })
    const wrapper = mountBar({ resolveInitialFilters: true })
    await flushPromises()
    expect(wrapper.emitted('apply')).toEqual([
      [{ review_state: ['pending_review', 'pending_recheck'] }, false],
    ])
    expect(wrapper.text()).toContain('本科室待审核（默认，内容不可用）')
    expect(wrapper.get('[role="status"]').text()).toBe('默认模板内容不可用，已按系统默认筛选')

    await selectTemplate(wrapper, 'tpl-1')
    expect(wrapper.emitted('apply')).toHaveLength(1)
    expect(wrapper.get('[data-testid="filter-template-update"]').attributes('disabled')).toBeUndefined()
  })

  it('URL 已显式给出筛选时不发出初始筛选', async () => {
    mocks.listFilterTemplates.mockResolvedValue({ success: true, data: [template({ is_default: true })] })
    const wrapper = mountBar({ resolveInitialFilters: false })
    await flushPromises()
    expect(wrapper.emitted('apply')).toBeUndefined()
  })

  it('模板加载失败不阻塞：提示不可用并按系统默认发出初始筛选，快捷筛选仍可用', async () => {
    mocks.listFilterTemplates.mockResolvedValue({ success: false, status: 503, message: '服务不可用' })
    const wrapper = mountBar({ resolveInitialFilters: true })
    await flushPromises()
    expect(wrapper.get('[data-testid="filter-template-unavailable"]').text()).toBe('筛选模板暂不可用')
    expect(wrapper.find('[data-testid="filter-template-select"]').exists()).toBe(false)
    expect(wrapper.emitted('apply')).toEqual([
      [{ review_state: ['pending_review', 'pending_recheck'] }, false],
    ])
    await wrapper.get('[data-testid="quick-filter-pending_review"]').trigger('click')
    expect(wrapper.emitted('apply')?.at(-1)).toEqual([{ review_state: ['pending_review'] }, false])
  })

  it('应用模板发出模板筛选；重置回默认模板或系统默认', async () => {
    mocks.listFilterTemplates.mockResolvedValue({ success: true, data: [template()] })
    const wrapper = mountBar()
    await flushPromises()
    await selectTemplate(wrapper, 'tpl-1')
    expect(wrapper.emitted('apply')?.at(-1)).toEqual([
      { dept: '心内科', review_state: ['pending_review'] },
      false,
    ])

    await wrapper.get('[data-testid="filter-template-reset"]').trigger('click')
    expect(wrapper.emitted('apply')?.at(-1)).toEqual([
      { review_state: ['pending_review', 'pending_recheck'] },
      false,
    ])
    expect(selectValue(wrapper)).toBe('')
  })

  it('另存为提交当前筛选与名称，成功后刷新并选中新模板', async () => {
    const created = template({ id: 'tpl-new', name: '我的筛选', filters: { keyword: '张' } })
    mocks.createFilterTemplate.mockResolvedValue({ success: true, data: created })
    const wrapper = mountBar({ currentFilters: { keyword: ' 张 ' } })
    await flushPromises()
    mocks.listFilterTemplates.mockResolvedValue({ success: true, data: [created] })

    await wrapper.get('[data-testid="filter-template-save-as"]').trigger('click')
    await wrapper.get('input[aria-label="模板名称"]').setValue('  我的筛选 ')
    await wrapper.get('input[aria-label="设为默认模板"]').setValue(true)
    await wrapper.get('[data-testid="filter-template-save-as-form"]').trigger('submit')
    await flushPromises()

    expect(mocks.createFilterTemplate).toHaveBeenCalledWith({
      page_key: 'v5_records_inpatient',
      name: '我的筛选',
      filters: { keyword: '张' },
      is_default: true,
    })
    expect(mocks.listFilterTemplates).toHaveBeenCalledTimes(2)
    expect(wrapper.find('[data-testid="filter-template-save-as-form"]').exists()).toBe(false)
    expect(selectValue(wrapper)).toBe('tpl-new')
    expect(wrapper.get('[role="status"]').text()).toBe('已保存模板「我的筛选」')
  })

  it.each([
    ['name_conflict', '已存在同名模板，请换一个名称'],
    ['limit_reached', '本页最多保存 20 个模板，请先删除不再使用的模板'],
  ])('另存为 409 %s 提示并刷新模板列表，表单保留', async (code, text) => {
    mocks.createFilterTemplate.mockResolvedValue({ success: false, status: 409, code })
    const wrapper = mountBar()
    await flushPromises()
    await wrapper.get('[data-testid="filter-template-save-as"]').trigger('click')
    await wrapper.get('input[aria-label="模板名称"]').setValue('重复')
    await wrapper.get('[data-testid="filter-template-save-as-form"]').trigger('submit')
    await flushPromises()
    expect(wrapper.get('[role="status"]').text()).toBe(text)
    expect(mocks.listFilterTemplates).toHaveBeenCalledTimes(2)
    expect(wrapper.find('[data-testid="filter-template-save-as-form"]').exists()).toBe(true)
  })

  it('更新当前模板带 version 提交当前筛选；未修改时禁用', async () => {
    mocks.listFilterTemplates.mockResolvedValue({ success: true, data: [template()] })
    mocks.updateFilterTemplate.mockResolvedValue({ success: true, data: template({ version: 3 }) })
    const wrapper = mountBar({
      currentFilters: { dept: '心内科', review_state: ['pending_review'] },
    })
    await flushPromises()
    await selectTemplate(wrapper, 'tpl-1')
    expect(wrapper.get('[data-testid="filter-template-update"]').attributes('disabled')).toBeDefined()

    await wrapper.setProps({ currentFilters: { dept: '心内科', doctor: '张医师' } })
    expect(wrapper.text()).toContain('已修改')
    await wrapper.get('[data-testid="filter-template-update"]').trigger('click')
    await flushPromises()
    expect(mocks.updateFilterTemplate).toHaveBeenCalledWith('tpl-1', {
      version: 2,
      filters: { dept: '心内科', doctor: '张医师' },
    })
    expect(wrapper.get('[role="status"]').text()).toBe('已更新模板「本科室待审核」')
  })

  it('设为默认带 version；version_conflict 提示并刷新列表', async () => {
    mocks.listFilterTemplates.mockResolvedValue({ success: true, data: [template()] })
    mocks.updateFilterTemplate.mockResolvedValue({
      success: false,
      status: 409,
      code: 'version_conflict',
    })
    const wrapper = mountBar()
    await flushPromises()
    await selectTemplate(wrapper, 'tpl-1')
    expect(wrapper.get('[data-testid="filter-template-toggle-default"]').text()).toBe('设为默认')
    await wrapper.get('[data-testid="filter-template-toggle-default"]').trigger('click')
    await flushPromises()
    expect(mocks.updateFilterTemplate).toHaveBeenCalledWith('tpl-1', {
      version: 2,
      is_default: true,
    })
    expect(wrapper.get('[role="status"]').text()).toBe(
      '模板已在别处被修改，已刷新模板列表，请确认后重试',
    )
    expect(mocks.listFilterTemplates).toHaveBeenCalledTimes(2)
  })

  it('删除需二次确认，携带 version，成功后清空当前模板', async () => {
    mocks.listFilterTemplates.mockResolvedValue({
      success: true,
      data: [template({ is_default: true })],
    })
    mocks.removeFilterTemplate.mockResolvedValue({ success: true })
    const wrapper = mountBar()
    await flushPromises()
    await selectTemplate(wrapper, 'tpl-1')
    expect(wrapper.get('[data-testid="filter-template-toggle-default"]').text()).toBe('取消默认')

    await wrapper.get('[data-testid="filter-template-delete"]').trigger('click')
    expect(mocks.removeFilterTemplate).not.toHaveBeenCalled()
    expect(wrapper.get('[data-testid="filter-template-delete-confirm"]').text()).toContain(
      '本科室待审核',
    )

    mocks.listFilterTemplates.mockResolvedValue({ success: true, data: [] })
    await wrapper.get('[data-testid="filter-template-delete-confirm"] button').trigger('click')
    await flushPromises()
    expect(mocks.removeFilterTemplate).toHaveBeenCalledWith('tpl-1', 2)
    expect(wrapper.find('[data-testid="filter-template-delete-confirm"]').exists()).toBe(false)
    expect(selectValue(wrapper)).toBe('')
    expect(wrapper.get('[role="status"]').text()).toBe('已删除模板「本科室待审核」')
  })
})
