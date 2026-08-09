import { nextTick } from 'vue'
import { shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const roles = vi.hoisted(() => ({ value: ['doctor'] as string[] }))
const getExtractionSettings = vi.hoisted(() => vi.fn())

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ userRoles: roles.value }),
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

  it.each(['admin', 'qc_manager', 'sync_admin', 'super_admin'])(
    '%s 可以编辑首页抽取配置',
    async (role) => {
      roles.value = [role]
      const wrapper = await mountPanel()

      expect(
        wrapper.get('[data-testid="frontpage-settings-save"]').attributes('disabled'),
      ).toBeUndefined()
    },
  )

  it('doctor 只能查看首页抽取配置', async () => {
    roles.value = ['doctor']
    const wrapper = await mountPanel()

    expect(
      wrapper.get('[data-testid="frontpage-settings-save"]').attributes('disabled'),
    ).toBeDefined()
    expect(wrapper.text()).toContain('当前账号仅可查看')
  })
})
