/* eslint-disable vue/one-component-per-file */
import { defineComponent, h, nextTick, reactive, ref } from 'vue'
import { flushPromises, mount, shallowMount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPut: vi.fn(),
  isAuthenticated: vi.fn(() => true),
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
  getCommunicationInbox: vi.fn(),
  getCommunication: vi.fn(),
  readCommunication: vi.fn(),
  getLuxianQcResultAnalysis: vi.fn(),
  routerPush: vi.fn(),
  routerReplace: vi.fn(),
  messageSuccess: vi.fn(),
  messageError: vi.fn(),
  messageWarning: vi.fn(),
  messageInfo: vi.fn(),
  route: {
    path: '/workstation-v5/stats',
    query: {} as Record<string, string | string[] | undefined>,
  },
  auth: {
    user: {
      id: 'user-1',
      institute_id: 'H1',
      department: '内科',
      roles: ['admin'] as string[],
      is_active: true,
      is_demo_account: false,
    },
    userRoles: ['admin'] as string[],
  },
}))

vi.mock('@/services/apiService', () => ({
  ApiService: {
    get: state.apiGet,
    put: state.apiPut,
    isAuthenticated: state.isAuthenticated,
  },
}))

vi.mock('@/services/sichuan-rule-workspace-service', () => ({
  getNotificationQcResult: state.getNotificationQcResult,
  getSichuanWorkspaceBatchJob: state.getSichuanWorkspaceBatchJob,
  getSichuanWorkspaceBatchJobDebugSnapshot: state.getSichuanWorkspaceBatchJobDebugSnapshot,
  exportSichuanWorkspaceBatchJob: state.exportSichuanWorkspaceBatchJob,
  reviewSichuanWorkspaceBatchJob: state.reviewSichuanWorkspaceBatchJob,
  getSichuanWorkspaceBatchJobRecordIdentities: vi.fn().mockResolvedValue({ success: true, data: { items: [] } }),
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

vi.mock('@/api/caseCommunications', () => ({
  getCommunicationInbox: state.getCommunicationInbox,
  getCommunication: state.getCommunication,
  readCommunication: state.readCommunication,
}))

vi.mock('@/services/luxian-qc-result-analysis-service', () => ({
  getLuxianQcResultAnalysis: state.getLuxianQcResultAnalysis,
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
    path: '/workstation-v5/stats',
    query: {} as Record<string, string | string[] | undefined>,
  })
  return {
    useRoute: () => ({
      get path() {
        return state.route.path
      },
      get query() {
        return state.route.query
      },
      get fullPath() {
        return `${state.route.path}?${JSON.stringify(state.route.query)}`
      },
    }),
    useRouter: () => ({
      push: state.routerPush,
      replace: state.routerReplace,
    }),
  }
})

vi.mock('ant-design-vue', () => ({
  DatePicker: defineComponent({
    name: 'ADatePickerStub',
    props: ['value'],
    emits: ['update:value'],
    template: '<input />',
  }),
  message: {
    success: state.messageSuccess,
    error: state.messageError,
    warning: state.messageWarning,
    info: state.messageInfo,
  },
}))

vi.mock(
  '@/views/workstation-v4/semantic-rules/components/SemanticRulesBatchResultDrawer.vue',
  () => ({
    default: defineComponent({
      name: 'ResultDrawerStub',
      props: ['batchJobDetail', 'close', 'backLabel'],
      template: `<section data-testid="drawer-stub">
        <button data-testid="drawer-back" @click="close">{{ backLabel || '返回样本验证' }}</button>
      </section>`,
    }),
  }),
)

import NotificationQcResult from '@/views/workstation/NotificationQcResult.vue'
import HomeRectificationTodos from '@/views/workstation/HomeRectificationTodos.vue'
import ModernAppealWorkflowDrawer from '@/components/qc/ModernAppealWorkflowDrawer.vue'
import HomeCaseCommunications from '@/views/workstation/HomeCaseCommunications.vue'
import {
  MESSAGE_TYPE_LABELS,
  messageTime,
  useMessageCenter,
} from '@/views/workstation/useMessageCenter'
import { useNotifications } from '@/views/workstation-v4/composables/useNotifications'
import LuxianQcAnalyticsView from '@/views/workstation-v4/LuxianQcAnalyticsView.vue'
import QcRecordResultAnalysisPanel from '@/views/workstation-v4/components/qc/QcRecordResultAnalysisPanel.vue'
import { analyticsDrilldownSignature } from '@/views/workstation-v4/utils/analyticsDrilldown'
import { readFileSync } from 'node:fs'

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

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
        slots.default?.(),
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
            emit('update:value', val || undefined)
            emit('change', val || undefined)
          },
        },
        [
          h('option', { value: '' }, '全部'),
          ...((props.options as Array<{ label: string; value: string }>) || []).map((opt) =>
            h('option', { value: opt.value }, opt.label),
          ),
        ],
      )
  },
})

