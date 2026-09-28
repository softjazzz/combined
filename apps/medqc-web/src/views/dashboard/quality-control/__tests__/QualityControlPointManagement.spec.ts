import { h, nextTick } from 'vue'
import { mount, type VueWrapper } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import QualityControlPointManagement from '@/views/dashboard/quality-control/QualityControlPointManagement.vue'
import type {
  RuleSetDraft,
  RuleSetEntryView,
  RuleSetVersionDetail,
  RuleSetVersionItem,
  RuleSetVersionList,
} from '@/api/ruleSetVersions'

const KEY = 'luxian_0609_qc_v1'
const BUILTIN = '2026-06-09'

const state = vi.hoisted(() => ({
  roles: ['qc_manager'] as string[],
  push: vi.fn(),
  message: { success: vi.fn(), warning: vi.fn(), info: vi.fn(), error: vi.fn() },
  api: {
    listRuleSetVersions: vi.fn(),
    getRuleSetVersion: vi.fn(),
    createRuleSetDraft: vi.fn(),
    updateRuleSetDraft: vi.fn(),
    deleteRuleSetDraft: vi.fn(),
    publishRuleSetDraft: vi.fn(),
    retireRuleSetVersion: vi.fn(),
    exportRuleSetVersion: vi.fn(),
    exportRuleSetDraft: vi.fn(),
    importRuleSetDraft: vi.fn(),
  },
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ hasRole: (role: string) => state.roles.includes(role) }),
}))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: state.push }) }))
vi.mock('ant-design-vue', () => ({ message: state.message }))
vi.mock('@/api/ruleSetVersions', () => state.api)
vi.mock('@/views/workstation-v4/customer-sample-validation/batchExport', () => ({ downloadBlob: vi.fn() }))

const entries: RuleSetEntryView[] = [
  { rule_id: 'LX0609-001', state: 'active', executable: true, qc_point: '入院记录完整性', source_document: '入院记录' },
  { rule_id: 'LX0609-002', state: 'active', executable: true, qc_point: '首次病程及时性', source_document: null },
  { rule_id: 'LX0609-020', state: 'paused', executable: false, qc_point: '会诊记录', source_document: '会诊记录' },
  { rule_id: 'LX0609-033', state: 'offline', executable: true, qc_point: '出院小结规范', source_document: '出院记录' },
]

function versionItem(overrides: Partial<RuleSetVersionItem> = {}): RuleSetVersionItem {
  return {
    id: null, rule_set_key: KEY, version: BUILTIN, status: 'builtin', source: 'builtin',
    base_version: null, content_digest: 'digest', note: null, version_seq: null,
    created_by: null, created_at: null, published_by: null, published_at: null,
    retired_by: null, retired_at: null, is_current: true,
    active_count: 2, paused_count: 1, offline_count: 1,
    ...overrides,
  }
}

function detail(version = BUILTIN, rows = entries): RuleSetVersionDetail {
  return {
    ...versionItem({ version }),
    entries: rows,
    resolution: {
      rule_set_key: KEY, version, source: 'builtin', active_rule_ids: [], paused_rule_ids: [],
      excluded_rule_ids: [], content_digest: 'digest',
    },
  }
}

function draftOf(rows: RuleSetEntryView[], seq = 1): RuleSetDraft {
  return {
    ...versionItem({ id: 'draft-1', version: null, status: 'draft', source: null, base_version: BUILTIN, content_digest: null, is_current: false, created_by: 'u-1', created_at: '2026-09-27T01:00:00' }),
    status: 'draft', version_seq: seq, base_version: BUILTIN, entries: rows,
  }
}

function list(overrides: Partial<RuleSetVersionList> = {}): RuleSetVersionList {
  return {
    rule_set_key: KEY, versionable: true, builtin_version: BUILTIN, current_version: BUILTIN,
    items: [versionItem()], draft: null, ...overrides,
  }
}

const ok = <T>(data: T) => ({ success: true, data, status: 200 })

