import { defineComponent, nextTick, reactive, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

// 用普通函数而非 vi.fn：避免测试框架给被拒绝的 Promise 再挂一条无人处理的分支。
const handler = vi.hoisted(() => ({ run: async (): Promise<unknown> => ({}) }))
const authState = vi.hoisted(() => ({
  user: { id: 'user-initial' } as { id: string } | null,
}))
vi.mock('@/api/businessAgent', () => ({ businessAgentApi: { access: () => handler.run() } }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => authStore }))
const authStore = reactive(authState)

import GlobalAssistantHost from '@/views/workstation-v4/components/GlobalAssistantHost.vue'
import {
  hasLocalAssistant,
  useLocalAssistantRegistration,
} from '@/views/workstation-v4/composables/useAssistantRegistry'

const PanelStub = defineComponent({
  name: 'WorkstationAssistPanel',
  props: { availableTabs: Array, chatLabel: String, visible: Boolean },
  template: '<div data-testid="host-panel"><slot name="chat" :active="true" /></div>',
})
const ChatStub = defineComponent({
  name: 'BusinessAgentDrawer',
  props: { embedded: Boolean, allowCaseSelection: Boolean, open: Boolean, userContext: Object },
  template: '<div data-testid="host-chat" />',
})

function mountHost() {
  return mount(GlobalAssistantHost, {
    global: { stubs: { WorkstationAssistPanel: PanelStub, BusinessAgentDrawer: ChatStub } },
  })
}

describe('全局智能助手', () => {
  beforeEach(() => {
    authStore.user = { id: 'user-initial' }
    handler.run = async () => ({})
  })

  it('有管理范围授权时显示，只含问数对话，并允许在已授权病例/科室间切换', async () => {
    handler.run = async () => ({ doctor_case_count: 0, manager_scopes: [{ department: 'D' }] })
    const wrapper = mountHost()
    await flushPromises()
    const panel = wrapper.getComponent(PanelStub)
    expect(panel.props('availableTabs')).toEqual(['chat'])
    expect(panel.props('chatLabel')).toBe('问数')
    const chat = wrapper.getComponent(ChatStub)
    expect(chat.props('embedded')).toBe(true)
    expect(chat.props('allowCaseSelection')).toBe(true)
    expect(chat.props('userContext')).toEqual({ view: 'manager' })
    wrapper.unmount()
  })

  it('没有任何授权时不显示入口', async () => {
    handler.run = async () => ({ doctor_case_count: 0, manager_scopes: [] })
    const wrapper = mountHost()
    await flushPromises()
    expect(wrapper.find('[data-testid="global-assistant-host"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('读取授权失败时不显示入口', async () => {
    handler.run = async () => {
      throw new Error('403')
    }
    const wrapper = mountHost()
    await flushPromises()
    expect(wrapper.find('[data-testid="global-assistant-host"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('页面登记了带病例上下文的本地助手时让位，注销后恢复', async () => {
    handler.run = async () => ({ doctor_case_count: 1, manager_scopes: [] })
    const wrapper = mountHost()
    await flushPromises()
    expect(wrapper.find('[data-testid="global-assistant-host"]').exists()).toBe(true)

    const active = ref(true)
    const Page = defineComponent({
      setup() {
        useLocalAssistantRegistration(active)
        return () => null
      },
    })
    const page = mount(Page)
    await nextTick()
    expect(hasLocalAssistant.value).toBe(true)
    expect(wrapper.find('[data-testid="global-assistant-host"]').exists()).toBe(false)

    active.value = false
    await nextTick()
    expect(wrapper.find('[data-testid="global-assistant-host"]').exists()).toBe(true)
    page.unmount()
    wrapper.unmount()
    expect(hasLocalAssistant.value).toBe(false)
  })

  it('切换账号时重新查询授权，退出登录隐藏入口，预期403静默不刷错', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    let callCount = 0
    handler.run = async () => {
      callCount += 1
      if (callCount === 1) return { doctor_case_count: 1, manager_scopes: [] }
      throw { isAxiosError: true, response: { status: 403 } }
    }
    const wrapper = mountHost()
    await flushPromises()
    expect(wrapper.find('[data-testid="global-assistant-host"]').exists()).toBe(true)

    authStore.user = { id: 'user-no-access' }
    await flushPromises()
    expect(callCount).toBe(2)
    expect(wrapper.find('[data-testid="global-assistant-host"]').exists()).toBe(false)
    expect(consoleErrorSpy).not.toHaveBeenCalled()

    authStore.user = null
    await flushPromises()
    expect(callCount).toBe(2)
    expect(wrapper.find('[data-testid="global-assistant-host"]').exists()).toBe(false)
    consoleErrorSpy.mockRestore()
    wrapper.unmount()
  })
})
