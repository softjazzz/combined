import { h, nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AppealList from '@/views/qc/AppealList.vue'
import { AppealStatus, AppealType, type Appeal } from '@/types/appeal'

const state = vi.hoisted(() => ({
  roles: ['doctor'] as string[],
  userId: 'doctor-1',
  todo: undefined as string | undefined,
  query: {} as Record<string, string | undefined>,
  getAppeals: vi.fn(),
  getAppeal: vi.fn(),
  withdrawAppeal: vi.fn(),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    get userRoles() {
      return state.roles
    },
    get user() {
      return { id: state.userId }
    },
  }),
}))
vi.mock('vue-router', () => ({
  useRoute: () => ({
    query: {
      get todo() {
        return state.todo
      },
      get action() {
        return state.query.action
      },
      get scene() {
        return state.query.scene
      },
      get institute_id() {
        return state.query.institute_id
      },
      get patient_id() {
        return state.query.patient_id
      },
      get visit_id() {
        return state.query.visit_id
      },
    },
  }),
}))
vi.mock('@/api/appeal', () => ({
  getAppeals: state.getAppeals,
  getAppeal: state.getAppeal,
  withdrawAppeal: state.withdrawAppeal,
  reviewAppeal: vi.fn(),
}))
vi.mock('ant-design-vue', () => ({ message: { error: vi.fn(), success: vi.fn() } }))

const appeal: Appeal = {
  id: 'appeal-1',
  appealNumber: 'AP-1',
  qcResultId: 'qc-1',
  recordId: 'record-1',
  appealType: AppealType.DEFECT,
  defectItem: '缺陷项',
  appealReason: '申诉理由达到最低长度',
  evidence: [],
  status: AppealStatus.PENDING,
  priority: 'medium',
  appellantId: 'doctor-1',
  appellantName: '张医生',
  appellantDepartment: '内科',
  reviewerId: null,
  reviewerName: null,
  reviewResult: null,
  reviewedAt: null,
  resolution: null,
  resolutionDate: null,
  notes: null,
  createdAt: '2026-09-23T00:00:00Z',
  updatedAt: '2026-09-23T00:00:00Z',
  targetKind: 'canonical_defect',
  targetId: 'LX0609-001',
  instituteId: 'H1',
  patientId: 'P1',
  visitId: 'V1',
  scene: 'running',
  rootJobId: 'job-1',
  envelopeId: 'env-1',
  ruleSetKey: 'luxian_0609_qc_v1',
  ruleSetVersion: 'v1',
  caseDepartment: '内科',
}

const slotStub = { template: '<div><slot /></div>' }
const tableStub = {
  props: ['dataSource', 'columns'],
  render() {
    const component = this as {
      dataSource: Appeal[]
      columns: { key: string }[]
      $slots: { bodyCell?: (props: { column: { key: string }; record: Appeal }) => unknown }
    }
    return h(
      'div',
      component.dataSource.flatMap((record) =>
        component.columns.map((column) =>
          h('div', component.$slots.bodyCell?.({ column, record }) as never),
        ),
      ),
    )
  },
}

const stubs = {
  'a-page-header': slotStub,
  'a-card': slotStub,
  'a-form': slotStub,
  'a-form-item': slotStub,
  'a-select': slotStub,
  'a-select-option': slotStub,
  'a-button': { emits: ['click'], template: '<button @click="$emit(\'click\')"><slot /></button>' },
  'a-table': tableStub,
  'a-tag': slotStub,
  'a-space': slotStub,
  'a-popconfirm': slotStub,
  'a-modal': { props: ['open'], template: '<div v-if="open"><slot /></div>' },
  'a-spin': slotStub,
  'a-alert': {
    props: ['message'],
    template: '<div>{{ message }}<slot /><slot name="action" /></div>',
  },
  'a-descriptions': slotStub,
  'a-descriptions-item': slotStub,
  AppealReviewModal: {
    props: ['visible'],
    template:
      '<button v-if="visible" class="review-success" @click="$emit(\'success\')">完成审核</button>',
  },
  AppealForm: { props: ['visible'], template: '<div v-if="visible" class="appeal-form-stub" />' },
}

async function flush() {
  await Promise.resolve()
  await nextTick()
  await Promise.resolve()
  await nextTick()
}

function render() {
  return mount(AppealList, { global: { stubs } })
}

