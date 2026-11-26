import { nextTick } from 'vue'
import { shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const authState = vi.hoisted(() => ({
  userRoles: ['doctor'] as string[],
  user: null as { institute_id?: string | null } | null,
}))
const getExtractionSettings = vi.hoisted(() => vi.fn())

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => authState,
}))

vi.mock('@/api/frontpage', () => ({
  frontpageApi: {
    getExtractionSettings,
    updateExtractionSettings: vi.fn(),
    resetExtractionSettings: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: { success: vi.fn(), error: vi.fn() },
}))

import FrontpageExtractionSettingsPanel from '@/views/workstation-v4/components/system-config/FrontpageExtractionSettingsPanel.vue'

const ButtonStub = {
  props: { disabled: { type: Boolean, default: false } },
  template: '<button :disabled="disabled"><slot /></button>',
}
const AlertStub = {
  props: { description: { type: String, default: '' } },
  template: '<div>{{ description }}</div>',
}

async function mountPanel() {
  const wrapper = shallowMount(FrontpageExtractionSettingsPanel, {
    global: {
      stubs: {
        'a-button': ButtonStub,
        'a-alert': AlertStub,
        'a-switch': true,
        'a-input-number': true,
        'a-select': true,
        'a-select-option': true,
      },
    },
  })
  await Promise.resolve()
  await nextTick()
  return wrapper
}

describe('FrontpageExtractionSettingsPanel 权限', () => {
  beforeEach(() => {
    getExtractionSettings.mockResolvedValue({
      source: 'database',
      settings: {
        sql_prefill_enabled: true,
        llm_backfill_enabled: true,
        allow_force_llm_regenerate: true,
        include_demo_records: false,
        auto_hide_demo_when_real_data: true,
        demo_hide_threshold: 1,
        stream_progress_enabled: true,
        default_preview_tab: 'preview',
      },
    })
  })

  it.each([
    { role: 'admin', institute_id: '' },
    { role: 'sync_admin', institute_id: 'H1' },
    { role: 'super_admin', institute_id: '' },
    { role: 'super_admin', institute_id: 'H1' },
  ])('$role (institute_id=$institute_id) 可以编辑首页抽取配置', async ({ role, institute_id }) => {
    authState.userRoles = [role]
    authState.user = { institute_id }
    const wrapper = await mountPanel()

    expect(
      wrapper.get('[data-testid="frontpage-settings-save"]').attributes('disabled'),
    ).toBeUndefined()
    expect(
      wrapper.get('[data-testid="frontpage-settings-reset"]').attributes('disabled'),
    ).toBeUndefined()
  })

  it.each([
    { label: 'qc_manager', roles: ['qc_manager'], institute_id: '' },
    { label: '绑定院区 admin', roles: ['admin'], institute_id: 'H1' },
    { label: 'doctor', roles: ['doctor'], institute_id: '' },
  ])('$label 只能查看首页抽取配置（只读模式）', async ({ roles: testRoles, institute_id }) => {
    authState.userRoles = testRoles
    authState.user = { institute_id }
    const wrapper = await mountPanel()

    expect(
      wrapper.get('[data-testid="frontpage-settings-save"]').attributes('disabled'),
    ).toBeDefined()
    expect(
      wrapper.get('[data-testid="frontpage-settings-reset"]').attributes('disabled'),
    ).toBeDefined()
    expect(wrapper.text()).toContain('当前账号仅可查看')
  })
})