const slot = { template: '<div><slot /></div>' }
const inputStub = {
  props: ['value'],
  emits: ['update:value'],
  template: '<input :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
}
const tableStub = {
  props: ['dataSource', 'columns', 'rowSelection'],
  render() {
    const self = this as unknown as {
      dataSource: Array<{ rule_id: string }>
      columns: Array<{ key: string }>
      rowSelection?: { onChange: (keys: string[]) => void }
      $slots: { bodyCell?: (props: { column: { key: string }; record: unknown }) => unknown }
    }
    return h('div', { class: 'table' }, self.dataSource.map((record) => h('div', { class: 'row', 'data-id': record.rule_id }, [
      self.rowSelection ? h('button', { class: 'select-row', onClick: () => self.rowSelection?.onChange([record.rule_id]) }, '选择') : null,
      h('span', record.rule_id),
      ...self.columns.map((column) => h('div', self.$slots.bodyCell?.({ column, record }) as never)),
    ])))
  },
}

const stubs = {
  'a-alert': { props: ['message', 'description'], template: '<div class="alert">{{ message }}{{ description }}<slot name="description" /></div>' },
  'a-select': {
    props: ['value', 'options', 'disabled'],
    emits: ['update:value'],
    template: '<select :value="value" @change="$emit(\'update:value\', $event.target.value)"><option v-for="o in options || []" :key="o.value" :value="o.value">{{ o.label }}</option><slot /></select>',
  },
  'a-select-option': slot,
  'a-tabs': {
    props: ['activeKey'],
    emits: ['update:activeKey'],
    template: '<div><button class="tab-online" @click="$emit(\'update:activeKey\', \'online\')">online</button><button class="tab-offline" @click="$emit(\'update:activeKey\', \'offline\')">offline</button><slot /></div>',
  },
  'a-tab-pane': { props: ['tab'], template: '<span class="tab-label">{{ tab }}</span>' },
  'a-button': { props: ['disabled', 'loading'], emits: ['click'], template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>' },
  'a-checkbox': { props: ['checked', 'disabled'], emits: ['update:checked'], template: '<label><input type="checkbox" :disabled="disabled"><slot /></label>' },
  'a-tooltip': { props: ['title'], template: '<span class="tooltip" :data-tip="title"><slot /></span>' },
  'a-popconfirm': { emits: ['confirm'], template: '<span><slot /><button class="pop-ok" @click="$emit(\'confirm\')">确认</button></span>' },
  'a-modal': { props: ['open'], template: '<div v-if="open" class="modal"><slot /></div>' },
  'a-drawer': { props: ['open'], template: '<div v-if="open" class="drawer"><slot /></div>' },
  'a-input': inputStub,
  'a-textarea': inputStub,
  'a-input-search': inputStub,
  'a-table': tableStub,
  'a-tag': { template: '<span class="tag"><slot /></span>' },
}

async function flush() {
  for (let index = 0; index < 6; index += 1) {
    await Promise.resolve()
    await nextTick()
  }
}

async function render() {
  const wrapper = mount(QualityControlPointManagement, { global: { stubs } })
  await flush()
  return wrapper
}

function button(wrapper: VueWrapper, text: string, scope = '') {
  const found = wrapper.findAll(`${scope} button`.trim()).find((item) => item.text() === text)
  if (!found) throw new Error(`未找到按钮：${text}`)
  return found
}

async function selectRow(wrapper: VueWrapper, ruleId: string) {
  await wrapper.find(`.row[data-id="${ruleId}"] .select-row`).trigger('click')
  await flush()
}

describe('QualityControlPointManagement', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    state.roles = ['qc_manager']
    state.api.listRuleSetVersions.mockResolvedValue(ok(list()))
    state.api.getRuleSetVersion.mockResolvedValue(ok(detail()))
  })

  it('按当前版本分页签，名称与文书取自 entries，下线规则名称可见', async () => {
    const wrapper = await render()
    expect(state.api.getRuleSetVersion).toHaveBeenCalledWith(KEY, BUILTIN)
    expect(wrapper.text()).toContain('已上线（2）')
    expect(wrapper.text()).toContain('未上线（2）')
    const rows = wrapper.findAll('.row').map((row) => row.attributes('data-id'))
    expect(rows).toEqual(['LX0609-001', 'LX0609-002'])
    expect(wrapper.find('.row[data-id="LX0609-001"]').text()).toContain('入院记录完整性')
    expect(wrapper.find('.row[data-id="LX0609-002"]').text()).toContain('文书：未知')

    await wrapper.find('.tab-offline').trigger('click')
    await flush()
    const paused = wrapper.find('.row[data-id="LX0609-020"]').text()
    expect(paused).toContain('已暂停')
    expect(paused).toContain('不可执行')
    const offline = wrapper.find('.row[data-id="LX0609-033"]').text()
    expect(offline).toContain('已下线')
    expect(offline).toContain('出院小结规范')
    expect(offline).toContain('文书：出院记录')
    expect(offline).toContain('可执行')
  })

  it('首次批量操作先以当前版本建草稿再写入，并展示差异', async () => {
    state.api.createRuleSetDraft.mockResolvedValue(ok(draftOf(entries, 1)))
    const updatedEntries = entries.map((item) => (item.rule_id === 'LX0609-001' ? { ...item, state: 'paused' as const } : item))
    state.api.updateRuleSetDraft.mockResolvedValue(ok(draftOf(updatedEntries, 2)))
    const wrapper = await render()

    await selectRow(wrapper, 'LX0609-001')
    await button(wrapper, '批量暂停').trigger('click')
    await flush()

    expect(state.api.createRuleSetDraft).toHaveBeenCalledWith(KEY, { base_version: BUILTIN })
    expect(state.api.updateRuleSetDraft).toHaveBeenCalledWith(KEY, {
      version_seq: 1,
      entries: [
        { rule_id: 'LX0609-001', state: 'paused' },
        { rule_id: 'LX0609-002', state: 'active' },
        { rule_id: 'LX0609-020', state: 'paused' },
        { rule_id: 'LX0609-033', state: 'offline' },
      ],
    })
    expect(state.message.success).toHaveBeenCalledWith(expect.stringContaining('发布新版本后生效'))
    const panel = wrapper.find('.draft-panel')
    expect(panel.exists()).toBe(true)
    expect(panel.findAll('.diff-item')).toHaveLength(1)
    expect(panel.find('.diff-item').text()).toMatch(/LX0609-001.*入院记录完整性.*已开启.*已暂停/)
    expect(wrapper.find('.row[data-id="LX0609-001"]').text()).toContain('草稿：已暂停')
  })

  it('不可执行规则的开启被禁用并提示原因；可执行规则写入已有草稿', async () => {
    state.api.listRuleSetVersions.mockResolvedValue(ok(list({ draft: draftOf(entries, 4) })))
    state.api.updateRuleSetDraft.mockResolvedValue(ok(draftOf(entries, 5)))
    const wrapper = await render()
    await wrapper.find('.tab-offline').trigger('click')
    await flush()

    await selectRow(wrapper, 'LX0609-020')
    const enable = button(wrapper, '批量开启')
    expect(enable.attributes('disabled')).toBeDefined()
    expect(wrapper.find('.tooltip').attributes('data-tip')).toContain('LX0609-020 当前不可执行')

    await selectRow(wrapper, 'LX0609-033')
    expect(button(wrapper, '批量开启').attributes('disabled')).toBeUndefined()
    await button(wrapper, '批量开启').trigger('click')
    await flush()
    expect(state.api.createRuleSetDraft).not.toHaveBeenCalled()
    expect(state.api.updateRuleSetDraft).toHaveBeenCalledWith(KEY, expect.objectContaining({ version_seq: 4 }))
    const sent = state.api.updateRuleSetDraft.mock.calls[0]?.[1] as { entries: Array<{ rule_id: string; state: string }> }
    expect(sent.entries.find((item) => item.rule_id === 'LX0609-033')?.state).toBe('active')
  })

  it('草稿 CAS 冲突时提示并刷新', async () => {
    state.api.listRuleSetVersions.mockResolvedValue(ok(list({ draft: draftOf(entries, 2) })))
    state.api.updateRuleSetDraft.mockResolvedValue({ success: false, status: 409, code: 'version_conflict', message: '草稿已被修改' })
    const wrapper = await render()
    await selectRow(wrapper, 'LX0609-002')
    await button(wrapper, '批量下线').trigger('click')
    await flush()
    expect(state.message.warning).toHaveBeenCalledWith(expect.stringContaining('已刷新'))
    expect(state.api.listRuleSetVersions).toHaveBeenCalledTimes(2)
  })

  it('发布：成功刷新、422 逐条展示 problems、409 提示版本号重复', async () => {
    const changed = entries.map((item) => (item.rule_id === 'LX0609-002' ? { ...item, state: 'offline' as const } : item))
    state.api.listRuleSetVersions.mockResolvedValue(ok(list({ draft: draftOf(changed, 3) })))
    state.api.publishRuleSetDraft
      .mockResolvedValueOnce({ success: false, status: 422, code: 'publish_validation_failed', message: '校验未通过', problems: ['至少需要 1 条 active 规则', '以下规则当前不可执行：LX0609-020'] })
      .mockResolvedValueOnce({ success: false, status: 409, code: 'version_exists', message: '版本号已存在' })
      .mockResolvedValueOnce(ok(detail('v2')))
    const wrapper = await render()
    expect(wrapper.find('.draft-panel .diff-item').text()).toContain('LX0609-002')

    await button(wrapper, '发布新版本').trigger('click')
    await flush()
    const modal = wrapper.find('.modal')
    await modal.find('.version-input').setValue('v2')
    await modal.find('.note-input').setValue('下线 002')

    await button(wrapper, '确认发布', '.modal').trigger('click')
    await flush()
    expect(state.api.publishRuleSetDraft).toHaveBeenLastCalledWith(KEY, { version: 'v2', note: '下线 002', version_seq: 3 })
    expect(wrapper.findAll('.problem-list li').map((item) => item.text())).toEqual([
      '至少需要 1 条 active 规则', '以下规则当前不可执行：LX0609-020',
    ])

    await button(wrapper, '确认发布', '.modal').trigger('click')
    await flush()
    expect(wrapper.find('.publish-error').text()).toContain('版本号已存在')
    expect(wrapper.find('.problem-list').exists()).toBe(false)

    await button(wrapper, '确认发布', '.modal').trigger('click')
    await flush()
    expect(state.message.success).toHaveBeenCalledWith(expect.stringContaining('已发布版本 v2'))
    expect(wrapper.find('.modal').exists()).toBe(false)
    expect(state.api.listRuleSetVersions).toHaveBeenCalledTimes(2)
  })

  it('发布前校验版本号格式，不发请求', async () => {
    state.api.listRuleSetVersions.mockResolvedValue(ok(list({ draft: draftOf(entries.map((item) => ({ ...item, state: 'paused' as const })), 1) })))
    const wrapper = await render()
    await button(wrapper, '发布新版本').trigger('click')
    await flush()
    await wrapper.find('.modal .version-input').setValue('-bad/version')
    await button(wrapper, '确认发布', '.modal').trigger('click')
    await flush()
    expect(state.api.publishRuleSetDraft).not.toHaveBeenCalled()
    expect(wrapper.find('.publish-error').text()).toContain('版本号只能包含')
  })

  it('放弃草稿带 version_seq', async () => {
    state.api.listRuleSetVersions.mockResolvedValue(ok(list({ draft: draftOf(entries, 7) })))
    state.api.deleteRuleSetDraft.mockResolvedValue(ok({ rule_set_key: KEY, deleted: true }))
    const wrapper = await render()
    expect(wrapper.find('.draft-panel').text()).toContain('草稿与基础版本无差异')
    expect(button(wrapper, '发布新版本').attributes('disabled')).toBeDefined()
    await wrapper.find('.draft-panel .pop-ok').trigger('click')
    await flush()
    expect(state.api.deleteRuleSetDraft).toHaveBeenCalledWith(KEY, 7)
  })

  it('版本历史展示来源与当前标记，仅非当前已发布版本可下线', async () => {
    state.api.listRuleSetVersions.mockResolvedValue(ok(list({
      current_version: 'v2',
      items: [
        versionItem({ id: 'id-2', version: 'v2', status: 'published', source: 'published', is_current: true, published_by: 'u-9', published_at: '2026-09-27T02:00:00', version_seq: 2 }),
        versionItem({ id: 'id-1', version: 'v1', status: 'published', source: 'published', is_current: false, published_by: 'u-8', published_at: '2026-09-26T02:00:00', version_seq: 2 }),
        versionItem({ id: 'id-0', version: 'v0', status: 'retired', source: 'retired', is_current: false, version_seq: 3 }),
        versionItem({ is_current: false }),
      ],
    })))
    state.api.getRuleSetVersion.mockResolvedValue(ok(detail('v2')))
    state.api.retireRuleSetVersion.mockResolvedValue(ok(detail('v1')))
    const wrapper = await render()
    expect(state.api.getRuleSetVersion).toHaveBeenCalledWith(KEY, 'v2')

    await button(wrapper, '版本历史').trigger('click')
    await flush()
    const drawer = wrapper.find('.drawer')
    const items = drawer.findAll('.history-item')
    expect(items).toHaveLength(4)
    expect(items[0]?.text()).toContain('当前版本')
    expect(items[0]?.text()).toContain('发布人 u-9')
    expect(items[2]?.text()).toContain('已下线')
    expect(items[3]?.text()).toContain('内置')
    expect(drawer.findAll('.retire-btn')).toHaveLength(1)
    expect(items[1]?.find('.retire-btn').exists()).toBe(true)

    await items[1]!.find('.pop-ok').trigger('click')
    await flush()
    expect(state.api.retireRuleSetVersion).toHaveBeenCalledWith(KEY, 'v1')
    expect(state.api.listRuleSetVersions).toHaveBeenCalledTimes(2)
  })

  it('下线冲突按 code 提示', async () => {
    state.api.listRuleSetVersions.mockResolvedValue(ok(list({
      items: [versionItem({ id: 'id-1', version: 'v1', status: 'published', source: 'published', is_current: false, version_seq: 1 }), versionItem()],
    })))
    state.api.retireRuleSetVersion.mockResolvedValue({ success: false, status: 409, code: 'already_retired', message: 'x' })
    const wrapper = await render()
    await button(wrapper, '版本历史').trigger('click')
    await flush()
    await wrapper.find('.drawer .pop-ok').trigger('click')
    await flush()
    expect(state.message.warning).toHaveBeenCalledWith('该版本已下线，已刷新版本列表')
  })

  it('只读角色不显示写操作', async () => {
    state.roles = ['qc_doctor']
    state.api.listRuleSetVersions.mockResolvedValue(ok(list({
      draft: draftOf(entries.map((item) => ({ ...item, state: 'paused' as const })), 1),
      items: [versionItem({ id: 'id-1', version: 'v1', status: 'published', source: 'published', is_current: false }), versionItem()],
    })))
    const wrapper = await render()
    expect(wrapper.text()).toContain('当前角色只读')
    expect(wrapper.findAll('button').some((item) => ['批量开启', '批量暂停', '批量下线', '新建质控点', '发布新版本', '放弃草稿'].includes(item.text()))).toBe(false)
    expect(wrapper.find('.select-row').exists()).toBe(false)
    await button(wrapper, '版本历史').trigger('click')
    await flush()
    expect(wrapper.find('.drawer .retire-btn').exists()).toBe(false)
  })

  it('0916 暂仅内置版本，只读展示', async () => {
    const wrapper = await render()
    state.api.listRuleSetVersions.mockResolvedValue(ok(list({ rule_set_key: 'luxian_0916_qc_v1', versionable: false, builtin_version: '2026-09-16', current_version: '2026-09-16', items: [versionItem({ rule_set_key: 'luxian_0916_qc_v1', version: '2026-09-16' })] })))
    state.api.getRuleSetVersion.mockResolvedValue(ok(detail('2026-09-16', [
      { rule_id: 'LX0916-001', state: 'active', executable: true, qc_point: null, source_document: null },
    ])))
    await wrapper.find('select').setValue('luxian_0916_qc_v1')
    await flush()
    expect(state.api.listRuleSetVersions).toHaveBeenLastCalledWith('luxian_0916_qc_v1')
    expect(state.api.getRuleSetVersion).toHaveBeenLastCalledWith('luxian_0916_qc_v1', '2026-09-16')
    expect(wrapper.text()).toContain('暂仅内置版本')
    const row = wrapper.find('.row[data-id="LX0916-001"]').text()
    expect(row).toContain('未知')
    expect(row).toContain('文书：未知')
    expect(wrapper.findAll('button').some((item) => item.text() === '批量开启')).toBe(false)
    expect(wrapper.find('.select-row').exists()).toBe(false)
  })
})