const InputStub = defineComponent({
  props: ['value'],
  emits: ['update:value'],
  setup(props, { attrs, emit }) {
    return () =>
      h('input', {
        ...attrs,
        value: props.value ?? '',
        onInput: (event: Event) =>
          emit('update:value', (event.target as HTMLInputElement).value),
      })
  },
})

const PaginationStub = defineComponent({
  props: ['current', 'total', 'pageSize'],
  emits: ['update:current', 'change'],
  setup(props, { emit }) {
    return () =>
      h('div', { class: 'pagination-stub' }, [
        h(
          'button',
          {
            type: 'button',
            'data-testid': 'next-page',
            onClick: () => {
              const next = (props.current || 1) + 1
              emit('update:current', next)
              emit('change', next)
            },
          },
          '下一页',
        ),
      ])
  },
})

const DrawerStub = defineComponent({
  props: ['open'],
  emits: ['update:open', 'close'],
  setup(props, { slots, emit }) {
    return () =>
      props.open
        ? h('aside', { 'data-testid': 'rect-drawer' }, [
            h(
              'button',
              {
                type: 'button',
                'data-testid': 'close-drawer',
                onClick: () => {
                  emit('update:open', false)
                  emit('close')
                },
              },
              '关闭抽屉',
            ),
            slots.default?.(),
          ])
        : null
  },
})

function makeAnalyticsPayload(overrides: Record<string, unknown> = {}) {
  return {
    scope: {
      time_basis: 'qc_completed_at',
      completed_from: null,
      completed_to: null,
      department: null,
      job_id: null,
      rule_set_key: 'luxian_0609_qc_v1',
      rule_set_version: '2026-06-09',
      generated_at: '2026-08-08T12:00:00+08:00',
    },
    kpis: {
      distinct_record_total: 10,
      completed_event_total: 12,
      records_with_non_compliant: 2,
      records_with_data_gap: 1,
      canonical_invalid_or_missing_total: 0,
    },
    status_distribution: [
      { status: 'non_compliant', count: 2 },
      { status: 'compliant', count: 10 },
    ],
    department_options: ['心内科', '骨科', 'ICU'],
    department_distribution: [
      {
        department: '心内科',
        distinct_record_total: 5,
        non_compliant_record_total: 2,
        data_gap_record_total: 0,
        uncertain_record_total: 0,
        problem_record_total: 2,
        primary_non_compliant_record_total: 2,
        primary_data_gap_record_total: 0,
        primary_uncertain_record_total: 0,
      },
    ],
    physician_distribution: [
      {
        physician: '张医生',
        distinct_record_total: 5,
        non_compliant_record_total: 2,
        data_gap_record_total: 0,
        uncertain_record_total: 0,
        problem_record_total: 2,
        primary_non_compliant_record_total: 2,
        primary_data_gap_record_total: 0,
        primary_uncertain_record_total: 0,
      },
    ],
    rule_distribution: [
      {
        rule_id: 'LX0609-01-01-01',
        rule_name: '入院记录时限',
        non_compliant_count: 2,
        data_gap_count: 0,
        uncertain_count: 0,
        evaluated_count: 10,
      },
      {
        rule_id: 'LX0609-01-02-01',
        rule_name: '零问题规则',
        non_compliant_count: 0,
        data_gap_count: 0,
        uncertain_count: 0,
        evaluated_count: 10,
      },
    ],
    completion_time_series: null,
    data_health: { canonical_invalid_or_missing_total: 0 },
    ...overrides,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  state.isAuthenticated.mockReturnValue(true)
  state.route.path = '/workstation-v5/stats'
  state.route.query = {}
  state.auth.user = reactive({
    id: 'user-1',
    institute_id: 'H1',
    department: '内科',
    roles: ['admin'],
    is_active: true,
    is_demo_account: false,
  })
  state.auth.userRoles = ['admin']
  state.routerReplace.mockImplementation(async (loc: { path?: string; query?: Record<string, unknown> }) => {
    if (loc.path) state.route.path = loc.path
    state.route.query = { ...(loc.query as Record<string, string | string[] | undefined>) }
  })
})

