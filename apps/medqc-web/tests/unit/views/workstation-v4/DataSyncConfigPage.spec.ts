import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, reactive, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DataSyncConfigPage from '@/views/workstation-v4/DataSyncConfigPage.vue'

const { mockRouterReplace, mockUseDataSync, mockConfirmDiscardChanges } = vi.hoisted(() => ({
  mockRouterReplace: vi.fn(),
  mockUseDataSync: vi.fn(),
  mockConfirmDiscardChanges: vi.fn(),
}))

let mockUserRoles = ['admin', 'qc_manager']
const mockLlmHasUnsavedChanges = ref(false)

const mockAuthStore = {
  get userRoles() {
    return mockUserRoles
  },
  user: {
    is_demo_account: false,
  },
}

const mockRoute = reactive({ query: {} as Record<string, string> })

vi.mock('@/views/workstation-v4/components/system-config/ClinicalSourceSettingsPanel.vue', () => ({
  default: { template: '<div data-testid="clinical-source-settings" />' },
}))

vi.mock('vue-router', () => ({
  useRoute: () => mockRoute,
  useRouter: () => ({
    replace: mockRouterReplace,
  }),
}))

vi.mock('@/views/workstation-v4/composables/useDataSync', () => ({
  useDataSync: mockUseDataSync,
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => mockAuthStore,
}))

const LLMApiConfigStub = defineComponent({
  name: 'LLMApiConfig',
  setup(_, { expose }) {
    expose({
      hasUnsavedChanges: mockLlmHasUnsavedChanges,
      confirmDiscardChanges: mockConfirmDiscardChanges,
    })
    return () => null
  },
  template: '<div data-testid="llm-config-panel" />',
})

function mountPage(options?: { attachTo?: HTMLElement }) {
  return mount(DataSyncConfigPage, {
    attachTo: options?.attachTo,
    global: {
      stubs: {
        FrontpageExtractionSettingsPanel: {
          template: '<div data-testid="frontpage-extraction-panel" />',
        },
        LLMApiConfig: LLMApiConfigStub,
        LlmPerformanceObservabilityPanel: {
          template: '<div data-testid="llm-observability-panel" />',
        },
        AccountManagementPanel: { template: '<div data-testid="real-accounts-panel" />' },
        QcRuntimeSettingsPanel: { template: '<div data-testid="qc-runtime-panel" />' },
        DataPipelineSettingsPanel: {
          emits: ['selection', 'ready'],
          mounted() {
            this.$emit('selection', 'legacy_pg')
            this.$emit('ready', true)
          },
          template:
            '<div data-testid="pipeline-settings-panel"><button data-testid="choose-independent" @click="$emit(\'selection\', \'independent_cdm\')">独立链路</button><button data-testid="pipeline-load-failed" @click="$emit(\'ready\', false)">配置失败</button></div>',
        },
        DailyQcSchedulePanel: { template: '<div data-testid="daily-schedule-panel" />' },
      },
    },
  })
}

