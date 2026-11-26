/* eslint-disable vue/one-component-per-file */
import { readFileSync } from 'node:fs'
import { defineComponent, h, reactive } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPut: vi.fn(),
  routerPush: vi.fn(),
  routerReplace: vi.fn(),
  getNotificationQcResult: vi.fn(),
  getSichuanWorkspaceBatchJob: vi.fn(),
  getSichuanWorkspaceBatchJobDebugSnapshot: vi.fn(),
  exportSichuanWorkspaceBatchJob: vi.fn(),
  reviewSichuanWorkspaceBatchJob: vi.fn(),
  listRectifications: vi.fn(),
  getRectification: vi.fn(),
  actOnRectification: vi.fn(),
  getRectificationComparison: vi.fn(),
  listModernAppeals: vi.fn(),
  getModernAppeal: vi.fn(),
  createModernAppeal: vi.fn(),
  actOnModernAppeal: vi.fn(),
  getEntryContexts: vi.fn(),
  getManualPendingCount: vi.fn(),
  getManualReviewQueue: vi.fn(),
  getOwnManualEntries: vi.fn(),
  createManualEntry: vi.fn(),
  decideManualDefect: vi.fn(),
  listRecordReviews: vi.fn(),
  getRecordReviewCurrent: vi.fn(),
  getRecordReviewHistory: vi.fn(),
  submitRecordReview: vi.fn(),
  route: {
    path: '/workstation-v5/messages',
    query: {} as Record<string, string | string[] | undefined>,
  },
  auth: {
    user: {
      id: 'user-1',
      institute_id: 'H1',
      department: '内科',
      roles: ['qc_manager'] as string[],
      is_active: true,
    },
    userRoles: ['qc_manager'] as string[],
  },
}))

vi.mock('@/services/apiService', () => ({
  ApiService: {
    get: state.apiGet,
    put: state.apiPut,
    isAuthenticated: () => true,
  },
}))

vi.mock('@/services/sichuan-rule-workspace-service', () => ({
  getNotificationQcResult: state.getNotificationQcResult,
  getSichuanWorkspaceBatchJob: state.getSichuanWorkspaceBatchJob,
  getSichuanWorkspaceBatchJobDebugSnapshot: state.getSichuanWorkspaceBatchJobDebugSnapshot,
  exportSichuanWorkspaceBatchJob: state.exportSichuanWorkspaceBatchJob,
  reviewSichuanWorkspaceBatchJob: state.reviewSichuanWorkspaceBatchJob,
}))

vi.mock('@/api/defectRectifications', () => ({
  listRectifications: state.listRectifications,
  getRectification: state.getRectification,
  actOnRectification: state.actOnRectification,
  getRectificationComparison: state.getRectificationComparison,
}))

vi.mock('@/api/modernAppeals', () => ({
  listModernAppeals: state.listModernAppeals,
  getModernAppeal: state.getModernAppeal,
  createModernAppeal: state.createModernAppeal,
  actOnModernAppeal: state.actOnModernAppeal,
}))

vi.mock('@/api/manualDefectWorkflow', () => ({
  getEntryContexts: state.getEntryContexts,
  getManualPendingCount: state.getManualPendingCount,
  getManualReviewQueue: state.getManualReviewQueue,
  getOwnManualEntries: state.getOwnManualEntries,
  createManualEntry: state.createManualEntry,
  decideManualDefect: state.decideManualDefect,
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
    path: '/workstation-v5/messages',
    query: {} as Record<string, string | string[] | undefined>,
  })
  return {
    useRoute: () => state.route,
    useRouter: () => ({
      push: state.routerPush,
      replace: state.routerReplace,
    }),
  }
})

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
}))

vi.mock(
  '@/views/workstation-v4/semantic-rules/components/SemanticRulesBatchResultDrawer.vue',
  () => ({
    default: defineComponent({
      name: 'ResultDrawerStub',
      props: ['batchJobDetail'],
      template: '<section data-testid="result-drawer-stub">{{ batchJobDetail?.id }}</section>',
    }),
  }),
)