afterEach(() => {
  vi.useRealTimers()
})

describe('Batch C P1 - 1. /workstation-v5/qc-task 返回链路权限与文案修复', () => {
  it('qc_staff 从 /qc-task 关闭回退到 /workstation-v5/messages 且文案为“返回消息中心”，super_admin 回运行质控', async () => {
    state.route.path = '/workstation-v5/qc-task'
    state.route.query = { job_id: 'job-123' }
    state.getSichuanWorkspaceBatchJob.mockResolvedValue({ success: true, data: { id: 'job-123' } })

    state.auth.userRoles = ['qc_staff']
    const staffWrapper = mount(NotificationQcResult, {
      props: { entryMode: 'task' },
      global: { stubs: { 'a-spin': true, 'a-result': true, 'a-button': ButtonStub } },
    })
    await flushPromises()
    expect(staffWrapper.get('[data-testid="drawer-back"]').text()).toBe('返回消息中心')
    await staffWrapper.get('[data-testid="drawer-back"]').trigger('click')
    expect(state.routerPush).toHaveBeenCalledWith('/workstation-v5/messages')
    staffWrapper.unmount()

    state.routerPush.mockClear()
    state.auth.userRoles = ['super_admin']
    const superWrapper = mount(NotificationQcResult, {
      props: { entryMode: 'task' },
      global: { stubs: { 'a-spin': true, 'a-result': true, 'a-button': ButtonStub } },
    })
    await flushPromises()
    expect(superWrapper.get('[data-testid="drawer-back"]').text()).toBe('返回运行质控')
    await superWrapper.get('[data-testid="drawer-back"]').trigger('click')
    expect(state.routerPush).toHaveBeenCalledWith('/workstation-v5/records/running')
    superWrapper.unmount()

    state.routerPush.mockClear()
    state.auth.userRoles = ['doctor']
    const doctorWrapper = mount(NotificationQcResult, {
      props: { entryMode: 'task' },
      global: { stubs: { 'a-spin': true, 'a-result': true, 'a-button': ButtonStub } },
    })
    await flushPromises()
    expect(doctorWrapper.get('[data-testid="drawer-back"]').text()).toBe('返回工作台')
    await doctorWrapper.get('[data-testid="drawer-back"]').trigger('click')
    expect(state.routerPush).toHaveBeenCalledWith('/workstation-v5')
    doctorWrapper.unmount()
  })

  it('SemanticRulesBatchResultDrawer 源码支持 backLabel prop 并默认回退“返回样本验证”', () => {
    const source = readFileSync(
      'src/views/workstation-v4/semantic-rules/components/SemanticRulesBatchResultDrawer.vue',
      'utf8',
    )
    expect(source).toContain('backLabel?: string')
    expect(source).toContain("props.backLabel || '返回样本验证'")
  })
})

