import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ScoringStandardDetail, ScoringStandardItem } from '@/api/scoring'

const state = vi.hoisted(() => ({
  roles: ['qc_manager'] as string[],
  message: { success: vi.fn(), warning: vi.fn(), info: vi.fn(), error: vi.fn() },
  api: {
    listScoringStandards: vi.fn(),
    getScoringStandard: vi.fn(),
    createScoringStandard: vi.fn(),
    updateScoringStandard: vi.fn(),
    saveScoringItems: vi.fn(),
    copyScoringStandard: vi.fn(),
    activateScoringStandard: vi.fn(),
    setDefaultScoringStandard: vi.fn(),
    archiveScoringStandard: vi.fn(),
    deleteScoringStandard: vi.fn(),
    exportScoringStandard: vi.fn(),
    importScoringStandard: vi.fn(),
  },
  rules: {
    listRuleSetVersions: vi.fn(),
    getRuleSetVersion: vi.fn(),
  },
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ hasRole: (role: string) => state.roles.includes(role) }),
}))
vi.mock('ant-design-vue', () => ({ message: state.message }))
vi.mock('@/api/scoring', () => state.api)
vi.mock('@/api/ruleSetVersions', () => state.rules)

import ScoringStandardsView from '@/views/qc/ScoringStandardsView.vue'

const KEY = 'luxian_0609_qc_v1'
const catalog = [
  { scene: 'running', rule_sets: [{ rule_set_key: KEY, rule_set_name: '泸县0609' }] },
  {
    scene: 'final',
    rule_sets: [
      { rule_set_key: 'sichuan_final_v1', rule_set_name: '终末病历规则' },
      { rule_set_key: KEY, rule_set_name: '泸县0609' },
    ],
  },
  { scene: 'outpatient', rule_sets: [] },
]
const bands = [
  { name: '甲', min_score: 90, max_score: 100 },
  { name: '乙', min_score: 75, max_score: 90 },
  { name: '丙', min_score: 0, max_score: 75 },
]

function standard(overrides: Partial<ScoringStandardItem> = {}): ScoringStandardItem {
  return {
    id: 'd1', name: '草稿标准', scene: 'running', rule_set_key: KEY, status: 'draft', is_default: false,
    base_score: 100, grade_bands: bands, veto_grade: '丙', version_seq: 2,
    created_by: 'u1', created_at: '2026-09-27T01:00:00', updated_by: 'u1', updated_at: '2026-09-27T01:00:00',
    activated_by: null, activated_at: null,
    ...overrides,
  }
}

const active = standard({ id: 'a1', name: '启用标准', status: 'active', is_default: true, version_seq: 3 })
const activeNonDefault = standard({
  id: 'a2', name: '原默认标准', status: 'active', is_default: false, version_seq: 6,
})
const draft = standard()
const archived = standard({ id: 'x1', name: '归档标准', status: 'archived', version_seq: 5 })

function detailOf(item: ScoringStandardItem, overrides: Partial<ScoringStandardDetail> = {}): ScoringStandardDetail {
  const groups = [{ group_name: '病程记录', max_deduction: 10, sort_order: 1 }]
  const items = [
    { group_name: '病程记录', rule_id: 'LX0609-001', deduction: 2, is_veto: false, enabled: true },
    { group_name: '病程记录', rule_id: 'LX0609-002', deduction: 3, is_veto: true, enabled: true },
  ]
  return { ...item, groups, items, group_count: 1, item_count: 2, ...overrides }
}

const ok = <T>(data: T) => ({ success: true, data, status: 200 })

const inputStub = {
  props: ['value', 'disabled'],
  emits: ['update:value'],
  template: '<input :value="value" :disabled="disabled" @input="$emit(\'update:value\', $event.target.value)" />',
}

