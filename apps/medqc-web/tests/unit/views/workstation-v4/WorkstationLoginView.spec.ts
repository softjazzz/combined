/* eslint-disable vue/one-component-per-file */
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import WorkstationLoginView from '@/views/workstation-v4/WorkstationLoginView.vue'

const { authState, message, realRouterRef, routeQuery, routerPush, routerReplace, signIn } = vi.hoisted(() => ({
  authState: { userRoles: ['admin'] as string[] },
  realRouterRef: { current: null as null | { resolve: (to: unknown) => unknown } },
  message: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  },
  routeQuery: {} as Record<string, unknown>,
  routerPush: vi.fn(),
  routerReplace: vi.fn(),
  signIn: vi.fn(),
}))

vi.mock('ant-design-vue', () => ({
  message,
}))

// 登录落地依赖真实路由表的 meta.permission，resolve 交给真实 router
vi.mock('vue-router', async (importOriginal) => ({
  ...(await importOriginal<typeof import('vue-router')>()),
  useRoute: () => ({
    query: routeQuery,
  }),
  useRouter: () => ({
    push: routerPush,
    replace: routerReplace,
    resolve: (to: unknown) => realRouterRef.current!.resolve(to),
  }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    signIn,
    get userRoles() {
      return authState.userRoles
    },
  }),
}))

vi.mock('@ant-design/icons-vue', () => ({
  AuditOutlined: defineComponent({
    name: 'AuditOutlinedStub',
    setup() {
      return () => h('span', { class: 'audit-icon-stub' })
    },
  }),
  LockOutlined: defineComponent({
    name: 'LockOutlinedStub',
    setup() {
      return () => h('span', { class: 'lock-icon-stub' })
    },
  }),
}))

window.scrollTo = vi.fn()
realRouterRef.current = (await import('@/router')).default as unknown as {
  resolve: (to: unknown) => unknown
}

const WorkstationLoginFormStub = defineComponent({
  name: 'WorkstationLoginForm',
  props: {
    loading: Boolean,
  },
  emits: ['login', 'forgot-password'],
  setup(_, { emit }) {
    return () =>
      h('div', { class: 'login-form-stub' }, [
        h(
          'button',
          {
            class: 'login-demo',
            type: 'button',
            onClick: () =>
              emit('login', {
                account: 'admin',
                password: 'admin888',
                role: 'admin',
                remember_me: true,
              }),
          },
          '演示登录',
        ),
        h(
          'button',
          {
            class: 'login-normal',
            type: 'button',
            onClick: () =>
              emit('login', {
                account: 'doctor@medqc.com',
                password: 'doctor-pass',
                role: 'doctor',
                remember_me: true,
              }),
          },
          '普通登录',
        ),
        h(
          'button',
          {
            class: 'login-sync-admin',
            type: 'button',
            onClick: () =>
              emit('login', {
                account: 'sync_admin',
                password: 'sync888',
                role: 'admin',
                remember_me: true,
              }),
          },
          '实施账号登录',
        ),
      ])
  },
})

function mountView() {
  return mount(WorkstationLoginView, {
    global: {
      stubs: {
        WorkstationLoginForm: WorkstationLoginFormStub,
      },
    },
  })
}

describe('WorkstationLoginView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    Object.keys(routeQuery).forEach((key) => delete routeQuery[key])
    signIn.mockResolvedValue({ success: true })
    authState.userRoles = ['admin']
  })

  it('演示账号登录后进入工作台首页', async () => {
    const wrapper = mountView()

    await wrapper.find('.login-demo').trigger('click')
    await flushPromises()

    expect(signIn).toHaveBeenCalledWith('admin@medqc.com', 'admin888', 'admin')
    expect(routerReplace).toHaveBeenCalledWith('/workstation-v5')
    expect(message.success).toHaveBeenCalledWith('登录成功')
  })

  it('普通账号登录后仍遵守 redirect 参数', async () => {
    authState.userRoles = ['doctor']
    // 规则管理仅 admin/qc_manager（后端 custom-qc），医生用可访问的 DRG 页面验证 redirect
    routeQuery.redirect = '/workstation-v5/drg/pre?source=link'
    const wrapper = mountView()

    await wrapper.find('.login-normal').trigger('click')
    await flushPromises()

    expect(signIn).toHaveBeenCalledWith('doctor@medqc.com', 'doctor-pass', 'doctor')
    expect(routerReplace).toHaveBeenCalledWith('/workstation-v5/drg/pre?source=link')
  })

  it('旧 V4 redirect 参数会升级为 V5 地址', async () => {
    routeQuery.redirect = '/workstation-v4/records/final?source=legacy'
    const wrapper = mountView()

    await wrapper.find('.login-normal').trigger('click')
    await flushPromises()

    expect(routerReplace).toHaveBeenCalledWith('/workstation-v5/records/final?source=legacy')
    expect(message.warning).not.toHaveBeenCalled()
  })

  it('redirect 无权访问时回到角色默认页并提示', async () => {
    authState.userRoles = ['doctor']
    routeQuery.redirect = '/workstation-v5/records/final'
    const wrapper = mountView()

    await wrapper.find('.login-normal').trigger('click')
    await flushPromises()

    expect(routerReplace).toHaveBeenCalledWith('/dashboard/qc/rectifications')
    expect(message.warning).toHaveBeenCalledWith('无权访问该页面')
  })

  it('无 redirect 时按角色默认落地：质控员进入我的任务-我收到', async () => {
    authState.userRoles = ['qc_staff']
    const wrapper = mountView()

    await wrapper.find('.login-normal').trigger('click')
    await flushPromises()

    expect(routerReplace).toHaveBeenCalledWith('/dashboard/tasks/my?tab=received')
    expect(message.warning).not.toHaveBeenCalled()
  })

  it('无 redirect 时按角色默认落地：医生优先进入整改任务', async () => {
    authState.userRoles = ['doctor']
    const wrapper = mountView()

    await wrapper.find('.login-normal').trigger('click')
    await flushPromises()

    expect(routerReplace).toHaveBeenCalledWith('/dashboard/qc/rectifications')
  })

  it('实施账号支持 sync_admin 简写登录', async () => {
    authState.userRoles = ['sync_admin']
    const wrapper = mountView()

    await wrapper.find('.login-sync-admin').trigger('click')
    await flushPromises()

    expect(signIn).toHaveBeenCalledWith('sync_admin@medqc.com', 'sync888', 'admin')
    expect(routerReplace).toHaveBeenCalledWith('/workstation-v5')
  })
})
