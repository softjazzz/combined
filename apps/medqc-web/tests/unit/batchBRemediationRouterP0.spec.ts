/* eslint-disable vue/one-component-per-file */
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.unmock('vue-router')

const state = vi.hoisted(() => ({
  authenticated: true,
  user: {
    id: 'u-1',
    email: 'admin@medqc.com',
    institute_id: 'H1',
    department: '内科',
    roles: ['admin'] as string[],
    is_demo_account: false,
  },
  routeQuery: {} as Record<string, string | string[]>,
  requestRaw: vi.fn(),
  listRectifications: vi.fn(),
  getRectification: vi.fn(),
  actOnRectification: vi.fn(),
  getRectificationComparison: vi.fn(),
  getCommunicationInbox: vi.fn(),
  getCommunication: vi.fn(),
  readCommunication: vi.fn(),
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
  signIn: vi.fn(),
  signOut: vi.fn(),
}))

vi.mock('@/services/apiService', () => ({
  ApiService: {
    requestRaw: state.requestRaw,
  },
}))

vi.mock('@/api/defectRectifications', () => ({
  listRectifications: state.listRectifications,
  getRectification: state.getRectification,
  actOnRectification: state.actOnRectification,
  getRectificationComparison: state.getRectificationComparison,
}))

vi.mock('@/api/caseCommunications', () => ({
  getCommunicationInbox: state.getCommunicationInbox,
  getCommunication: state.getCommunication,
  readCommunication: state.readCommunication,
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
    get isAuthenticated() {
      return state.authenticated
    },
    get user() {
      return state.user
    },
    get userRoles() {
      return state.user.roles
    },
    get userName() {
      return state.user.email
    },
    hasRole: (role: string) => state.user.roles.includes(role),
    initialize: vi.fn(),
    signIn: state.signIn,
    signOut: state.signOut,
  }),
}))

