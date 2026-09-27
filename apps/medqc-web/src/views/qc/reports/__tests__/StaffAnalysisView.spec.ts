import { mount } from '@vue/test-utils'
import { nextTick, reactive } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import StaffAnalysisView from '@/views/qc/reports/StaffAnalysisView.vue'

const getReport = vi.hoisted(() => vi.fn())
const route = reactive({ path: '/dashboard/qc/reports/staff-analysis', query: { scene: 'all' } })
const replace = vi.fn(async ({ query }: { query: { scene: string } }) => {
  route.query.scene = query.scene
})
vi.mock('vue-router', () => ({ useRoute: () => route, useRouter: () => ({ replace }) }))
vi.mock('@/api/staffAnalysis', () => ({ getStaffAnalysis: getReport }))

const allReport = {
  period: 'this_month',
  period_label: '本月',
  range: { start: '2026-09-01T00:00:00Z', end: '2026-09-27T00:00:00Z' },
  scene: 'all',
  unavailable_reason: null,
  summary: {
    active_staff_count: 2,
    record_reviewer_count: 2,
    record_review_count: 4,
    reviewed_case_count: 2,
    initial_count: 3,
    recheck_count: 1,
    avg_record_reviews_per_active_staff: 2,
    avg_reviewed_cases_per_reviewer: 1.5,
    manual_defect_created_count: 1,
    manual_review_approved_count: 1,
    manual_review_rejected_count: 0,
    appeal_approved_count: 0,
    appeal_rejected_count: 1,
  },
  staff: [
    {
      user_id: 'staff-1', name: '张质控', rank: 1,
      record_review_count: 3, reviewed_case_count: 2,
      initial_count: 2, recheck_count: 1,
      manual_defect_created_count: 1, manual_review_approved_count: 1,
      manual_review_rejected_count: 0, appeal_approved_count: 0, appeal_rejected_count: 1,
    },
  ],
}

async function flush() {
  await Promise.resolve()
  await nextTick()
  await Promise.resolve()
  await nextTick()
}
const mounted: Array<ReturnType<typeof mount>> = []
function render() {
  const wrapper = mount(StaffAnalysisView)
  mounted.push(wrapper)
  return wrapper
}

describe('StaffAnalysisView', () => {
  beforeEach(() => {
    getReport.mockReset()
    replace.mockClear()
    route.query.scene = 'all'
    getReport.mockResolvedValue({ success: true, data: allReport })
  })
  afterEach(() => {
    mounted.splice(0).forEach((wrapper) => wrapper.unmount())
  })

  it('shows distinct cases and action counts without presenting decisions as cases', async () => {
    const wrapper = render()
    await flush()
    expect(wrapper.text()).toContain('审核病历')
    expect(wrapper.text()).toContain('全局三坐标去重')
    expect(wrapper.text()).toContain('审核次数')
    expect(wrapper.text()).toContain('张质控')
    expect(wrapper.text()).toContain('北京时间')
    expect(wrapper.findAll('tbody tr')).toHaveLength(1)
  })

  it('shows the scene attribution blocker and no guessed staff figures', async () => {
    route.query.scene = 'final'
    getReport.mockResolvedValue({
      success: true,
      data: { ...allReport, scene: 'final', summary: null, staff: null, unavailable_reason: 'scene_not_attributable' },
    })
    const wrapper = render()
    await flush()
    expect(wrapper.get('[data-testid="staff-unavailable"]').text()).toContain('不能可靠区分运行与终末场景')
    expect(wrapper.findAll('tbody tr')).toHaveLength(0)
    expect(wrapper.findAll('.metric')).toHaveLength(0)
  })

  it('ignores stale results after changing period', async () => {
    let resolveOld: ((value: unknown) => void) | undefined
    getReport.mockImplementationOnce(() => new Promise((resolve) => { resolveOld = resolve }))
      .mockResolvedValueOnce({ success: false, message: '读取失败' })
    const wrapper = render()
    await wrapper.findAll('.segmented')[0]!.findAll('button')[0]!.trigger('click')
    await flush()
    expect(getReport).toHaveBeenCalledTimes(2)
    resolveOld?.({ success: true, data: allReport })
    await flush()
    expect(wrapper.get('[data-testid="staff-error"]').text()).toContain('读取失败')
    expect(wrapper.findAll('tbody tr')).toHaveLength(0)
  })
})
