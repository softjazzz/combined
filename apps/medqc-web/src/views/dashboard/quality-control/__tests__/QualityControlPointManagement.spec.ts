import { h, nextTick, reactive } from 'vue'
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
  auth: null as null | {
    user: { id: string } | null
    userRoles: string[]
    hasRole: (role: string) => boolean
  },
  push: vi.fn(),
  query: {} as Record<string, string>,
  message: { success: vi.fn(), warning: vi.fn(), info: vi.fn(), error: vi.fn() },
  api: {
    listRuleSetVersions: vi.fn(),
    getRuleSetVersion: vi.fn(),
    getMedicalCoreSystems: vi
      .fn()
      .mockResolvedValue({
        success: true,
        data: { items: [{ id: 'CORE-15', name: '病历管理制度' }] },
      }),
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
  useAuthStore: () => state.auth,
}))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: state.push }), useRoute: () => ({ query: state.query }) }))
vi.mock('ant-design-vue', () => ({ message: state.message }))
vi.mock('@/api/ruleSetVersions', () => state.api)
vi.mock('@/views/workstation-v4/customer-sample-validation/batchExport', () => ({
  downloadBlob: vi.fn(),
}))

const entries: RuleSetEntryView[] = [
  {
    rule_id: 'LX0609-001',
    state: 'active',
    executable: true,
    qc_point: '入院记录完整性',
    source_document: '入院记录',
  },
  {
    rule_id: 'LX0609-002',
    state: 'active',
    executable: true,
    qc_point: '首次病程及时性',
    source_document: null,
  },
  {
    rule_id: 'LX0609-020',
    state: 'paused',
    executable: false,
    qc_point: '会诊记录',
    source_document: '会诊记录',
  },
  {
    rule_id: 'LX0609-033',
    state: 'offline',
    executable: true,
    qc_point: '出院小结规范',
    source_document: '出院记录',
  },
]

function versionItem(overrides: Partial<RuleSetVersionItem> = {}): RuleSetVersionItem {
  return {
    id: null,
    rule_set_key: KEY,
    version: BUILTIN,
    status: 'builtin',
    source: 'builtin',
    base_version: null,
    content_digest: 'digest',
    note: null,
    version_seq: null,
    created_by: null,
    created_at: null,
    published_by: null,
    published_at: null,
    retired_by: null,
    retired_at: null,
    is_current: true,
    active_count: 2,
    paused_count: 1,
    offline_count: 1,
    deleted_count: 0,
    ...overrides,
  }
}

function detail(version = BUILTIN, rows = entries): RuleSetVersionDetail {
  return {
    ...versionItem({ version }),
    entries: rows,
    resolution: {
      rule_set_key: KEY,
      version,
      source: 'builtin',
      active_rule_ids: [],
      paused_rule_ids: [],
      excluded_rule_ids: [],
      content_digest: 'digest',
    },
  }
}

function draftOf(rows: RuleSetEntryView[], seq = 1): RuleSetDraft {
  return {
    ...versionItem({
      id: 'draft-1',
      version: null,
      status: 'draft',
      source: null,
      base_version: BUILTIN,
      content_digest: null,
      is_current: false,
      created_by: 'u-1',
      created_at: '2026-09-27T01:00:00',
    }),
    status: 'draft',
    version_seq: seq,
    base_version: BUILTIN,
    entries: rows,
  }
}

function list(overrides: Partial<RuleSetVersionList> = {}): RuleSetVersionList {
  return {
    rule_set_key: KEY,
    versionable: true,
    builtin_version: BUILTIN,
    current_version: BUILTIN,
    items: [versionItem()],
    draft: null,
    ...overrides,
  }
}

const ok = <T>(data: T) => ({ success: true, data, status: 200 })

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => {
    resolve = done
  })
  return { promise, resolve }
}

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
      rowSelection?: {
        onChange: (keys: string[]) => void
        getCheckboxProps?: (record: { rule_id: string }) => { disabled?: boolean }
      }
      $slots: { bodyCell?: (props: { column: { key: string }; record: unknown }) => unknown }
    }
    return h(
      'div',
      { class: 'table' },
      self.dataSource.map((record) =>
        h('div', { class: 'row', 'data-id': record.rule_id }, [
          self.rowSelection
            ? h(
                'button',
                {
                  class: 'select-row',
                  disabled: self.rowSelection.getCheckboxProps?.(record).disabled,
                  onClick: () => self.rowSelection?.onChange([record.rule_id]),
                },
                '选择',
              )
            : null,
          h('span', record.rule_id),
          ...self.columns.map((column) =>
            h('div', self.$slots.bodyCell?.({ column, record }) as never),
          ),
        ]),
      ),
    )
  },
}

