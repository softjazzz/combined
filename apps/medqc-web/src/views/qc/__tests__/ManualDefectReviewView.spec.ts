import { mount } from '@vue/test-utils'
import { nextTick, reactive } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ManualDefectReviewView from '@/views/qc/ManualDefectReviewView.vue'
import type {
  ManualDefectReviewItem,
  ManualDefectReviewPage,
  ManualDefectReviewScene,
} from '@/api/manualDefectReviews'

const state = vi.hoisted(() => ({
  getManualDefects: vi.fn(),
  reviewManualDefect: vi.fn(),
  success: vi.fn(),
  warning: vi.fn(),
}))

const route = reactive({
  path: '/dashboard/qc/manual-defects',
  query: {} as Record<string, unknown>,
})
const replace = vi.fn(async ({ query }: { query: Record<string, unknown> }) => {
  Object.keys(route.query).forEach((key) => delete route.query[key])
  Object.assign(route.query, query)
})

vi.mock('vue-router', () => ({ useRoute: () => route, useRouter: () => ({ replace }) }))
vi.mock('@/api/manualDefectReviews', () => ({
  getManualDefects: state.getManualDefects,
  reviewManualDefect: state.reviewManualDefect,
}))
vi.mock('ant-design-vue', () => ({
  message: { success: state.success, warning: state.warning },
}))

const item: ManualDefectReviewItem = {
  id: 'defect-running',
  institute_id: 'H1',
  patient_id: 'P1',
  visit_id: 'V1',
  task_id: 'task-1',
  task_record_id: 'record-1',
  run_number: 1,
  rule_code: 'LX0609-001',
  rule_name: '运行病历人工缺陷',
  description: '缺陷描述',
  severity: 'warning',
  location: null,
  suggestion: null,
  manual_review_status: 'pending',
  manual_created_by: 'creator-1',
  created_at: '2026-09-28T01:00:00Z',
}

function page(scene: ManualDefectReviewScene, nextItem: ManualDefectReviewItem = item): ManualDefectReviewPage {
  return { items: [nextItem], total: 1, page: 1, page_size: 20, scene }
}

const slot = { template: '<div><slot /><slot name="action" /></div>' }
const stubs = {
  'a-page-header': slot,
  'a-card': slot,
  'a-radio-group': slot,
  'a-radio-button': slot,
  'a-select': slot,
  'a-select-option': slot,
  'a-result': { props: ['title', 'subTitle'], template: '<div>{{ title }}{{ subTitle }}</div>' },
  'a-alert': { props: ['message'], template: '<div>{{ message }}<slot name="action" /></div>' },
  'a-empty': { props: ['description'], template: '<div>{{ description }}</div>' },
  'a-tag': slot,
  'a-button': { emits: ['click'], template: '<button @click="$emit(\'click\')"><slot /></button>' },
  'a-pagination': slot,
  'a-modal': { props: ['open'], template: '<div v-if="open"><slot /></div>' },
  'a-textarea': { template: '<textarea />' },
}

async function flush() {
  await Promise.resolve()
  await nextTick()
  await Promise.resolve()
  await nextTick()
}

const mounted: Array<ReturnType<typeof mount>> = []
function render() {
  const wrapper = mount(ManualDefectReviewView, { global: { stubs } })
  mounted.push(wrapper)
  return wrapper
}

describe('ManualDefectReviewView scene contract', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    Object.keys(route.query).forEach((key) => delete route.query[key])
    state.getManualDefects.mockResolvedValue({ success: true, data: page('all') })
    state.reviewManualDefect.mockResolvedValue({
      success: true,
      data: { id: item.id, manual_review_status: 'approved' },
    })
  })

  afterEach(() => {
    mounted.splice(0).forEach((wrapper) => wrapper.unmount())
  })

  it('uses all for a legacy link without scene', async () => {
    const wrapper = render()
    await flush()

    expect(state.getManualDefects).toHaveBeenCalledWith('pending', 1, 20, 'all')
    expect(wrapper.text()).toContain('运行病历人工缺陷')
  })

  it('keeps scene through paging and resets paging when scene changes', async () => {
    route.query.scene = 'running'
    state.getManualDefects.mockResolvedValue({ success: true, data: page('running') })
    const wrapper = render()
    await flush()
    const vm = wrapper.vm as unknown as {
      changePage: (value: number) => Promise<void>
      changeScene: (value: unknown) => Promise<void>
    }

    await vm.changePage(3)
    state.getManualDefects.mockResolvedValue({ success: true, data: page('final') })
    await vm.changeScene('final')
    await flush()

    expect(replace).toHaveBeenCalledWith({ query: { scene: 'final' } })
    expect(state.getManualDefects).toHaveBeenLastCalledWith('pending', 1, 20, 'final')
  })

  it('fails closed for an unknown route scene without requesting all', async () => {
    route.query.scene = 'unexpected'
    const wrapper = render()
    await flush()

    expect(state.getManualDefects).not.toHaveBeenCalled()
    expect(wrapper.get('[data-testid="manual-defect-review-error"]').text()).toContain('场景参数无效')
    expect(wrapper.findAll('[data-testid="manual-defect-review-item"]')).toHaveLength(0)
  })

  it('ignores a late response from the previous scene', async () => {
    route.query.scene = 'running'
    let resolveRunning: ((value: unknown) => void) | undefined
    state.getManualDefects
      .mockImplementationOnce(() => new Promise((resolve) => { resolveRunning = resolve }))
      .mockResolvedValueOnce({
        success: true,
        data: page('final', { ...item, id: 'defect-final', rule_name: '终末病历人工缺陷' }),
      })
    const wrapper = render()
    const vm = wrapper.vm as unknown as { changeScene: (value: unknown) => Promise<void> }

    await vm.changeScene('final')
    await flush()
    resolveRunning?.({ success: true, data: page('running') })
    await flush()

    expect(wrapper.text()).toContain('终末病历人工缺陷')
    expect(wrapper.text()).not.toContain('运行病历人工缺陷')
  })

  it('refreshes the same scene after review succeeds', async () => {
    route.query.scene = 'outpatient_emergency'
    const outpatientItem = { ...item, id: 'defect-outpatient', rule_name: '门急诊人工缺陷' }
    state.getManualDefects.mockResolvedValue({
      success: true,
      data: page('outpatient_emergency', outpatientItem),
    })
    state.reviewManualDefect.mockResolvedValue({
      success: true,
      data: { id: outpatientItem.id, manual_review_status: 'approved' },
    })
    const wrapper = render()
    await flush()
    const vm = wrapper.vm as unknown as {
      openReview: (target: ManualDefectReviewItem, decision: 'approved') => void
      submitReview: () => Promise<void>
    }

    vm.openReview(outpatientItem, 'approved')
    await vm.submitReview()
    await flush()

    expect(state.getManualDefects).toHaveBeenLastCalledWith('pending', 1, 20, 'outpatient_emergency')
  })

  it('rejects a response whose echoed scene does not match the request', async () => {
    route.query.scene = 'running'
    state.getManualDefects.mockResolvedValue({ success: true, data: page('final') })
    const wrapper = render()
    await flush()

    expect(wrapper.get('[data-testid="manual-defect-review-error"]').text()).toContain('读取人工缺陷失败')
    expect(wrapper.findAll('[data-testid="manual-defect-review-item"]')).toHaveLength(0)
  })
})