describe('DataSyncConfigPage', () => {
  beforeEach(() => {
    mockRouterReplace.mockReset()
    mockUseDataSync.mockReset()
    mockConfirmDiscardChanges.mockReset()
    mockConfirmDiscardChanges.mockResolvedValue(true)
    mockLlmHasUnsavedChanges.value = false
    mockUserRoles = ['admin', 'qc_manager']
    mockAuthStore.user.is_demo_account = false
    mockRoute.query = {}
  })

  it('系统管理员可直接进入质控运行设置', async () => {
    mockUserRoles = ['sync_admin']
    mockRoute.query = { tab: 'qcRuntime' }
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.find('[data-testid="qc-runtime-tab"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="qc-runtime-panel"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('演示账号不能通过链接进入质控运行设置', async () => {
    mockUserRoles = ['admin']
    mockAuthStore.user.is_demo_account = true
    mockRoute.query = { tab: 'qcRuntime' }
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.find('[data-testid="qc-runtime-tab"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="qc-runtime-panel"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('旧PG同步向导已彻底移除，不会调用 useDataSync 或渲染旧同步界面', async () => {
    mockUserRoles = ['sync_admin']
    const wrapper = mountPage()
    await flushPromises()
    expect(mockUseDataSync).not.toHaveBeenCalled()
    expect(wrapper.find('[data-testid="clinical-source-settings"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="pipeline-settings-panel"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="check-record-scope-action"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('病历数据同步设置')
    expect(wrapper.text()).not.toContain('高级设置与运行记录')
    await wrapper.get('[data-testid="choose-independent"]').trigger('click')
    await wrapper.get('[data-testid="pipeline-load-failed"]').trigger('click')
    expect(wrapper.text()).not.toContain('病历数据同步设置')
    expect(mockUseDataSync).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('每日质控页签可直达且非管理员不能直达', async () => {
    mockUserRoles = ['sync_admin']
    mockRoute.query = { tab: 'dailyQc' }
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.find('[data-testid="daily-schedule-panel"]').exists()).toBe(true)
    wrapper.unmount()

    mockUserRoles = ['doctor']
    const denied = mountPage()
    await flushPromises()
    expect(denied.find('[data-testid="daily-schedule-panel"]').exists()).toBe(false)
    denied.unmount()
  })

  it('管理员可在V5系统配置进入真实账号管理，不跳旧版页面', async () => {
    mockUserRoles = ['admin']
    mockRoute.query = { tab: 'accounts' }
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.find('[data-testid="account-management-tab"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="real-accounts-panel"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('非管理员不显示账号管理，不能通过查询参数打开', async () => {
    mockUserRoles = ['qc_manager']
    mockRoute.query = { tab: 'accounts' }
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.find('[data-testid="account-management-tab"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="real-accounts-panel"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('super_admin 完整显示全部 7 个活动页签并支持键盘导航切换', async () => {
    mockUserRoles = ['super_admin']
    const wrapper = mountPage({ attachTo: document.body })
    await flushPromises()

    const tabs = wrapper.findAll('[role="tab"]')
    expect(tabs.map((tab) => tab.text())).toEqual([
      '数据同步',
      '质控运行',
      '定时质控',
      '首页抽取设置',
      '模型性能',
      '模型配置',
      '账号管理',
    ])

    await tabs[0].trigger('keydown', { key: 'End' })
    await flushPromises()
    expect(wrapper.get('[data-testid="system-config-tabs"]').attributes('data-active-key')).toBe(
      'accounts',
    )

    await tabs[6].trigger('keydown', { key: 'Home' })
    await flushPromises()
    expect(wrapper.get('[data-testid="system-config-tabs"]').attributes('data-active-key')).toBe(
      'dataSync',
    )
    wrapper.unmount()
  })

  it('程序或浏览器变更 ?tab= 时同样遵守 llmConfig 未保存修改拦截', async () => {
    mockUserRoles = ['super_admin']
    mockRoute.query = { tab: 'llmConfig' }
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.get('[data-testid="system-config-tabs"]').attributes('data-active-key')).toBe(
      'llmConfig',
    )

    // 有未保存修改且用户取消离开 -> 停留在 llmConfig 并回写路由查询参数
    mockLlmHasUnsavedChanges.value = true
    mockConfirmDiscardChanges.mockResolvedValueOnce(false)
    mockRoute.query = { tab: 'accounts' }
    await flushPromises()

    expect(mockConfirmDiscardChanges).toHaveBeenCalledTimes(1)
    expect(wrapper.get('[data-testid="system-config-tabs"]').attributes('data-active-key')).toBe(
      'llmConfig',
    )
    expect(mockRouterReplace).toHaveBeenCalledWith({ query: { tab: 'llmConfig' } })

    // 模拟回写后再次切换且用户确认放弃 -> 成功切换到 dailyQc
    mockRoute.query = { tab: 'llmConfig' }
    await flushPromises()
    mockConfirmDiscardChanges.mockResolvedValueOnce(true)
    mockRoute.query = { tab: 'dailyQc' }
    await flushPromises()

    expect(mockConfirmDiscardChanges).toHaveBeenCalledTimes(2)
    expect(wrapper.get('[data-testid="system-config-tabs"]').attributes('data-active-key')).toBe(
      'dailyQc',
    )
    expect(wrapper.find('[data-testid="daily-schedule-panel"]').exists()).toBe(true)
    wrapper.unmount()
  })
})