describe('Batch C P1 - 2. 整改待办 / 申诉 / 沟通 / 消息中心 / 通知前端修复', () => {
  const baseTask = {
    id: 'rect-1',
    institute_id: 'H1',
    patient_id: 'P1',
    visit_id: 'V1',
    department: '内科',
    target_id: 'R1',
    target_kind: 'canonical_defect',
    scene: 'running',
    root_job_id: 'J1',
    envelope_id: 'E1',
    assignee_id: 'doc-1',
    assignee_name: '张医生',
    status: 'approved',
    version: 3,
    requirement: '补充现病史',
    events: [
      {
        id: 'urge-1',
        action: 'urge',
        comment: '请尽快处理',
        created_at: '2026-10-22 16:00:00',
        version: 2,
        can_withdraw: true,
      },
      {
        id: 'submit-1',
        action: 'submit',
        comment: '已补充完成',
        created_at: '2026-10-22T16:30:00Z',
        version: 3,
      },
    ],
  }

  function mountRectifications() {
    return mount(HomeRectificationTodos, {
      global: {
        stubs: {
          MqIcon: true,
          'router-link': { template: '<a><slot/></a>' },
          ManualDefectWorkflowDrawer: true,
          RecordReviewWorkflowDrawer: true,
          ModernAppealWorkflowDrawer: defineComponent({
            props: ['open', 'appealId'],
            emits: ['close', 'changed'],
            template:
              '<div v-if="open" data-testid="appeal-drawer"><button data-testid="close-appeal" @click="$emit(\'close\')">关</button></div>',
          }),
          'a-button': ButtonStub,
          'a-spin': { template: '<div><slot/></div>' },
          'a-select': SelectStub,
          'a-pagination': PaginationStub,
          'a-drawer': DrawerStub,
          'a-descriptions': { template: '<div><slot/></div>' },
          'a-descriptions-item': { template: '<div><slot/></div>' },
          'a-form': { template: '<div><slot/></div>' },
          'a-form-item': { template: '<div><slot/></div>' },
          'a-space': { template: '<div><slot/></div>' },
          'a-timeline': { template: '<div><slot/></div>' },
          'a-timeline-item': { template: '<div><slot/></div>' },
          'a-textarea': {
            props: ['value'],
            emits: ['update:value'],
            template:
              '<textarea :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
          },
        },
      },
    })
  }

  it('HomeRectificationTodos: 对齐撤回催办与 10 字说明表单、东八区时间、关闭清 query、URL 同步与加载保留旧列表', async () => {
    state.route.path = '/workstation-v5/feedback'
    state.route.query = { status: 'approved', page: '2', rectification_id: 'rect-1' }
    state.auth.user.id = 'mgr-1'
    state.auth.userRoles = ['qc_manager']
    state.listRectifications.mockResolvedValue({ items: [baseTask], total: 25 })
    state.getRectification.mockResolvedValue(baseTask)
    state.getRectificationComparison.mockResolvedValue({
      available: true,
      before_at: '2026-10-22 16:00:00',
      after_at: '2026-10-22 17:00:00',
      documents: [],
    })

    const wrapper = mountRectifications()
    await flushPromises()

    // 从 URL 恢复 status=approved, page=2
    expect(state.listRectifications).toHaveBeenCalledWith('approved', 2)
    // approved 状态无常规 actions，但存在可撤回催办，因此 10 字说明表单可见且展示提示
    expect(wrapper.find('textarea').exists()).toBe(true)
    expect(wrapper.get('[data-testid="rectification-comment-hint"]').text()).toContain('至少 10 字')
    expect(wrapper.text()).toContain('撤回该催办')
    // 操作记录时间按 Asia/Shanghai 展示（UTC 16:00 -> 北京次日 00:00）
    expect(wrapper.text()).toContain('2026/10/23 00:00:00')
    expect(wrapper.text()).toContain('2026/10/23 00:30:00')

    // 比较快照时间同样按 Asia/Shanghai 展示
    await wrapper
      .findAll('button')
      .find((btn) => btn.text().includes('查看本次正文比较'))!
      .trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('2026/10/23 00:00:00 / 2026/10/23 01:00:00')

    // 关闭整改抽屉清理 ?rectification_id
    await wrapper.get('[data-testid="close-drawer"]').trigger('click')
    await flushPromises()
    expect(state.route.query.rectification_id).toBeUndefined()
    expect(state.route.query.status).toBe('approved')

    // 加载期间保留旧列表不闪烁
    const pendingList = deferred<{ items: typeof baseTask[]; total: number }>()
    state.listRectifications.mockReturnValueOnce(pendingList.promise)
    await wrapper.get('[data-testid="next-page"]').trigger('click')
    await nextTick()
    expect(wrapper.findAll('.rectification-task-list li')).toHaveLength(1)
    expect(state.route.query.page).toBe('3')
    pendingList.resolve({ items: [baseTask], total: 25 })
    await flushPromises()

    // 兼任受领人时隐藏撤回催办按钮，避免永久置灰
    state.auth.user.id = 'doc-1'
    state.auth.userRoles = ['qc_manager', 'doctor']
    await flushPromises()
    await wrapper.get('.rectification-task-list li button').trigger('click')
    await flushPromises()
    expect(wrapper.text()).not.toContain('撤回该催办')

    // 申诉抽屉关闭时清理 ?appeal_id
    state.route.query = { appeal_id: 'appeal-9' }
    await flushPromises()
    expect(wrapper.find('[data-testid="appeal-drawer"]').exists()).toBe(true)
    await wrapper.get('[data-testid="close-appeal"]').trigger('click')
    await flushPromises()
    expect(state.route.query.appeal_id).toBeUndefined()
    wrapper.unmount()
  })

  it('ModernAppealWorkflowDrawer: 时间按 Asia/Shanghai 格式化且展示“至少 10 字”提示', async () => {
    state.auth.user.id = 'doc-1'
    state.auth.userRoles = ['doctor']
    const appeal = {
      id: 'ap-1',
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
      status: 'pending',
      reason: '病历已完整记录无缺陷',
      events: [
        {
          id: 'ev-1',
          action: 'withdraw',
          reviewer_name: '张医生',
          comment: '已补充记录撤回申诉',
          created_at: '2026-10-22 16:00:00',
        },
      ],
    }
    state.listModernAppeals.mockResolvedValue({ items: [appeal], total: 1, pending_count: 1 })
    state.getModernAppeal.mockResolvedValue(appeal)

    const wrapper = mount(ModernAppealWorkflowDrawer, {
      props: {
        open: true,
        source: {
          ...baseTask,
          assignee_id: 'doc-1',
          creator_id: 'mgr-1',
          submission: null,
          review_comment: null,
          updated_at: '2026-10-22',
        } as never,
      },
      global: {
        stubs: {
          MqIcon: true,
          'a-drawer': DrawerStub,
        },
      },
    })
    await flushPromises()
    expect(wrapper.get('[data-testid="appeal-reason-hint"]').text()).toContain('至少 10 字')
    await wrapper.get('.appeal-row').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="appeal-comment-hint"]').text()).toContain('至少 10 字')
    expect(wrapper.text()).toContain('2026/10/23 00:00:00')
    wrapper.unmount()
  })

  it('HomeCaseCommunications: 已读消息再次打开跳过重复 POST /{id}/read', async () => {
    state.auth.user.id = 'doc-1'
    state.auth.userRoles = ['doctor']
    const readItem = {
      id: 'comm-1',
      notification_id: 'n-1',
      action: 'urge' as const,
      content: '已读催办内容',
      department: '内科',
      visit_id: 'V1',
      scene: 'final' as const,
      root_job_id: 'J1',
      envelope_id: 'E1',
      rule_set_key: 'K1',
      rule_set_version: '1',
      is_read: true,
      withdrawn: false,
      created_at: '2026-10-24T00:00:00Z',
    }
    state.getCommunicationInbox.mockResolvedValue({ items: [readItem], total: 1 })
    state.getCommunication.mockResolvedValue({ ...readItem, history: [readItem] })

    const wrapper = mount(HomeCaseCommunications, {
      global: {
        stubs: {
          MqIcon: true,
          MqIconTile: true,
          CaseCommunicationHistory: true,
          'router-link': { template: '<a><slot/></a>' },
          'a-button': ButtonStub,
          'a-spin': { template: '<div><slot/></div>' },
          'a-alert': { template: '<div/>' },
          'a-pagination': true,
          'a-drawer': DrawerStub,
        },
      },
    })
    await flushPromises()
    await wrapper.get('.case-inbox__row').trigger('click')
    await flushPromises()

    expect(state.getCommunication).toHaveBeenCalledWith('comm-1')
    expect(state.readCommunication).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('useMessageCenter: 补齐类型标签、全类型走 parseQcTaskTime 且筛选/页码双向同步 URL', async () => {
    expect(MESSAGE_TYPE_LABELS.case_communication).toBe('病历沟通')
    expect(MESSAGE_TYPE_LABELS.account_registration).toBe('账号注册审核')
    expect(messageTime('2026-10-22 16:00:00', 'remediation')).toBe('2026/10/23 00:00')
    expect(messageTime('2026-10-22 16:00:00', 'case_communication')).toBe('2026/10/23 00:00')

    state.route.path = '/workstation-v5/messages'
    state.route.query = { status: 'read', type: 'case_communication', page: '2' }
    state.apiGet.mockResolvedValue({
      success: true,
      data: {
        items: [
          {
            id: 'm1',
            title: '病历沟通提醒',
            content: '内容',
            created_at: '2026-10-22 16:00:00',
            is_read: true,
            type: 'case_communication',
          },
        ],
        total: 40,
        unread_count: 2,
      },
    })

    let mc!: ReturnType<typeof useMessageCenter>
    const wrapper = mount(
      defineComponent({
        setup() {
          mc = useMessageCenter()
          return () => h('div')
        },
      }),
    )
    await flushPromises()
    expect(mc.status.value).toBe('read')
    expect(mc.type.value).toBe('case_communication')
    expect(mc.page.value).toBe(2)
    expect(state.apiGet).toHaveBeenCalledWith('/api/v1/notifications', {
      page: 2,
      page_size: 20,
      type: 'case_communication',
      is_read: true,
    })

    // 切换筛选同步 URL
    mc.status.value = 'all'
    await flushPromises()
    expect(state.route.query.status).toBe('all')
    expect(state.route.query.page).toBeUndefined()

    // 翻页同步 URL
    mc.page.value = 3
    await mc.load()
    expect(state.route.query.page).toBe('3')
    wrapper.unmount()
  })

  it('useNotifications: 防重入锁、概览序号守卫且缺省日期交服务端、formatRelativeTime 统一 UTC 解析', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-10-22T16:10:00Z'))

    const notify = useNotifications(ref([]), vi.fn(), ref(false), ref('message'), ref('fields'))
    // 任意类型无时区时间按 UTC 解读：16:00:00Z 距 16:10:00Z 为 10 分钟前
    expect(notify.formatRelativeTime('2026-10-22 16:00:00', 'remediation')).toBe('10 分钟前')
    expect(notify.formatRelativeTime('2026-10-22 16:00:00', 'defect_urge')).toBe('10 分钟前')

    // 1. markAllAssistNotificationsRead 防重入锁
    const readAllDeferred = deferred<{ success: boolean }>()
    state.apiPut.mockReturnValueOnce(readAllDeferred.promise)
    state.apiGet.mockResolvedValue({ success: true, data: { items: [], unread_count: 0 } })
    const p1 = notify.markAllAssistNotificationsRead()
    const p2 = notify.markAllAssistNotificationsRead()
    expect(state.apiPut).toHaveBeenCalledTimes(1)
    readAllDeferred.resolve({ success: true })
    await Promise.all([p1, p2])

    // 2. handleAssistOverviewClick 防重入锁
    state.apiPut.mockClear()
    const clickDeferred = deferred<{ success: boolean }>()
    state.apiPut.mockReturnValueOnce(clickDeferred.promise)
    const openInteraction = vi.fn().mockResolvedValue(undefined)
    const notify2 = useNotifications(
      ref([]),
      vi.fn(),
      ref(false),
      ref('message'),
      ref('fields'),
      openInteraction,
    )
    const overviewItem = {
      overview_id: 'ov-1',
      type: 'remediation',
      severity: 'warning',
      department: '内科',
      record_id: '',
      title: '提醒',
      summary: '摘要',
      occurrence_count: 1,
      unread_count: 1,
      latest_created_at: '',
      source_notification_ids: ['n-1'],
      interaction_target: { kind: 'rectification' as const, id: 'r-1' },
    }
    const c1 = notify2.handleAssistOverviewClick(overviewItem)
    const c2 = notify2.handleAssistOverviewClick(overviewItem)
    expect(state.apiPut).toHaveBeenCalledTimes(1)
    clickDeferred.resolve({ success: true })
    await Promise.all([c1, c2])
    expect(openInteraction).toHaveBeenCalledTimes(1)

    // 3. fetchAssistNotificationOverview 不传前端本地 date，且乱序旧响应被序号守卫丢弃
    state.apiGet.mockClear()
    const oldOverview = deferred<{ success: boolean; data: { items: unknown[] } }>()
    const newOverview = deferred<{ success: boolean; data: { items: unknown[] } }>()
    state.apiGet
      .mockReturnValueOnce(oldOverview.promise)
      .mockReturnValueOnce(newOverview.promise)

    const ov1 = notify2.fetchAssistNotificationOverview()
    const ov2 = notify2.fetchAssistNotificationOverview()
    expect(state.apiGet).toHaveBeenNthCalledWith(1, '/api/v1/notifications/overview')
    expect(state.apiGet).toHaveBeenNthCalledWith(2, '/api/v1/notifications/overview')

    newOverview.resolve({
      success: true,
      data: { items: [{ overview_id: 'new', title: '最新概览', department: '心内科' }] },
    })
    await ov2
    expect(notify2.notificationOverviewItems.value.map((i) => i.overview_id)).toEqual(['new'])

    oldOverview.resolve({
      success: true,
      data: { items: [{ overview_id: 'old', title: '过期概览', department: '旧科' }] },
    })
    await ov1
    expect(notify2.notificationOverviewItems.value.map((i) => i.overview_id)).toEqual(['new'])
  })
})

