import { mount } from '@vue/test-utils'
import { reactive } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import RecordReviewDecisionBlock from '@/components/qc/RecordReviewDecisionBlock.vue'
import {
  formatReviewTime,
  isPendingReviewState,
  reviewConflictMessage,
  reviewDecisionLabel,
  reviewStageLabel,
  reviewStateColor,
  reviewStateLabel,
  reviewUnavailableReason,
} from '@/composables/useRecordReviewDecision'
import type { RecordReviewDecisionController } from '@/composables/useRecordReviewDecision'
import { recordReviewStubs } from './recordReviewStubs'

function controller(overrides: Partial<RecordReviewDecisionController> = {}) {
  return reactive({
    view: {
      state: 'pending_review', stage: 'initial', reason_code: null, can_submit: true, current: null,
      history: [{
        id: 'rv-1', request_id: 'req-1', job_id: 'job-1', envelope_id: 'env-1', rule_set_key: 'lx0609',
        rule_set_version: 'v1', stage: 'initial', decision: 'doubtful', reason: '证据不足',
        reviewer_id: '', created_at: 'not-a-time',
      }],
      result: { job_id: 'job-1', envelope_id: 'env-1' },
    },
    loading: false,
    loadError: '',
    loadStatus: undefined,
    submitting: false,
    actionError: '',
    successMessage: '',
    decisionOpen: false,
    activeDecision: 'approved',
    reason: '',
    reasonError: '',
    canAct: true,
    refresh: vi.fn(),
    openDecision: vi.fn(),
    setReason: vi.fn(),
    closeDecision: vi.fn(),
    confirmDecision: vi.fn(),
    ...overrides,
  }) as RecordReviewDecisionController
}

describe('RecordReviewDecisionBlock', () => {
  it('上下文无关的标签映射：未知值显示未知，不伪造', () => {
    expect(['pending_review', 'pending_recheck', 'approved', 'doubtful', 'unavailable'].map((state) =>
      reviewStateLabel(state as never))).toEqual(['待审核', '待复审', '审核通过', '审核存疑', '不可审核'])
    expect(reviewStateLabel('mystery' as never)).toBe('未知')
    expect(reviewStateColor('approved')).toBe('success')
    expect(reviewStateColor('doubtful')).toBe('warning')
    expect(reviewStageLabel(null)).toBe('未知阶段')
    expect(reviewDecisionLabel('x' as never)).toBe('未知')
    expect(reviewUnavailableReason(null)).toBe('原因未知')
    expect(reviewUnavailableReason('new_code')).toBe('原因未知（new_code）')
    expect(reviewConflictMessage('result_changed')).toContain('质控结果已被替换')
    expect(reviewConflictMessage(undefined)).toBeUndefined()
    expect(formatReviewTime(null)).toBe('时间未知')
    expect(isPendingReviewState('pending_recheck')).toBe(true)
    expect(isPendingReviewState('approved')).toBe(false)
  })

  it('渲染状态、历史（缺失字段显示未知）与插槽，按钮与弹窗转发到控制器', async () => {
    const ctrl = controller()
    const wrapper = mount(RecordReviewDecisionBlock, {
      props: { controller: ctrl, blockedMessage: '不允许' },
      slots: { 'history-meta': '<em data-testid="meta">来源</em>' },
      global: { stubs: recordReviewStubs },
    })
    expect(wrapper.get('[data-testid="record-review-state"]').text()).toBe('待审核')
    const history = wrapper.get('[data-testid="record-review-history-item"]').text()
    expect(history).toContain('时间未知')
    expect(history).toContain('审核人 未知')
    expect(history).toContain('证据不足')
    expect(wrapper.find('[data-testid="meta"]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('不允许')

    await wrapper.get('[data-testid="record-review-doubt"]').trigger('click')
    expect(ctrl.openDecision).toHaveBeenCalledWith('doubtful')
    await wrapper.get('[data-testid="record-review-refresh"]').trigger('click')
    expect(ctrl.refresh).toHaveBeenCalled()

    ctrl.decisionOpen = true
    ctrl.activeDecision = 'doubtful'
    ctrl.reasonError = '请填写存疑原因'
    await wrapper.vm.$nextTick()
    expect(wrapper.get('[data-testid="modal"]').text()).toContain('存疑原因（必填）')
    expect(wrapper.get('[data-testid="modal"]').text()).toContain('请填写存疑原因')
    await wrapper.get('#record-review-reason').setValue('新原因')
    expect(ctrl.setReason).toHaveBeenCalledWith('新原因')
    await wrapper.get('[data-testid="modal-ok"]').trigger('click')
    expect(ctrl.confirmDecision).toHaveBeenCalled()
    await wrapper.get('[data-testid="modal-cancel"]').trigger('click')
    expect(ctrl.closeDecision).toHaveBeenCalled()
  })

  it('待审核但不可提交时显示上下文说明且按钮禁用', () => {
    const ctrl = controller({ canAct: false })
    if (ctrl.view) ctrl.view.can_submit = false
    const wrapper = mount(RecordReviewDecisionBlock, {
      props: { controller: ctrl, blockedMessage: '当前病历结果不允许提交审核。' },
      global: { stubs: recordReviewStubs },
    })
    expect(wrapper.text()).toContain('当前病历结果不允许提交审核。')
    expect(wrapper.get('[data-testid="record-review-approve"]').attributes('disabled')).toBeDefined()
  })
})