const stubs = {
  'a-alert': {
    props: ['message', 'description'],
    template: '<div class="alert">{{ message }}{{ description }}<slot name="description" /></div>',
  },
  'a-select': {
    props: ['value', 'options', 'disabled'],
    emits: ['update:value'],
    template:
      '<select :value="value" @change="$emit(\'update:value\', $event.target.value)"><option v-for="o in options || []" :key="o.value" :value="o.value">{{ o.label }}</option><slot /></select>',
  },
  'a-select-option': slot,
  'a-tabs': {
    props: ['activeKey'],
    emits: ['update:activeKey'],
    template:
      '<div><button class="tab-online" @click="$emit(\'update:activeKey\', \'online\')">online</button><button class="tab-offline" @click="$emit(\'update:activeKey\', \'offline\')">offline</button><slot /></div>',
  },
  'a-tab-pane': { props: ['tab'], template: '<span class="tab-label">{{ tab }}</span>' },
  'a-button': {
    props: ['disabled', 'loading'],
    emits: ['click'],
    template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
  },
  'a-checkbox': {
    props: ['checked', 'disabled'],
    emits: ['update:checked'],
    template: '<label><input type="checkbox" :disabled="disabled"><slot /></label>',
  },
  'a-tooltip': {
    props: ['title'],
    template: '<span class="tooltip" :data-tip="title"><slot /></span>',
  },
  'a-popconfirm': {
    emits: ['confirm', 'openChange'],
    template:
      '<span><slot /><button class="pop-open" @click="$emit(\'openChange\', true)">打开确认</button><button class="pop-ok" @click="$emit(\'confirm\')">确认</button></span>',
  },
  'a-modal': { props: ['open'], template: '<div v-if="open" class="modal"><slot /></div>' },
  'a-drawer': { props: ['open'], template: '<div v-if="open" class="drawer"><slot /></div>' },
  'a-radio-group': {
    props: ['value'],
    emits: ['update:value'],
    template:
      '<select class="radio-group" :value="value" @change="$emit(\'update:value\', $event.target.value)"><option value="all">全部科室</option><option value="selected">指定科室</option><option value="visible">开放</option><option value="hidden">不开放</option></select>',
  },
  'a-radio-button': slot,
  'a-input': inputStub,
  'a-textarea': inputStub,
  'a-input-search': inputStub,
  'a-table': tableStub,
  'a-tag': { template: '<span class="tag"><slot /></span>' },
  CustomDraftPointsPanel: {
    props: ['actorKey', 'canManage'],
    template:
      '<div class="custom-draft-panel-stub" :data-actor="actorKey" :data-can-manage="String(canManage)" />',
  },
}

async function flush() {
  for (let index = 0; index < 6; index += 1) {
    await Promise.resolve()
    await nextTick()
  }
}

