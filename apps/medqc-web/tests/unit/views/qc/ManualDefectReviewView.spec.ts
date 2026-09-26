import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  review: vi.fn(),
  replace: vi.fn(),
  message: { success: vi.fn(), warning: vi.fn(), error: vi.fn() },
  route: null as null | { query: Record<string, string> },
}))

vi.mock('@/api/manualDefectReviews', () => ({ getManualDefects: mocks.list, reviewManualDefect: mocks.review }))
vi.mock('ant-design-vue', () => ({ message: mocks.message }))
vi.mock('vue-router', () => ({
  useRoute: () => mocks.route,
  useRouter: () => ({ replace: mocks.replace }),
}))

import ManualDefectReviewView from '@/views/qc/ManualDefectReviewView.vue'

const ButtonStub = defineComponent({
  name: 'AButton',
  inheritAttrs: false,
  props: { disabled: Boolean },
  emits: ['click'],
  setup(props, { attrs, emit, slots }) {
    return () => h('button', { ...attrs, disabled: props.disabled, onClick: () => emit('click') }, slots.default?.())
  },
})

const ModalStub = defineComponent({
  name: 'AModal',
  props: { open: Boolean },
  emits: ['ok', 'cancel'],
  setup(props, { emit, slots }) {
    return () => props.open
      ? h('div', { 'data-testid': 'modal' }, [
          slots.default?.(),
          h('button', { 'data-testid': 'modal-ok', onClick: () => emit('ok') }, '提交'),
        ])
      : null
  },
})

const TextareaStub = defineComponent({
  name: 'ATextarea',
  inheritAttrs: false,
  props: { value: String },
  emits: ['update:value'],
  setup(props, { attrs, emit }) {
    return () => h('textarea', {
      ...attrs, value: props.value,
      onInput: (event: Event) => emit('update:value', (event.target as HTMLTextAreaElement).value),
    })
  },
})

const slot = { template: '<div><slot /></div>' }

function defect(overrides: Record<string, unknown> = {}) {
  return {
    id: 'd-1', institute_id: 'H1', patient_id: 'P1', visit_id: 'V1', task_id: 'task-1',
    task_record_id: 'assoc-1', run_number: 2, rule_code: null, rule_name: '现病史不完整',
    description: '缺少关键症状', severity: 'warning', location: null, suggestion: null,
    manual_review_status: 'pending', manual_created_by: 'qc-a', created_at: '2026-09-25T08:00:00Z',
    ...overrides,
  }
}

function page(items: Array<Record<string, unknown>>, total = items.length) {
  return { success: true, status: 200, data: { items, total, page: 1, page_size: 20 } }
}

function mountView() {
  return mount(ManualDefectReviewView, {
    global: { stubs: {
      'a-page-header': true, 'a-card': slot, 'a-radio-group': slot, 'a-radio-button': slot,
      'a-result': { template: '<div data-testid="manual-defect-review-forbidden">{{ $attrs.title }}</div>' },
      'a-alert': { template: '<div data-testid="manual-defect-review-error">{{ $attrs.message }}</div>' },
      'a-empty': { template: '<div data-testid="empty">{{ $attrs.description }}</div>' },
      'a-tag': { template: '<span><slot /></span>' },
      'a-pagination': true,
      'a-button': ButtonStub, 'a-modal': ModalStub, 'a-textarea': TextareaStub,
    } },
  })
}