describe('Batch C P1 - 3. 统计分析 / 结果分析 / 下钻前端修复', () => {
  function mountAnalytics() {
    return shallowMount(LuxianQcAnalyticsView, {
      global: {
        stubs: {
          'a-button': ButtonStub,
          'a-range-picker': InputStub,
          'a-select': SelectStub,
          'a-input': InputStub,
          'a-spin': { template: '<div />' },
          'a-empty': { template: '<div />' },
        },
      },
    })
  }

  it('LuxianQcAnalyticsView: AbortController 自动取消、department_options 缓存防自毁、0 问题规则过滤与副标题对齐', async () => {
    const firstReq = deferred<{ success: boolean; data: ReturnType<typeof makeAnalyticsPayload> }>()
    const signals: AbortSignal[] = []
    state.apiGet.mockImplementationOnce((_url, _params, config) => {
      signals.push(config.signal)
      return firstReq.promise
    })
    state.apiGet.mockImplementationOnce((_url, _params, config) => {
      signals.push(config.signal)
      return Promise.resolve({
        success: true,
        data: makeAnalyticsPayload({
          department_options: [],
          department_distribution: [],
          kpis: {
            distinct_record_total: 0,
            completed_event_total: 0,
            records_with_non_compliant: 0,
            records_with_data_gap: 0,
            canonical_invalid_or_missing_total: 0,
          },
        }),
      })
    })

    const wrapper = mountAnalytics()
    await nextTick()
    expect(signals).toHaveLength(1)
    expect(signals[0].aborted).toBe(false)

    // 先完成首次全院查询拿到 department_options
    firstReq.resolve({ success: true, data: makeAnalyticsPayload() })
    await flushPromises()

    // 副标题文案对齐且过滤掉 0 问题规则
    expect(wrapper.get('[data-testid="analytics-physician-chart"]').text()).toContain(
      '按病历主治医师归属',
    )
    expect(wrapper.text()).not.toContain('按首页主治医师签名归属')
    const ruleButtons = wrapper.findAll('[data-testid="analytics-rule-chart"] .rule-list button')
    expect(ruleButtons).toHaveLength(1)
    expect(ruleButtons[0].text()).toContain('LX0609-01-01-01')
    expect(wrapper.text()).not.toContain('零问题规则')

    // 选中单科并触发重查返回空数据时，科室下拉仍保留全院 3 个缓存选项
    const select = wrapper.findComponent(SelectStub)
    expect(select.props('options')).toHaveLength(3)
    await wrapper.get('select').setValue('心内科')
    const queryBtn = wrapper.findAll('button').find((b) => b.text().trim() === '查询')!
    await queryBtn.trigger('click')
    await flushPromises()
    expect(state.route.query.department).toBe('心内科')
    expect(select.props('options')).toHaveLength(3)

    // 再次发起挂起请求并卸载，验证自动 abort()
    const hanging = deferred<{ success: boolean; data: ReturnType<typeof makeAnalyticsPayload> }>()
    state.apiGet.mockImplementationOnce((_url, _params, config) => {
      signals.push(config.signal)
      return hanging.promise
    })
    await queryBtn.trigger('click')
    await nextTick()
    const lastSignal = signals[signals.length - 1]
    expect(lastSignal.aborted).toBe(false)
    wrapper.unmount()
    expect(lastSignal.aborted).toBe(true)
  })

  it('LuxianQcAnalyticsView: 支持单边时间 URL 同步、重置清空 URL、非法 UUID 拦截防 422', async () => {
    state.route.path = '/workstation-v5/stats'
    state.route.query = {
      department: '骨科',
      completed_from: '2026-08-01T00:00:00',
    }
    state.apiGet.mockResolvedValue({ success: true, data: makeAnalyticsPayload() })

    const wrapper = mountAnalytics()
    await flushPromises()

    expect(state.apiGet).toHaveBeenCalledWith(
      '/api/v1/workstation/analytics/luxian-0609',
      {
        completed_from: '2026-08-01T00:00:00',
        completed_to: undefined,
        department: '骨科',
        job_id: undefined,
      },
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )

    // 输入非法 UUID 拦截请求防 422
    const jobInput = wrapper.findAll('input')[1]
    await jobInput.setValue('not-a-uuid')
    await nextTick()
    state.apiGet.mockClear()
    const queryBtn = wrapper.findAll('button').find((b) => b.text().trim() === '查询')!
    await queryBtn.trigger('click')
    await flushPromises()
    expect(state.apiGet).not.toHaveBeenCalled()
    expect(wrapper.get('[data-testid="analytics-error"]').text()).toContain('UUID')

    // 重置清空 URL query 并重新查询
    const resetBtn = wrapper.findAll('button').find((b) => b.text().trim() === '重置')!
    await resetBtn.trigger('click')
    await flushPromises()
    expect(state.route.query).toEqual({})
    expect(state.apiGet).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('QcRecordResultAnalysisPanel: 缓存全院科室防下拉自毁，且超 20 条下钻提供翻页控件', async () => {
    const makePage = (page: number, depts: string[], total = 25) => ({
      scope: {
        care_phase: 'inpatient',
        department: null,
        doctor: null,
        rule_id: 'R1',
        result_status: null,
        completed_from: null,
        completed_to: null,
      },
      kpis: { scoped_record_total: total, ready_record_total: total, unavailable_result_total: 0 },
      status_distribution: [{ status: 'non_compliant', count: total }],
      rule_distribution: [
        {
          rule_id: 'R1',
          rule_name: '规则一',
          evaluated_count: total,
          non_compliant_count: total,
          data_gap_count: 0,
          uncertain_count: 0,
          issue_count: total,
          department_distribution: depts.map((dept) => ({
            department: dept,
            record_total: 10,
            non_compliant_count: 10,
            data_gap_count: 0,
            uncertain_count: 0,
          })),
        },
      ],
      physician_distribution: [],
      selected_rule: { rule_id: 'R1', rule_name: '规则一' },
      record_page: {
        page,
        page_size: 20,
        total,
        items: [
          {
            record_key: `["H","P${page}","V${page}"]`,
            institute_id: 'H',
            patient_id: `P${page}`,
            visit_id: `V${page}`,
            patient_name: `患者${page}`,
            department: depts[0] || '心内科',
            attending_physician: '张医生',
            status: 'non_compliant',
            completed_at: '2026-08-19T08:00:00+00:00',
          },
        ],
      },
    })

    state.getLuxianQcResultAnalysis
      .mockResolvedValueOnce(makePage(1, ['心内科', '骨科', '神经内科'], 25))
      .mockResolvedValueOnce(makePage(2, ['心内科', '骨科', '神经内科'], 25))
      .mockResolvedValueOnce(makePage(1, ['心内科'], 5))

    const wrapper = mount(QcRecordResultAnalysisPanel, {
      props: { carePhase: 'inpatient' },
    })
    await flushPromises()

    // 超 20 条展示分页控件
    const pagination = wrapper.get('[data-testid="qc-result-analysis-pagination"]')
    expect(pagination.text()).toContain('第 1 / 2 页')
    await pagination.findAll('button')[1].trigger('click')
    await flushPromises()
    expect(state.getLuxianQcResultAnalysis).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 2, pageSize: 20 }),
    )
    expect(wrapper.get('[data-testid="qc-result-analysis-pagination"]').text()).toContain('第 2 / 2 页')

    // 选中单科后科室下拉仍保留全部 3 个缓存科室
    const deptSelect = wrapper.get('select[aria-label="分析科室筛选"]')
    await deptSelect.setValue('心内科')
    await wrapper.get('.qc-result-analysis__query').trigger('click')
    await flushPromises()
    const optionValues = deptSelect.findAll('option').map((opt) => opt.element.value)
    expect(optionValues).toEqual(['', '骨科', '神经内科', '心内科'])
    wrapper.unmount()
  })

  it('analyticsDrilldownSignature 纳入 department，且 WorkstationV4View 同步重置 activeDept', () => {
    const sigA = analyticsDrilldownSignature({
      source: 'analytics',
      analytics_scope: 'final',
      analytics_rule_id: 'R1',
      department: 'ICU',
    })
    const sigB = analyticsDrilldownSignature({
      source: 'analytics',
      analytics_scope: 'final',
      analytics_rule_id: 'R1',
      department: '心内科',
    })
    const sigNone = analyticsDrilldownSignature({
      source: 'analytics',
      analytics_scope: 'final',
      analytics_rule_id: 'R1',
    })
    expect(sigA).not.toBe(sigB)
    expect(sigA).not.toBe(sigNone)

    const viewSource = readFileSync('src/views/workstation-v4/WorkstationV4View.vue', 'utf8')
    expect(viewSource).toContain("activeDept.value = routeDept || '全部科室'")
    expect(viewSource).toContain("function clearAnalyticsDrilldown() {\n  activeDept.value = '全部科室'")
  })
})
