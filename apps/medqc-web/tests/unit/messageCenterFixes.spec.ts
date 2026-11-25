/* eslint-disable vue/one-component-per-file */
import { readFileSync } from 'node:fs'
import { defineComponent, h, nextTick, reactive } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { flushPromises, mount } from '@vue/test-utils'
import { Button as AntButton, ConfigProvider } from 'ant-design-vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  authenticated: true,
  apiGet: vi.fn(),
  apiPut: vi.fn(),
  signOut: vi.fn(),
  messageError: vi.fn(),
  auth: {
    user: {
      id: 'admin-1',
      email: 'admin@medqc.com',
      roles: ['admin'] as string[],
      is_demo_account: false,
    },
    userRoles: ['admin'] as string[],
  },
}))

vi.mock('@/services/apiService', () => ({
  ApiService: {
    get: state.apiGet,
    put: state.apiPut,
    isAuthenticated: () => state.authenticated,
  },
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    get isAuthenticated() {
      return state.authenticated
    },
    get user() {
      return state.auth.user
    },
    get userRoles() {
      return state.auth.userRoles
    },
    get userName() {
      return state.auth.user.email
    },
    signOut: state.signOut,
  }),
}))

vi.mock('@/components/layout/RuntimeBuildStatus.vue', () => ({
  default: { template: '<div />' },
}))
vi.mock('@/views/workstation-v4/components/GlobalAssistantHost.vue', () => ({
  default: { template: '<div />' },
}))
vi.mock('@/components/layout/WorkstationConfirmDialog.vue', () => ({
  default: { template: '<div />' },
}))
vi.mock('ant-design-vue', async () => {
  const actual = await vi.importActual<typeof import('ant-design-vue')>('ant-design-vue')
  return {
    ...actual,
    message: {
      error: state.messageError,
      success: vi.fn(),
      warning: vi.fn(),
      info: vi.fn(),
    },
  }
})

import WorkstationLayout from '@/components/layout/WorkstationLayout.vue'
import MessageCenter from '@/views/workstation/MessageCenter.vue'
import {
  messageTypeLabel,
  syncSharedMessageCenterUnreadCount,
} from '@/views/workstation/useMessageCenter'

const ButtonStub = defineComponent({
  props: ['shape', 'loading', 'disabled', 'type'],
  emits: ['click'],
  setup(props, { slots, attrs, emit }) {
    return () =>
      h(
        'button',
        {
          type: 'button',
          'data-shape': props.shape,
          disabled: Boolean(props.disabled),
          ...attrs,
          onClick: () => emit('click'),
        },
        [slots.icon?.(), slots.default?.()],
      )
  },
})

const SelectStub = defineComponent({
  props: ['value', 'options', 'disabled'],
  emits: ['update:value'],
  setup(props, { attrs, emit }) {
    return () =>
      h(
        'select',
        {
          ...attrs,
          value: props.value ?? '',
          disabled: Boolean(props.disabled),
          onChange: (event: Event) => {
            emit('update:value', (event.target as HTMLSelectElement).value)
          },
        },
        ((props.options as Array<{ value: string; label: string }>) || []).map((option) =>
          h('option', { value: option.value }, option.label),
        ),
      )
  },
})

const TooltipStub = defineComponent({
  props: ['title'],
  setup(props, { slots }) {
    return () => h('span', { class: 'tooltip-stub', 'data-title': props.title }, slots.default?.())
  },
})

const layoutStubs = {
  MqIcon: true,
  MqIconTile: true,
  'a-tooltip': TooltipStub,
  'a-dropdown': { template: '<div><slot /><slot name="overlay" /></div>' },
  'a-popover': { template: '<div><slot /></div>' },
  'a-menu': { template: '<div><slot /></div>' },
  'a-menu-item': { template: '<div><slot /></div>' },
  'a-menu-divider': true,
}

const messageCenterStubs = {
  MqIcon: true,
  MqIconTile: true,
  'a-tooltip': TooltipStub,
  'a-button': ButtonStub,
  'a-select': SelectStub,
  'a-spin': { template: '<div><slot /></div>' },
  'a-alert': { props: ['message'], template: '<div role="alert">{{ message }}</div>' },
  'a-pagination': true,
}

