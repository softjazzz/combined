import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import ScoringStandardsView from '../../ScoringStandardsView.vue'

const mocks = vi.hoisted(() => ({ get: vi.fn(), list: vi.fn(), put: vi.fn() }))
vi.mock('@/api/scoring', () => ({
  getSpecialReportDefault: mocks.get, listScoringStandards: mocks.list, setSpecialReportDefault: mocks.put,
  activateScoringStandard: vi.fn(), archiveScoringStandard: vi.fn(), copyScoringStandard: vi.fn(),
  createScoringStandard: vi.fn(), deleteScoringStandard: vi.fn(), exportScoringStandard: vi.fn(),
  importScoringStandard: vi.fn(), setDefaultScoringStandard: vi.fn(),
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ user: { id: 'synthetic-user' }, hasRole: () => true }) }))
describe('专用绑定来源与原配置页隔离', () => {
  it('迁移缺失503只阻断专用用途，原标准列表与编辑仍可用', async () => {
    mocks.get.mockResolvedValue({ success: false, status: 503, message: '特殊报表配置不可用' })
    mocks.list.mockResolvedValue({ success: true, data: {
      items: [{ id: 'S1', name: '合成运行标准', scene: 'running', status: 'draft', is_default: false, base_score: 100, grade_bands: [], version_seq: 1 }],
      scenes: [{ scene: 'running', rule_sets: [{ rule_set_key: 'synthetic', rule_set_name: '合成规则集' }] }],
    } })
    const wrapper = mount(ScoringStandardsView, { global: { stubs: {
      ScoringStandardEditor: { props: ['open', 'standardId'], template: '<div data-testid="editor" :data-open="open" :data-id="standardId" />' },
      'a-tabs': { template: '<div><slot /></div>' }, 'a-tab-pane': true,
      'a-button': { props: ['htmlType', 'disabled'], template: '<button :type="htmlType || \'button\'" :disabled="disabled"><slot /></button>' },
      'a-modal': true, 'a-popconfirm': true, 'a-alert': true,
      'a-input': true, 'a-select': true, 'a-radio': true, 'a-radio-group': true,
    } } })
    await flushPromises()
    expect(wrapper.text()).toContain('特殊报表配置不可用')
    expect(wrapper.get('[data-testid="scoring-standard-row"]').text()).toContain('合成运行标准')
    expect(wrapper.find('[data-testid="special-default-save"]').exists()).toBe(false)
    await wrapper.get('[data-testid="scoring-action-open"]').trigger('click')
    expect(wrapper.get('[data-testid="editor"]').attributes('data-id')).toBe('S1')
    expect(wrapper.get('[data-testid="editor"]').attributes('data-open')).toBe('true')
    expect(mocks.put).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
