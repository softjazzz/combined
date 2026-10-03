import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ScoringStandardsView from '../../ScoringStandardsView.vue'
const mocks = vi.hoisted(() => ({ list: vi.fn(), create: vi.fn(), activate: vi.fn() }))
vi.mock('@/api/scoring', () => ({ listScoringStandards: mocks.list, createScoringStandard: mocks.create, activateScoringStandard: mocks.activate,
  archiveScoringStandard: vi.fn(), copyScoringStandard: vi.fn(), deleteScoringStandard: vi.fn(), exportScoringStandard: vi.fn(), importScoringStandard: vi.fn(), setDefaultScoringStandard: vi.fn(),
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ hasRole: () => true }) }))
vi.mock('ant-design-vue', () => ({ message: { success: vi.fn(), error: vi.fn(), warning: vi.fn() } }))
const scenes = [{ scene: 'running', rule_sets: [] }, { scene: 'frontpage', rule_sets: [{ rule_set_key: 'frontpage_formal_v1', rule_set_name: '病案首页形式质控' }] }, { scene: 'outpatient', rule_sets: [] }]
const render = () => mount(ScoringStandardsView, { global: { stubs: {
  SpecialReportDefaultPanel: true, ScoringStandardEditor: true,
  'a-tabs': { emits: ['update:activeKey'], template: '<div><button data-testid="frontpage-tab" @click="$emit(\'update:activeKey\', \'frontpage\')">病案首页</button><button data-testid="outpatient-tab" @click="$emit(\'update:activeKey\', \'outpatient\')">门急诊</button><slot /></div>' },
  'a-tab-pane': true, 'a-alert': true, 'a-select': true, 'a-radio': true, 'a-radio-group': true, 'a-popconfirm': true,
  'a-modal': { props: ['open'], emits: ['ok'], template: '<div v-if="open"><slot /><button class="modal-ok" @click="$emit(\'ok\')">确认</button></div>' },
  'a-input': { props: ['value'], emits: ['update:value'], template: '<input :value="value" @input="$emit(\'update:value\', $event.target.value)" />' },
  'a-button': { props: ['disabled'], template: '<button :disabled="disabled"><slot /></button>' },
} } })
beforeEach(() => { vi.resetAllMocks(); mocks.list.mockResolvedValue({ success: true, data: { items: [], scenes } }); mocks.create.mockResolvedValue({ success: true, data: { id: 'F1', scene: 'frontpage' } }) })
describe('首页评分配置沿用标准流程', () => {
  it('真实FQ目录启用首页新建，payload明确独立scene/key', async () => {
    const wrapper = render(); await flushPromises()
    await wrapper.get('[data-testid="frontpage-tab"]').trigger('click'); await flushPromises()
    expect(mocks.list).toHaveBeenLastCalledWith({ scene: 'frontpage' })
    expect(wrapper.get('[data-testid="scoring-create"]').attributes('disabled')).toBeUndefined()
    await wrapper.get('[data-testid="scoring-create"]').trigger('click')
    await wrapper.get('[data-testid="scoring-form-name"]').setValue('合成首页标准')
    await wrapper.get('.modal-ok').trigger('click'); await flushPromises()
    expect(mocks.create).toHaveBeenCalledWith(expect.objectContaining({ scene: 'frontpage', rule_set_key: 'frontpage_formal_v1' }))
    wrapper.unmount()
  })
  it('门急诊仍失败关闭，不因首页新增目录误开放创建', async () => {
    const wrapper = render(); await flushPromises()
    await wrapper.get('[data-testid="frontpage-tab"]').trigger('click'); await flushPromises()
    await wrapper.get('[data-testid="outpatient-tab"]').trigger('click'); await flushPromises()
    expect(wrapper.get('[data-testid="scoring-create"]').attributes('disabled')).toBeDefined()
    expect(mocks.create).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('首页默认只取本场景，草稿启用保留已有版本CAS流程', async () => {
    const frontpage = { id: 'F1', name: '合成首页标准', scene: 'frontpage', rule_set_key: 'frontpage_formal_v1', status: 'draft', is_default: false, version_seq: 4, base_score: 100, grade_bands: [] }
    mocks.list.mockResolvedValue({ success: true, data: { items: [frontpage, { ...frontpage, id: 'final-default', scene: 'final', name: '禁止继承的终末默认', status: 'active', is_default: true }], scenes } })
    mocks.activate.mockResolvedValue({ success: true, data: { ...frontpage, status: 'active', is_default: true } })
    const wrapper = render(); await flushPromises()
    await wrapper.get('[data-testid="frontpage-tab"]').trigger('click'); await flushPromises()
    expect(wrapper.text()).not.toContain('禁止继承的终末默认')
    expect(wrapper.get('[data-testid="scoring-default-name"]').text()).toBe('未配置评分标准')
    await wrapper.get('[data-testid="scoring-action-activate"]').trigger('click')
    await wrapper.get('.modal-ok').trigger('click'); await flushPromises()
    expect(mocks.activate).toHaveBeenCalledWith('F1', { version_seq: 4, replace_mode: 'archive' })
    wrapper.unmount()
  })
})