import MessageCenter from '@/views/workstation/MessageCenter.vue'
import NotificationQcResult from '@/views/workstation/NotificationQcResult.vue'
import HomeRectificationTodos from '@/views/workstation/HomeRectificationTodos.vue'
import ModernAppealWorkflowDrawer from '@/components/qc/ModernAppealWorkflowDrawer.vue'
import ManualDefectWorkflowDrawer from '@/components/qc/ManualDefectWorkflowDrawer.vue'
import RecordReviewWorkflowDrawer from '@/components/qc/RecordReviewWorkflowDrawer.vue'

const DrawerStub = defineComponent({
  props: ['open'],
  template: '<aside v-if="open"><slot /></aside>',
})

const ButtonStub = defineComponent({
  emits: ['click'],
  setup(_, { slots, attrs, emit }) {
    return () =>
      h(
        'button',
        {
          type: 'button',
          ...attrs,
          onClick: () => emit('click'),
        },
        [slots.icon?.(), slots.default?.()],
      )
  },
})

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}

beforeEach(() => {
  vi.clearAllMocks()
  state.route.path = '/workstation-v5/messages'
  state.route.query = {}
  state.auth.user = reactive({
    id: 'user-1',
    institute_id: 'H1',
    department: '内科',
    roles: ['qc_manager'],
    is_active: true,
  })
  state.auth.userRoles = ['qc_manager']
  state.apiGet.mockResolvedValue({
    success: true,
    data: { items: [], total: 0, unread_count: 0 },
  })
  state.apiPut.mockResolvedValue({ success: true })
  state.listRectifications.mockResolvedValue({ items: [], total: 0 })
  state.listModernAppeals.mockResolvedValue({ items: [], total: 0, pending_count: 0 })
  state.getEntryContexts.mockResolvedValue({ items: [], page: 1, has_more: false })
  state.getManualPendingCount.mockResolvedValue(2)
  state.getManualReviewQueue.mockResolvedValue({ items: [], total: 0 })
  state.getOwnManualEntries.mockResolvedValue({ items: [], total: 0 })
  state.listRecordReviews.mockResolvedValue({
    items: [],
    total: 0,
    pending_count: 0,
    initial_count: 0,
    recheck_count: 0,
  })
})

