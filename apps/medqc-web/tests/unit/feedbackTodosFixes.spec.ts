/* eslint-disable vue/one-component-per-file */
import { readFileSync } from 'node:fs'
import { defineComponent, h, reactive } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  listRectifications: vi.fn(),
  getRectification: vi.fn(),
  actOnRectification: vi.fn(),
  getRectificationComparison: vi.fn(),
  getEntryContexts: vi.fn(),
  getManualPendingCount: vi.fn(),
  getManualReviewQueue: vi.fn(),
  getOwnManualEntries: vi.fn(),
  createManualEntry: vi.fn(),
  decideManualDefect: vi.fn(),
  listModernAppeals: vi.fn(),
  getModernAppeal: vi.fn(),
  createModernAppeal: vi.fn(),
  actOnModernAppeal: vi.fn(),
  listRecordReviews: vi.fn(),
  getRecordReviewCurrent: vi.fn(),
  getRecordReviewHistory: vi.fn(),
  submitRecordReview: vi.fn(),
  routerReplace: vi.fn(),
  route: {
    path: '/workstation-v5/feedback',
    query: {} as Record<string, string | string[] | undefined>,
  },
  auth: {
    user: {
      id: 'mgr-1',
      institute_id: 'H1',
      department: '内科',
      roles: ['qc_manager'] as string[],
      is_active: true,
    },
    userRoles: ['qc_manager'] as string[],
  },
}))

vi.mock('@/api/defectRectifications', () => ({
  listRectifications: state.listRectifications,
  getRectification: state.getRectification,
  actOnRectification: state.actOnRectification,
  getRectificationComparison: state.getRectificationComparison,
}))

vi.mock('@/api/manualDefectWorkflow', () => ({
  getEntryContexts: state.getEntryContexts,
  getManualPendingCount: state.getManualPendingCount,
  getManualReviewQueue: state.getManualReviewQueue,
  getOwnManualEntries: state.getOwnManualEntries,
  createManualEntry: state.createManualEntry,
  decideManualDefect: state.decideManualDefect,
}))

vi.mock('@/api/modernAppeals', () => ({
  listModernAppeals: state.listModernAppeals,
  getModernAppeal: state.getModernAppeal,
  createModernAppeal: state.createModernAppeal,
  actOnModernAppeal: state.actOnModernAppeal,
}))

vi.mock('@/api/recordReviews', () => ({
  listRecordReviews: state.listRecordReviews,
  getRecordReviewCurrent: state.getRecordReviewCurrent,
  getRecordReviewHistory: state.getRecordReviewHistory,
  submitRecordReview: state.submitRecordReview,
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    get user() {
      return state.auth.user
    },
    get userRoles() {
      return state.auth.userRoles
    },
    hasRole: (role: string) => state.auth.userRoles.includes(role),
  }),
}))

vi.mock('vue-router', async () => {
  const { reactive: vueReactive } = await import('vue')
  state.route = vueReactive({
    path: '/workstation-v5/feedback',
    query: {} as Record<string, string | string[] | undefined>,
  })
  return {
    useRoute: () => state.route,
    useRouter: () => ({
      replace: state.routerReplace,
    }),
  }
})

import HomeRectificationTodos from '@/views/workstation/HomeRectificationTodos.vue'
import ManualDefectWorkflowDrawer from '@/components/qc/ManualDefectWorkflowDrawer.vue'
import ModernAppealWorkflowDrawer from '@/components/qc/ModernAppealWorkflowDrawer.vue'
import RecordReviewWorkflowDrawer from '@/components/qc/RecordReviewWorkflowDrawer.vue'

function deferred<T = void>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}

const ButtonStub = defineComponent({
  props: ['shape', 'disabled'],
  emits: ['click'],
  setup(props, { slots, attrs, emit }) {
    return () =>
      h(
        'button',
        {
          type: 'button',
          'data-shape': props.shape,
          disabled: props.disabled,
          ...attrs,
          onClick: () => emit('click'),
        },
        [
          slots.icon ? h('span', { 'data-slot': 'icon' }, slots.icon()) : null,
          slots.default?.(),
        ],
      )
  },
})

