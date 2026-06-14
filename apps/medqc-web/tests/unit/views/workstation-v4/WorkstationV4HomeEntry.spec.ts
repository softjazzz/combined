import { defineComponent, h } from 'vue'
import { shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const routeState = vi.hoisted(() => ({
  query: {} as Record<string, string>,
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
    hasRole: (role: string) => role === 'admin',
  }),
}))

import WorkstationV4HomeEntry from '@/views/workstation-v4/WorkstationV4HomeEntry.vue'

const QCAgentChatDrawerStub = defineComponent({
  name: 'QCAgentChatDrawer',
  props: {
    open: {
      type: Boolean,
      default: false,
    },
    contextLabel: {
      type: String,
      default: '',
    },
  },
  setup(props) {
    return () =>
      h('div', {
        'data-testid': 'qc-agent-home-drawer',
        open: props.open,
        'data-context-label': props.contextLabel,
      })
  },
})

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
        QCAgentChatDrawer: QCAgentChatDrawerStub,
      },
    },
  })
}

describe('WorkstationV4HomeEntry qc agent entry', () => {
  beforeEach(() => {
    routeState.query = {}
  })

  it('renders qc agent entry on workstation home and opens drawer', async () => {
    const wrapper = mountHomeEntry()

    expect(wrapper.find('[data-testid="qc-overview-view"]').exists()).toBe(true)
    const entry = wrapper.find('[data-testid="qc-agent-home-entry"]')
    expect(entry.exists()).toBe(true)
    expect(entry.text()).toContain('智能助手')

    await entry.trigger('click')

    const drawer = wrapper.find('[data-testid="qc-agent-home-drawer"]')
    expect(drawer.attributes('open')).toBe('true')
    expect(drawer.attributes('data-context-label')).toContain('工作台首页')
  })

  it('does not render qc agent entry when route enters workstation list mode', () => {
    routeState.query = { stage: 'frontpage_generate' }

    const wrapper = mountHomeEntry()

    expect(wrapper.find('[data-testid="workstation-v4-view"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="qc-agent-home-entry"]').exists()).toBe(false)
  })
})
