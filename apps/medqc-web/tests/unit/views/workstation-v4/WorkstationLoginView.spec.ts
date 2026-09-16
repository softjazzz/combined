/* eslint-disable vue/one-component-per-file */
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import WorkstationLoginView from '@/views/workstation-v4/WorkstationLoginView.vue'

const { message, routeQuery, routerPush, routerReplace, signIn } = vi.hoisted(() => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
  },
  routeQuery: {} as Record<string, unknown>,
  routerPush: vi.fn(),
  routerReplace: vi.fn(),
  signIn: vi.fn(),
}))

vi.mock('ant-design-vue', () => ({
  message,
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({
    query: routeQuery,
  }),
  useRouter: () => ({
    push: routerPush,
    replace: routerReplace,
  }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    signIn,
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
    routeQuery.redirect = '/workstation-v5/rules?tab=semantic'
    const wrapper = mountView()

    await wrapper.find('.login-normal').trigger('click')
    await flushPromises()

    expect(signIn).toHaveBeenCalledWith('doctor@medqc.com', 'doctor-pass', 'doctor')
    expect(routerReplace).toHaveBeenCalledWith('/workstation-v5/rules?tab=semantic')
  })

  it('旧 V4 redirect 参数会升级为 V5 地址', async () => {
    routeQuery.redirect = '/workstation-v4/records/final?source=legacy'
    const wrapper = mountView()

    await wrapper.find('.login-normal').trigger('click')
    await flushPromises()

    expect(routerReplace).toHaveBeenCalledWith('/workstation-v5/records/final?source=legacy')
  })

  it('实施账号支持 sync_admin 简写登录', async () => {
    const wrapper = mountView()

    await wrapper.find('.login-sync-admin').trigger('click')
    await flushPromises()

    expect(signIn).toHaveBeenCalledWith('sync_admin@medqc.com', 'sync888', 'admin')
    expect(routerReplace).toHaveBeenCalledWith('/workstation-v5')
  })
})