const SelectStub = defineComponent({
  props: ['value', 'options'],
  emits: ['update:value', 'change'],
  setup(props, { attrs, emit }) {
    return () =>
      h(
        'select',
        {
          ...attrs,
          value: props.value ?? '',
          onChange: (event: Event) => {
            const val = (event.target as HTMLSelectElement).value
            emit('update:value', val)
            emit('change', val)
          },
        },
        ((props.options as Array<{ label: string; value: string }>) || []).map((opt) =>
          h('option', { value: opt.value }, opt.label),
        ),
      )
  },
})

const PaginationStub = defineComponent({
  props: ['current', 'total', 'pageSize'],
  emits: ['update:current', 'change'],
  setup(props, { emit }) {
    return () =>
      h(
        'button',
        {
          type: 'button',
          'data-testid': 'goto-page-2',
          onClick: () => {
            const next = (props.current || 1) + 1
            emit('update:current', next)
            emit('change', next)
          },
        },
        '下一页',
      )
  },
})

const DrawerStub = defineComponent({
  props: ['open'],
  template: '<aside v-if="open"><slot /></aside>',
})

function mountTodos(props: Record<string, unknown> = {}) {
  return mount(HomeRectificationTodos, {
    props,
    global: {
      stubs: {
        'router-link': { template: '<a class="mq-btn"><slot /></a>' },
        ManualDefectWorkflowDrawer: true,
        ModernAppealWorkflowDrawer: true,
        RecordReviewWorkflowDrawer: true,
        'a-button': ButtonStub,
        'a-select': SelectStub,
        'a-pagination': PaginationStub,
        'a-spin': { template: '<div><slot /></div>' },
        'a-drawer': DrawerStub,
        'a-descriptions': { template: '<div><slot /></div>' },
        'a-descriptions-item': { template: '<div><slot /></div>' },
        'a-form': { template: '<div><slot /></div>' },
        'a-form-item': { template: '<div><slot /></div>' },
        'a-space': { template: '<div><slot /></div>' },
        'a-timeline': { template: '<div><slot /></div>' },
        'a-timeline-item': { template: '<div><slot /></div>' },
        'a-textarea': { template: '<textarea />' },
      },
    },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  state.route.path = '/workstation-v5/feedback'
  state.route.query = {}
  state.auth.user = reactive({
    id: 'mgr-1',
    institute_id: 'H1',
    department: '内科',
    roles: ['qc_manager'],
    is_active: true,
  })
  state.auth.userRoles = ['qc_manager']
  state.listRectifications.mockResolvedValue({ items: [], total: 25 })
  state.getEntryContexts.mockResolvedValue({ items: [], page: 1, has_more: false })
  state.getManualPendingCount.mockResolvedValue(2)
  state.getManualReviewQueue.mockResolvedValue({ items: [], total: 0 })
  state.getOwnManualEntries.mockResolvedValue({ items: [], total: 0 })
  state.listModernAppeals.mockResolvedValue({ items: [], total: 0, pending_count: 0 })
  state.listRecordReviews.mockResolvedValue({
    items: [],
    total: 0,
    pending_count: 0,
    initial_count: 0,
    recheck_count: 0,
  })
  state.routerReplace.mockImplementation(
    async (loc: { path?: string; query?: Record<string, string | string[] | undefined> }) => {
      if (loc.path) state.route.path = loc.path
      state.route.query = { ...(loc.query || {}) }
    },
  )
})

describe('P1 #3b - 整改待办页切换状态单一数据源驱动，杜绝取消+重发双请求', () => {
  it('逐一遍历 all/pending/submitted/approved/rejected 时每次切换仅发出 1 次请求并同步 URL', async () => {
    const wrapper = mountTodos()
    await flushPromises()
    expect(state.listRectifications).toHaveBeenCalledTimes(1)
    expect(state.listRectifications).toHaveBeenLastCalledWith('submitted', 1)

    const select = wrapper.get('#rectification-status')
    const transitions: Array<{ value: string; expectedState: string | undefined; expectedQuery: string }> = [
      { value: '', expectedState: undefined, expectedQuery: 'all' },
      { value: 'pending', expectedState: 'pending', expectedQuery: 'pending' },
      { value: 'submitted', expectedState: 'submitted', expectedQuery: 'submitted' },
      { value: 'approved', expectedState: 'approved', expectedQuery: 'approved' },
      { value: 'rejected', expectedState: 'rejected', expectedQuery: 'rejected' },
    ]

    for (const step of transitions) {
      state.listRectifications.mockClear()
      await select.setValue(step.value)
      await flushPromises()
      expect(state.listRectifications).toHaveBeenCalledTimes(1)
      expect(state.listRectifications).toHaveBeenCalledWith(step.expectedState, 1)
      expect(state.route.query.status).toBe(step.expectedQuery)
      expect(state.route.query.page).toBeUndefined()
    }

    // 重复选择当前同状态且已在第 1 页不重复请求
    state.listRectifications.mockClear()
    await select.setValue('rejected')
    await flushPromises()
    expect(state.listRectifications).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('router.replace 异步未完成前不提前发请求；连续快速切换仅发最终状态 1 次请求', async () => {
    const wrapper = mountTodos()
    await flushPromises()
    state.listRectifications.mockClear()

    const nav1 = deferred()
    const nav2 = deferred()
    state.routerReplace
      .mockImplementationOnce(async (loc: { query?: Record<string, string | undefined> }) => {
        await nav1.promise
        state.route.query = { ...(loc.query || {}) }
      })
      .mockImplementationOnce(async (loc: { query?: Record<string, string | undefined> }) => {
        await nav2.promise
        state.route.query = { ...(loc.query || {}) }
      })

    const select = wrapper.get('#rectification-status')
    await select.setValue('pending')
    // 路由尚未完成时不发请求
    expect(state.listRectifications).not.toHaveBeenCalled()

    // 第一次路由尚在途中时立即切换到 approved
    await select.setValue('approved')
    expect(state.listRectifications).not.toHaveBeenCalled()

    // 即使旧路由先完成，也不应把状态回退或触发旧请求
    nav1.resolve()
    await flushPromises()
    expect(state.listRectifications).not.toHaveBeenCalled()

    // 最终路由完成后仅发 1 次 approved 请求
    nav2.resolve()
    await flushPromises()
    expect(state.listRectifications).toHaveBeenCalledTimes(1)
    expect(state.listRectifications).toHaveBeenCalledWith('approved', 1)
    expect(state.route.query.status).toBe('approved')

    wrapper.unmount()
  })

  it('从第 2 页切换状态时重置回第 1 页、清理 query.page 且仅发 1 次请求', async () => {
    state.route.query = { status: 'submitted', page: '2' }
    const wrapper = mountTodos()
    await flushPromises()
    expect(state.listRectifications).toHaveBeenCalledWith('submitted', 2)

    state.listRectifications.mockClear()
    await wrapper.get('#rectification-status').setValue('pending')
    await flushPromises()
    expect(state.listRectifications).toHaveBeenCalledTimes(1)
    expect(state.listRectifications).toHaveBeenCalledWith('pending', 1)
    expect(state.route.query.status).toBe('pending')
    expect(state.route.query.page).toBeUndefined()

    // 浏览器前进/后退更新 URL 时依然正常同步并仅发 1 次请求
    state.listRectifications.mockClear()
    state.route.query = { status: 'approved', page: '3' }
    await flushPromises()
    expect(state.listRectifications).toHaveBeenCalledTimes(1)
    expect(state.listRectifications).toHaveBeenCalledWith('approved', 3)

    wrapper.unmount()
  })

  it('嵌入缺陷模式（props.scope）不触发 router.replace，切换状态仅发 1 次请求', async () => {
    const scope = {
      institute_id: 'H1',
      patient_id: 'P1',
      visit_id: 'V1',
      scene: 'running' as const,
      target_kind: 'canonical_defect' as const,
      target_id: 'R1',
      root_job_id: 'J1',
      envelope_id: 'E1',
    }
    const wrapper = mountTodos({ scope })
    await flushPromises()
    state.listRectifications.mockClear()

    await wrapper.get('#defect-rectification-status').setValue('pending')
    await flushPromises()
    expect(state.routerReplace).not.toHaveBeenCalled()
    expect(state.listRectifications).toHaveBeenCalledTimes(1)
    expect(state.listRectifications).toHaveBeenCalledWith('pending', 1, scope)

    wrapper.unmount()
  })
})

describe('P2 #6b - 页头 36×36 圆形刷新按钮 SVG 图标严格居中不偏移裁切', () => {
  it('HomeRectificationTodos 圆形刷新按钮使用 shape="circle"、#icon 插槽及专属样式类', async () => {
    const wrapper = mountTodos()
    await flushPromises()

    const refreshBtn = wrapper.get('button[aria-label="刷新整改待办"]')
    expect(refreshBtn.classes()).toContain('rectification-todos__refresh')
    expect(refreshBtn.attributes('data-shape')).toBe('circle')
    const iconSlot = refreshBtn.get('[data-slot="icon"]')
    const svg = iconSlot.get('svg.mq-icon')
    expect(svg.attributes('width')).toBe('16')
    expect(svg.attributes('height')).toBe('16')

    wrapper.unmount()
  })

  it('rectification-todos.css 使用 :deep 强制 inline-flex 居中、padding: 0 与 transform: none', () => {
    const css = readFileSync('src/views/workstation/styles/rectification-todos.css', 'utf8')
    expect(css).toContain('.rectification-todos__actions :deep(.rectification-todos__refresh.ant-btn)')
    expect(css).toMatch(
      /\.rectification-todos__refresh\.ant-btn\)\s*\{[^}]*display:\s*inline-flex;[^}]*align-items:\s*center;[^}]*justify-content:\s*center;[^}]*width:\s*36px;[^}]*height:\s*36px;[^}]*padding:\s*0;/s,
    )
    expect(css).toMatch(
      /\.rectification-todos__refresh\.ant-btn\s+\.mq-icon\)\s*\{[^}]*margin:\s*0;[^}]*transform:\s*none;/s,
    )
  })
})