const stubs = {
  'a-tabs': {
    props: ['activeKey'],
    emits: ['update:activeKey'],
    template: `<div class="tabs" :data-active="activeKey">
      <button v-for="key in ['running', 'final', 'outpatient']" :key="key" :class="'tab-' + key" @click="$emit('update:activeKey', key)">{{ key }}</button>
      <slot />
    </div>`,
  },
  'a-tab-pane': { props: ['tab'], template: '<span class="tab-label">{{ tab }}</span>' },
  'a-alert': { props: ['message'], template: '<div class="alert">{{ message }}<slot name="description" /></div>' },
  'a-button': {
    props: ['disabled', 'loading'],
    emits: ['click'],
    template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
  },
  'a-popconfirm': {
    emits: ['confirm'],
    template: '<span class="pop"><slot /><button class="pop-ok" @click="$emit(\'confirm\')">确认</button></span>',
  },
  'a-modal': {
    props: ['open', 'title'],
    emits: ['ok', 'cancel'],
    template: '<div v-if="open" class="modal"><h4>{{ title }}</h4><slot /><button class="modal-ok" @click="$emit(\'ok\')">确定</button></div>',
  },
  'a-drawer': { props: ['open', 'title'], template: '<div v-if="open" class="drawer"><h3>{{ title }}</h3><slot /></div>' },
  'a-input': inputStub,
  'a-input-number': {
    props: ['value', 'disabled'],
    emits: ['update:value'],
    template: '<input type="number" :value="value ?? \'\'" :disabled="disabled" @input="$emit(\'update:value\', $event.target.value === \'\' ? null : Number($event.target.value))" />',
  },
  'a-select': {
    props: ['value', 'options', 'disabled'],
    emits: ['update:value'],
    template: '<select :value="value" :disabled="disabled" @change="$emit(\'update:value\', $event.target.value)"><option v-for="o in options || []" :key="o.value" :value="o.value">{{ o.label }}</option></select>',
  },
  'a-checkbox': {
    props: ['checked', 'disabled'],
    emits: ['update:checked'],
    template: '<input type="checkbox" :checked="checked" :disabled="disabled" @change="$emit(\'update:checked\', $event.target.checked)" />',
  },
  'a-radio-group': {
    props: ['value'],
    emits: ['update:value'],
    template: `<div class="radio-group" :data-value="value">
      <button class="mode-archive" @click="$emit('update:value', 'archive')">archive</button>
      <button class="mode-undefault" @click="$emit('update:value', 'undefault')">undefault</button>
      <slot />
    </div>`,
  },
  'a-radio': { template: '<label><slot /></label>' },
}

async function render(): Promise<VueWrapper> {
  const wrapper = mount(ScoringStandardsView, { global: { stubs } })
  await flushPromises()
  return wrapper
}

function row(wrapper: VueWrapper, id: string) {
  return wrapper.get(`[data-testid="scoring-standard-row"][data-id="${id}"]`)
}

async function openEditor(wrapper: VueWrapper, id: string) {
  await row(wrapper, id).get('[data-testid="scoring-action-open"]').trigger('click')
  await flushPromises()
}