async function render(props: Record<string, unknown> = {}) {
  const wrapper = mount(QualityControlPointManagement, { props, global: { stubs } })
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
    state.query = {}
    state.auth = reactive({
      user: { id: 'manager-1' },
      userRoles: ['qc_manager'],
      hasRole(role: string) {
        return this.userRoles.includes(role)
      },
    })
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
    const updatedEntries = entries.map((item) =>
      item.rule_id === 'LX0609-001' ? { ...item, state: 'paused' as const } : item,
    )
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

  it('仅配置非核心制度也可独立保存，差异可发布且不补适用范围', async () => {
    state.api.createRuleSetDraft.mockResolvedValue(ok(draftOf(entries, 1)))
    state.api.updateRuleSetDraft.mockImplementation(
      async (_key: string, payload: { entries: RuleSetEntryView[] }) =>
        ok(draftOf(payload.entries, 2)),
    )
    const wrapper = await render()
    await button(wrapper, '查看', '.row[data-id="LX0609-001"]').trigger('click')
    await flush()
    await wrapper.findAll('.drawer .radio-group')[2].setValue('none')
    await button(wrapper, '保存核心制度归属到草稿', '.drawer').trigger('click')
    await flush()
    const saved = state.api.updateRuleSetDraft.mock.calls[0][1].entries[0]
    expect(saved.core_system_ids).toEqual([])
    expect(saved.department_scope_mode).toBeUndefined()
    expect(wrapper.find('.diff-item').text()).toContain('核心制度归属变更')
    expect(button(wrapper, '发布新版本').attributes('disabled')).toBeUndefined()
  })

  it('缺陷分类独立写入版本草稿并显示可发布差异', async () => {
    state.api.createRuleSetDraft.mockResolvedValue(ok(draftOf(entries, 1)))
    state.api.updateRuleSetDraft.mockImplementation(async (_key: string, payload: { entries: RuleSetEntryView[] }) => ok(draftOf(payload.entries, 2)))
    const wrapper = await render()
    await button(wrapper, '查看', '.row[data-id="LX0609-001"]').trigger('click')
    await flush()
    await wrapper.get('#defect-category').setValue('合成大类')
    await wrapper.get('#defect-type').setValue('合成类型')
    await wrapper.get('#reminder-level').setValue('强制')
    await button(wrapper, '保存分类与提醒等级到草稿', '.drawer').trigger('click')
    await flush()
    const saved = state.api.updateRuleSetDraft.mock.calls[0][1].entries[0]
    expect(saved.defect_category).toBe('合成大类')
    expect(saved.defect_type).toBe('合成类型')
    expect(saved.reminder_level).toBe('强制')
    expect(saved.department_scope_mode).toBeUndefined()
    expect(wrapper.find('.diff-item').text()).toContain('缺陷分类变更')
    expect(button(wrapper, '发布新版本').attributes('disabled')).toBeUndefined()
  })

  it('规则引用按规则集与精确ID定位暂停规则，未知规则集失败关闭', async () => {
    state.query = { rule_set_key: KEY, rule_id: 'LX0609-020' }
    const wrapper = await render()
    expect(wrapper.find('.drawer').text()).toContain('LX0609-020')
    expect(wrapper.find('.row[data-id="LX0609-020"]').exists()).toBe(true)
    wrapper.unmount()
    vi.clearAllMocks()
    state.query = { rule_set_key: 'unknown-set', rule_id: 'LX0609-001' }
    const invalid = await render()
    expect(invalid.text()).toContain('不支持请求的规则集')
    expect(state.api.listRuleSetVersions).not.toHaveBeenCalled()
    invalid.unmount()
  })

  it('在现有详情抽屉显式配置科室范围与医生端开关并保存到同一草稿', async () => {
    state.api.createRuleSetDraft.mockResolvedValue(ok(draftOf(entries, 1)))
    state.api.updateRuleSetDraft.mockImplementation(
      async (_key: string, payload: { entries: RuleSetEntryView[] }) =>
        ok(draftOf(payload.entries, 2)),
    )
    const wrapper = await render()

    await button(wrapper, '查看', '.row[data-id="LX0609-001"]').trigger('click')
    await flush()
    const choices = wrapper.findAll('.drawer .radio-group')
    await choices[0].setValue('all')
    await choices[1].setValue('visible')
    await button(wrapper, '保存到草稿', '.drawer').trigger('click')
    await flush()

    expect(state.api.updateRuleSetDraft).toHaveBeenCalledWith(KEY, {
      version_seq: 1,
      entries: expect.arrayContaining([
        expect.objectContaining({
          rule_id: 'LX0609-001',
          department_scope_mode: 'all',
          department_refs: [],
          doctor_visible: true,
        }),
      ]),
    })
    expect(state.message.success).toHaveBeenCalledWith(expect.stringContaining('发布新版本后生效'))
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
    expect(state.api.updateRuleSetDraft).toHaveBeenCalledWith(
      KEY,
      expect.objectContaining({ version_seq: 4 }),
    )
    const sent = state.api.updateRuleSetDraft.mock.calls[0]?.[1] as {
      entries: Array<{ rule_id: string; state: string }>
    }
    expect(sent.entries.find((item) => item.rule_id === 'LX0609-033')?.state).toBe('active')
  })

  it('草稿 CAS 冲突时提示并刷新', async () => {
    state.api.listRuleSetVersions.mockResolvedValue(ok(list({ draft: draftOf(entries, 2) })))
    state.api.updateRuleSetDraft.mockResolvedValue({
      success: false,
      status: 409,
      code: 'version_conflict',
      message: '草稿已被修改',
    })
    const wrapper = await render()
    await selectRow(wrapper, 'LX0609-002')
    await button(wrapper, '批量下线').trigger('click')
    await flush()
    expect(state.message.warning).toHaveBeenCalledWith(expect.stringContaining('已刷新'))
    expect(state.api.listRuleSetVersions).toHaveBeenCalledTimes(2)
  })

  it('只把确认时冻结的当前暂停或下线规则写为删除态，并在草稿中禁止恢复', async () => {
    state.api.listRuleSetVersions.mockResolvedValue(ok(list({ draft: draftOf(entries, 4) })))
    const deletedEntries = entries.map((item) =>
      item.rule_id === 'LX0609-020' ? { ...item, state: 'deleted' as const } : item,
    )
    state.api.updateRuleSetDraft.mockResolvedValue(ok(draftOf(deletedEntries, 5)))
    const wrapper = await render()
    await wrapper.find('.tab-offline').trigger('click')
    await flush()

    await selectRow(wrapper, 'LX0609-020')
    const confirm = wrapper.find('.batch-delete').element.parentElement
    ;(confirm?.querySelector('.pop-open') as HTMLElement).click()
    await selectRow(wrapper, 'LX0609-033')
    ;(confirm?.querySelector('.pop-ok') as HTMLElement).click()
    await flush()

    expect(state.api.updateRuleSetDraft).toHaveBeenCalledWith(KEY, {
      version_seq: 4,
      entries: expect.arrayContaining([{ rule_id: 'LX0609-020', state: 'deleted' }]),
    })
    expect(state.api.updateRuleSetDraft.mock.calls[0]?.[1].entries).toContainEqual({
      rule_id: 'LX0609-033',
      state: 'offline',
    })
    expect(wrapper.find('.row[data-id="LX0609-020"]').text()).toContain('草稿：已删除')
    expect(
      wrapper.find('.row[data-id="LX0609-020"] .select-row').attributes('disabled'),
    ).toBeDefined()
  })

  it('当前在线规则不能直接删除，已发布删除项不出现在管理列表但历史计数保留', async () => {
    const withDeleted: RuleSetEntryView[] = [
      ...entries,
      {
        rule_id: 'LX0609-099',
        state: 'deleted',
        executable: false,
        qc_point: '历史删除规则',
        source_document: null,
      },
    ]
    state.api.listRuleSetVersions.mockResolvedValue(
      ok(
        list({
          items: [versionItem({ deleted_count: 1 })],
        }),
      ),
    )
    state.api.getRuleSetVersion.mockResolvedValue(ok(detail(BUILTIN, withDeleted)))
    const wrapper = await render()

    await selectRow(wrapper, 'LX0609-001')
    expect(wrapper.find('.batch-delete').attributes('disabled')).toBeDefined()
    expect(wrapper.find('.row[data-id="LX0609-099"]').exists()).toBe(false)
    await button(wrapper, '版本历史').trigger('click')
    await flush()
    expect(wrapper.find('.history-counts').text()).toContain('删除 1')
  })

  it('删除确认冻结规则集，切换规则集后不能把同ID删除到新规则集', async () => {
    state.api.listRuleSetVersions.mockResolvedValue(ok(list({ draft: draftOf(entries, 4) })))
    const wrapper = await render()
    await wrapper.find('.tab-offline').trigger('click')
    await selectRow(wrapper, 'LX0609-033')
    const confirm = wrapper.find('.batch-delete').element.parentElement
    ;(confirm?.querySelector('.pop-open') as HTMLElement).click()

    await wrapper.find('.rule-set-select').setValue('luxian_0916_qc_v1')
    await flush()
    ;(confirm?.querySelector('.pop-ok') as HTMLElement).click()
    await flush()

    expect(state.api.updateRuleSetDraft).not.toHaveBeenCalled()
    expect(state.api.createRuleSetDraft).not.toHaveBeenCalled()
    expect(state.message.success).not.toHaveBeenCalled()
  })

  it.each([
    [
      '旧成功',
      ok(
        draftOf(
          entries.map((item) =>
            item.rule_id === 'LX0609-001' ? { ...item, state: 'paused' as const } : item,
          ),
          5,
        ),
      ),
    ],
    ['旧失败', { success: false, status: 409, code: 'version_conflict', message: '旧账号冲突' }],
  ])('同角色换账号后丢弃在途更新的%s回执，不污染新账号状态或提示', async (_label, lateResult) => {
    state.api.listRuleSetVersions.mockResolvedValue(ok(list({ draft: draftOf(entries, 4) })))
    const pending = deferred<typeof lateResult>()
    state.api.updateRuleSetDraft.mockReturnValue(pending.promise)
    const wrapper = await render()
    await selectRow(wrapper, 'LX0609-001')
    await button(wrapper, '批量暂停').trigger('click')
    await flush()
    expect(state.api.updateRuleSetDraft).toHaveBeenCalledTimes(1)

    state.auth!.user = { id: 'manager-2' }
    await flush()
    pending.resolve(lateResult)
    await flush()

    expect(state.api.listRuleSetVersions).toHaveBeenCalledTimes(2)
    expect(state.message.success).not.toHaveBeenCalledWith(expect.stringContaining('改为“已暂停”'))
    expect(state.message.warning).not.toHaveBeenCalledWith(expect.stringContaining('旧账号冲突'))
    expect(wrapper.find('.row[data-id="LX0609-001"]').text()).not.toContain('草稿：已暂停')
  })

  it('发布：成功刷新、422 逐条展示 problems、409 提示版本号重复', async () => {
    const changed = entries.map((item) =>
      item.rule_id === 'LX0609-002' ? { ...item, state: 'offline' as const } : item,
    )
    state.api.listRuleSetVersions.mockResolvedValue(ok(list({ draft: draftOf(changed, 3) })))
    state.api.publishRuleSetDraft
      .mockResolvedValueOnce({
        success: false,
        status: 422,
        code: 'publish_validation_failed',
        message: '校验未通过',
        problems: ['至少需要 1 条 active 规则', '以下规则当前不可执行：LX0609-020'],
      })
      .mockResolvedValueOnce({
        success: false,
        status: 409,
        code: 'version_exists',
        message: '版本号已存在',
      })
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
    expect(state.api.publishRuleSetDraft).toHaveBeenLastCalledWith(KEY, {
      version: 'v2',
      note: '下线 002',
      version_seq: 3,
    })
    expect(wrapper.findAll('.problem-list li').map((item) => item.text())).toEqual([
      '至少需要 1 条 active 规则',
      '以下规则当前不可执行：LX0609-020',
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
    state.api.listRuleSetVersions.mockResolvedValue(
      ok(
        list({
          draft: draftOf(
            entries.map((item) => ({ ...item, state: 'paused' as const })),
            1,
          ),
        }),
      ),
    )
    const wrapper = await render()
    await button(wrapper, '发布新版本').trigger('click')
    await flush()
    await wrapper.find('.modal .version-input').setValue('-bad/version')
    await button(wrapper, '确认发布', '.modal').trigger('click')
    await flush()
    expect(state.api.publishRuleSetDraft).not.toHaveBeenCalled()
    expect(wrapper.find('.publish-error').text()).toContain('版本号只能包含')
  })

  it('发布结果未知时不提示成功，先回读版本与草稿', async () => {
    const changed = entries.map((item) =>
      item.rule_id === 'LX0609-033' ? { ...item, state: 'deleted' as const } : item,
    )
    state.api.listRuleSetVersions.mockResolvedValue(ok(list({ draft: draftOf(changed, 6) })))
    state.api.publishRuleSetDraft.mockResolvedValue({
      success: false,
      status: 503,
      message: '服务暂不可用',
    })
    const wrapper = await render()
    await button(wrapper, '发布新版本').trigger('click')
    await flush()
    await wrapper.find('.modal .version-input').setValue('v-delete')
    await button(wrapper, '确认发布', '.modal').trigger('click')
    await flush()

    expect(state.message.success).not.toHaveBeenCalledWith(expect.stringContaining('v-delete'))
    expect(state.message.warning).toHaveBeenCalledWith(expect.stringContaining('发布结果未确认'))
    expect(state.api.listRuleSetVersions).toHaveBeenCalledTimes(2)
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
    state.api.listRuleSetVersions.mockResolvedValue(
      ok(
        list({
          current_version: 'v2',
          items: [
            versionItem({
              id: 'id-2',
              version: 'v2',
              status: 'published',
              source: 'published',
              is_current: true,
              published_by: 'u-9',
              published_at: '2026-09-27T02:00:00',
              version_seq: 2,
            }),
            versionItem({
              id: 'id-1',
              version: 'v1',
              status: 'published',
              source: 'published',
              is_current: false,
              published_by: 'u-8',
              published_at: '2026-09-26T02:00:00',
              version_seq: 2,
            }),
            versionItem({
              id: 'id-0',
              version: 'v0',
              status: 'retired',
              source: 'retired',
              is_current: false,
              version_seq: 3,
            }),
            versionItem({ is_current: false }),
          ],
        }),
      ),
    )
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
    state.api.listRuleSetVersions.mockResolvedValue(
      ok(
        list({
          items: [
            versionItem({
              id: 'id-1',
              version: 'v1',
              status: 'published',
              source: 'published',
              is_current: false,
              version_seq: 1,
            }),
            versionItem(),
          ],
        }),
      ),
    )
    state.api.retireRuleSetVersion.mockResolvedValue({
      success: false,
      status: 409,
      code: 'already_retired',
      message: 'x',
    })
    const wrapper = await render()
    await button(wrapper, '版本历史').trigger('click')
    await flush()
    await wrapper.find('.drawer .pop-ok').trigger('click')
    await flush()
    expect(state.message.warning).toHaveBeenCalledWith('该版本已下线，已刷新版本列表')
  })

  it('未上线页签接入本人自定义草稿，内置规则判定逻辑保持只读', async () => {
    const wrapper = await render()
    expect(wrapper.find('.custom-draft-panel-stub').exists()).toBe(false)
    await wrapper.find('.tab-offline').trigger('click')
    await flush()
    const panel = wrapper.get('.custom-draft-panel-stub')
    expect(panel.attributes('data-actor')).toBe('manager-1|qc_manager')
    expect(panel.attributes('data-can-manage')).toBe('true')

    await button(wrapper, '查看', '.row[data-id="LX0609-020"]').trigger('click')
    await flush()
    const drawer = wrapper.get('.drawer')
    expect(drawer.text()).toContain('LX0609-020')
    expect(drawer.text()).toContain('会诊记录')
    expect(drawer.text()).toContain('已暂停')
    expect(drawer.text()).toContain('不可执行')
    expect(drawer.text()).toContain('不支持在线编辑')
    expect(drawer.text()).toContain('科室范围')
    expect(drawer.text()).toContain('医生端结果')
    expect(drawer.findAll('button').some((item) => item.text() === '编辑')).toBe(false)
  })

  it('只读角色不显示写操作', async () => {
    state.auth!.userRoles = ['qc_doctor']
    state.api.listRuleSetVersions.mockResolvedValue(
      ok(
        list({
          draft: draftOf(
            entries.map((item) => ({ ...item, state: 'paused' as const })),
            1,
          ),
          items: [
            versionItem({
              id: 'id-1',
              version: 'v1',
              status: 'published',
              source: 'published',
              is_current: false,
            }),
            versionItem(),
          ],
        }),
      ),
    )
    const wrapper = await render()
    expect(wrapper.text()).toContain('当前角色只读')
    expect(
      wrapper
        .findAll('button')
        .some((item) =>
          ['批量开启', '批量暂停', '批量下线', '新建质控点', '发布新版本', '放弃草稿'].includes(
            item.text(),
          ),
        ),
    ).toBe(false)
    expect(wrapper.find('.select-row').exists()).toBe(false)
    await button(wrapper, '版本历史').trigger('click')
    await flush()
    expect(wrapper.find('.drawer .retire-btn').exists()).toBe(false)
  })

  it('0916 暂仅内置版本，只读展示', async () => {
    const wrapper = await render()
    state.api.listRuleSetVersions.mockResolvedValue(
      ok(
        list({
          rule_set_key: 'luxian_0916_qc_v1',
          versionable: false,
          builtin_version: '2026-09-16',
          current_version: '2026-09-16',
          items: [versionItem({ rule_set_key: 'luxian_0916_qc_v1', version: '2026-09-16' })],
        }),
      ),
    )
    state.api.getRuleSetVersion.mockResolvedValue(
      ok(
        detail('2026-09-16', [
          {
            rule_id: 'LX0916-001',
            state: 'active',
            executable: true,
            qc_point: null,
            source_document: null,
          },
        ]),
      ),
    )
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

  it('编码模式使用独立规则集与权威分类，不提供新建或单项查看编辑', async () => {
    const codingEntries: RuleSetEntryView[] = [
      {
        rule_id: 'CR-001',
        state: 'active',
        executable: true,
        qc_point: '诊断编码格式校验',
        source_document: null,
        category: 'format',
        category_name: '格式校验',
      },
      {
        rule_id: 'CR-011',
        state: 'paused',
        executable: false,
        qc_point: '非特指编码检测',
        source_document: null,
        category: 'specificity',
        category_name: '特异性校验',
      },
      {
        rule_id: 'CR-018',
        state: 'paused',
        executable: false,
        qc_point: 'AI语义综合审查',
        source_document: null,
        category: 'ai_semantic',
        category_name: 'AI语义审查',
      },
    ]
    state.api.listRuleSetVersions.mockResolvedValue(
      ok({
        rule_set_key: 'coding_qc_v1',
        versionable: true,
        builtin_version: '1.0',
        current_version: '1.0',
        items: [
          versionItem({
            rule_set_key: 'coding_qc_v1',
            version: '1.0',
            active_count: 1,
            paused_count: 2,
            offline_count: 0,
          }),
        ],
        draft: null,
      }),
    )
    state.api.getRuleSetVersion.mockResolvedValue(
      ok({
        ...detail('1.0', codingEntries),
        rule_set_key: 'coding_qc_v1',
        resolution: {
          rule_set_key: 'coding_qc_v1',
          version: '1.0',
          source: 'builtin',
          active_rule_ids: ['CR-001'],
          paused_rule_ids: ['CR-011', 'CR-018'],
          excluded_rule_ids: ['CR-011', 'CR-018'],
          content_digest: 'coding-digest',
        },
      }),
    )

    const wrapper = await render({ managementMode: 'coding' })
    expect(state.api.listRuleSetVersions).toHaveBeenCalledWith('coding_qc_v1')
    expect(wrapper.text()).toContain('编码质控点管理')
    expect(wrapper.text()).toContain('格式校验')
    expect(wrapper.find('.rule-set-select').exists()).toBe(false)
    expect(
      wrapper
        .findAll('button')
        .some((item) => ['新建质控点', '查看', '编辑'].includes(item.text())),
    ).toBe(false)

    await wrapper.find('.tab-offline').trigger('click')
    await flush()
    expect(wrapper.find('.custom-draft-panel-stub').exists()).toBe(false)
    expect(wrapper.findAll('button').some((item) => item.text() === '查看')).toBe(false)
    await selectRow(wrapper, 'CR-011')
    expect(button(wrapper, '批量开启').attributes('disabled')).toBeDefined()
    expect(wrapper.find('.tooltip').attributes('data-tip')).toContain('CR-011 当前不可执行')
  })

  it('同一组件双向切换管理模式时切换真实规则集，并丢弃旧模式迟到回执', async () => {
    const oldNoncoding = deferred<{ success: boolean; data: RuleSetVersionList; status: number }>()
    const codingList: RuleSetVersionList = {
      rule_set_key: 'coding_qc_v1',
      versionable: true,
      builtin_version: '1.0',
      current_version: '1.0',
      items: [versionItem({ rule_set_key: 'coding_qc_v1', version: '1.0' })],
      draft: null,
    }
    state.api.listRuleSetVersions
      .mockReturnValueOnce(oldNoncoding.promise)
      .mockResolvedValueOnce(ok(codingList))
      .mockResolvedValueOnce(ok(list()))
    const wrapper = await render()
    expect(state.api.listRuleSetVersions).toHaveBeenNthCalledWith(1, KEY)

    await wrapper.setProps({ managementMode: 'coding' })
    await flush()
    expect(state.api.listRuleSetVersions).toHaveBeenNthCalledWith(2, 'coding_qc_v1')
    expect(wrapper.text()).toContain('编码质控点管理')

    oldNoncoding.resolve(ok(list()))
    await flush()
    expect(wrapper.text()).toContain('编码质控点管理')
    expect(wrapper.find('.rule-set-select').exists()).toBe(false)

    await wrapper.setProps({ managementMode: 'noncoding' })
    await flush()
    expect(state.api.listRuleSetVersions).toHaveBeenNthCalledWith(3, KEY)
    expect(wrapper.text()).toContain('非编码质控点管理')
    expect(wrapper.find('.rule-set-select').exists()).toBe(true)
  })
})
