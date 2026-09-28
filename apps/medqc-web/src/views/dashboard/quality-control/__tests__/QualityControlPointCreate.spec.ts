import { flushPromises, mount } from '@vue/test-utils'
import { reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  list: vi.fn(), options: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(),
  conditionOptions: vi.fn(), conditionGet: vi.fn(), conditionUpdate: vi.fn(),
  auth: null as null | { user: { id: string; email: string } | null; userRoles: string[] },
}))

vi.mock('@/stores/auth', async () => {
  const { reactive: makeReactive } = await import('vue')
  return { useAuthStore: () => {
    if (!mocks.auth) mocks.auth = makeReactive({ user: { id: 'manager-1', email: 'm@example.com' }, userRoles: ['qc_manager'] })
    return mocks.auth
  } }
})
vi.mock('@/services/custom-rule-workspace-service', () => ({
  listWorkspaceDrafts: mocks.list,
  getDraftBasicInfoOptions: mocks.options,
  getDraftBasicInfo: mocks.get,
  createDraftBasicInfo: mocks.create,
  updateDraftBasicInfo: mocks.update,
  getDraftConditionOptions: mocks.conditionOptions,
  getDraftCondition: mocks.conditionGet,
  updateDraftCondition: mocks.conditionUpdate,
}))

import QualityControlPointCreate from '@/views/dashboard/quality-control/QualityControlPointCreate.vue'