describe('ScoringStandardsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    state.roles = ['qc_manager']
    state.api.listScoringStandards.mockImplementation(async ({ scene }: { scene: string }) =>
      ok({ items: scene === 'running' ? [active, draft, archived] : [], scenes: catalog }),
    )
    state.api.getScoringStandard.mockImplementation(async (id: string) => {
      const source = [active, activeNonDefault, draft, archived].find((item) => item.id === id) ?? draft
      return ok(detailOf(source))
    })
    state.api.exportScoringStandard.mockResolvedValue({ success: false, message: '未配置导出' })
    state.api.importScoringStandard.mockResolvedValue({
      success: false, message: '未配置导入', problems: [], resultUnknown: false,
    })
    state.rules.listRuleSetVersions.mockResolvedValue(ok({ rule_set_key: KEY, current_version: '2026-06-09' }))
    state.rules.getRuleSetVersion.mockResolvedValue(ok({
      entries: [
        { rule_id: 'LX0609-001', state: 'active', executable: true, qc_point: '入院记录完整性', source_document: null },
        { rule_id: 'LX0609-002', state: 'active', executable: true, qc_point: null, source_document: null },
        { rule_id: 'LX0609-003', state: 'paused', executable: true, qc_point: '首次病程及时性', source_document: null },
      ],
    }))
  })

  it('按场景读取列表：名称、状态、默认、满分、档位与更新时间', async () => {
    const wrapper = await render()
    expect(state.api.listScoringStandards).toHaveBeenCalledWith({ scene: 'running' })
    expect(wrapper.findAll('[data-testid="scoring-standard-row"]')).toHaveLength(3)
    const activeRow = row(wrapper, 'a1')
    expect(activeRow.text()).toContain('启用标准')
    expect(activeRow.get('[data-testid="scoring-standard-status"]').text()).toBe('启用中')
    expect(activeRow.get('[data-testid="scoring-standard-default"]').text()).toBe('默认')
    expect(activeRow.text()).toContain('甲 90–100 · 乙 75–90 · 丙 0–75')
    expect(activeRow.text()).toMatch(/2026-09-2\d \d{2}:\d{2}/u)
    expect(row(wrapper, 'd1').get('[data-testid="scoring-standard-status"]').text()).toBe('草稿')
    expect(row(wrapper, 'x1').get('[data-testid="scoring-standard-status"]').text()).toBe('已归档')
    expect(wrapper.get('[data-testid="scoring-default-name"]').text()).toBe('启用标准')
    // 启用中只能复制/归档，草稿才能启用/删除。
    expect(row(wrapper, 'a1').find('[data-testid="scoring-action-activate"]').exists()).toBe(false)
    expect(row(wrapper, 'a1').find('[data-testid="scoring-action-delete"]').exists()).toBe(false)
    expect(row(wrapper, 'd1').find('[data-testid="scoring-action-archive"]').exists()).toBe(false)
    expect(row(wrapper, 'x1').find('[data-testid="scoring-action-archive"]').exists()).toBe(false)
  })

  it('门急诊无可用规则集：提示且不可新建；空场景显示未配置默认标准', async () => {
    const wrapper = await render()
    await wrapper.get('.tab-outpatient').trigger('click')
    await flushPromises()
    expect(state.api.listScoringStandards).toHaveBeenLastCalledWith({ scene: 'outpatient' })
    expect(wrapper.get('[data-testid="scoring-scene-unavailable"]').text()).toContain('门急诊暂无可用规则集')
    expect(wrapper.get('[data-testid="scoring-create"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="scoring-default-name"]').text()).toBe('未配置评分标准')
    expect(wrapper.text()).toContain('该场景暂无评分标准')
  })

  it('新建草稿：默认三档起步，按场景与规则集提交后打开编辑', async () => {
    state.api.createScoringStandard.mockResolvedValue(ok(detailOf(standard({ id: 'new-1', name: '新标准' }))))
    const wrapper = await render()
    await wrapper.get('[data-testid="scoring-create"]').trigger('click')
    await wrapper.get('[data-testid="scoring-form-name"]').setValue('  新标准  ')
    await wrapper.get('.modal-ok').trigger('click')
    await flushPromises()
    expect(state.api.createScoringStandard).toHaveBeenCalledWith({
      name: '新标准', scene: 'running', rule_set_key: KEY, base_score: 100,
      grade_bands: bands, veto_grade: '丙',
    })
    expect(state.api.getScoringStandard).toHaveBeenCalledWith('new-1')
    expect(wrapper.find('.drawer').exists()).toBe(true)
  })

  it('终末场景有多个规则集时须选择；名称为空不提交；422 逐条显示', async () => {
    state.api.createScoringStandard.mockResolvedValue({
      success: false, status: 422, code: 'invalid', message: '校验未通过', problems: ['名称不能超过 100 个字符'],
    })
    const wrapper = await render()
    await wrapper.get('.tab-final').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="scoring-create"]').trigger('click')
    await wrapper.get('.modal-ok').trigger('click')
    expect(state.api.createScoringStandard).not.toHaveBeenCalled()
    expect(wrapper.get('[data-testid="scoring-form-problems"]').text()).toContain('标准名称不能为空')

    await wrapper.get('[data-testid="scoring-form-rule-set"]').setValue(KEY)
    await wrapper.get('[data-testid="scoring-form-name"]').setValue('终末标准')
    await wrapper.get('.modal-ok').trigger('click')
    await flushPromises()
    expect(state.api.createScoringStandard).toHaveBeenCalledWith(expect.objectContaining({ scene: 'final', rule_set_key: KEY }))
    expect(wrapper.get('[data-testid="scoring-form-problems"]').text()).toContain('名称不能超过 100 个字符')
  })

  it('复制、删除草稿与归档均带 version_seq 并刷新列表', async () => {
    state.api.copyScoringStandard.mockResolvedValue(ok(detailOf(standard({ id: 'c1', name: '启用标准（副本）' }))))
    state.api.deleteScoringStandard.mockResolvedValue(ok({ id: 'd1', deleted: true }))
    state.api.archiveScoringStandard.mockResolvedValue(ok(detailOf(archived)))
    const wrapper = await render()

    await row(wrapper, 'a1').get('[data-testid="scoring-action-copy"]').trigger('click')
    await wrapper.get('.modal-ok').trigger('click')
    await flushPromises()
    expect(state.api.copyScoringStandard).toHaveBeenCalledWith('a1', '启用标准（副本）')

    await row(wrapper, 'd1').get('[data-testid="scoring-action-delete"]').element.parentElement?.querySelector<HTMLButtonElement>('.pop-ok')?.click()
    await flushPromises()
    expect(state.api.deleteScoringStandard).toHaveBeenCalledWith('d1', 2)

    await row(wrapper, 'a1').get('[data-testid="scoring-action-archive"]').element.parentElement?.querySelector<HTMLButtonElement>('.pop-ok')?.click()
    await flushPromises()
    expect(state.api.archiveScoringStandard).toHaveBeenCalledWith('a1', 3)
    expect(state.api.listScoringStandards.mock.calls.length).toBeGreaterThanOrEqual(4)
  })

  it.each(['archive', 'undefault'] as const)('启用草稿：原默认标准按 %s 处理', async (mode) => {
    state.api.activateScoringStandard.mockResolvedValue(ok(detailOf({ ...draft, status: 'active', is_default: true })))
    const wrapper = await render()
    await row(wrapper, 'd1').get('[data-testid="scoring-action-activate"]').trigger('click')
    expect(wrapper.get('.modal').text()).toContain('原默认标准「启用标准」')
    await wrapper.get(`.mode-${mode}`).trigger('click')
    await wrapper.get('.modal-ok').trigger('click')
    await flushPromises()
    expect(state.api.activateScoringStandard).toHaveBeenCalledWith('d1', { version_seq: 2, replace_mode: mode })
    expect(state.message.success).toHaveBeenCalled()
  })

  it.each(['archive', 'undefault'] as const)('已启用非默认标准可直接按 %s 设回默认', async (mode) => {
    state.api.listScoringStandards.mockResolvedValue(ok({
      items: [active, activeNonDefault], scenes: catalog,
    }))
    state.api.setDefaultScoringStandard.mockResolvedValue(ok(detailOf({ ...activeNonDefault, is_default: true })))
    const wrapper = await render()

    expect(row(wrapper, 'a1').find('[data-testid="scoring-action-set-default"]').exists()).toBe(false)
    await row(wrapper, 'a2').get('[data-testid="scoring-action-set-default"]').trigger('click')
    expect(wrapper.get('.modal').text()).toContain('无需复制草稿')
    expect(wrapper.get('.modal').text()).toContain('原默认标准「启用标准」')
    await wrapper.get(`.mode-${mode}`).trigger('click')
    await wrapper.get('.modal-ok').trigger('click')
    await flushPromises()

    expect(state.api.setDefaultScoringStandard).toHaveBeenCalledWith('a2', {
      version_seq: 6, replace_mode: mode,
    })
    expect(state.api.activateScoringStandard).not.toHaveBeenCalled()
    expect(state.message.success).toHaveBeenCalledWith('已设为默认评分标准')
  })

  it('启用校验失败时在弹窗中逐条展示 problems', async () => {
    state.api.activateScoringStandard.mockResolvedValue({
      success: false, status: 422, code: 'standard_validation_failed', message: '评分标准校验未通过',
      problems: ['至少需要 1 条启用的扣分条目'],
    })
    const wrapper = await render()
    await row(wrapper, 'd1').get('[data-testid="scoring-action-activate"]').trigger('click')
    await wrapper.get('.modal-ok').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="scoring-activate-problems"]').text()).toContain('至少需要 1 条启用的扣分条目')
  })

  it('只读角色：无新建/复制/启用/删除/归档，编辑抽屉只读', async () => {
    state.roles = ['doctor']
    const wrapper = await render()
    expect(wrapper.get('[data-testid="scoring-readonly-role"]').text()).toContain('当前角色只读')
    expect(wrapper.find('[data-testid="scoring-create"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="scoring-import"]').exists()).toBe(false)
    for (const action of ['copy', 'activate', 'set-default', 'delete', 'archive']) {
      expect(wrapper.find(`[data-testid="scoring-action-${action}"]`).exists()).toBe(false)
    }
    expect(row(wrapper, 'd1').get('[data-testid="scoring-action-open"]').text()).toBe('查看')
    await openEditor(wrapper, 'd1')
    expect(wrapper.get('[data-testid="scoring-editor-readonly"]').text()).toContain('当前角色只读')
    expect(wrapper.get('[data-testid="scoring-editor-name"]').attributes('disabled')).toBeDefined()
    expect(wrapper.find('[data-testid="scoring-editor-save"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="scoring-item-remove"]').exists()).toBe(false)
    expect(row(wrapper, 'd1').find('[data-testid="scoring-action-export"]').exists()).toBe(true)
  })

  it('导出任意状态标准并使用安全文件名下载', async () => {
    const blob = new Blob(['xlsx'])
    state.api.exportScoringStandard.mockResolvedValue(ok(blob))
    const createObjectURL = vi.fn(() => 'blob:score')
    const revokeObjectURL = vi.fn()
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: createObjectURL })
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: revokeObjectURL })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    const wrapper = await render()

    await row(wrapper, 'd1').get('[data-testid="scoring-action-export"]').trigger('click')
    await flushPromises()
    expect(state.api.exportScoringStandard).toHaveBeenCalledWith('d1')
    expect(createObjectURL).toHaveBeenCalledWith(blob)
    expect(click).toHaveBeenCalled()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:score')
  })

  it('导入成功创建草稿、刷新列表并打开编辑', async () => {
    const imported = detailOf(standard({ id: 'i1', name: '导入草稿' }))
    state.api.importScoringStandard.mockResolvedValue({
      success: true, data: imported, message: '已导入', problems: [], resultUnknown: false,
    })
    const wrapper = await render()
    await wrapper.get('[data-testid="scoring-import"]').trigger('click')
    const input = wrapper.get('[data-testid="scoring-import-file"]')
    const file = new File(['xlsx'], 'standard.xlsx')
    Object.defineProperty(input.element, 'files', { configurable: true, value: [file] })
    await input.trigger('change')
    expect(wrapper.get('[data-testid="scoring-import-filename"]').text()).toContain('standard.xlsx')
    await wrapper.get('.modal-ok').trigger('click')
    await flushPromises()

    expect(state.api.importScoringStandard).toHaveBeenCalledWith(file)
    expect(state.message.success).toHaveBeenCalledWith('评分标准已导入为新草稿')
    expect(state.api.listScoringStandards.mock.calls.length).toBeGreaterThan(1)
    expect(state.api.getScoringStandard).toHaveBeenCalledWith('i1')
  })

  it('导入逐行错误可定位；结果未知时同一文件不能重复提交', async () => {
    state.api.importScoringStandard
      .mockResolvedValueOnce({
        success: false,
        message: '校验未通过',
        problems: [{ sheet: '评分条目', row: 3, field: '规则ID', code: 'rule_duplicate', message: '规则重复' }],
        resultUnknown: false,
      })
      .mockResolvedValueOnce({
        success: false,
        message: '可能已写入',
        problems: [],
        resultUnknown: true,
      })
    const wrapper = await render()
    await wrapper.get('[data-testid="scoring-import"]').trigger('click')
    const input = wrapper.get('[data-testid="scoring-import-file"]')
    const first = new File(['xlsx'], 'first.xlsx')
    Object.defineProperty(input.element, 'files', { configurable: true, value: [first] })
    await input.trigger('change')
    await wrapper.get('.modal-ok').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="scoring-import-problems"]').text()).toContain('评分条目 第 3 行 · 规则ID：规则重复')

    await wrapper.get('.modal-ok').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="scoring-import-unknown"]').text()).toContain('可能已经创建草稿')
    await wrapper.get('.modal-ok').trigger('click')
    expect(state.api.importScoringStandard).toHaveBeenCalledTimes(2)

    const second = new File(['xlsx'], 'second.xlsx')
    Object.defineProperty(input.element, 'files', { configurable: true, value: [second] })
    await input.trigger('change')
    expect(wrapper.find('[data-testid="scoring-import-unknown"]').exists()).toBe(false)
  })

  it('启用中的标准只读并提示复制为新草稿', async () => {
    const wrapper = await render()
    await openEditor(wrapper, 'a1')
    expect(wrapper.get('[data-testid="scoring-editor-readonly"]').text()).toContain('如需修改请复制为新草稿')
    expect(wrapper.find('[data-testid="scoring-editor-save"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="scoring-item-deduction"]').attributes('disabled')).toBeDefined()
  })

  it('条目显示 rule_id 与质控点，缺失质控点显示未知；规则来自当前版本 entries', async () => {
    const wrapper = await render()
    await openEditor(wrapper, 'd1')
    expect(state.rules.listRuleSetVersions).toHaveBeenCalledWith(KEY)
    expect(state.rules.getRuleSetVersion).toHaveBeenCalledWith(KEY, '2026-06-09')
    const points = wrapper.findAll('[data-testid="scoring-item-qc-point"]').map((node) => node.text())
    expect(points).toEqual(['入院记录完整性', '未知'])
    const options = wrapper.get('[data-testid="scoring-item-rule"]').findAll('option').map((node) => node.text())
    expect(options).toEqual(['LX0609-001 · 入院记录完整性', 'LX0609-002 · 未知', 'LX0609-003 · 首次病程及时性'])
  })

  it('档位不连续时前端拦截保存并提示空隙', async () => {
    const wrapper = await render()
    await openEditor(wrapper, 'd1')
    await wrapper.findAll('[data-testid="scoring-band-min"]')[1].setValue('80')
    expect(wrapper.get('[data-testid="scoring-band-problems"]').text()).toContain('之间有空隙')
    await wrapper.get('[data-testid="scoring-editor-save"]').trigger('click')
    await flushPromises()
    expect(state.api.updateScoringStandard).not.toHaveBeenCalled()
    expect(state.api.saveScoringItems).not.toHaveBeenCalled()
    expect(wrapper.get('[data-testid="scoring-editor-problems"]').text()).toContain('之间有空隙')
  })

  it('任意档数：新增第四档并调整衔接后校验通过', async () => {
    const wrapper = await render()
    await openEditor(wrapper, 'd1')
    await wrapper.get('[data-testid="scoring-band-add"]').trigger('click')
    const names = wrapper.findAll('[data-testid="scoring-band-name"]')
    expect(names).toHaveLength(4)
    await names[3].setValue('丁')
    await wrapper.findAll('[data-testid="scoring-band-min"]')[2].setValue('60')
    await wrapper.findAll('[data-testid="scoring-band-max"]')[3].setValue('60')
    await wrapper.findAll('[data-testid="scoring-band-min"]')[3].setValue('0')
    expect(wrapper.find('[data-testid="scoring-band-problems"]').exists()).toBe(false)
  })

  it('编辑条目与项目组后整表保存：先改基本信息推进 version_seq，再带新序号保存条目', async () => {
    state.api.updateScoringStandard.mockResolvedValue(ok(detailOf({ ...draft, name: '草稿标准 v2', version_seq: 3 })))
    state.api.saveScoringItems.mockImplementation(async (_id: string, payload: { version_seq: number }) =>
      ok(detailOf({ ...draft, name: '草稿标准 v2', version_seq: payload.version_seq + 1 })),
    )
    const wrapper = await render()
    await openEditor(wrapper, 'd1')

    await wrapper.get('[data-testid="scoring-editor-name"]').setValue('草稿标准 v2')
    await wrapper.get('[data-testid="scoring-group-add"]').trigger('click')
    const groupNames = wrapper.findAll('[data-testid="scoring-group-name"]')
    await groupNames[1].setValue('首页')
    await wrapper.findAll('[data-testid="scoring-group-cap"]')[0].setValue('')
    await wrapper.get('[data-testid="scoring-item-add"]').trigger('click')
    const rules = wrapper.findAll('[data-testid="scoring-item-rule"]')
    await rules[2].setValue('LX0609-003')
    await wrapper.findAll('[data-testid="scoring-item-group"]')[2].setValue('首页')
    await wrapper.findAll('[data-testid="scoring-item-deduction"]')[2].setValue('1.5')
    await wrapper.findAll('[data-testid="scoring-item-enabled"]')[0].setValue(false)
    expect(wrapper.findAll('[data-testid="scoring-item-qc-point"]')[2].text()).toBe('首次病程及时性')

    await wrapper.get('[data-testid="scoring-editor-save"]').trigger('click')
    await flushPromises()
    expect(state.api.updateScoringStandard).toHaveBeenCalledWith('d1', {
      version_seq: 2, name: '草稿标准 v2', base_score: 100, grade_bands: bands, veto_grade: '丙',
    })
    expect(state.api.saveScoringItems).toHaveBeenCalledWith('d1', {
      version_seq: 3,
      groups: [
        { group_name: '病程记录', max_deduction: null, sort_order: 1 },
        { group_name: '首页', max_deduction: null, sort_order: 2 },
      ],
      items: [
        { group_name: '病程记录', rule_id: 'LX0609-001', deduction: 2, is_veto: false, enabled: false },
        { group_name: '病程记录', rule_id: 'LX0609-002', deduction: 3, is_veto: true, enabled: true },
        { group_name: '首页', rule_id: 'LX0609-003', deduction: 1.5, is_veto: false, enabled: true },
      ],
    })
    expect(state.message.success).toHaveBeenCalledWith('评分标准草稿已保存')
    expect(wrapper.text()).toContain('版本序号 4')
  })

  it('基本信息未改动时只保存条目；重复规则前端拦截', async () => {
    state.api.saveScoringItems.mockResolvedValue(ok(detailOf({ ...draft, version_seq: 3 })))
    const wrapper = await render()
    await openEditor(wrapper, 'd1')
    await wrapper.findAll('[data-testid="scoring-item-rule"]')[1].setValue('LX0609-001')
    await wrapper.get('[data-testid="scoring-editor-save"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="scoring-editor-problems"]').text()).toContain('规则重复')
    expect(state.api.saveScoringItems).not.toHaveBeenCalled()

    await wrapper.findAll('[data-testid="scoring-item-rule"]')[1].setValue('LX0609-002')
    await wrapper.get('[data-testid="scoring-editor-save"]').trigger('click')
    await flushPromises()
    expect(state.api.updateScoringStandard).not.toHaveBeenCalled()
    expect(state.api.saveScoringItems).toHaveBeenCalledWith('d1', expect.objectContaining({ version_seq: 2 }))
  })

  it('保存遇 409 version_conflict 提示刷新，刷新后重新读取详情', async () => {
    state.api.saveScoringItems.mockResolvedValue({
      success: false, status: 409, code: 'version_conflict', message: '评分标准已被修改，请刷新后重试',
    })
    const wrapper = await render()
    await openEditor(wrapper, 'd1')
    await wrapper.get('[data-testid="scoring-editor-save"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="scoring-editor-conflict"]').text()).toContain('请刷新后重新编辑')
    expect(wrapper.get('[data-testid="scoring-editor-save"]').attributes('disabled')).toBeDefined()
    const reads = state.api.getScoringStandard.mock.calls.length
    await wrapper.get('[data-testid="scoring-editor-refresh"]').trigger('click')
    await flushPromises()
    expect(state.api.getScoringStandard.mock.calls.length).toBe(reads + 1)
    expect(wrapper.find('[data-testid="scoring-editor-conflict"]').exists()).toBe(false)
  })

  it('保存遇后端 422 以 problems 为准逐条展示', async () => {
    state.api.saveScoringItems.mockResolvedValue({
      success: false, status: 422, code: 'items_validation_failed', message: '评分条目校验未通过',
      problems: ['以下规则不属于该规则集当前版本：LX0609-002'],
    })
    const wrapper = await render()
    await openEditor(wrapper, 'd1')
    await wrapper.get('[data-testid="scoring-editor-save"]').trigger('click')
    await flushPromises()
    const problems = wrapper.get('[data-testid="scoring-editor-problems"]').text()
    expect(problems).toContain('评分条目校验未通过')
    expect(problems).toContain('LX0609-002')
  })
})