describe('AppealList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    state.roles = ['doctor']
    state.userId = 'doctor-1'
    state.todo = undefined
    state.query = {}
    state.getAppeals.mockResolvedValue({
      items: [appeal],
      total: 1,
      page: 1,
      pageSize: 20,
      totalPages: 1,
    })
  })

  it('hides review from non-reviewers and withdrawal from another appellant', async () => {
    state.userId = 'doctor-2'
    const wrapper = render()
    await flush()
    expect(wrapper.text()).toContain('详情')
    expect(wrapper.findAll('button').some((button) => button.text() === '审核')).toBe(false)
    expect(wrapper.findAll('button').some((button) => button.text() === '撤销')).toBe(false)
  })

  it('uses the reviewable queue from the home deep link', async () => {
    state.roles = ['qc_manager']
    state.todo = 'review'
    const wrapper = render()
    await flush()
    expect(state.getAppeals).toHaveBeenCalledWith(expect.objectContaining({ status: 'reviewable' }))
    expect(wrapper.text()).toContain('审核')
  })

  it('医生从首页三坐标深链打开真实候选表单', async () => {
    state.query = { action: 'create', institute_id: 'H1', patient_id: 'P1', visit_id: 'V1' }
    const wrapper = render()
    await flush()
    expect(wrapper.find('.appeal-form-stub').exists()).toBe(true)
  })

  it('非法场景深链按全部场景查询', async () => {
    state.query = { scene: 'unexpected-scene' }
    render()
    await flush()

    expect(state.getAppeals).toHaveBeenCalledWith(expect.objectContaining({ scene: 'all' }))
  })

  it('shows empty and loading errors without stale rows', async () => {
    state.getAppeals.mockResolvedValueOnce({
      items: [],
      total: 0,
      page: 1,
      pageSize: 20,
      totalPages: 0,
    })
    const wrapper = render()
    await flush()
    expect(wrapper.text()).not.toContain('申诉理由达到最低长度')
    state.getAppeals.mockRejectedValueOnce(new Error('unavailable'))
    await wrapper
      .findAll('button')
      .find((button) => button.text() === '查询')
      ?.trigger('click')
    await flush()
    expect(wrapper.text()).not.toContain('申诉理由达到最低长度')
  })

  it('shows detail request failure and refreshes after review success', async () => {
    state.roles = ['admin']
    state.getAppeal.mockRejectedValueOnce(new Error('详情不可用'))
    const wrapper = render()
    await flush()
    await wrapper
      .findAll('button')
      .find((button) => button.text() === '详情')
      ?.trigger('click')
    await flush()
    expect(state.getAppeal).toHaveBeenCalledWith('appeal-1')
    expect((wrapper.vm as unknown as { detailError: string }).detailError).toBe('详情不可用')
    await wrapper
      .findAll('button')
      .find((button) => button.text() === '审核')
      ?.trigger('click')
    await wrapper.find('.review-success').trigger('click')
    await flush()
    expect(state.getAppeals).toHaveBeenCalledTimes(2)
  })

  it('keeps the latest detail when an older request resolves last', async () => {
    const second = { ...appeal, id: 'appeal-2' }
    state.getAppeals.mockResolvedValueOnce({
      items: [appeal, second],
      total: 2,
      page: 1,
      pageSize: 20,
      totalPages: 1,
    })
    let resolveFirst: (value: Appeal) => void = () => undefined
    state.getAppeal.mockImplementationOnce(
      () =>
        new Promise<Appeal>((resolve) => {
          resolveFirst = resolve
        }),
    )
    state.getAppeal.mockResolvedValueOnce(second)
    const wrapper = render()
    await flush()
    const detailButtons = wrapper.findAll('button').filter((button) => button.text() === '详情')
    await detailButtons[0]?.trigger('click')
    await detailButtons[1]?.trigger('click')
    await flush()
    resolveFirst(appeal)
    await flush()
    expect((wrapper.vm as unknown as { detailAppeal: Appeal | null }).detailAppeal?.id).toBe(
      'appeal-2',
    )
  })

  it('keeps the latest list when an older filter request resolves last', async () => {
    let resolveFirst: (value: { items: Appeal[]; total: number }) => void = () => undefined
    state.getAppeals.mockReset()
    state.getAppeals.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveFirst = resolve
        }),
    )
    state.getAppeals.mockResolvedValueOnce({ items: [{ ...appeal, id: 'appeal-2' }], total: 1 })
    const wrapper = render()
    const vm = wrapper.vm as unknown as {
      filters: { status?: string }
      fetchAppeals: () => Promise<void>
      appeals: Appeal[]
    }
    vm.filters.status = 'approved'
    void vm.fetchAppeals()
    await flush()
    resolveFirst({ items: [appeal], total: 1 })
    await flush()

    expect(vm.appeals.map((item) => item.id)).toEqual(['appeal-2'])
  })
})
