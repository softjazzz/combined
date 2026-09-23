import { defineComponent, h, nextTick } from 'vue'
import { shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const routerPush = vi.hoisted(() => vi.fn())
const authState = vi.hoisted(() => ({ userRoles: ['admin'] as string[] }))
const routeState = vi.hoisted(() => ({
  path: '/workstation-v5',
  fullPath: '/workstation-v5',
  query: {} as Record<string, string>,
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: routerPush }),
  useRoute: () => routeState,
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    user: { id: 'test-user', email: 'tester@medqc.com' },
    userRoles: authState.userRoles,
    signOut: vi.fn(),
  }),
}))

import WorkstationLayout from '@/components/layout/WorkstationLayout.vue'

const PassThroughStub = defineComponent({
  setup(_, { slots }) {
    return () => h('div', slots.default?.())
  },
})

const MenuStub = defineComponent({
  name: 'MenuStub',
  props: {
    selectedKeys: { type: Array, default: () => [] },
    openKeys: { type: Array, default: () => [] },
  },
  emits: ['click', 'openChange', 'update:selectedKeys'],
  setup(props, { slots }) {
    return () =>
      h(
        'nav',
        {
          'data-selected-keys': JSON.stringify(props.selectedKeys),
          'data-open-keys': JSON.stringify(props.openKeys),
        },
        slots.default?.(),
      )
  },
})

const MenuItemStub = defineComponent({
  name: 'MenuItemStub',
  setup(_, { slots }) {
    return () => h('div', { class: 'menu-item' }, slots.default?.())
  },
})

const SubMenuStub = defineComponent({
  name: 'SubMenuStub',
  setup(_, { slots }) {
    return () => h('section', { class: 'sub-menu' }, slots.default?.())
  },
})

function mountLayout() {
  return shallowMount(WorkstationLayout, {
    global: {
      stubs: {
        'a-layout': PassThroughStub,
        'a-layout-sider': PassThroughStub,
        'a-layout-header': PassThroughStub,
        'a-layout-content': PassThroughStub,
        'a-menu': MenuStub,
        'a-menu-item': MenuItemStub,
        'a-sub-menu': SubMenuStub,
        'a-button': PassThroughStub,
        'a-breadcrumb': PassThroughStub,
        'a-breadcrumb-item': PassThroughStub,
        'a-popover': PassThroughStub,
        'a-badge': PassThroughStub,
        'a-dropdown': PassThroughStub,
        'a-avatar': PassThroughStub,
        RouterLink: PassThroughStub,
        RouterView: true,
        RuntimeBuildStatus: true,
        Transition: false,
      },
    },
  })
}

describe('WorkstationLayout 门急诊入口', () => {
  beforeEach(() => {
    routerPush.mockReset()
    authState.userRoles = ['admin']
    routeState.path = '/workstation-v5'
    routeState.fullPath = '/workstation-v5'
    routeState.query = {}
  })

  it.each(['admin', 'qc_manager'])('%s 可以看到入口并导航到已有路由', async (role) => {
    authState.userRoles = [role]
    const wrapper = mountLayout()

    expect(wrapper.text()).toContain('门急诊病历')
    wrapper.findComponent(MenuStub).vm.$emit('click', {
      key: '/workstation-v5/records/outpatient-emergency',
    })
    await nextTick()

    expect(routerPush).toHaveBeenCalledWith('/workstation-v5/records/outpatient-emergency')
  })

  it.each(['doctor', 'reviewer', 'sync_admin', 'super_admin'])(
    '%s 不显示门急诊入口',
    (role) => {
      authState.userRoles = [role]
      const wrapper = mountLayout()

      expect(wrapper.text()).not.toContain('门急诊病历')
      expect(wrapper.text()).toContain('病历池')
      expect(wrapper.text()).toContain('运行病历质控')
      expect(wrapper.text()).toContain('已出院病历质控')
    },
  )

  it('直达门急诊页面时选中入口并展开工作台菜单', () => {
    routeState.path = '/workstation-v5/records/outpatient-emergency'
    routeState.fullPath = routeState.path
    const wrapper = mountLayout()
    const menu = wrapper.findComponent(MenuStub)

    expect(menu.props('selectedKeys')).toEqual(['/workstation-v5/records/outpatient-emergency'])
    expect(menu.props('openKeys')).toContain('workstation-sub')
    expect(wrapper.text()).toContain('门急诊病历')
  })
})