function makeNotification(overrides: Record<string, unknown> = {}) {
  return {
    id: 'notif-1',
    title: '账号注册待审批',
    content: '有新的账号申请待核定',
    created_at: '2026-10-25T12:00:00Z',
    is_read: false,
    type: 'account_registration',
    interaction_target: { kind: 'account_registration', id: 'reg-1' },
    ...overrides,
  }
}

function makeListResponse(items: unknown[] = [], total = items.length, unreadCount = 0) {
  return {
    success: true,
    data: { items, total, unread_count: unreadCount },
  }
}

function createTestRouter(asyncGuard = false) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/workstation-v5',
        component: WorkstationLayout,
        children: [
          { path: '', component: defineComponent({ template: '<div>首页</div>' }) },
          { path: 'worklist', component: defineComponent({ template: '<div>病历池</div>' }) },
          { path: 'stats', component: defineComponent({ template: '<div>统计分析</div>' }) },
          { path: 'feedback', component: defineComponent({ template: '<div>整改待办</div>' }) },
          { path: 'messages', component: MessageCenter },
          { path: 'system-config', component: defineComponent({ template: '<div>系统配置</div>' }) },
        ],
      },
    ],
  })
  if (asyncGuard) {
    router.beforeEach(async (_to, _from, next) => {
      await Promise.resolve()
      next()
    })
  }
  return router
}

function setUser(roles: string[], id = 'admin-1') {
  state.auth.user = reactive({
    id,
    email: `${roles[0] || 'user'}@medqc.com`,
    roles: [...roles],
    is_demo_account: false,
  })
  state.auth.userRoles = [...roles]
}

beforeEach(() => {
  vi.clearAllMocks()
  state.authenticated = true
  setUser(['admin'], 'admin-1')
  syncSharedMessageCenterUnreadCount(null, { emitEvent: false })
  state.apiGet.mockResolvedValue(makeListResponse([], 0, 0))
  state.apiPut.mockResolvedValue({ success: true })
  state.signOut.mockResolvedValue(undefined)
})

afterEach(() => {
  syncSharedMessageCenterUnreadCount(null, { emitEvent: false })
})