describe('Batch D - 1. 消除嵌套 <main> 地标与加载态居中提示', () => {
  it('MessageCenter 根节点使用 <section> 且无任何嵌套 <main>', async () => {
    const wrapper = mount(MessageCenter, {
      global: {
        stubs: {
          MqIcon: true,
          MqIconTile: true,
          'a-tooltip': { template: '<span><slot /></span>' },
          'a-button': ButtonStub,
          'a-select': { props: ['options', 'value'], template: '<select aria-label="消息类型" />' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-alert': { template: '<div><slot /></div>' },
          'a-pagination': true,
        },
      },
    })
    await flushPromises()
    expect(wrapper.element.tagName).toBe('SECTION')
    expect(wrapper.find('main').exists()).toBe(false)
    wrapper.unmount()
  })

  it('NotificationQcResult 根节点使用 <section> 且加载态显示居中容器与“正在加载质控结果…”', async () => {
    const pending = deferred<{ success: boolean; data: { id: string } }>()
    state.route.query = { notification_id: 'notice-1' }
    state.getNotificationQcResult.mockReturnValueOnce(pending.promise)

    const wrapper = mount(NotificationQcResult, {
      global: {
        stubs: {
          'a-spin': { template: '<div data-testid="spin-stub" />' },
          'a-result': true,
          'a-button': ButtonStub,
        },
      },
    })

    expect(wrapper.element.tagName).toBe('SECTION')
    expect(wrapper.find('main').exists()).toBe(false)
    const loadingBox = wrapper.get('.notification-qc-result__loading')
    expect(loadingBox.attributes('role')).toBe('status')
    expect(loadingBox.find('[data-testid="spin-stub"]').exists()).toBe(true)
    expect(loadingBox.text()).toContain('正在加载质控结果…')

    pending.resolve({ success: true, data: { id: 'job-1' } })
    await flushPromises()
    expect(wrapper.find('.notification-qc-result__loading').exists()).toBe(false)
    expect(wrapper.get('[data-testid="result-drawer-stub"]').text()).toContain('job-1')
    wrapper.unmount()
  })
})

describe('Batch D - 2. 1280px–1440px 消息中心视口布局与双滚动条修复', () => {
  it('message-center.css 使用 100dvh 网格自适应 1fr 并移除硬编码 148px 高度', () => {
    const css = readFileSync('src/views/workstation/styles/message-center.css', 'utf8')
    expect(css).toContain('height: calc(100dvh - 18px);')
    expect(css).toContain('grid-template-rows: auto auto minmax(0, 1fr);')
    expect(css).toContain('grid-template-rows: auto minmax(0, 1fr);')
    expect(css).not.toContain('calc(100dvh - 148px)')
    expect(css).not.toContain('min-height: 520px')
    expect(css).toMatch(/\.message-center__workspace\s*\{[^}]*min-height:\s*0;/s)
  })
})

describe('Batch D - 3. 1280px 整改待办页头操作群分组与裸标签 CSS 清理', () => {
  it('HomeRectificationTodos 将全部 7 个页头操作控件包入 .mq-page-head__actions', async () => {
    state.auth.user.roles = ['qc_manager', 'doctor']
    state.auth.userRoles = ['qc_manager', 'doctor']
    const wrapper = mount(HomeRectificationTodos, {
      global: {
        stubs: {
          MqIcon: true,
          ManualDefectWorkflowDrawer: true,
          ModernAppealWorkflowDrawer: true,
          RecordReviewWorkflowDrawer: true,
          'router-link': { props: ['to'], template: '<a class="mq-btn"><slot /></a>' },
          'a-select': {
            props: ['id', 'options', 'value'],
            template: '<select :id="id" data-testid="rect-status-select" />',
          },
          'a-button': ButtonStub,
          'a-spin': { template: '<div><slot /></div>' },
          'a-pagination': true,
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
    await flushPromises()

    const header = wrapper.get('header.rectification-todos__header.mq-page-head')
    const actions = header.get('.mq-page-head__actions')
    expect(actions.text()).toContain('人工缺陷处理')
    expect(actions.text()).toContain('申诉处理')
    expect(actions.text()).toContain('病历审核')
    expect(actions.text()).toContain('病历沟通')
    expect(actions.text()).toContain('消息面板')
    expect(actions.find('[data-testid="rect-status-select"]').exists()).toBe(true)
    expect(actions.find('button[aria-label="刷新整改待办"]').exists()).toBe(true)
    // 页头直属子元素仅包含标题块与操作群，避免折行错位
    expect(header.element.children).toHaveLength(2)
    wrapper.unmount()
  })

  it('rectification-todos.css 移除裸 header/h2 选择器，改用专属类选择器', () => {
    const css = readFileSync('src/views/workstation/styles/rectification-todos.css', 'utf8')
    expect(css).not.toMatch(/^\s*header\s*\{/m)
    expect(css).not.toMatch(/^\s*h2\s*\{/m)
    expect(css).toContain('.rectification-todos__header')
    expect(css).toContain('.rectification-heading__title')
  })
})

describe('Batch D - 4. 申诉抽屉 CSS Token、状态类与焦点环修复', () => {
  it('ModernAppealWorkflowDrawer 不再引用未定义 Token 或 .mq-status--neutral，并补齐焦点环', () => {
    const source = readFileSync('src/components/qc/ModernAppealWorkflowDrawer.vue', 'utf8')
    expect(source).not.toContain('var(--mq-danger)')
    expect(source).not.toContain('var(--mq-text-muted)')
    expect(source).not.toContain('mq-status--neutral')
    expect(source).toContain('var(--mq-danger-text)')
    expect(source).toContain('var(--mq-danger-bg)')
    expect(source).toContain('var(--mq-text-tertiary)')
    expect(source).toContain('.appeal-row:focus-visible')
  })

  it('已撤回/已失效状态使用合法默认中性 .mq-status，且全部非提交按钮声明 type="button"', async () => {
    state.auth.user.id = 'doc-1'
    state.auth.user.roles = ['doctor']
    state.auth.userRoles = ['doctor']
    const withdrawnAppeal = {
      id: 'ap-w',
      appellant_id: 'doc-1',
      appellant_name: '张医生',
      target_id: 'R1',
      target_kind: 'canonical_defect',
      scene: 'running',
      institute_id: 'H1',
      patient_id: 'P1',
      visit_id: 'V1',
      root_job_id: 'J1',
      envelope_id: 'E1',
      status: 'withdrawn',
      reason: '已撤回的申诉原因',
      events: [],
    }
    const pendingAppeal = {
      ...withdrawnAppeal,
      id: 'ap-p',
      status: 'pending',
    }
    state.listModernAppeals.mockResolvedValue({
      items: [withdrawnAppeal, pendingAppeal],
      total: 15,
      pending_count: 1,
    })
    state.getModernAppeal.mockResolvedValue(pendingAppeal)

    const wrapper = mount(ModernAppealWorkflowDrawer, {
      props: {
        open: true,
        source: {
          id: 'task-1',
          assignee_id: 'doc-1',
          target_id: 'R1',
          target_kind: 'canonical_defect',
          scene: 'running',
          visit_id: 'V1',
          institute_id: 'H1',
          patient_id: 'P1',
          root_job_id: 'J1',
          envelope_id: 'E1',
          assignee_name: '张医生',
          creator_id: 'mgr-1',
          department: '内科',
          requirement: '要求',
          status: 'pending',
          version: 1,
          submission: null,
          review_comment: null,
          updated_at: '2026-10-24',
        },
      },
      global: { stubs: { 'a-drawer': DrawerStub, MqIcon: true } },
    })
    await flushPromises()
    await wrapper.findAll('.appeal-row')[1].trigger('click')
    await flushPromises()

    const firstStatus = wrapper.findAll('.appeal-row .mq-status')[0]
    expect(firstStatus.classes()).toContain('mq-status')
    expect(firstStatus.classes()).not.toContain('mq-status--neutral')

    const buttons = wrapper.findAll('button')
    expect(buttons.length).toBeGreaterThan(0)
    for (const btn of buttons) {
      if (btn.text().trim() === '提交申诉') {
        expect(btn.attributes('type')).toBe('submit')
      } else {
        expect(btn.attributes('type')).toBe('button')
      }
    }
    wrapper.unmount()
  })
})

describe('Batch D - 5. 抽屉键盘可访问性与人工缺陷 tablist/tabpanel 语义补齐', () => {
  it('RecordReviewWorkflowDrawer 所有按钮均显式声明 type="button"', async () => {
    const source = {
      institute_id: 'I',
      patient_id: 'P',
      visit_id: 'V1',
      scene: 'running' as const,
      root_job_id: 'J',
      envelope_id: 'E',
      rule_set_key: 'K',
      rule_set_version: '1',
    }
    state.listRecordReviews.mockResolvedValue({
      items: [{ ...source, state: 'pending_review', stage: 'initial', case_department: '内科', review_id: null }],
      total: 15,
      pending_count: 1,
      initial_count: 1,
      recheck_count: 0,
    })
    state.getRecordReviewCurrent.mockResolvedValue({
      ...source,
      state: 'pending_review',
      stage: 'initial',
      case_department: '内科',
      current_review: null,
      history: [],
      can_submit: true,
    })

    const wrapper = mount(RecordReviewWorkflowDrawer, {
      props: { open: true, source },
      global: { stubs: { 'a-drawer': DrawerStub, MqIcon: true, MqIconTile: true } },
    })
    await flushPromises()
    const buttons = wrapper.findAll('button')
    expect(buttons.length).toBeGreaterThanOrEqual(6)
    for (const btn of buttons) {
      expect(btn.attributes('type')).toBe('button')
    }
    wrapper.unmount()
  })

  it('ManualDefectWorkflowDrawer 补齐 tabpanel/aria-controls/aria-labelledby、方向键导航与 button type', async () => {
    const entryContext = {
      task_id: 't1',
      task_record_id: 'rec-1',
      task_name: '任务一',
      institute_id: 'I',
      patient_id: 'P',
      visit_id: 'V1',
      scene: 'running',
      run_number: 1,
      job_id: 'job-1',
      available: true,
      reason: null,
    }
    const reviewItem = {
      id: 'd1',
      task_id: 't1',
      task_record_id: 'rec-1',
      run_number: 1,
      manual_created_by: 'other-user',
      rule_name: '人工缺陷示例',
      description: '示例描述',
      manual_review_status: 'pending',
      institute_id: 'I',
      patient_id: 'P',
      visit_id: 'V1',
    }
    state.getEntryContexts.mockResolvedValue({ items: [entryContext], page: 1, has_more: true })
    state.getManualReviewQueue.mockResolvedValue({ items: [reviewItem], total: 25 })
    state.getOwnManualEntries.mockResolvedValue({ items: [reviewItem], total: 5 })

    const wrapper = mount(ManualDefectWorkflowDrawer, {
      attachTo: document.body,
      props: { open: true },
      global: { stubs: { 'a-drawer': DrawerStub, MqIcon: true } },
    })
    await flushPromises()

    const tabs = wrapper.findAll('[role="tab"]')
    expect(tabs).toHaveLength(2)
    const [entryTab, reviewTab] = tabs

    // ARIA 关联与 roving tabindex
    expect(entryTab.attributes('type')).toBe('button')
    expect(reviewTab.attributes('type')).toBe('button')
    expect(entryTab.attributes('id')).toBe('manual-defect-tab-entry')
    expect(entryTab.attributes('aria-controls')).toBe('manual-defect-panel-entry')
    expect(entryTab.attributes('aria-selected')).toBe('true')
    expect(entryTab.attributes('tabindex')).toBe('0')
    expect(reviewTab.attributes('id')).toBe('manual-defect-tab-review')
    expect(reviewTab.attributes('aria-controls')).toBe('manual-defect-panel-review')
    expect(reviewTab.attributes('aria-selected')).toBe('false')
    expect(reviewTab.attributes('tabindex')).toBe('-1')

    const entryPanel = wrapper.get('#manual-defect-panel-entry')
    const reviewPanel = wrapper.get('#manual-defect-panel-review')
    expect(entryPanel.attributes('role')).toBe('tabpanel')
    expect(entryPanel.attributes('aria-labelledby')).toBe('manual-defect-tab-entry')
    expect(entryPanel.attributes('hidden')).toBeUndefined()
    expect(reviewPanel.attributes('role')).toBe('tabpanel')
    expect(reviewPanel.attributes('aria-labelledby')).toBe('manual-defect-tab-review')
    expect(reviewPanel.attributes('hidden')).toBeDefined()

    // 选中受领病例以验证录入页所有按钮 type
    await wrapper.findAll('select')[1].setValue('rec-1')
    await flushPromises()
    for (const btn of wrapper.findAll('button')) {
      if (btn.text().includes('提交人工缺陷')) {
        expect(btn.attributes('type')).toBe('submit')
      } else {
        expect(btn.attributes('type')).toBe('button')
      }
    }

    // ArrowRight 从录入切到待审核并转移焦点
    ;(entryTab.element as HTMLButtonElement).focus()
    await entryTab.trigger('keydown', { key: 'ArrowRight' })
    await flushPromises()
    expect(reviewTab.attributes('aria-selected')).toBe('true')
    expect(reviewTab.attributes('tabindex')).toBe('0')
    expect(entryTab.attributes('aria-selected')).toBe('false')
    expect(entryTab.attributes('tabindex')).toBe('-1')
    expect(document.activeElement).toBe(reviewTab.element)
    expect(reviewPanel.attributes('hidden')).toBeUndefined()
    expect(entryPanel.attributes('hidden')).toBeDefined()

    // 待审核面板全部按钮均为 type="button"
    for (const btn of wrapper.findAll('button')) {
      expect(btn.attributes('type')).toBe('button')
    }

    // ArrowLeft 从待审核切回录入并转移焦点
    await reviewTab.trigger('keydown', { key: 'ArrowLeft' })
    await flushPromises()
    expect(entryTab.attributes('aria-selected')).toBe('true')
    expect(document.activeElement).toBe(entryTab.element)
    expect(entryPanel.attributes('hidden')).toBeUndefined()
    expect(reviewPanel.attributes('hidden')).toBeDefined()

    wrapper.unmount()
  })
})
