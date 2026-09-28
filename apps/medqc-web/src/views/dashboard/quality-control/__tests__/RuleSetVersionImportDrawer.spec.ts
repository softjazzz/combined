import { defineComponent } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  importDraft: vi.fn(),
  warning: vi.fn(),
}))

vi.mock('@/api/ruleSetVersions', () => ({ importRuleSetDraft: mocks.importDraft }))
vi.mock('ant-design-vue', () => ({ message: { warning: mocks.warning } }))

import RuleSetVersionImportDrawer from '@/views/dashboard/quality-control/components/RuleSetVersionImportDrawer.vue'

const global = {
  stubs: {
    'a-drawer': defineComponent({
      props: { open: Boolean },
      template: '<section v-if="open"><slot/><footer><slot name="footer"/></footer></section>',
    }),
    'a-button': defineComponent({
      props: { disabled: Boolean, loading: Boolean },
      template: '<button :disabled="disabled || loading"><slot name="icon"/><slot/></button>',
    }),
    'a-checkbox': defineComponent({
      props: { checked: Boolean, disabled: Boolean },
      emits: ['update:checked'],
      template: '<label><input type="checkbox" :checked="checked" :disabled="disabled" @change="$emit(\'update:checked\', $event.target.checked)"><slot/></label>',
    }),
    'a-alert': defineComponent({
      props: { message: String, description: String },
      template: '<div><strong>{{ message }}</strong><span>{{ description }}</span></div>',
    }),
  },
}

function file(name = 'rules.xlsx', size?: number) {
  const result = new File(['xlsx'], name)
  if (size !== undefined) Object.defineProperty(result, 'size', { value: size })
  return result
}

async function choose(wrapper: ReturnType<typeof mount>, value: File) {
  const input = wrapper.get('[data-testid="rule-version-import-file"]')
  Object.defineProperty(input.element, 'files', { value: [value], configurable: true })
  await input.trigger('change')
}

async function confirm(wrapper: ReturnType<typeof mount>) {
  await wrapper.get('[data-testid="rule-version-import-confirm"] input').setValue(true)
}

describe('规则集版本导入抽屉', () => {
  beforeEach(() => vi.resetAllMocks())

  it('明确确认后导入草稿，成功刷新并锁住重复提交', async () => {
    mocks.importDraft.mockResolvedValue({
      success: true,
      status: 200,
      resultUnknown: false,
      data: { version_seq: 2, base_version: '2026-06-09' },
    })
    const selected = file()
    const wrapper = mount(RuleSetVersionImportDrawer, {
      props: { open: true, ruleSetKey: 'luxian_0609_qc_v1' }, global,
    })
    await choose(wrapper, selected)
    expect(wrapper.get('[data-testid="rule-version-import-submit"]').attributes('disabled')).toBeDefined()
    await confirm(wrapper)
    await wrapper.get('[data-testid="rule-version-import-submit"]').trigger('click')
    await flushPromises()
    expect(mocks.importDraft).toHaveBeenCalledWith('luxian_0609_qc_v1', selected)
    expect(wrapper.text()).toContain('修订号 2')
    expect(wrapper.emitted('refresh')).toHaveLength(1)
    await wrapper.get('[data-testid="rule-version-import-submit"]').trigger('click')
    expect(mocks.importDraft).toHaveBeenCalledOnce()
  })

  it('422 展示 Sheet/行/字段并允许修正文件', async () => {
    mocks.importDraft.mockResolvedValue({
      success: false, status: 422, message: '校验失败',
      resultUnknown: false,
      issues: [{ sheet: '质控点', row: 4, field: '状态', code: 'invalid_state', message: '状态无效' }],
    })
    const wrapper = mount(RuleSetVersionImportDrawer, {
      props: { open: true, ruleSetKey: 'luxian_0609_qc_v1' }, global,
    })
    await choose(wrapper, file())
    await confirm(wrapper)
    await wrapper.get('[data-testid="rule-version-import-submit"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('质控点 第 4 行')
    expect(wrapper.text()).toContain('状态无效')
    expect(wrapper.get('[data-testid="rule-version-import-file"]').attributes('disabled')).toBeUndefined()
  })

  it.each([
    { status: undefined, label: '网络异常' },
    { status: 503, label: '服务异常' },
    { status: 200, label: '异常成功响应' },
  ])('$label 视为结果未知并禁止同文件盲目重试', async ({ status }) => {
    mocks.importDraft.mockResolvedValue({ success: false, status, message: '请求失败', resultUnknown: true })
    const wrapper = mount(RuleSetVersionImportDrawer, {
      props: { open: true, ruleSetKey: 'luxian_0609_qc_v1' }, global,
    })
    await choose(wrapper, file())
    await confirm(wrapper)
    await wrapper.get('[data-testid="rule-version-import-submit"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="rule-version-import-error"]').text()).toContain('导入结果未知')
    expect(wrapper.get('[data-testid="rule-version-import-file"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="rule-version-import-submit"]').attributes('disabled')).toBeDefined()
  })

  it('拒绝非 xlsx 与超过 2 MiB 文件', async () => {
    const wrapper = mount(RuleSetVersionImportDrawer, {
      props: { open: true, ruleSetKey: 'luxian_0609_qc_v1' }, global,
    })
    await choose(wrapper, file('rules.xls'))
    expect(wrapper.text()).toContain('仅支持 .xlsx')
    await choose(wrapper, file('rules.xlsx', 2 * 1024 * 1024 + 1))
    expect(wrapper.text()).toContain('文件不能超过 2 MiB')
    expect(mocks.importDraft).not.toHaveBeenCalled()
  })
})