const basicDraft = {
  id: 'draft-1', rule_code: 'CUSTOM-001', status: 'draft', updated_at: '2026-09-28T12:00:00Z',
  name: '出院记录完整性', category: '病历书写与管理基本规范', rule_type: '完整性', document_type: '出院记录',
}
const listDraft = {
  ...basicDraft, description: '', source_requirement: '', prompt_template: '', applicable_documents: ['出院记录'],
  severity: 'major', defect_level: '一般缺陷', complexity: '中复杂度', scene: 'final', generation_mode: 'fallback_template',
  examples: [], check_logic: { basic_info: { version: 1 } }, created_by: 'manager-1', created_at: '2026-09-28T12:00:00Z',
}
const visualOptions = {
  schema_version: 'visual-condition-v1',
  fields: [{ key: 'record.department', label: '当前科室', value_type: 'string', kind: 'record', operators: [{ value: 'eq', label: '等于', value_required: true }] }],
  document_types: [{ value: 'discharge_record', label: '出院记录' }],
  group_operators: ['all', 'any'], limits: { max_groups: 3, max_conditions_per_group: 4 },
  result_semantics: { true: 'non_compliant', false: 'compliant', unknown: 'data_gap' },
  timeliness: {
    start_fields: [{ value: 'record.admission_datetime', label: '入院时间' }],
    end_fields: [{ value: 'document.discharge_record.latest', label: '出院记录时间' }],
    allowed_pairs: [{ start_fact: 'record.admission_datetime', end_fact: 'document.discharge_record.latest' }],
    operators: [{ value: 'gt', label: '超过' }], units: [{ value: 'hours', label: '小时' }],
  },
}
const emptyVisualTree = {
  schema_version: 'visual-condition-v1', root_operator: 'all',
  groups: [{ id: 'group-1', operator: 'all', conditions: [] }],
}
const conditionDraft = {
  id: 'draft-1', rule_code: 'CUSTOM-001', status: 'draft', updated_at: '2026-09-28T12:00:00Z', visual_condition: null,
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

function render() {
  return mount(QualityControlPointCreate, {
    global: {
      stubs: {
        'router-link': { template: '<a><slot /></a>' },
        'a-breadcrumb': { template: '<nav><slot /></nav>' },
        'a-breadcrumb-item': { template: '<span><slot /></span>' },
        'a-alert': { props: ['message', 'description'], template: '<div class="alert">{{ message }} {{ description }}</div>' },
      },
    },
  })
}

async function fillRequired(wrapper: ReturnType<typeof render>) {
  await wrapper.get('[data-testid="draft-name"]').setValue('  新规则  ')
  await wrapper.get('[data-testid="draft-category"]').setValue('自定义质量大类')
  await wrapper.get('[data-testid="draft-rule-type"]').setValue('跨文书一致性')
  await wrapper.get('[data-testid="draft-document"]').setValue('出院记录')
}

describe('QualityControlPointCreate', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.auth = null
    mocks.options.mockResolvedValue({ success: true, data: { documents: [{ value: '出院记录', label: '出院记录' }] } })
    mocks.list.mockResolvedValue({ success: true, data: { items: [listDraft], total: 1, page: 1, page_size: 10 } })
    mocks.get.mockResolvedValue({ success: true, data: basicDraft })
    mocks.create.mockResolvedValue({ success: true, data: basicDraft, resultUnknown: false, conflict: false })
    mocks.update.mockResolvedValue({ success: true, data: { ...basicDraft, name: '已修改' }, resultUnknown: false, conflict: false })
    mocks.conditionOptions.mockResolvedValue({ success: true, data: visualOptions })
    mocks.conditionGet.mockResolvedValue({ success: true, data: conditionDraft })
    mocks.conditionUpdate.mockResolvedValue({
      success: true,
      data: { ...conditionDraft, updated_at: '2026-09-28T13:00:00Z', visual_condition: emptyVisualTree },
      resultUnknown: false, conflict: false,
    })
  })

  it('无管理权限时不读取目录和草稿且不能提交', async () => {
    mocks.auth = reactive({ user: { id: 'doctor-1', email: 'd@example.com' }, userRoles: ['doctor'] })
    const wrapper = render()
    await flushPromises()
    expect(mocks.options).not.toHaveBeenCalled()
    expect(mocks.list).not.toHaveBeenCalled()
    expect(wrapper.get('[data-testid="save-draft-basic-info"]').attributes('disabled')).toBeDefined()
    await wrapper.get('form').trigger('submit')
    expect(mocks.create).not.toHaveBeenCalled()
    expect(mocks.update).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('从真实目录选择文书并只保存四项基础信息草稿', async () => {
    const wrapper = render()
    await flushPromises()
    await fillRequired(wrapper)
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(mocks.create).toHaveBeenCalledWith({
      name: '新规则', category: '自定义质量大类', rule_type: '跨文书一致性', document_type: '出院记录',
    })
    expect(wrapper.text()).toContain('草稿 CUSTOM-001 已保存')
    expect(wrapper.text()).toContain('缺陷触发条件')
    expect(wrapper.text()).not.toContain('保存并下一步')
  })

  it('四项不完整或文书不在服务端目录时不发送写请求', async () => {
    const wrapper = render()
    await flushPromises()
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('请完整填写')
    expect(mocks.create).not.toHaveBeenCalled()
  })

  it('打开basic_info草稿按服务端回读并使用updated_at做CAS更新', async () => {
    const wrapper = render()
    await flushPromises()
    await wrapper.get('[data-testid="open-draft-draft-1"]').trigger('click')
    await flushPromises()
    expect((wrapper.get('[data-testid="draft-name"]').element as HTMLInputElement).value).toBe('出院记录完整性')
    await wrapper.get('[data-testid="draft-name"]').setValue('已修改')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mocks.update).toHaveBeenCalledWith('draft-1', expect.objectContaining({
      name: '已修改', expected_updated_at: '2026-09-28T12:00:00Z',
    }))
  })

  it('未配置条件只显示本地空组，保存后才提交visual_condition与CAS', async () => {
    const wrapper = render()
    await flushPromises()
    await wrapper.get('[data-testid="open-draft-draft-1"]').trigger('click')
    await flushPromises()
    expect(mocks.conditionGet).toHaveBeenCalledWith('draft-1')
    await wrapper.get('[data-testid="save-visual-condition"]').trigger('click')
    expect(wrapper.text()).toContain('条件组不能为空')
    await wrapper.find('.group-actions button').trigger('click')
    const selects = wrapper.findAll('.condition-row select')
    await selects[1].setValue('record.department')
    await selects[2].setValue('eq')
    await wrapper.get('input[aria-label="比较值"]').setValue('内科')
    await wrapper.get('[data-testid="save-visual-condition"]').trigger('click')
    await flushPromises()
    expect(mocks.conditionUpdate).toHaveBeenCalledWith('draft-1', {
      expected_updated_at: '2026-09-28T12:00:00Z',
      visual_condition: expect.objectContaining({ schema_version: 'visual-condition-v1' }),
    })
    expect(wrapper.text()).toContain('缺陷触发条件已保存')
  })

  it('条件有未保存修改时阻止基础信息保存，避免重载丢失', async () => {
    const wrapper = render()
    await flushPromises()
    await wrapper.get('[data-testid="open-draft-draft-1"]').trigger('click')
    await flushPromises()
    await wrapper.find('.group-actions button').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="draft-name"]').setValue('不应提交的名称')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mocks.update).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('请先保存条件配置后再修改基础信息')
    expect(wrapper.find('.condition-row').exists()).toBe(true)
  })

  it('切换账号后丢弃旧账号迟到的条件详情', async () => {
    const pending = deferred<{ success: true; data: typeof conditionDraft }>()
    mocks.conditionGet.mockReturnValueOnce(pending.promise)
    const wrapper = render()
    await flushPromises()
    await wrapper.get('[data-testid="open-draft-draft-1"]').trigger('click')
    await Promise.resolve()
    if (!mocks.auth) throw new Error('auth missing')
    mocks.auth.user = reactive({ id: 'manager-2', email: 'm2@example.com' })
    await flushPromises()
    pending.resolve({ success: true, data: conditionDraft })
    await flushPromises()
    expect(wrapper.find('[data-testid="save-visual-condition"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('条件组 1')
  })

  it('条件保存未知结果禁重复，角色变化后旧成功不落地', async () => {
    mocks.conditionUpdate.mockResolvedValueOnce({ success: false, message: '条件保存结果未知', resultUnknown: true, conflict: false })
    const wrapper = render()
    await flushPromises()
    await wrapper.get('[data-testid="open-draft-draft-1"]').trigger('click')
    await flushPromises()
    await wrapper.find('.group-actions button').trigger('click')
    const selects = wrapper.findAll('.condition-row select')
    await selects[1].setValue('record.department')
    await selects[2].setValue('eq')
    await wrapper.get('input[aria-label="比较值"]').setValue('内科')
    await wrapper.get('[data-testid="save-visual-condition"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('条件保存结果未知')
    expect(wrapper.get('[data-testid="save-visual-condition"]').attributes('disabled')).toBeDefined()
    wrapper.unmount()

    const pending = deferred<{
      success: true
      data: typeof conditionDraft & { visual_condition: typeof emptyVisualTree }
      resultUnknown: false
      conflict: false
    }>()
    mocks.conditionUpdate.mockReturnValueOnce(pending.promise)
    const editing = render()
    await flushPromises()
    await editing.get('[data-testid="open-draft-draft-1"]').trigger('click')
    await flushPromises()
    await editing.find('.group-actions button').trigger('click')
    const editingSelects = editing.findAll('.condition-row select')
    await editingSelects[1].setValue('record.department')
    await editingSelects[2].setValue('eq')
    await editing.get('input[aria-label="比较值"]').setValue('内科')
    await editing.get('[data-testid="save-visual-condition"]').trigger('click')
    if (!mocks.auth) throw new Error('auth missing')
    mocks.auth.userRoles = reactive(['admin'])
    await flushPromises()
    pending.resolve({
      success: true,
      data: { ...conditionDraft, updated_at: '2026-09-28T13:00:00Z', visual_condition: emptyVisualTree },
      resultUnknown: false, conflict: false,
    })
    await flushPromises()
    expect(editing.text()).not.toContain('缺陷触发条件已保存')
  })

  it('旧workspace草稿只展示且不冒充可编辑基础信息草稿', async () => {
    mocks.list.mockResolvedValue({
      success: true,
      data: { items: [{ ...listDraft, id: 'legacy', category: undefined, rule_type: undefined, check_logic: {} }], total: 1, page: 1, page_size: 10 },
    })
    const wrapper = render()
    await flushPromises()
    expect(wrapper.text()).toContain('旧草稿不可在此编辑')
    expect(wrapper.find('[data-testid="open-draft-legacy"]').exists()).toBe(false)
    expect(mocks.get).not.toHaveBeenCalled()
  })

  it('未知写结果锁定重复提交，CAS冲突要求重新读取', async () => {
    mocks.create.mockResolvedValue({ success: false, message: '结果未知', resultUnknown: true, conflict: false })
    const wrapper = render()
    await flushPromises()
    await fillRequired(wrapper)
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.find('[data-testid="draft-result-unknown"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="save-draft-basic-info"]').attributes('disabled')).toBeDefined()

    wrapper.unmount()
    mocks.create.mockResolvedValue({ success: true, data: basicDraft, resultUnknown: false, conflict: false })
    mocks.update.mockResolvedValue({ success: false, message: '版本冲突', resultUnknown: false, conflict: true })
    const editing = render()
    await flushPromises()
    await editing.get('[data-testid="open-draft-draft-1"]').trigger('click')
    await flushPromises()
    await editing.get('form').trigger('submit')
    await flushPromises()
    expect(editing.text()).toContain('版本冲突')
    expect(editing.get('[data-testid="save-draft-basic-info"]').attributes('disabled')).toBeDefined()
  })

  it('账号变化后旧列表迟到响应不能落地', async () => {
    const pending = deferred<{
      success: true
      data: { items: Array<typeof listDraft>; total: number; page: number; page_size: number }
    }>()
    mocks.list.mockReturnValueOnce(pending.promise).mockResolvedValueOnce({ success: true, data: { items: [], total: 0, page: 1, page_size: 10 } })
    const wrapper = render()
    await Promise.resolve()
    if (!mocks.auth) throw new Error('auth missing')
    mocks.auth.user = reactive({ id: 'manager-2', email: 'm2@example.com' })
    await flushPromises()
    pending.resolve({ success: true, data: { items: [listDraft], total: 1, page: 1, page_size: 10 } })
    await flushPromises()
    expect(wrapper.text()).not.toContain('CUSTOM-001')
  })

  it('同账号两次列表请求后发先回时不被旧页覆盖', async () => {
    const oldList = deferred<{
      success: true
      data: { items: Array<typeof listDraft>; total: number; page: number; page_size: number }
    }>()
    mocks.list
      .mockReturnValueOnce(oldList.promise)
      .mockResolvedValueOnce({ success: true, data: { items: [], total: 0, page: 1, page_size: 10 } })
    const wrapper = render()
    await flushPromises()
    await fillRequired(wrapper)
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    oldList.resolve({ success: true, data: { items: [listDraft], total: 1, page: 1, page_size: 10 } })
    await flushPromises()
    expect(mocks.list).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('共 0 条')
    expect(wrapper.find('.draft-table-wrap').exists()).toBe(false)
  })

  it('读取草稿期间新建另一条后丢弃旧详情迟到回执', async () => {
    const wrapper = render()
    await flushPromises()
    await wrapper.get('[data-testid="open-draft-draft-1"]').trigger('click')
    await flushPromises()

    const pendingDetail = deferred<{ success: true; data: typeof basicDraft }>()
    mocks.get.mockReturnValueOnce(pendingDetail.promise)
    await wrapper.get('[data-testid="open-draft-draft-1"]').trigger('click')
    await Promise.resolve()
    const newButton = wrapper.findAll('button').find((button) => button.text() === '新建另一条')
    if (!newButton) throw new Error('缺少新建另一条按钮')
    await newButton.trigger('click')
    pendingDetail.resolve({ success: true, data: { ...basicDraft, name: '迟到草稿' } })
    await flushPromises()

    expect((wrapper.get('[data-testid="draft-name"]').element as HTMLInputElement).value).toBe('')
    expect(wrapper.text()).not.toContain('迟到草稿')
    expect(wrapper.find('.draft-code').exists()).toBe(false)
  })

  it('保存期间角色变化后旧成功回执不改写页面或触发额外刷新', async () => {
    const pendingCreate = deferred<{
      success: true
      data: typeof basicDraft
      resultUnknown: false
      conflict: false
    }>()
    mocks.list.mockResolvedValue({ success: true, data: { items: [], total: 0, page: 1, page_size: 10 } })
    mocks.create.mockReturnValueOnce(pendingCreate.promise)
    const wrapper = render()
    await flushPromises()
    await fillRequired(wrapper)
    await wrapper.get('form').trigger('submit')
    await Promise.resolve()

    if (!mocks.auth) throw new Error('auth missing')
    mocks.auth.userRoles = reactive(['admin'])
    await flushPromises()
    pendingCreate.resolve({ success: true, data: basicDraft, resultUnknown: false, conflict: false })
    await flushPromises()

    expect(wrapper.text()).not.toContain('草稿 CUSTOM-001 已保存')
    expect((wrapper.get('[data-testid="draft-name"]').element as HTMLInputElement).value).toBe('')
    expect(mocks.list).toHaveBeenCalledTimes(2)
  })

  it('文书目录失败后可通过刷新草稿重试', async () => {
    mocks.options
      .mockResolvedValueOnce({ success: false, message: '文书目录暂不可用' })
      .mockResolvedValueOnce({ success: true, data: { documents: [{ value: '出院记录', label: '出院记录' }] } })
    const wrapper = render()
    await flushPromises()
    expect(wrapper.text()).toContain('文书目录暂不可用')
    expect(wrapper.get('[data-testid="draft-document"]').attributes('disabled')).toBeDefined()

    await wrapper.get('button[title="刷新草稿"]').trigger('click')
    await flushPromises()
    expect(mocks.options).toHaveBeenCalledTimes(2)
    expect(wrapper.get('[data-testid="draft-document"]').attributes('disabled')).toBeUndefined()
  })

  it('非管理角色不读取目录或草稿且不能提交', async () => {
    mocks.auth = reactive({ user: { id: 'staff-1', email: 'staff@example.com' }, userRoles: ['qc_staff'] })
    const wrapper = render()
    await flushPromises()

    expect(mocks.options).not.toHaveBeenCalled()
    expect(mocks.list).not.toHaveBeenCalled()
    expect(wrapper.get('[data-testid="draft-name"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="save-draft-basic-info"]').attributes('disabled')).toBeDefined()
    await wrapper.get('form').trigger('submit')
    expect(mocks.create).not.toHaveBeenCalled()
  })
})