vi.mock('@/components/layout/RuntimeBuildStatus.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/views/workstation-v4/components/GlobalAssistantHost.vue', () => ({
  default: { template: '<div />' },
}))
vi.mock('@/components/layout/WorkstationConfirmDialog.vue', () => ({
  default: { template: '<div />' },
}))
vi.mock('@/views/auth/ProfileView.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/views/workstation-v4/WorkstationV4HomeEntry.vue', () => ({
  default: { template: '<div />' },
}))
vi.mock('@/views/workstation-v4/WorkstationV4View.vue', () => ({
  default: { template: '<div />' },
}))
vi.mock('@/views/workstation-v4/frontpage-qc/FrontpageQcView.vue', () => ({
  default: { template: '<div />' },
}))
vi.mock('@/views/workstation-v4/LuxianQcAnalyticsView.vue', () => ({
  default: { template: '<div />' },
}))
vi.mock('@/views/qc/reports/RecordQualityReportView.vue', () => ({
  default: { template: '<div />' },
}))
vi.mock('@/components/layout/MainLayout.vue', () => ({
  default: { template: '<router-view />' },
}))
vi.mock('ant-design-vue', () => ({
  ConfigProvider: defineComponent({ template: '<div><slot /></div>' }),
  message: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

window.scrollTo = vi.fn()

import {
  actOnModernAppeal,
  getModernAppeal,
  listModernAppeals,
} from '@/api/modernAppeals'
import ModernAppealWorkflowDrawer from '@/components/qc/ModernAppealWorkflowDrawer.vue'
import ManualDefectWorkflowDrawer from '@/components/qc/ManualDefectWorkflowDrawer.vue'
import RecordReviewWorkflowDrawer from '@/components/qc/RecordReviewWorkflowDrawer.vue'
import HomeRectificationTodos from '@/views/workstation/HomeRectificationTodos.vue'
import HomeCaseCommunications from '@/views/workstation/HomeCaseCommunications.vue'
import WorkstationLayout from '@/components/layout/WorkstationLayout.vue'
import WorkstationLoginView from '@/views/workstation-v4/WorkstationLoginView.vue'
import {
  WORKSTATION_NAV,
  filterVisibleNav,
  findActiveNav,
  resolveAuthorizedWorkstationPath,
  resolveDefaultWorkstationPath,
} from '@/components/layout/workstationNav'
import router from '@/router'

const baseAppeal = {
  id: 'appeal-superseded',
  target_kind: 'canonical_defect' as const,
  target_id: 'RULE-001',
  institute_id: 'H1',
  patient_id: 'P1',
  visit_id: 'V1',
  scene: 'final' as const,
  root_job_id: 'JOB-1',
  envelope_id: 'ENV-1',
  rule_set_key: 'luxian_0609_qc_v1',
  rule_set_version: '1',
  case_department: '内科',
  appellant_id: 'doctor-1',
  appellant_name: '张医生',
  reason: '该病历实际已完成补充记录请核对',
  status: 'superseded' as const,
  resolution: '质控已重跑至新轮次，终结原失效轮次未决申诉',
  created_at: '2026-10-24T08:00:00Z',
}

const rectificationTask = {
  id: 'rect-1',
  institute_id: 'H1',
  patient_id: 'P1',
  visit_id: 'V1',
  department: '内科',
  target_id: 'RULE-001',
  target_kind: 'canonical_defect',
  scene: 'running',
  root_job_id: 'JOB-1',
  envelope_id: 'ENV-1',
  assignee_id: 'doctor-1',
  assignee_name: '张医生',
  status: 'submitted',
  version: 1,
  requirement: '请补充完善入院记录现病史',
  events: [],
}

const commonStubs = {
  MqIcon: true,
  MqIconTile: true,
  'router-link': { props: ['to'], template: '<a :href="typeof to === \'string\' ? to : to.path"><slot/></a>' },
  RouterLink: { props: ['to'], template: '<a :href="typeof to === \'string\' ? to : to.path"><slot/></a>' },
  'a-drawer': { props: ['open'], template: '<aside v-if="open"><slot/></aside>' },
  'a-button': { template: '<button type="button"><slot/></button>' },
  'a-alert': { props: ['message'], template: '<p role="alert">{{ message }}</p>' },
  'a-spin': { template: '<div><slot/></div>' },
  'a-select': { template: '<div />' },
  'a-pagination': true,
  'a-descriptions': { template: '<div><slot/></div>' },
  'a-descriptions-item': { template: '<div><slot/></div>' },
  'a-form': { template: '<div><slot/></div>' },
  'a-form-item': { template: '<div><slot/></div>' },
  'a-space': { template: '<div><slot/></div>' },
  'a-timeline': { template: '<div><slot/></div>' },
  'a-timeline-item': { template: '<div><slot/></div>' },
  'a-textarea': { template: '<textarea />' },
  'a-tooltip': { template: '<div><slot/></div>' },
  'a-dropdown': { template: '<div><slot/><slot name="overlay"/></div>' },
  'a-popover': { template: '<div><slot/></div>' },
  'a-menu': { template: '<div><slot/></div>' },
  'a-menu-item': { template: '<div><slot/></div>' },
  'a-menu-divider': true,
}

function setUser(roles: string[], id = 'u-1') {
  state.user = reactive({
    id,
    email: `${roles[0] || 'user'}@medqc.com`,
    institute_id: 'H1',
    department: '内科',
    roles: [...roles],
    is_demo_account: false,
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  state.authenticated = true
  setUser(['admin'])
  state.listRectifications.mockResolvedValue({ items: [rectificationTask], total: 1 })
  state.getRectification.mockResolvedValue(rectificationTask)
  state.getCommunicationInbox.mockResolvedValue({ items: [], total: 0 })
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
  state.getRecordReviewCurrent.mockResolvedValue({
    institute_id: 'H1',
    patient_id: 'P1',
    visit_id: 'V1',
    scene: 'running',
    root_job_id: 'JOB-1',
    envelope_id: 'ENV-1',
    rule_set_key: 'K',
    rule_set_version: '1',
    state: 'pending_review',
    stage: 'initial',
    case_department: '内科',
    current_review: null,
    history: [],
    can_submit: true,
  })
  state.signIn.mockResolvedValue({ success: true })
})

describe('P0-1 现代申诉状态机合同修复', () => {
  it('modernAppeals API 接受 superseded 状态与 close_stale / supersede 历史动作而不抛错', async () => {
    state.requestRaw.mockResolvedValueOnce({
      data: {
        success: true,
        data: { items: [baseAppeal], total: 1, pending_count: 0 },
      },
    })
    const list = await listModernAppeals()
    expect(list.items).toHaveLength(1)
    expect(list.items[0].status).toBe('superseded')

    state.requestRaw.mockResolvedValueOnce({
      data: {
        success: true,
        data: {
          ...baseAppeal,
          events: [
            {
              id: 'ev-1',
              action: 'close_stale',
              reviewer_name: '质控主管',
              comment: '质控重跑产生新轮次，关闭原失效申诉',
              created_at: '2026-10-25T09:00:00Z',
            },
            {
              id: 'ev-2',
              action: 'supersede',
              reviewer_name: '系统管理员',
              comment: '新轮次结果已替代原申诉目标对象',
              created_at: '2026-10-25T09:05:00Z',
            },
          ],
        },
      },
    })
    const detail = await getModernAppeal(baseAppeal.id)
    expect(detail.events.map((event) => event.action)).toEqual(['close_stale', 'supersede'])

    state.requestRaw.mockResolvedValueOnce({
      data: { success: true, data: baseAppeal },
    })
    const closed = await actOnModernAppeal(
      baseAppeal.id,
      'pending',
      'close_stale',
      '质控重跑产生新轮次，终结原申诉',
    )
    expect(closed.status).toBe('superseded')
  })

  it('ModernAppealWorkflowDrawer 正常渲染 superseded 列表与 close_stale / supersede 操作记录，不报无效错误', async () => {
    setUser(['super_admin'], 'super-1')
    state.requestRaw.mockResolvedValueOnce({
      data: {
        success: true,
        data: { items: [baseAppeal], total: 1, pending_count: 0 },
      },
    })
    state.requestRaw.mockResolvedValueOnce({
      data: {
        success: true,
        data: {
          ...baseAppeal,
          events: [
            {
              id: 'ev-1',
              action: 'close_stale',
              reviewer_name: '质控主管',
              comment: '质控重跑关闭原失效申诉记录',
              created_at: '2026-10-25T09:00:00Z',
            },
            {
              id: 'ev-2',
              action: 'supersede',
              reviewer_name: '超级管理员',
              comment: '新轮次覆盖原失效申诉记录',
              created_at: '2026-10-25T09:05:00Z',
            },
          ],
        },
      },
    })

    const wrapper = mount(ModernAppealWorkflowDrawer, {
      props: { open: true },
      global: { stubs: commonStubs },
    })
    await flushPromises()
    expect(wrapper.text()).not.toContain('申诉待办数据无效')
    expect(wrapper.text()).toContain('已失效（重跑关闭）')

    await wrapper.get('.appeal-row').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('重跑关闭')
    expect(wrapper.text()).toContain('新轮次替代关闭')
    expect(wrapper.text()).not.toContain('审核通过')
    wrapper.unmount()
  })
})

describe('P0-2 sync_admin / super_admin 角色与无权限空态修复', () => {
  it.each([['sync_admin'], ['super_admin']])(
    '%s 进入整改待办与病历沟通均正常渲染且具备管理与审核权限，不出现白屏',
    async (role) => {
      setUser([role], `${role}-1`)

      const todos = mount(HomeRectificationTodos, {
        global: {
          plugins: [router],
          stubs: {
            ...commonStubs,
            ManualDefectWorkflowDrawer: true,
            ModernAppealWorkflowDrawer: true,
            RecordReviewWorkflowDrawer: true,
          },
        },
      })
      await flushPromises()
      expect(todos.text()).toContain('缺陷整改待办')
      expect(todos.text()).toContain('人工缺陷处理')
      expect(todos.text()).toContain('申诉处理')
      expect(todos.text()).toContain('病历审核')
      expect(state.listRectifications).toHaveBeenCalledWith('submitted', 1)
      todos.unmount()

      const comms = mount(HomeCaseCommunications, {
        global: {
          plugins: [router],
          stubs: {
            ...commonStubs,
            CaseCommunicationHistory: true,
          },
        },
      })
      await flushPromises()
      expect(comms.text()).toContain('病历沟通')
      expect(comms.text()).toContain('接收记录')
      comms.unmount()

      const manual = mount(ManualDefectWorkflowDrawer, {
        props: { open: true },
        global: { stubs: commonStubs },
      })
      await flushPromises()
      expect(manual.text()).toContain('待审核 2')
      expect(state.getManualPendingCount).toHaveBeenCalled()
      manual.unmount()

      const review = mount(RecordReviewWorkflowDrawer, {
        props: {
          open: true,
          source: {
            institute_id: 'H1',
            patient_id: 'P1',
            visit_id: 'V1',
            scene: 'running',
            root_job_id: 'JOB-1',
            envelope_id: 'ENV-1',
            rule_set_key: 'K',
            rule_set_version: '1',
          },
        },
        global: { stubs: commonStubs },
      })
      await flushPromises()
      expect(review.find('textarea').exists()).toBe(true)
      expect(review.text()).toContain('审核通过')
      review.unmount()

      state.requestRaw.mockResolvedValueOnce({
        data: {
          success: true,
          data: {
            items: [{ ...baseAppeal, status: 'pending', resolution: null }],
            total: 1,
            pending_count: 1,
          },
        },
      })
      state.requestRaw.mockResolvedValueOnce({
        data: {
          success: true,
          data: { ...baseAppeal, status: 'pending', resolution: null, events: [] },
        },
      })
      const appeals = mount(ModernAppealWorkflowDrawer, {
        props: { open: true },
        global: { stubs: commonStubs },
      })
      await flushPromises()
      await appeals.get('.appeal-row').trigger('click')
      await flushPromises()
      expect(appeals.text()).toContain('审核通过')
      expect(appeals.text()).toContain('驳回申诉')
      appeals.unmount()
    },
  )

  it('无权角色进入整改待办和病历沟通展示明确的无权限提示空态而非空白页', async () => {
    setUser(['coder'], 'coder-1')

    const todos = mount(HomeRectificationTodos, {
      global: {
        plugins: [router],
        stubs: {
          ...commonStubs,
          ManualDefectWorkflowDrawer: true,
          ModernAppealWorkflowDrawer: true,
          RecordReviewWorkflowDrawer: true,
        },
      },
    })
    await flushPromises()
    expect(todos.text()).toContain('无权访问缺陷整改待办')
    expect(state.listRectifications).not.toHaveBeenCalled()
    todos.unmount()

    const comms = mount(HomeCaseCommunications, {
      global: {
        plugins: [router],
        stubs: {
          ...commonStubs,
          CaseCommunicationHistory: true,
        },
      },
    })
    await flushPromises()
    expect(comms.text()).toContain('无权访问病历沟通')
    expect(state.getCommunicationInbox).not.toHaveBeenCalled()
    comms.unmount()
  })
})

describe('P0-3 super_admin 权限断层与导航高亮修复', () => {
  it('super_admin 可进入 /stats、/reports/record-quality，qc_staff 可进入 /dashboard/qc/rectifications', async () => {
    expect(router.resolve('/workstation-v5/stats').meta.permission).toContain('super_admin')
    expect(router.resolve('/workstation-v5/reports/record-quality').meta.permission).toContain(
      'super_admin',
    )
    expect(router.resolve('/dashboard/qc/rectifications').meta.permission).toContain('qc_staff')

    setUser(['super_admin'], 'super-1')
    await router.push('/workstation-v5/stats')
    expect(router.currentRoute.value.path).toBe('/workstation-v5/stats')
    await router.push('/workstation-v5/reports/record-quality')
    expect(router.currentRoute.value.path).toBe('/workstation-v5/reports/record-quality')

    setUser(['qc_staff'], 'staff-1')
    await router.push('/dashboard/qc/rectifications')
    expect(router.currentRoute.value.path).toBe('/dashboard/qc/rectifications')
  }, 15_000)

  it('workstationNav 支持 super_admin 导航可见性并正确高亮 /case-communications、/qc-task、/qc-result', () => {
    const visibleKeys = filterVisibleNav(WORKSTATION_NAV, {
      isDemoFeedbackAccount: false,
      userRoles: ['super_admin'],
      resolvePermission: (to) => router.resolve(to).meta.permission as string[] | undefined,
    }).flatMap((group) => group.items.map((item) => item.key))

    expect(visibleKeys).toContain('stats')
    expect(visibleKeys).toContain('report-record-quality')
    expect(visibleKeys).toContain('feedback-worklist')
    expect(visibleKeys).toContain('message-center')
    expect(visibleKeys).not.toContain('qc-feedback-demo')

    expect(
      findActiveNav(WORKSTATION_NAV, {
        path: '/workstation-v5/case-communications',
        query: {},
        meta: {},
      })?.item.key,
    ).toBe('feedback-worklist')
    expect(
      findActiveNav(WORKSTATION_NAV, {
        path: '/workstation-v5/qc-task',
        query: { job_id: 'job-1' },
        meta: {},
      })?.item.key,
    ).toBe('worklist')
    expect(
      findActiveNav(WORKSTATION_NAV, {
        path: '/workstation-v5/qc-result',
        query: { notification_id: 'n-1' },
        meta: {},
      })?.item.key,
    ).toBe('message-center')
  })
})

describe('P0-4 coder 默认着陆页、守卫兜底与侧栏 Logo 修复', () => {
  it('统一默认工作台着陆页解析：仅 coder 指向 /workstation-v5/frontpage-qc', () => {
    expect(resolveDefaultWorkstationPath(['coder'])).toBe('/workstation-v5/frontpage-qc')
    expect(resolveAuthorizedWorkstationPath(['coder'])).toBe('/workstation-v5/frontpage-qc')
    expect(resolveDefaultWorkstationPath(['coder', 'doctor'])).toBe('/workstation-v5')
    expect(resolveDefaultWorkstationPath(['qc_staff'])).toBe('/workstation-v5/feedback')
    expect(resolveAuthorizedWorkstationPath(['nurse'])).toBeNull()
  })

  it('coder 访问无权页、根首页与已登录登录页均落到 /workstation-v5/frontpage-qc，不被踢回 /auth/profile', async () => {
    setUser(['coder'], 'coder-1')
    await router.push('/workstation-v5')
    expect(router.currentRoute.value.path).toBe('/workstation-v5/frontpage-qc')

    await router.push('/workstation-v5/stats')
    expect(router.currentRoute.value.path).toBe('/workstation-v5/frontpage-qc')

    await router.push('/workstation-v5/login')
    expect(router.currentRoute.value.path).toBe('/workstation-v5/frontpage-qc')
  }, 15_000)

  it('WorkstationLayout 侧栏品牌 Logo 对 coder 指向 /workstation-v5/frontpage-qc，对 admin 指向 /workstation-v5', async () => {
    setUser(['coder'], 'coder-1')
    await router.push('/workstation-v5/frontpage-qc')
    const coderLayout = mount(WorkstationLayout, {
      global: {
        plugins: [router],
        stubs: {
          ...commonStubs,
          'router-view': { template: '<div />' },
        },
      },
    })
    await flushPromises()
    expect(coderLayout.get('a.ws-brand').attributes('href')).toBe('/workstation-v5/frontpage-qc')
    coderLayout.unmount()

    setUser(['admin'], 'admin-1')
    await router.push('/workstation-v5')
    const adminLayout = mount(WorkstationLayout, {
      global: {
        plugins: [router],
        stubs: {
          ...commonStubs,
          'router-view': { template: '<div />' },
        },
      },
    })
    await flushPromises()
    expect(adminLayout.get('a.ws-brand').attributes('href')).toBe('/workstation-v5')
    adminLayout.unmount()
  }, 15_000)

  it('WorkstationLoginView 中 coder 登录（无 redirect 或 bare /workstation-v5 redirect）直接落到 /workstation-v5/frontpage-qc', async () => {
    state.authenticated = false
    setUser([], 'anon')
    await router.push('/workstation-v5/login?redirect=/workstation-v5')
    const replaceSpy = vi.spyOn(router, 'replace')
    state.signIn.mockImplementationOnce(async () => {
      state.authenticated = true
      setUser(['coder'], 'coder-1')
      return { success: true, data: { id: 'coder-1', roles: ['coder'] } }
    })

    const LoginFormStub = defineComponent({
      emits: ['login'],
      setup(_, { emit }) {
        return () =>
          h(
            'button',
            {
              class: 'trigger-coder-login',
              type: 'button',
              onClick: () =>
                emit('login', {
                  account: 'coder@medqc.com',
                  password: 'password123',
                  role: 'coder',
                  remember_me: true,
                }),
            },
            '编码员登录',
          )
      },
    })

    const wrapper = mount(WorkstationLoginView, {
      global: {
        plugins: [router],
        stubs: {
          ...commonStubs,
          WorkstationLoginForm: LoginFormStub,
        },
      },
    })
    await wrapper.get('.trigger-coder-login').trigger('click')
    await flushPromises()
    expect(replaceSpy).toHaveBeenCalledWith('/workstation-v5/frontpage-qc')
    expect(router.currentRoute.value.path).toBe('/workstation-v5/frontpage-qc')
    wrapper.unmount()
  }, 15_000)
})
