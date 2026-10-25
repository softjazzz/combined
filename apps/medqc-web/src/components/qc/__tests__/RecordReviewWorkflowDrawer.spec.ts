import { flushPromises, mount } from '@vue/test-utils'
import { reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Drawer from '../RecordReviewWorkflowDrawer.vue'

const mocks = vi.hoisted(() => ({
  auth: { user: { id: 'staff', roles: ['qc_staff'] } },
  list: vi.fn(),
  current: vi.fn(),
  history: vi.fn(),
  submit: vi.fn(),
}))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    get user() {
      return mocks.auth.user
    },
    hasRole: (role: string) => mocks.auth.user.roles.includes(role),
  }),
}))
vi.mock('@/api/recordReviews', () => ({
  listRecordReviews: mocks.list,
  getRecordReviewCurrent: mocks.current,
  getRecordReviewHistory: mocks.history,
  submitRecordReview: mocks.submit,
}))
const source = {
  institute_id: 'I',
  patient_id: 'P',
  visit_id: 'V',
  scene: 'running',
  root_job_id: 'J',
  envelope_id: 'E',
  rule_set_key: 'K',
  rule_set_version: '1',
} as const
const detail = {
  ...source,
  state: 'pending_review',
  stage: 'initial',
  case_department: '内科',
  current_review: null,
  history: [],
  can_submit: true,
}
const row = {
  ...source,
  state: 'pending_review',
  stage: 'initial',
  case_department: '内科',
  review_id: null,
}
function make(props = {}) {
  return mount(Drawer, {
    props: { open: true, ...props },
    global: {
      stubs: {
        'a-drawer': { props: ['open'], template: '<aside v-if="open"><slot/></aside>' },
        MqIcon: true,
      },
    },
  })
}
beforeEach(() => {
  vi.clearAllMocks()
  mocks.auth = reactive({ user: { id: 'staff', roles: ['qc_staff'] } })
  mocks.list.mockResolvedValue({
    items: [row],
    total: 1,
    pending_count: 1,
    initial_count: 1,
    recheck_count: 0,
  })
  mocks.current.mockResolvedValue(detail)
  mocks.history.mockResolvedValue({ ...detail, state: 'approved', can_submit: false })
  mocks.submit.mockResolvedValue({ id: 'review' })
})
describe('病历初审复审抽屉', () => {
  it('待办选中当前结果，审核成功带CAS和完整来源并刷新父报表', async () => {
    const wrapper = make()
    await flushPromises()
    expect(wrapper.text()).toContain('待初审 1')
    await wrapper.get('.review-row').trigger('click')
    await flushPromises()
    await wrapper.get('textarea').setValue('合成审核意见')
    await wrapper
      .findAll('button')
      .find((button) => button.text() === '审核通过')!
      .trigger('click')
    await flushPromises()
    expect(mocks.submit).toHaveBeenCalledWith(
      source,
      'pending_review',
      'approved',
      '合成审核意见',
      expect.any(String),
    )
    expect(wrapper.emitted('changed')).toHaveLength(1)
    expect(mocks.list).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })
  it('存疑须填意见，复审提交新轮来源和预期状态', async () => {
    mocks.current.mockResolvedValue({
      ...detail,
      state: 'pending_recheck',
      stage: 'recheck',
      envelope_id: 'E2',
    })
    const wrapper = make({ source })
    await flushPromises()
    const doubtful = () => wrapper.findAll('button').find((button) => button.text() === '标记存疑')!
    expect(doubtful().attributes('disabled')).toBeDefined()
    await wrapper.get('textarea').setValue('复审保留疑点')
    await doubtful().trigger('click')
    await flushPromises()
    expect(mocks.submit).toHaveBeenCalledWith(
      { ...source, envelope_id: 'E2' },
      'pending_recheck',
      'doubtful',
      '复审保留疑点',
      expect.any(String),
    )
    wrapper.unmount()
  })
  it('精确审核事件ID打开旧历史且不显示写操作', async () => {
    const wrapper = make({ reviewId: 'old-review' })
    await flushPromises()
    expect(mocks.history).toHaveBeenCalledWith('old-review')
    expect(wrapper.findAll('textarea')).toHaveLength(0)
    expect(mocks.current).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('未知提交不自动重发，核对失败显示未知', async () => {
    mocks.submit.mockRejectedValue(new Error('回执待核对'))
    const wrapper = make({ source })
    await flushPromises()
    await wrapper
      .findAll('button')
      .find((button) => button.text() === '审核通过')!
      .trigger('click')
    await flushPromises()
    expect(mocks.submit).toHaveBeenCalledTimes(1)
    expect(wrapper.emitted('changed')).toBeUndefined()
    expect(wrapper.findAll('textarea')).toHaveLength(0)
    expect(wrapper.text()).toContain('提交结果未核实')
    mocks.list.mockRejectedValue(new Error('核对失败'))
    mocks.current.mockRejectedValue(new Error('核对失败'))
    await wrapper
      .findAll('button')
      .find((button) => button.text().includes('刷新核对'))!
      .trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('待初审 未知')
    expect(mocks.submit).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })
  it('账号切换丢弃旧响应并清空详情', async () => {
    let resolve!: (value: unknown) => void
    mocks.current.mockReturnValueOnce(
      new Promise((done) => {
        resolve = done
      }),
    )
    const wrapper = make({ source })
    await flushPromises()
    mocks.auth.user = { id: 'doctor', roles: ['doctor'] }
    await flushPromises()
    resolve(detail)
    await flushPromises()
    expect(wrapper.findAll('textarea')).toHaveLength(0)
    expect(wrapper.text()).toContain('待初审 未知')
    wrapper.unmount()
  })
  it('同账号撤销质控角色时立即丢弃原详情与迟到响应', async () => {
    const wrapper = make({ source })
    await flushPromises()
    expect(wrapper.findAll('textarea')).toHaveLength(1)
    let resolve!: (value: unknown) => void
    mocks.current.mockReturnValueOnce(
      new Promise((done) => {
        resolve = done
      }),
    )
    await wrapper
      .findAll('button')
      .find((button) => button.text().includes('刷新核对'))!
      .trigger('click')
    await flushPromises()
    mocks.auth.user.roles = ['doctor']
    await flushPromises()
    resolve(detail)
    await flushPromises()
    expect(wrapper.findAll('textarea')).toHaveLength(0)
    expect(wrapper.text()).toContain('待初审 未知')
    wrapper.unmount()
  })
})
