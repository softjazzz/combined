import { flushPromises, mount } from '@vue/test-utils'
import { reactive, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import CoreSystemReportPanel from '@/views/qc/reports/CoreSystemReportPanel.vue'
import type { CoreSystemReport } from '@/api/coreSystemReports'

const api = vi.hoisted(() => ({
  getCoreSystemReport: vi.fn(),
  exportCoreSystemReport: vi.fn(),
}))
const auth = reactive({ user: { id: 'sync-admin' } })

vi.mock('@/api/coreSystemReports', () => ({
  getCoreSystemReport: api.getCoreSystemReport,
  exportCoreSystemReport: api.exportCoreSystemReport,
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => auth }))
vi.mock('@/composables/useQcResultVisibility', () => ({
  useQcResultVisibility: () => ({ confirmedResultsOnly: ref(false) }),
}))

const sampleReport: CoreSystemReport = {
  scene: 'running',
  scope: { scope_label: '当前在院病历', scope_basis: 'inpatient_with_qc_result', archive_status: null },
  contract: '测试口径',
  as_of: '2026-10-01T02:00:00Z',
  reference: { title: '医疗质量安全核心制度要点', reference_note: '参考说明', source_url: 'https://example.invalid', reference_date: '2018-04-18', systems: [] },
  systems: [
    {
      id: 'CORE-01',
      name: '首诊负责制度',
      record_count: 2,
      problem_records: 1,
      defect_total: 1,
      problem_rate: 0.5,
      points: [],
    },
  ],
  top_systems: [{ id: 'CORE-01', name: '首诊负责制度', defect_total: 1 }],
  summary: {
    candidate_records: 3,
    unknown_records: 1,
    unavailable_records: 1,
    unknown_points: 1,
    unknown_defects: 0,
  },
  items: [],
  total: 0,
  page: 1,
  page_size: 20,
}

describe('CoreSystemReportPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.getCoreSystemReport.mockResolvedValue(sampleReport)
  })

  it('先按仅问题病例下钻某制度后，再点击结果不可用/未知覆盖会重置 problems_only 为 false', async () => {
    const wrapper = mount(CoreSystemReportPanel, {
      global: {
        stubs: {
          MqIcon: true,
          'a-drawer': { props: ['open'], template: '<div v-if="open"><slot /></div>' },
        },
      },
    })
    await flushPromises()

    // 点击 Top20 制度芯片，开启 problems_only = true
    await wrapper.get('[data-testid="core-defect-top"] button').trigger('click')
    await flushPromises()
    expect(api.getCoreSystemReport.mock.lastCall?.[0]).toMatchObject({
      system_id: 'CORE-01',
      problems_only: true,
    })

    // 再点击「结果不可用 / 未知覆盖」，必须重置 problems_only = false
    const unavailableBtn = wrapper
      .findAll('button')
      .find((btn) => btn.text().includes('结果不可用'))
    expect(unavailableBtn).toBeTruthy()
    await unavailableBtn!.trigger('click')
    await flushPromises()
    expect(api.getCoreSystemReport.mock.lastCall?.[0]).toMatchObject({
      system_id: 'unknown',
      problems_only: false,
    })
    wrapper.unmount()
  })
})
