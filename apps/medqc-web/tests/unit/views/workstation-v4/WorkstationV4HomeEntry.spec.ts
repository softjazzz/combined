import { defineComponent, h } from 'vue'
import { shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const routeState = vi.hoisted(() => ({
  query: {} as Record<string, string>,
}))
const authState = vi.hoisted(() => ({
  roles: [] as string[],
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({
    query: routeState.query,
  }),
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
  }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    hasRole: (role: string) => authState.roles.includes(role),
  }),
}))

import WorkstationV4HomeEntry from '@/views/workstation-v4/WorkstationV4HomeEntry.vue'

function mountHomeEntry() {
  return shallowMount(WorkstationV4HomeEntry, {
    global: {
      stubs: {
        QCOverviewView: defineComponent({
          name: 'QCOverviewView',
          setup() {
            return () => h('section', { 'data-testid': 'qc-overview-view' }, '首页')
          },
        }),
        WorkstationV4View: defineComponent({
          name: 'WorkstationV4View',
          setup() {
            return () => h('section', { 'data-testid': 'workstation-v4-view' }, '列表页')
          },
        }),
      },
    },
  })
}

describe('WorkstationV4HomeEntry', () => {
  beforeEach(() => {
    routeState.query = {}
    authState.roles = []
  })

  it('shows the all-hospital home for any authenticated session without an admin role gate', () => {
    const wrapper = mountHomeEntry()

    expect(wrapper.find('[data-testid="qc-overview-view"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="workstation-v4-view"]').exists()).toBe(false)
  })

  it('首页不再自带助手入口（由布局层的全局智能助手统一提供）', () => {
    const wrapper = mountHomeEntry()

    expect(wrapper.find('[data-testid="qc-agent-home-entry"]').exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'BusinessAgentDrawer' }).exists()).toBe(false)
  })

  it('带启动参数时进入工作台列表模式', () => {
    routeState.query = { stage: 'frontpage_generate' }

    const wrapper = mountHomeEntry()

    expect(wrapper.find('[data-testid="workstation-v4-view"]').exists()).toBe(true)
  })
})