describe('ManualDefectReviewView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.route = reactive({ query: {} })
    mocks.list.mockResolvedValue(page([defect()]))
  })

  it('默认读取 pending，展示三坐标、任务、规则、创建人；未知值显示为未知', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(mocks.list).toHaveBeenCalledWith('pending', 1, 20)
    const text = wrapper.get('[data-testid="manual-defect-review-item"]').text()
    expect(text).toContain('机构 H1 / 患者 P1 / 就诊 V1')
    expect(text).toContain('task-1 · 第 2 次运行')
    expect(text).toContain('规则未知')
    expect(text).toContain('qc-a')
    expect(text).toContain('待审核')
    expect(wrapper.text()).toContain('共 1 条')
  })

  it('query review_status 决定筛选，无效值回落 pending', async () => {
    mocks.route = reactive({ query: { review_status: 'rejected' } })
    mocks.list.mockResolvedValueOnce(page([defect({ manual_review_status: 'rejected' })]))
    const wrapper = mountView()
    await flushPromises()
    expect(mocks.list).toHaveBeenCalledWith('rejected', 1, 20)
    expect(wrapper.find('[data-testid="manual-defect-approve-d-1"]').exists()).toBe(false)
    wrapper.unmount()

    mocks.route = reactive({ query: { review_status: 'bogus' } })
    mountView()
    await flushPromises()
    expect(mocks.list).toHaveBeenLastCalledWith('pending', 1, 20)
  })

  it('驳回必须填写原因；通过后提交 expected_status 并刷新', async () => {
    const wrapper = mountView()
    await flushPromises()
    await wrapper.get('[data-testid="manual-defect-reject-d-1"]').trigger('click')
    await wrapper.get('[data-testid="modal-ok"]').trigger('click')
    expect(mocks.review).not.toHaveBeenCalled()
    expect(wrapper.get('[data-testid="modal"]').text()).toContain('请填写驳回原因')

    await wrapper.get('#manual-defect-review-reason').setValue('  证据不足  ')
    mocks.review.mockResolvedValueOnce({ success: true, status: 200, data: { id: 'd-1', manual_review_status: 'rejected' } })
    await wrapper.get('[data-testid="modal-ok"]').trigger('click')
    await flushPromises()
    expect(mocks.review).toHaveBeenCalledWith('d-1', { decision: 'rejected', reason: '证据不足', expected_status: 'pending' })
    expect(mocks.message.success).toHaveBeenCalled()
    expect(mocks.list).toHaveBeenCalledTimes(2)
    expect(wrapper.find('[data-testid="modal"]').exists()).toBe(false)
  })

  it('409 not_pending 提示并刷新列表', async () => {
    const wrapper = mountView()
    await flushPromises()
    await wrapper.get('[data-testid="manual-defect-approve-d-1"]').trigger('click')
    mocks.review.mockResolvedValueOnce({ success: false, status: 409, code: 'not_pending', message: '已不是待审核' })
    await wrapper.get('[data-testid="modal-ok"]').trigger('click')
    await flushPromises()
    expect(mocks.review).toHaveBeenCalledWith('d-1', { decision: 'approved', reason: null, expected_status: 'pending' })
    expect(mocks.message.warning).toHaveBeenCalledWith('该缺陷已不是待审核状态，已刷新列表')
    expect(mocks.list).toHaveBeenCalledTimes(2)
  })

  it('提交 403（自审）在弹窗内提示，网络异常可重试不卡住', async () => {
    const wrapper = mountView()
    await flushPromises()
    await wrapper.get('[data-testid="manual-defect-approve-d-1"]').trigger('click')
    mocks.review
      .mockResolvedValueOnce({ success: false, status: 403, message: '审核人不能审核本人创建的人工缺陷' })
      .mockRejectedValueOnce(new Error('timeout'))
    await wrapper.get('[data-testid="modal-ok"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="modal"]').text()).toContain('不能审核本人创建')
    await wrapper.get('[data-testid="modal-ok"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="modal"]').text()).toContain('网络异常')
    expect(mocks.review).toHaveBeenCalledTimes(2)
  })

  it('列表 403 显示无权限，其他失败显示错误而非空列表', async () => {
    mocks.list.mockResolvedValueOnce({ success: false, status: 403, message: '没有人工缺陷审核权限' })
    const forbidden = mountView()
    await flushPromises()
    expect(forbidden.get('[data-testid="manual-defect-review-forbidden"]').text()).toContain('没有人工缺陷审核权限')
    expect(forbidden.find('[data-testid="empty"]').exists()).toBe(false)
    forbidden.unmount()

    mocks.list.mockResolvedValueOnce({ success: false, status: 503, message: '人工缺陷审核服务暂不可用' })
    const failed = mountView()
    await flushPromises()
    expect(failed.get('[data-testid="manual-defect-review-error"]').text()).toContain('暂不可用')
    expect(failed.text()).not.toContain('共 0 条')
  })
})
