/* eslint-disable vue/one-component-per-file */
import { defineComponent, h, reactive } from 'vue'
import { shallowMount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

const authState = vi.hoisted(() => ({ userRoles: ['admin'] as string[] }))
const realRouterRef = vi.hoisted(() => ({
  current: null as null | { resolve: (to: unknown) => unknown },
}))

// 菜单过滤依赖真实路由表的 meta.permission，resolve 交给真实 router
vi.mock('vue-router', async (importOriginal) => ({
  ...(await importOriginal<typeof import('vue-router')>()),
  useRouter: () => ({
    push: vi.fn(),
    resolve: (to: unknown) => realRouterRef.current!.resolve(to),
  }),
  useRoute: () => reactiveRoute,
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    user: { id: 'test-user', email: 'tester@medqc.com' },
    userName: '测试用户',
    get userRoles() {
      return authState.userRoles
    },
    hasRole: (role: string) => authState.userRoles.includes(role),
    signOut: vi.fn(),
  }),
}))

import MainLayout from '@/components/layout/MainLayout.vue'

const reactiveRoute = reactive({
  path: '/dashboard/tasks/my',
  fullPath: '/dashboard/tasks/my',
  query: {},
})

window.scrollTo = vi.fn()
realRouterRef.current = (await import('@/router')).default as unknown as {
  resolve: (to: unknown) => unknown
}

const PassThroughStub = defineComponent({
  setup(_, { slots }) {
    return () => h('div', slots.default?.())
  },
})
const MenuItemStub = defineComponent({
  setup(_, { slots }) {
    return () => h('div', { class: 'menu-item' }, slots.default?.())
  },
})
const SubMenuStub = defineComponent({
  setup(_, { slots }) {
    return () => h('section', { class: 'sub-menu' }, slots.default?.())
  },
})

function visibleMenu(role: string) {
  authState.userRoles = [role]
  const wrapper = shallowMount(MainLayout, {
    global: {
      stubs: {
        'a-layout': PassThroughStub,
        'a-layout-sider': PassThroughStub,
        'a-layout-header': PassThroughStub,
        'a-layout-content': PassThroughStub,
        'a-menu': PassThroughStub,
        'a-menu-item': MenuItemStub,
        'a-sub-menu': SubMenuStub,
        'a-dropdown': true,
        'a-popover': true,
        'a-breadcrumb': true,
        'a-breadcrumb-item': true,
        'a-button': true,
        'a-badge': true,
        'a-avatar': true,
        RouterView: true,
        RouterLink: true,
      },
    },
  })
  return {
    // 只取侧栏菜单项（用户下拉菜单被 stub，不会出现在这里）
    items: wrapper.findAll('.menu-item').map((item) => item.text().trim()),
    groups: wrapper.findAll('.sub-menu').length,
  }
}

const DRG = ['DRG 首页', '编码辅助', '分组预测', '事中监控', '付费监测', '事后分析']
// DRG 角色（后端 drg.py：admin/qc_manager/doctor/reviewer）；事后分析另限质控科
const DRG_WITHOUT_ANALYSIS = DRG.filter((item) => item !== '事后分析')
const RULES = ['编码质控规则', '全病历质控规则', '首页质控规则', '医保结算清单规则']

describe('MainLayout 菜单按路由权限过滤', () => {
  it.each([
    [
      'admin',
      [
        '仪表板',
        '智能质控工作站',
        '工作台首页',
        '运行病历',
        '已出院病历',
        ...RULES,
        '自定义质控点',
        '我的任务',
        '全部任务',
        '病历审核待办',
        '统计总览',
        '运行病历质量分析',
        '终末病历质量分析',
        '病案首页统计分析',
        '质控员工作分析',
        ...DRG,
        '系统设置',
      ],
      6,
    ],
    [
      'qc_manager',
      [
        '仪表板',
        '智能质控工作站',
        '工作台首页',
        '运行病历',
        '已出院病历',
        ...RULES,
        '自定义质控点',
        '我的任务',
        '全部任务',
        '病历审核待办',
        '统计总览',
        '运行病历质量分析',
        '终末病历质量分析',
        '病案首页统计分析',
        '质控员工作分析',
        ...DRG,
      ],
      5,
    ],
    // 质控员：病案质控、质控规则、DRG、系统管理分组均无可访问子项而整体隐藏
    ['qc_staff', ['我的任务', '病历审核待办', '统计总览'], 2],
    [
      'doctor',
      ['仪表板', '智能质控工作站', '工作台首页', '我的任务', '统计总览', ...DRG_WITHOUT_ANALYSIS],
      3,
    ],
    ['reviewer', ['我的任务', '统计总览', ...DRG_WITHOUT_ANALYSIS], 3],
    // coder 不在后端 DRG 角色内，DRG 分组整体隐藏
    ['coder', ['智能质控工作站', '我的任务', '统计总览'], 2],
  ])('%s 可见菜单', (role, expected, groups) => {
    const menu = visibleMenu(role as string)
    expect(menu.items).toEqual(expected)
    expect(menu.groups).toBe(groups)
  })
})