describe('P1 #2 侧栏左下角消息中心铃铛未读徽标与已读联动', () => {
  it('有权限登录时仅拉取一次轻量未读数，913 条展示 99+ 且切页不风暴请求', async () => {
    state.apiGet.mockResolvedValue(makeListResponse([], 913, 913))
    const router = createTestRouter()
    await router.push('/workstation-v5/worklist')
    await router.isReady()

    const wrapper = mount(
      defineComponent({ template: '<router-view />' }),
      {
        global: {
          plugins: [router],
          stubs: { ...layoutStubs, ...messageCenterStubs },
        },
      },
    )
    await flushPromises()

    expect(state.apiGet).toHaveBeenCalledTimes(1)
    expect(state.apiGet).toHaveBeenCalledWith(
      '/api/v1/notifications',
      { page: 1, page_size: 1, is_read: false },
      { skipErrorToast: true },
    )
    expect(wrapper.get('[data-testid="ws-message-unread-badge"]').text()).toBe('99+')
    expect(wrapper.get('.ws-icon-button--messages').attributes('aria-label')).toBe(
      '消息中心，913 条未读',
    )

    // 切页不重复风暴请求
    await router.push('/workstation-v5/stats')
    await flushPromises()
    await router.push('/workstation-v5/feedback')
    await flushPromises()
    expect(state.apiGet).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('无消息中心权限（doctor）或未登录时不拉取未读数也不显示徽标', async () => {
    setUser(['doctor'], 'doc-1')
    const router = createTestRouter()
    await router.push('/workstation-v5/worklist')
    await router.isReady()

    const doctorWrapper = mount(
      defineComponent({ template: '<router-view />' }),
      { global: { plugins: [router], stubs: layoutStubs } },
    )
    await flushPromises()
    expect(state.apiGet).not.toHaveBeenCalled()
    expect(doctorWrapper.find('[data-testid="ws-message-unread-badge"]').exists()).toBe(false)
    doctorWrapper.unmount()

    state.authenticated = false
    setUser(['admin'], 'admin-2')
    const anonWrapper = mount(
      defineComponent({ template: '<router-view />' }),
      { global: { plugins: [router], stubs: layoutStubs } },
    )
    await flushPromises()
    expect(state.apiGet).not.toHaveBeenCalled()
    expect(anonWrapper.find('[data-testid="ws-message-unread-badge"]').exists()).toBe(false)
    anonWrapper.unmount()
  })

  it('在消息中心标记单条已读和全部已读后，侧栏铃铛未读数字实时联动更新直至隐藏', async () => {
    const first = makeNotification({ id: 'n-1' })
    const second = makeNotification({ id: 'n-2', title: '第二条消息' })
    state.apiGet
      // WorkstationLayout 初始拉取
      .mockResolvedValueOnce(makeListResponse([first], 5, 5))
      // 进入 MessageCenter 拉取
      .mockResolvedValueOnce(makeListResponse([first, second], 5, 5))
      // 单条标记已读后刷新
      .mockResolvedValueOnce(makeListResponse([second], 4, 4))
      // 全部标为已读后刷新
      .mockResolvedValueOnce(makeListResponse([], 0, 0))

    const router = createTestRouter()
    await router.push('/workstation-v5/worklist')
    await router.isReady()

    const wrapper = mount(
      defineComponent({ template: '<router-view />' }),
      {
        global: {
          plugins: [router],
          stubs: { ...layoutStubs, ...messageCenterStubs },
        },
      },
    )
    await flushPromises()
    expect(wrapper.get('[data-testid="ws-message-unread-badge"]').text()).toBe('5')

    await router.push('/workstation-v5/messages')
    await flushPromises()
    expect(wrapper.get('[data-testid="ws-message-unread-badge"]').text()).toBe('5')

    // 标为已读：5 -> 4
    await wrapper.get('.message-center__read').trigger('click')
    await flushPromises()
    expect(state.apiPut).toHaveBeenCalledWith('/api/v1/notifications/n-1/read')
    expect(wrapper.get('[data-testid="ws-message-unread-badge"]').text()).toBe('4')

    // 全部标为已读：4 -> 0（徽标隐藏）
    await wrapper.get('button[aria-label="全部标为已读"]').trigger('click')
    await flushPromises()
    expect(state.apiPut).toHaveBeenCalledWith('/api/v1/notifications/read-all')
    expect(wrapper.find('[data-testid="ws-message-unread-badge"]').exists()).toBe(false)
    wrapper.unmount()
  })
})

describe('P1 #3a 消除切换未读/全部/已读 Tab 与路由变更双请求', () => {
  it('在异步路由守卫下切换「全部 / 已读 / 未读」Tab 每次严格仅发 1 次 GET 请求', async () => {
    state.apiGet.mockResolvedValue(makeListResponse([makeNotification()], 1, 1))
    const router = createTestRouter(true)
    const replaceSpy = vi.spyOn(router, 'replace')
    await router.push('/workstation-v5/messages')
    await router.isReady()

    const wrapper = mount(MessageCenter, {
      global: { plugins: [router], stubs: messageCenterStubs },
    })
    await flushPromises()
    expect(state.apiGet).toHaveBeenCalledTimes(1)

    const tabs = wrapper.findAll('.mq-segmented__item')
    const [unreadTab, allTab, readTab] = tabs

    // 切到「全部」
    state.apiGet.mockClear()
    replaceSpy.mockClear()
    await allTab.trigger('click')
    await flushPromises()
    expect(state.apiGet).toHaveBeenCalledTimes(1)
    expect(replaceSpy).toHaveBeenCalledTimes(1)
    expect(state.apiGet).toHaveBeenCalledWith('/api/v1/notifications', {
      page: 1,
      page_size: 20,
      type: undefined,
      is_read: undefined,
    })
    expect(router.currentRoute.value.query.status).toBe('all')

    // 再次点击当前激活 Tab 不重复发请求
    state.apiGet.mockClear()
    await allTab.trigger('click')
    await flushPromises()
    expect(state.apiGet).not.toHaveBeenCalled()

    // 切到「已读」
    state.apiGet.mockClear()
    replaceSpy.mockClear()
    await readTab.trigger('click')
    await flushPromises()
    expect(state.apiGet).toHaveBeenCalledTimes(1)
    expect(replaceSpy).toHaveBeenCalledTimes(1)
    expect(state.apiGet).toHaveBeenCalledWith('/api/v1/notifications', {
      page: 1,
      page_size: 20,
      type: undefined,
      is_read: true,
    })
    expect(router.currentRoute.value.query.status).toBe('read')

    // 切回「未读」
    state.apiGet.mockClear()
    replaceSpy.mockClear()
    await unreadTab.trigger('click')
    await flushPromises()
    expect(state.apiGet).toHaveBeenCalledTimes(1)
    expect(replaceSpy).toHaveBeenCalledTimes(1)
    expect(state.apiGet).toHaveBeenCalledWith('/api/v1/notifications', {
      page: 1,
      page_size: 20,
      type: undefined,
      is_read: false,
    })
    expect(router.currentRoute.value.query.status).toBeUndefined()

    // 外部路由 query 变更（模拟浏览器前进/后退）也只发 1 次请求，不再因 syncingFromRoute 微任务复位二次请求
    state.apiGet.mockClear()
    await router.push({
      path: '/workstation-v5/messages',
      query: { status: 'read', type: 'account_registration' },
    })
    await flushPromises()
    expect(state.apiGet).toHaveBeenCalledTimes(1)
    expect(state.apiGet).toHaveBeenCalledWith('/api/v1/notifications', {
      page: 1,
      page_size: 20,
      type: 'account_registration',
      is_read: true,
    })

    wrapper.unmount()
  })
})

describe('P1 #4b 筛选为空空态文案、重置筛选与账号注册审核标签对齐', () => {
  it('存在未读消息但按 DRG 提醒筛选为空时，显示“当前筛选条件下暂无匹配消息”和“重置筛选”按钮', async () => {
    const unreadItem = makeNotification({ id: 'n-reg-1', title: '账号注册待审批' })
    state.apiGet
      .mockResolvedValueOnce(makeListResponse([unreadItem], 913, 913))
      .mockResolvedValueOnce(makeListResponse([], 0, 913))
      .mockResolvedValueOnce(makeListResponse([unreadItem], 913, 913))

    const router = createTestRouter()
    await router.push('/workstation-v5/messages')
    await router.isReady()

    const wrapper = mount(MessageCenter, {
      global: { plugins: [router], stubs: messageCenterStubs },
    })
    await flushPromises()

    await wrapper.get('select[aria-label="消息类型"]').setValue('drg_alert')
    await flushPromises()

    const emptyText = wrapper.get('.message-center__empty strong').text()
    expect(emptyText).toBe('当前筛选条件下暂无匹配消息')
    expect(wrapper.text()).not.toContain('未读消息已处理完毕')
    expect(wrapper.find('[data-testid="message-center-reset-filters"]').exists()).toBe(true)

    // 点击重置筛选恢复全部类型列表
    await wrapper.get('[data-testid="message-center-reset-filters"]').trigger('click')
    await flushPromises()
    expect(state.apiGet.mock.lastCall?.[1]).toEqual({
      page: 1,
      page_size: 20,
      type: undefined,
      is_read: false,
    })
    expect(wrapper.findAll('.message-center__row')).toHaveLength(1)
    wrapper.unmount()
  })

  it('无附加筛选且未读确为 0 时才显示“未读消息已处理完毕”', async () => {
    state.apiGet.mockResolvedValueOnce(makeListResponse([], 0, 0))
    const router = createTestRouter()
    await router.push('/workstation-v5/messages')
    await router.isReady()

    const wrapper = mount(MessageCenter, {
      global: { plugins: [router], stubs: messageCenterStubs },
    })
    await flushPromises()

    expect(wrapper.get('.message-center__empty strong').text()).toBe('未读消息已处理完毕')
    expect(wrapper.find('[data-testid="message-center-view-all"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('账号注册审批消息统一显示“账号注册审核”标签并支持按 type=account_registration 筛选', async () => {
    const legacyTypedReg = makeNotification({
      id: 'reg-legacy',
      type: 'system',
      interaction_target: { kind: 'account_registration', id: 'u-req-1' },
    })
    const normalizedReg = makeNotification({
      id: 'reg-norm',
      type: 'account_registration',
      interaction_target: { kind: 'account_registration', id: 'u-req-2' },
    })
    const regResult = makeNotification({
      id: 'reg-res',
      type: 'account_registration_result',
      interaction_target: { kind: 'account_registration_result', id: 'u-req-3' },
    })

    expect(messageTypeLabel(legacyTypedReg as never)).toBe('账号注册审核')
    expect(messageTypeLabel(normalizedReg as never)).toBe('账号注册审核')
    expect(messageTypeLabel(regResult as never)).toBe('账号注册审核')

    state.apiGet.mockResolvedValue(makeListResponse([normalizedReg], 1, 1))
    const router = createTestRouter()
    await router.push('/workstation-v5/messages')
    await router.isReady()

    const wrapper = mount(MessageCenter, {
      global: { plugins: [router], stubs: messageCenterStubs },
    })
    await flushPromises()
    expect(wrapper.get('.message-center__category').text()).toBe('账号注册审核')

    await wrapper.get('select[aria-label="消息类型"]').setValue('account_registration')
    await flushPromises()
    expect(state.apiGet.mock.lastCall?.[1]).toEqual({
      page: 1,
      page_size: 20,
      type: 'account_registration',
      is_read: false,
    })
    wrapper.unmount()
  })
})

describe('P2 #6a 36×36 圆形刷新按钮居中与无裁切修复', () => {
  it('刷新消息按钮使用真实 ant-design-vue Button(shape=circle + #icon)，加载切换时不出现双图标右移裁切', async () => {
    let resolveSecond!: (value: unknown) => void
    state.apiGet
      .mockResolvedValueOnce(makeListResponse([makeNotification()], 1, 1))
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveSecond = resolve
        }),
      )

    const router = createTestRouter()
    await router.push('/workstation-v5/messages')
    await router.isReady()

    const wrapper = mount(
      defineComponent({
        setup() {
          return () => h(ConfigProvider, null, { default: () => h(MessageCenter) })
        },
      }),
      {
        global: {
          plugins: [router],
          components: { 'a-button': AntButton },
          stubs: {
            MqIconTile: true,
            'a-tooltip': TooltipStub,
            'a-select': SelectStub,
            'a-spin': { template: '<div><slot /></div>' },
            'a-alert': { template: '<div />' },
            'a-pagination': true,
          },
        },
      },
    )
    await flushPromises()

    const refreshBtn = wrapper.get('button[aria-label="刷新消息"]')
    expect(refreshBtn.classes()).toContain('message-center__refresh')
    expect(refreshBtn.classes()).toContain('ant-btn-circle')
    expect(refreshBtn.classes()).toContain('ant-btn-icon-only')
    expect(refreshBtn.findAll('svg')).toHaveLength(1)

    // 点击刷新进入 loading：仅显示加载图标，与静态图标互斥，不会双图标并存把 SVG 挤出右边界
    await refreshBtn.trigger('click')
    await nextTick()
    expect(refreshBtn.classes()).toContain('ant-btn-loading')
    expect(refreshBtn.classes()).toContain('ant-btn-icon-only')
    expect(refreshBtn.findAll('.mq-icon')).toHaveLength(0)
    expect(refreshBtn.findAll('.ant-btn-loading-icon')).toHaveLength(1)

    // 加载完成立即切回单个同步图标，不残留 leaving 的 loading-icon
    resolveSecond(makeListResponse([makeNotification()], 1, 1))
    await flushPromises()
    expect(refreshBtn.classes()).not.toContain('ant-btn-loading')
    expect(refreshBtn.findAll('.ant-btn-loading-icon')).toHaveLength(0)
    expect(refreshBtn.findAll('.mq-icon')).toHaveLength(1)

    // 源码包含穿透居中样式，覆盖 Ant Design 默认 padding 与缩放
    const source = readFileSync('src/views/workstation/MessageCenter.vue', 'utf8')
    expect(source).toContain(':deep(.ant-btn.message-center__refresh)')
    expect(source).toContain('padding: 0;')
    expect(source).toContain('display: inline-flex;')
    expect(source).toContain('justify-content: center;')
    expect(source).toContain('transform: none;')

    wrapper.unmount()
  })
})