describe('P2 #7 - 三个抽屉工具栏原生 <select>、Tab 与刷新按钮统一 34px 高度与垂直居中对齐', () => {
  it('ManualDefectWorkflowDrawer 工具栏 Tab、select 与刷新按钮统一 34px、box-sizing 且居中对齐', async () => {
    const source = readFileSync('src/components/qc/ManualDefectWorkflowDrawer.vue', 'utf8')
    expect(source).toMatch(/\.workflow-toolbar,\s*\.workflow-actions\s*\{[^}]*align-items:\s*center;/s)
    expect(source).toMatch(/\.workflow-toolbar\s+\.mq-segmented\s*\{[^}]*box-sizing:\s*border-box;[^}]*height:\s*34px;/s)
    expect(source).toMatch(/\.workflow-toolbar\s+\.mq-field\s*\{[^}]*flex-direction:\s*row;[^}]*align-items:\s*center;/s)
    expect(source).toMatch(/\.workflow-toolbar\s+select\.mq-input\s*\{[^}]*box-sizing:\s*border-box;[^}]*height:\s*34px;/s)
    expect(source).toMatch(/\.workflow-toolbar\s+\.mq-btn\s*\{[^}]*box-sizing:\s*border-box;[^}]*display:\s*inline-flex;[^}]*align-items:\s*center;[^}]*justify-content:\s*center;[^}]*height:\s*34px;/s)
    expect(source).toMatch(/\.workflow-toolbar\s+\.mq-btn\s+\.mq-icon\s*\{[^}]*margin:\s*0;/s)

    const wrapper = mount(ManualDefectWorkflowDrawer, {
      props: { open: true },
      global: { stubs: { 'a-drawer': DrawerStub } },
    })
    await flushPromises()
    expect(wrapper.find('.workflow-toolbar [role="tablist"]').exists()).toBe(true)
    expect(wrapper.find('.workflow-toolbar select.mq-input').exists()).toBe(true)
    expect(wrapper.find('.workflow-toolbar button.mq-btn svg.mq-icon').exists()).toBe(true)
    wrapper.unmount()
  })

  it('ModernAppealWorkflowDrawer 工具栏 select 与刷新按钮统一 34px、box-sizing 且居中对齐', async () => {
    const source = readFileSync('src/components/qc/ModernAppealWorkflowDrawer.vue', 'utf8')
    expect(source).toMatch(/\.appeal-toolbar\s*\{[^}]*align-items:\s*center;/s)
    expect(source).toMatch(/\.appeal-toolbar\s+\.mq-field\s*\{[^}]*flex-direction:\s*row;[^}]*align-items:\s*center;/s)
    expect(source).toMatch(/\.appeal-toolbar\s+select\.mq-input\s*\{[^}]*box-sizing:\s*border-box;[^}]*height:\s*34px;/s)
    expect(source).toMatch(/\.appeal-toolbar\s+\.mq-btn\s*\{[^}]*box-sizing:\s*border-box;[^}]*display:\s*inline-flex;[^}]*align-items:\s*center;[^}]*justify-content:\s*center;[^}]*height:\s*34px;/s)
    expect(source).toMatch(/\.appeal-toolbar\s+\.mq-btn\s+\.mq-icon\s*\{[^}]*margin:\s*0;/s)

    const wrapper = mount(ModernAppealWorkflowDrawer, {
      props: { open: true },
      global: { stubs: { 'a-drawer': DrawerStub } },
    })
    await flushPromises()
    expect(wrapper.findAll('.appeal-toolbar select.mq-input')).toHaveLength(2)
    expect(wrapper.find('.appeal-toolbar button.mq-btn svg.mq-icon').exists()).toBe(true)
    wrapper.unmount()
  })

  it('RecordReviewWorkflowDrawer 工具栏 select 与刷新按钮统一 34px、box-sizing 且居中对齐', async () => {
    const css = readFileSync('src/components/qc/styles/record-review-workflow.css', 'utf8')
    expect(css).toMatch(/\.review-filters\s*\{[^}]*align-items:\s*center;/s)
    expect(css).toMatch(/\.review-filters\s+\.mq-field\s*\{[^}]*flex-direction:\s*row;[^}]*align-items:\s*center;/s)
    expect(css).toMatch(/\.review-filters\s+select\.mq-input\s*\{[^}]*box-sizing:\s*border-box;[^}]*height:\s*34px;/s)
    expect(css).toMatch(
      /\.review-filters\s+\.mq-btn,\s*\.review-history-context\s+\.mq-btn\s*\{[^}]*box-sizing:\s*border-box;[^}]*display:\s*inline-flex;[^}]*align-items:\s*center;[^}]*justify-content:\s*center;[^}]*height:\s*34px;/s,
    )
    expect(css).toMatch(
      /\.review-filters\s+\.mq-btn\s+\.mq-icon,\s*\.review-history-context\s+\.mq-btn\s+\.mq-icon\s*\{[^}]*margin:\s*0;/s,
    )

    const wrapper = mount(RecordReviewWorkflowDrawer, {
      props: { open: true },
      global: { stubs: { 'a-drawer': DrawerStub, MqIconTile: true } },
    })
    await flushPromises()
    expect(wrapper.findAll('.review-filters select.mq-input')).toHaveLength(2)
    expect(wrapper.find('.review-filters button.mq-btn svg.mq-icon').exists()).toBe(true)
    wrapper.unmount()
  })
})
