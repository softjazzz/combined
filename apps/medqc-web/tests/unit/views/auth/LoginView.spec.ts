import { flushPromises, shallowMount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { authState, message, realRouterRef, routeQuery, routerPush, signIn } = vi.hoisted(() => ({
  authState: { userRoles: ['admin'] as string[] },
  realRouterRef: { current: null as null | { resolve: (to: unknown) => unknown } },
  message: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
  routeQuery: {} as Record<string, unknown>,
  routerPush: vi.fn(),
  signIn: vi.fn(),
}))

vi.mock('ant-design-vue', () => ({ message }))

// 登录落地依赖真实路由表的 meta.permission，resolve 交给真实 router
vi.mock('vue-router', async (importOriginal) => ({
  ...(await importOriginal<typeof import('vue-router')>()),
  useRouter: () => ({
    push: routerPush,
    currentRoute: { value: { query: routeQuery } },
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

import LoginView from '@/views/auth/LoginView.vue'

window.scrollTo = vi.fn()
realRouterRef.current = (await import('@/router')).default as unknown as {
  resolve: (to: unknown) => unknown
}

const LoginFormStub = defineComponent({
  name: 'LoginForm',
  emits: ['login', 'forgot-password'],
  setup(_, { emit }) {
    return () =>
      h(
        'button',
        {
          class: 'login-submit',
          type: 'button',
          onClick: () => emit('login', { account: 'u@medqc.com', password: 'p', role: '' }),
        },
        '登录',
      )
  },
})

function mountView() {
  return shallowMount(LoginView, {
    global: {
      stubs: { LoginForm: LoginFormStub, MedicineBoxOutlined: true, BarChartOutlined: true },
    },
  })
}

async function login() {
  const wrapper = mountView()
  await wrapper.find('.login-submit').trigger('click')
  await flushPromises()
}

describe('LoginView 登录落地', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    Object.keys(routeQuery).forEach((key) => delete routeQuery[key])
    signIn.mockResolvedValue({ success: true })
    vi.spyOn(console, 'log').mockImplementation(() => undefined)
  })

  it('管理员无 redirect 时进入项目现有默认首页', async () => {
    authState.userRoles = ['admin']
    await login()
    expect(routerPush).toHaveBeenCalledWith('/workstation-v5')
  })

  it('质控员无 redirect 时进入我的任务-我收到', async () => {
    authState.userRoles = ['qc_staff']
    await login()
    expect(routerPush).toHaveBeenCalledWith('/dashboard/tasks/my?tab=received')
  })

  it('redirect 可访问时直达', async () => {
    authState.userRoles = ['doctor']
    routeQuery.redirect = '/dashboard/qc/appeals'
    await login()
    expect(routerPush).toHaveBeenCalledWith('/dashboard/qc/appeals')
    expect(message.warning).not.toHaveBeenCalled()
  })

  it('redirect 无权访问时回到角色默认页并提示', async () => {
    authState.userRoles = ['qc_staff']
    routeQuery.redirect = '/dashboard/tasks/all'
    await login()
    expect(routerPush).toHaveBeenCalledWith('/dashboard/tasks/my?tab=received')
    expect(message.warning).toHaveBeenCalledWith('无权访问该页面')
  })
})
