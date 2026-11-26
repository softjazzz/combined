import { flushPromises, mount } from '@vue/test-utils'
import { AxiosError, AxiosHeaders, type AxiosResponse } from 'axios'
import { reactive } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiService } from '@/services/apiService'
import {
  clinicalSourceForRequest,
  resetClinicalSourceMode,
  setClinicalSourceMode,
} from '@/utils/clinical-source'
import {
  exportRecordQualityReport,
  exportRecordRemediationAnalysis,
  getRecordQualityRecords,
  getRecordQualityReport,
  getRecordRemediationAnalysis,
} from '@/api/qualityReports'
import {
  exportFrontpageQualityReport,
  getFrontpageQualityRecords,
  getFrontpageQualityReport,
} from '@/api/frontpageQualityReport'
import {
  SPECIAL_RECORD_TYPES,
  exportSpecialRecordReport,
  getSpecialRecordReport,
  getSpecialReportDefects,
  getSpecialReportRecords,
  getSpecialSourceConfig,
  saveSpecialSourceConfig,
} from '@/api/specialRecordReports'
import {
  exportStaffAnalysis,
  getStaffAnalysis,
  getStaffAnalysisDetails,
} from '@/api/staffAnalysis'
import { exportCoreSystemReport, getCoreSystemReport } from '@/api/coreSystemReports'
import { exportManualQualityReport, getManualQualityReport } from '@/api/manualQualityReport'
import RecordQualityReportView from '@/views/qc/reports/RecordQualityReportView.vue'
import FrontpageQualityReportView from '@/views/qc/reports/FrontpageQualityReportView.vue'
import SpecialRecordReportView from '@/views/qc/reports/SpecialRecordReportView.vue'
import StaffAnalysisView from '@/views/qc/reports/StaffAnalysisView.vue'
import CoreSystemReportPanel from '@/views/qc/reports/CoreSystemReportPanel.vue'
import ManualQualityReportPanel from '@/views/qc/reports/ManualQualityReportPanel.vue'
import RecordRemediationAnalysisPanel from '@/views/qc/reports/RecordRemediationAnalysisPanel.vue'

const routeState = reactive({
  path: '/dashboard/qc/reports/test',
  query: {} as Record<string, string>,
})
const routerReplace = vi.fn(async (loc: { path?: string; query?: Record<string, string> }) => {
  routeState.query = { ...(loc.query || {}) }
})
const routerPush = vi.fn(async (loc: { path?: string; query?: Record<string, string> }) => {
  routeState.query = { ...(loc.query || {}) }
})

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({ replace: routerReplace, push: routerPush }),
}))

const authUser = reactive<{
  id: string
  institute_id: string
  department: string
  roles: string[]
  is_demo_account: boolean
}>({
  id: 'u-1',
  institute_id: 'H1',
  department: '内科',
  roles: ['qc_manager'],
  is_demo_account: false,
})

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    get user() {
      return authUser.id ? authUser : null
    },
    get userRoles() {
      return authUser.roles
    },
    hasRole(role: string) {
      return authUser.roles.includes(role)
    },
  }),
}))

vi.mock('ant-design-vue', () => ({
  message: { error: vi.fn(), success: vi.fn(), warning: vi.fn() },
  DatePicker: {
    props: ['value'],
    emits: ['update:value'],
    template:
      '<input class="mock-date-picker" :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
  },
}))

function axiosErr(status: number, data: unknown, msg = `Request failed with status code ${status}`) {
  const response = {
    status,
    data,
    statusText: '',
    headers: {},
    config: { headers: new AxiosHeaders() },
  } as AxiosResponse
  return new AxiosError(msg, String(status), undefined, undefined, response)
}

function jsonBlob(payload: unknown): Blob {
  return new Blob([JSON.stringify(payload)], { type: 'application/json' })
}

function okResponse<T>(data: T, headers: Record<string, string> = {}) {
  return {
    status: 200,
    statusText: 'OK',
    data: { success: true, data },
    headers: new AxiosHeaders(headers),
    config: { headers: new AxiosHeaders() },
  } as AxiosResponse
}

const specialTypesPayload = SPECIAL_RECORD_TYPES.map((key) => ({
  key,
  label: key,
  count: null as number | null,
  known_positive_total: 2,
  unknown_total: 3,
  status: 'partial' as const,
}))

const specialReportData = {
  scope: {
    institute_id: 'H1',
    discharged_from: '2026-10-01',
    discharged_to: '2026-10-30',
    record_type: 'death' as const,
    record_type_state: 'positive' as const,
    timezone: 'Asia/Shanghai' as const,
    archive_status: 'unverified' as const,
    result_source: 'frozen',
    classification_version_seq: 1,
  },
  summary: {
    cohort_total: 10,
    record_total: 4,
    unavailable_result_total: 2,
    unknown_type_total: 3,
    graded_total: 2,
    ungraded_total: 2,
    grade_ratio_denominator: 'graded_total' as const,
    known_result_total: 2,
    selected_unavailable_result_total: 1,
    defect_ratio_denominator: 'confirmed_auto_defect_total' as const,
  },
  types: specialTypesPayload,
  top_departments: [{ name: '内科', count: 2 }],
  grade_distribution: [{ grade: '甲级', count: 2, ratio: 1 }],
  top_defects: [],
  score_standard: {
    status: 'configured' as const,
    standard_id: 'STD-1',
    standard_version_seq: 1,
    binding_version_seq: 1,
    standard_name: '专用标准',
  },
}

const coreSystemsPayload = Array.from({ length: 18 }, (_, index) => ({
  id: `CORE-${String(index + 1).padStart(2, '0')}`,
  name: `核心制度${index + 1}`,
  record_count: index === 0 ? 2 : null,
  problem_records: index === 0 ? 1 : null,
  problem_rate: index === 0 ? 0.5 : null,
  defect_total: index === 0 ? 1 : null,
  points: [],
}))

const coreReportData = {
  as_of: '2026-10-01T00:00:00Z',
  scene: 'running' as const,
  contract: '已配置质控点范围的问题率',
  scope: { scope_label: '当前在院病历', scope_basis: 'inpatient_with_qc_result', archive_status: null },
  summary: {
    candidate_records: 5,
    unknown_records: 2,
    unavailable_records: 1,
    unknown_points: 3,
    unknown_defects: 4,
  },
  systems: coreSystemsPayload,
  reference: {
    title: '医疗质量安全核心制度要点',
    reference_date: '2018-04-18',
    source_url: 'https://www.nhc.gov.cn/reference',
    reference_note: '2018版参考',
    systems: coreSystemsPayload.map((s) => ({ ...s, text: '制度原文内容' })),
  },
  top_systems: [{ id: 'CORE-01', name: '核心制度1', defect_total: 1 }],
  items: [
    {
      institute_id: 'H1',
      patient_id: 'P1',
      visit_id: 'V1',
      patient_name: '确诊患者',
      department: '内科',
      doctor: '张医生',
      completed_at: '2026-10-01T00:00:00Z',
      root_job_id: 'J1',
      envelope_id: 'E1',
      rule_set_key: 'rs',
      rule_set_version: 'v1',
      coverage: 'known' as const,
      points: [
        {
          rule_id: 'R-CONFIRMED',
          rule_name: '确认缺陷规则',
          status: 'non_compliant',
          is_confirmed_issue: true,
          system_ids: ['CORE-01'],
        },
        {
          rule_id: 'R-GAP',
          rule_name: '数据缺失规则',
          status: 'data_gap',
          is_confirmed_issue: false,
          system_ids: null,
        },
      ],
    },
    {
      institute_id: 'H1',
      patient_id: 'P2',
      visit_id: 'V2',
      patient_name: '不可用患者',
      department: '内科',
      doctor: '李医生',
      completed_at: '2026-10-01T00:00:00Z',
      root_job_id: null,
      envelope_id: null,
      rule_set_key: null,
      rule_set_version: null,
      coverage: 'unavailable' as const,
      points: [],
    },
  ],
  total: 2,
  page: 1,
  page_size: 20,
}

const manualReportData = {
  as_of: '2026-10-01T00:00:00Z',
  timezone: 'Asia/Shanghai',
  assumption: '已确认统计口径',
  filters: { start_date: '2026-10-01', end_date: '2026-10-10', scene: 'all' as const },
  summary: {
    entered: 2,
    review: { pending: 1, approved: 0, rejected: 0, unknown: 1 },
    rectification: { pending: 1, submitted: 0, approved: 0, rejected: 0, unassigned: 0, unknown: 1 },
  },
  filter_options: {
    institutes: ['H1'],
    departments: [{ institute_id: 'H1', department: '内科' }],
    creators: [{ id: 'u1', name: '张质控' }],
    tasks: [{ id: 'T1', name: '抽检任务1' }],
  },
  items: [
    {
      id: 'D1',
      institute_id: 'H1',
      patient_id: 'P1',
      visit_id: 'V1',
      department: '内科',
      creator_id: 'u1',
      creator_name: '张质控',
      scene: 'running',
      task_id: 'T1',
      task_name: '抽检任务1',
      task_record_id: 'TR1',
      run_number: 1,
      rule_name: '确定人工缺陷',
      created_at: '2026-10-01T01:30:00Z',
      review_status: 'pending',
      rectification_status: 'pending',
      source_verified: true,
      root_job_id: 'J1',
      envelope_id: 'E1',
    },
    {
      id: 'D2',
      institute_id: 'H1',
      patient_id: 'P2',
      visit_id: 'V2',
      department: '内科',
      creator_id: 'u1',
      creator_name: '李质控',
      scene: 'running',
      task_id: 'T1',
      task_name: '抽检任务1',
      task_record_id: 'TR2',
      run_number: 1,
      rule_name: '未知状态缺陷',
      created_at: '2026-10-01T02:30:00Z',
      review_status: 'unknown',
      rectification_status: 'unknown',
      source_verified: false,
      root_job_id: null,
      envelope_id: null,
    },
  ],
  total: 2,
  page: 1,
  page_size: 20,
}

beforeEach(() => {
  vi.restoreAllMocks()
  vi.clearAllMocks()
  resetClinicalSourceMode()
  routeState.path = '/dashboard/qc/reports/test'
  routeState.query = {}
  authUser.id = 'u-1'
  authUser.institute_id = 'H1'
  authUser.department = '内科'
  authUser.roles = ['qc_manager']
  authUser.is_demo_account = false
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('T1-B3 1. 临床源白名单对齐 (clinical-source.ts)', () => {
  it.each([
    '/api/v1/core-system-reports',
    '/api/v1/core-system-reports/export?scene=running',
    '/api/v1/custom-qc/workspace',
    '/api/v1/custom-qc/workspace/drafts',
  ])('白名单路径 %s 遵循 fixed_donghua_cdm 回退与 legacy_compat 透传语义', (url) => {
    window.history.replaceState({}, '', '/workstation-v5/reports')
    expect(clinicalSourceForRequest(url)).toBeUndefined()

    window.history.replaceState({}, '', '/workstation-v5/reports?source_id=independent_cdm')
    expect(clinicalSourceForRequest(url)).toBe('independent_cdm')

    setClinicalSourceMode('legacy_compat', 'legacy_pg')
    window.history.replaceState({}, '', '/workstation-v5/reports?source_id=legacy_pg')
    expect(clinicalSourceForRequest(url)).toBe('legacy_pg')
  })
})

describe('T1-B3 2. 6 个报表 API Client (signal, skipErrorToast, 60s/120s timeout, Blob JSON 错误解析)', () => {
  it('qualityReports.ts 透传 signal/skipErrorToast/超时并解析导出 Blob 中文错误', async () => {
    const controller = new AbortController()
    const reqSpy = vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(okResponse({}))
    await getRecordQualityReport({ scene: 'running' }, controller.signal)
    await getRecordQualityRecords({ scene: 'running' }, controller.signal)
    await getRecordRemediationAnalysis({ scene: 'running' }, controller.signal)
    for (const call of reqSpy.mock.calls) {
      expect(call[0]).toMatchObject({
        skipErrorToast: true,
        timeout: 60_000,
        signal: controller.signal,
      })
    }

    const getSpy = vi.spyOn(ApiService, 'getRaw').mockRejectedValue(
      axiosErr(422, jsonBlob({ detail: { code: 'range_too_large', message: '导出范围不能超过90天' } })),
    )
    const exp1 = await exportRecordQualityReport({ scene: 'running' }, 'records', undefined, controller.signal)
    const exp2 = await exportRecordRemediationAnalysis({ scene: 'running' }, controller.signal)
    expect(exp1).toMatchObject({
      success: false,
      status: 422,
      code: 'range_too_large',
      message: '导出范围不能超过90天',
    })
    expect(exp2).toMatchObject({
      success: false,
      status: 422,
      code: 'range_too_large',
      message: '导出范围不能超过90天',
    })
    for (const call of getSpy.mock.calls) {
      expect(call[2]).toMatchObject({
        responseType: 'blob',
        skipErrorToast: true,
        timeout: 120_000,
        signal: controller.signal,
      })
    }
  })

  it('frontpageQualityReport.ts 透传 signal/skipErrorToast/超时并解析导出 Blob 中文错误', async () => {
    const controller = new AbortController()
    const reqSpy = vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(okResponse({}))
    await getFrontpageQualityReport({}, controller.signal)
    await getFrontpageQualityRecords({}, controller.signal)
    expect(reqSpy.mock.calls[0]?.[0]).toMatchObject({
      skipErrorToast: true,
      timeout: 60_000,
      signal: controller.signal,
    })

    const getSpy = vi.spyOn(ApiService, 'getRaw').mockRejectedValue(
      axiosErr(422, jsonBlob({ detail: '首页导出条数超过上限' })),
    )
    const res = await exportFrontpageQualityReport({}, 'departments', controller.signal)
    expect(res).toMatchObject({ success: false, status: 422, message: '首页导出条数超过上限' })
    expect(getSpy.mock.calls[0]?.[2]).toMatchObject({
      responseType: 'blob',
      skipErrorToast: true,
      timeout: 120_000,
      signal: controller.signal,
    })
  })

  it('specialRecordReports.ts 透传 signal/skipErrorToast/超时并解析导出 Blob 中文错误', async () => {
    const controller = new AbortController()
    const filters = {
      institute_id: 'H1',
      discharged_from: '2026-10-01',
      discharged_to: '2026-10-30',
      record_type: 'death' as const,
      record_type_state: 'positive' as const,
    }
    const reqSpy = vi
      .spyOn(ApiService, 'requestRaw')
      .mockResolvedValueOnce(okResponse(specialReportData))
      .mockResolvedValueOnce(
        okResponse({
          total: 0,
          page: 1,
          page_size: 20,
          items: [],
          scope: specialReportData.scope,
          score_standard: specialReportData.score_standard,
        }),
      )
      .mockResolvedValueOnce(
        okResponse({
          total: 0,
          page: 1,
          page_size: 20,
          items: [],
          scope: specialReportData.scope,
          score_standard: specialReportData.score_standard,
        }),
      )
      .mockResolvedValueOnce(
        okResponse({
          institute_id: 'H1',
          version_seq: 1,
          config: {
            critical: { positive_codes: [], negative_codes: [] },
            difficult: { positive_codes: [], negative_codes: [] },
            surgery_level_codes: { '1': [], '2': [], '3': [], '4': [] },
          },
          sources: [],
        }),
      )
      .mockResolvedValueOnce(
        okResponse({
          institute_id: 'H1',
          version_seq: 2,
          config: {
            critical: { positive_codes: [], negative_codes: [] },
            difficult: { positive_codes: [], negative_codes: [] },
            surgery_level_codes: { '1': [], '2': [], '3': [], '4': [] },
          },
          sources: [],
        }),
      )
      .mockRejectedValueOnce(axiosErr(422, jsonBlob({ detail: '特殊病历导出窗口过长' })))

    await getSpecialRecordReport(filters, controller.signal)
    await getSpecialReportRecords(filters, 1, controller.signal)
    await getSpecialReportDefects(filters, 1, controller.signal)
    await getSpecialSourceConfig('H1', controller.signal)
    await saveSpecialSourceConfig(
      'H1',
      1,
      {
        critical: { positive_codes: [], negative_codes: [] },
        difficult: { positive_codes: [], negative_codes: [] },
        surgery_level_codes: { '1': [], '2': [], '3': [], '4': [] },
      },
      controller.signal,
    )
    for (let i = 0; i < 5; i++) {
      expect(reqSpy.mock.calls[i]?.[0]).toMatchObject({
        skipErrorToast: true,
        timeout: 60_000,
        signal: controller.signal,
      })
    }

    await expect(
      exportSpecialRecordReport(filters, 'summary', undefined, controller.signal),
    ).rejects.toThrow('特殊病历导出窗口过长')
    expect(reqSpy.mock.calls[5]?.[0]).toMatchObject({
      responseType: 'blob',
      skipErrorToast: true,
      timeout: 120_000,
      signal: controller.signal,
    })
  })

  it('staffAnalysis.ts 透传 signal/skipErrorToast/超时并解析导出 Blob 中文错误', async () => {
    const controller = new AbortController()
    const reqSpy = vi
      .spyOn(ApiService, 'requestRaw')
      .mockResolvedValueOnce(okResponse({}))
      .mockResolvedValueOnce(okResponse({}))
      .mockRejectedValueOnce(axiosErr(422, jsonBlob({ error: { message: '质控员导出权限不足' } })))

    await getStaffAnalysis({ period: 'this_month', scene: 'all' }, undefined, controller.signal)
    await getStaffAnalysisDetails(
      'u1',
      { period: 'this_month', scene: 'all' },
      'record_review_count',
      1,
      20,
      controller.signal,
    )
    expect(reqSpy.mock.calls[0]?.[0]).toMatchObject({
      skipErrorToast: true,
      timeout: 60_000,
      signal: controller.signal,
    })
    expect(reqSpy.mock.calls[1]?.[0]).toMatchObject({
      skipErrorToast: true,
      timeout: 60_000,
      signal: controller.signal,
    })

    const exp = await exportStaffAnalysis(
      { period: 'this_month', scene: 'all' },
      undefined,
      controller.signal,
    )
    expect(exp).toMatchObject({ success: false, status: 422, message: '质控员导出权限不足' })
    expect(reqSpy.mock.calls[2]?.[0]).toMatchObject({
      responseType: 'blob',
      skipErrorToast: true,
      timeout: 120_000,
      signal: controller.signal,
    })
  })

  it('coreSystemReports.ts 与 manualQualityReport.ts 透传 signal/skipErrorToast/超时并解析 Blob 中文错误', async () => {
    const controller = new AbortController()
    const reqSpy = vi
      .spyOn(ApiService, 'requestRaw')
      .mockResolvedValueOnce(okResponse(coreReportData))
      .mockRejectedValueOnce(axiosErr(422, jsonBlob({ detail: '核心制度导出超出限制' })))
      .mockResolvedValueOnce(okResponse(manualReportData))
      .mockRejectedValueOnce(axiosErr(422, jsonBlob({ message: '人工报表导出失败原因' })))

    await getCoreSystemReport({ scene: 'running' }, 1, controller.signal)
    await expect(exportCoreSystemReport({ scene: 'running' }, controller.signal)).rejects.toThrow(
      '核心制度导出超出限制',
    )
    await getManualQualityReport(
      { start_date: '2026-10-01', end_date: '2026-10-10', scene: 'all' },
      1,
      controller.signal,
    )
    await expect(
      exportManualQualityReport(
        { start_date: '2026-10-01', end_date: '2026-10-10', scene: 'all' },
        controller.signal,
      ),
    ).rejects.toThrow('人工报表导出失败原因')

    expect(reqSpy.mock.calls[0]?.[0]).toMatchObject({
      skipErrorToast: true,
      timeout: 60_000,
      signal: controller.signal,
    })
    expect(reqSpy.mock.calls[1]?.[0]).toMatchObject({
      responseType: 'blob',
      skipErrorToast: true,
      timeout: 120_000,
      signal: controller.signal,
    })
    expect(reqSpy.mock.calls[2]?.[0]).toMatchObject({
      skipErrorToast: true,
      timeout: 60_000,
      signal: controller.signal,
    })
    expect(reqSpy.mock.calls[3]?.[0]).toMatchObject({
      responseType: 'blob',
      skipErrorToast: true,
      timeout: 120_000,
      signal: controller.signal,
    })
  })
})

describe('T1-B3 3-5. 四大报表与 3 子面板演示隔离、super_admin、AbortController、URL 同步与时区修复', () => {
  it('RecordQualityReportView: 演示隔离、+08:00 提交、URL 双向同步与卸载 abort', async () => {
    authUser.is_demo_account = true
    const signals: AbortSignal[] = []
    vi.spyOn(ApiService, 'requestRaw').mockImplementation(async (cfg) => {
      if (cfg.signal) signals.push(cfg.signal as AbortSignal)
      return okResponse({
        scope: { scene: 'running' },
        score_standard: {
          status: 'no_standard',
          standard_id: null,
          standard_name: null,
          standard_updated_at: null,
        },
        source_status: { review: 'unavailable', manual_defect: 'unavailable' },
        kpis: {
          record_total: 10,
          qc_ready_total: 8,
          qc_unavailable_total: 2,
          scored_total: null,
          average_score: null,
          top_grade_rate: null,
          review_approved_total: null,
          auto_defect_total: 3,
          manual_defect_total: null,
          veto_defect_total: null,
        },
        grade_distribution: null,
        score_distribution: null,
        defect_level_distribution: [
          { name: '严重', defect_total: 2 },
          { name: 'data_gap', defect_total: 1 },
        ],
        defect_type_distribution: [
          { name: '内涵', defect_total: 2 },
          { name: 'uncertain', defect_total: 1 },
        ],
        document_distribution: [{ name: '入院记录', defect_total: 2 }],
        top_rules: null,
        top_departments: null,
        top_doctors: null,
        top_documents: null,
        classification_unknown: { defect_category: 2, defect_type: 1 },
        department_rows: [],
        doctor_rows: [],
        unavailable_dimensions: [{ key: 'remediation', label: '整改', reason_code: 'remediation_owner_undefined' }],
      })
    })

    const wrapper = mount(RecordQualityReportView, {
      global: {
        stubs: {
          'a-drawer': true,
          CoreSystemReportPanel: true,
          RecordRemediationAnalysisPanel: true,
        },
      },
    })
    await flushPromises()

    // 演示账号隐藏不可用提示、未知分类、未接入维度与 data_gap/uncertain
    expect(wrapper.text()).not.toContain('质控结果无法读取')
    expect(wrapper.text()).not.toContain('部分来源暂不可用')
    expect(wrapper.text()).not.toContain('暂未接入的维度')
    expect(wrapper.text()).not.toContain('大类未知')
    expect(wrapper.text()).not.toContain('data_gap')
    expect(wrapper.text()).not.toContain('uncertain')

    // datetime-local 规范带 +08:00 且同步至 URL
    await wrapper.get('#report-department').setValue('心内科')
    await wrapper.get('#report-from').setValue('2026-10-01T08:00')
    await wrapper.get('#report-to').setValue('2026-10-02T18:30')
    await wrapper.get('.filters .primary').trigger('click')
    await flushPromises()
    expect(signals[0]?.aborted).toBe(true)
    expect(routerReplace).toHaveBeenCalledWith(
      expect.objectContaining({
        query: expect.objectContaining({
          department: '心内科',
          completed_from: '2026-10-01T08:00:00+08:00',
          completed_to: '2026-10-02T18:30:00+08:00',
        }),
      }),
    )

    // Tab 切换同步 URL
    await wrapper.get('[data-testid="core-tab"]').trigger('click')
    expect(routeState.query.tab).toBe('core')

    // 卸载时中止在途请求
    const latestSignal = signals.at(-1)
    wrapper.unmount()
    expect(latestSignal?.aborted).toBe(true)
  })

  it('FrontpageQualityReportView: 演示隔离、+08:00 提交、URL 双向同步与卸载 abort', async () => {
    authUser.is_demo_account = true
    const signals: AbortSignal[] = []
    const reqSpy = vi.spyOn(ApiService, 'requestRaw').mockImplementation(async (cfg) => {
      if (cfg.signal) signals.push(cfg.signal as AbortSignal)
      return okResponse({
        scope: { sources: ['frontpage_formal_qc', 'coding_qc'] },
        kpis: {
          case_total: 2,
          problem_case_total: 1,
          problem_rate: 0.5,
          frontpage_case_total: 2,
          coding_case_total: 1,
          noncoding_defect_total: 2,
          coding_defect_total: 1,
          noncoding_problem_case_total: 1,
          coding_problem_case_total: 1,
        },
        sources: [
          {
            source_key: 'frontpage_formal_qc',
            label: '非编码（首页质控）',
            severity_distribution: [
              { severity: 'error', defect_total: 1 },
              { severity: 'data_gap', defect_total: 1 },
            ],
            category_distribution: [
              { category: 'required', defect_total: 1 },
              { category: 'uncertain', defect_total: 1 },
            ],
            top_rules: [],
          },
          {
            source_key: 'coding_qc',
            label: '编码（编码质控）',
            severity_distribution: [],
            category_distribution: [],
            top_rules: [],
          },
        ],
        department_rows: [],
      })
    })

    const wrapper = mount(FrontpageQualityReportView, {
      global: { stubs: { 'a-drawer': true } },
    })
    await flushPromises()
    expect(wrapper.text()).not.toContain('data_gap')
    expect(wrapper.text()).not.toContain('uncertain')

    await wrapper.get('#fp-from').setValue('2026-09-01T09:00')
    await wrapper.get('#fp-to').setValue('2026-09-10T10:00')
    await wrapper.get('.filters .primary').trigger('click')
    await flushPromises()
    expect(reqSpy.mock.calls.at(-1)?.[0].params).toMatchObject({
      analyzed_from: '2026-09-01T09:00:00+08:00',
      analyzed_to: '2026-09-10T10:00:00+08:00',
    })
    expect(routeState.query.analyzed_from).toBe('2026-09-01T09:00:00+08:00')

    const codingBtn = wrapper.findAll('.segmented button').find((b) => b.text().startsWith('编码'))
    await codingBtn?.trigger('click')
    expect(routeState.query.source).toBe('coding_qc')

    const lastSignal = signals.at(-1)
    wrapper.unmount()
    expect(lastSignal?.aborted).toBe(true)
  })

  it('SpecialRecordReportView: super_admin 权限、演示隔离、移除 death 回退、上海时区与中文错误提取', async () => {
    authUser.roles = ['super_admin']
    authUser.is_demo_account = false
    const signals: AbortSignal[] = []
    const recordRow = {
      institute_id: 'H1',
      patient_id: 'P1',
      visit_id: 'V1',
      patient_name: '患者甲',
      department: '外科',
      discharged_at: '2026-10-02T01:30:00Z',
      types: Object.fromEntries(
        SPECIAL_RECORD_TYPES.map((key) => [
          key,
          key === 'surgery'
            ? { state: 'positive', reason_code: null }
            : { state: 'unknown', reason_code: 'missing' },
        ]),
      ),
      report_score_status: 'scored' as const,
      report_score: 95,
      report_grade: '甲级',
      reason_code: 'detail_diag',
      standard_id: 'STD-1',
      standard_version_seq: 1,
      binding_version_seq: 1,
      historical_score: 90,
      historical_grade: '甲级',
      result_anchor: 'A1',
    }
    vi.spyOn(ApiService, 'requestRaw').mockImplementation(async (cfg) => {
      if (cfg.signal) signals.push(cfg.signal as AbortSignal)
      if (String(cfg.url).endsWith('/records')) {
        return okResponse({
          total: 1,
          page: 1,
          page_size: 20,
          items: [recordRow],
          scope: specialReportData.scope,
          score_standard: specialReportData.score_standard,
        })
      }
      if (String(cfg.url).endsWith('/defects')) {
        return okResponse({
          total: 0,
          page: 1,
          page_size: 20,
          items: [],
          scope: specialReportData.scope,
          score_standard: specialReportData.score_standard,
        })
      }
      return okResponse(specialReportData)
    })

    const wrapper = mount(SpecialRecordReportView, {
      global: {
        stubs: {
          SpecialReportConfigDrawer: { template: '<div />' },
          SpecialReportCharts: { template: '<div />' },
          'a-select': {
            props: ['value', 'options'],
            emits: ['update:value'],
            template:
              '<select :value="value ?? \'\'" @change="$emit(\'update:value\', $event.target.value)"><option value="">全部</option><option v-for="o in options" :key="o.value" :value="o.value">{{ o.label }}</option></select>',
          },
        },
      },
    })
    try {
      await flushPromises()
      // super_admin 可见机构代码配置
      expect(wrapper.text()).toContain('机构代码配置')
      // ISO 出院时间格式化为东八区上海时间
      expect(wrapper.text()).toContain('2026-10-02 09:30:00')

      // record_type 为空时不硬回退 death，而是展示实际命中的类型“手术”
      await wrapper.get('#sr-type').setValue('')
      await wrapper.get('form').trigger('submit')
      await flushPromises()
      expect(wrapper.text()).toContain('手术')
      expect(wrapper.text()).not.toContain('未知（missing）')

      // 切换为演示账号：隐藏范围内结果不可用、未知按钮、标准版本
      authUser.roles = ['qc_staff']
      authUser.is_demo_account = true
      await flushPromises()
      expect(wrapper.text()).not.toContain('范围内结果不可用')
      expect(wrapper.text()).not.toContain('标准版本')
      expect(wrapper.text()).not.toContain('缺失来源单列未知')

      // 英文 AxiosError 转为后端中文错误原因
      vi.spyOn(ApiService, 'requestRaw').mockRejectedValueOnce(
        axiosErr(422, { detail: '特殊病历查询时间跨度超出90天' }),
      )
      await wrapper.find('button[title="刷新报表"]').trigger('click')
      await flushPromises()
      expect(wrapper.text()).toContain('特殊病历查询时间跨度超出90天')
      expect(wrapper.text()).not.toContain('Request failed with status code 422')

      const lastSig = signals.at(-1)
      wrapper.unmount()
      expect(lastSig?.aborted).toBe(true)
    } finally {
      wrapper.unmount()
    }
  })

  it('StaffAnalysisView: super_admin 权限、演示隔离、URL 双向同步与卸载 abort', async () => {
    authUser.roles = ['super_admin']
    authUser.is_demo_account = false
    const signals: AbortSignal[] = []
    vi.spyOn(ApiService, 'requestRaw').mockImplementation(async (cfg) => {
      if (cfg.signal) signals.push(cfg.signal as AbortSignal)
      return okResponse({
        period: 'this_month',
        period_label: '本月',
        range: { start: '2026-09-01T00:00:00Z', end: '2026-09-28T00:00:00Z' },
        scene: 'all',
        filters: {
          period: 'this_month',
          scene: 'all',
          institute_id: null,
          department: null,
          task_id: null,
          start_date: null,
          end_date: null,
          as_of: '2026-09-28T23:59:59+08:00',
        },
        filter_options: { departments: [], tasks: [] },
        filter_options_unavailable_reason: 'task_source_unavailable',
        context_unavailable_count: 3,
        defect_snapshot_coverage: {
          initial_review_count: 2,
          covered_initial_review_count: 1,
          missing_initial_review_count: 1,
          known_defect_count: 5,
        },
        unavailable_reason: null,
        unavailable_metrics: {},
        summary: {
          active_staff_count: 1,
          record_reviewer_count: 1,
          record_review_count: 2,
          reviewed_case_count: 1,
          rechecked_case_count: 0,
          initial_count: 2,
          recheck_count: 0,
          avg_record_reviews_per_active_staff: 2,
          avg_reviewed_cases_per_reviewer: 1,
          avg_reviewed_cases_per_active_staff: 1,
          avg_rechecked_cases_per_active_staff: 0,
          avg_manual_defects_per_active_staff: 0,
          avg_rejected_defects_per_active_staff: 0,
          manual_defect_created_count: 0,
          manual_review_approved_count: 0,
          manual_review_rejected_count: 0,
          appeal_approved_count: 0,
          appeal_rejected_count: 0,
          urged_defect_count: 0,
          confirmed_defect_count: null,
        },
        staff: [],
      })
    })

    const wrapper = mount(StaffAnalysisView, {
      global: {
        stubs: {
          ManualQualityReportPanel: true,
          ModernAppealWorkflowDrawer: true,
          RecordReviewWorkflowDrawer: true,
          'a-drawer': true,
        },
      },
    })
    await flushPromises()
    // super_admin 同时具备病历审核和申诉处理权限
    expect(wrapper.text()).toContain('病历审核')
    expect(wrapper.text()).toContain('申诉处理')

    // URL 同步 Tab 与排名指标
    await wrapper.get('[data-testid="staff-rank-metric"]').setValue('urged_defect_count')
    await flushPromises()
    expect(routeState.query.rank_metric).toBe('urged_defect_count')
    await wrapper.get('[data-testid="staff-report-tab-manual"]').trigger('click')
    expect(routeState.query.tab).toBe('manual')

    // 切换演示账号隐藏非确定排障提示
    authUser.roles = ['qc_staff']
    authUser.is_demo_account = true
    await flushPromises()
    expect(wrapper.find('[data-testid="staff-defect-snapshot-coverage"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="staff-context-unavailable"]').exists()).toBe(false)
    expect(wrapper.find('.filter-hint').exists()).toBe(false)

    const lastSig = signals.at(-1)
    wrapper.unmount()
    expect(lastSig?.aborted).toBe(true)
  })

  it('CoreSystemReportPanel: 固定 18 项下拉不清空、演示隔离、中文错误提取与 abort', async () => {
    authUser.is_demo_account = true
    let resolvePending!: (v: AxiosResponse) => void
    const signals: AbortSignal[] = []
    vi.spyOn(ApiService, 'requestRaw').mockImplementation((cfg) => {
      if (cfg.signal) signals.push(cfg.signal as AbortSignal)
      return new Promise<AxiosResponse>((resolve) => {
        resolvePending = resolve
      })
    })

    const wrapper = mount(CoreSystemReportPanel, {
      global: {
        stubs: { 'a-drawer': { props: ['open'], template: '<div v-if="open"><slot /></div>' } },
      },
    })
    await flushPromises()
    // 请求在途（report === null）时下拉仍固定保留 18 项核心制度，且演示账号不含“未知覆盖”
    const systemSelectOptions = wrapper
      .findAll('select')[1]
      .findAll('option')
      .map((o) => o.attributes('value'))
    expect(systemSelectOptions).toContain('CORE-01')
    expect(systemSelectOptions).toContain('CORE-18')
    expect(systemSelectOptions).not.toContain('unknown')

    resolvePending(okResponse(coreReportData))
    await flushPromises()
    // 演示账号隐藏不可用卡片、不可用病例与 data_gap 质控点
    expect(wrapper.text()).not.toContain('结果不可用')
    expect(wrapper.text()).not.toContain('不可用患者')
    expect(wrapper.text()).toContain('确诊患者')
    await wrapper.findAll('button').find((b) => b.text() === '详情')!.trigger('click')
    expect(wrapper.text()).toContain('确认缺陷规则')
    expect(wrapper.text()).not.toContain('数据缺失规则')

    // AxiosError 提取中文错误
    vi.spyOn(ApiService, 'requestRaw').mockRejectedValueOnce(
      axiosErr(422, { detail: '核心制度时间范围不合法' }),
    )
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('核心制度时间范围不合法')
    expect(wrapper.text()).not.toContain('Request failed with status code 422')

    const lastSig = signals.at(-1)
    wrapper.unmount()
    expect(lastSig?.aborted).toBe(true)
  })

  it('ManualQualityReportPanel: 演示隔离、上海时区、改日期同步刷新 options、中文错误与 abort', async () => {
    authUser.is_demo_account = true
    const signals: AbortSignal[] = []
    const reqSpy = vi.spyOn(ApiService, 'requestRaw').mockImplementation(async (cfg) => {
      if (cfg.signal) signals.push(cfg.signal as AbortSignal)
      if ((cfg.params as Record<string, unknown>)?.start_date === '2026-09-01') {
        return okResponse({
          ...manualReportData,
          filter_options: {
            institutes: ['H9'],
            departments: [{ institute_id: 'H9', department: '儿科' }],
            creators: [{ id: 'u9', name: '九月录入人' }],
            tasks: [{ id: 'T9', name: '九月任务' }],
          },
        })
      }
      return okResponse(manualReportData)
    })

    const wrapper = mount(ManualQualityReportPanel, {
      global: {
        stubs: {
          ManualDefectWorkflowDrawer: true,
          CaseRectificationCreate: true,
          'a-spin': { template: '<div><slot /></div>' },
          'a-table': {
            props: ['dataSource'],
            template:
              '<div class="rows"><div v-for="row in dataSource" :key="row.id"><slot name="bodyCell" :column="{ dataIndex: \'created_at\' }" :record="row" :text="row.created_at" /><span>{{ row.rule_name }}</span></div></div>',
          },
          'a-pagination': true,
          'a-drawer': true,
          'a-descriptions': true,
          'a-descriptions-item': true,
        },
      },
    })
    await flushPromises()

    // UTC as_of 与 created_at 转为东八区可读时间
    expect(wrapper.text()).toContain('2026-10-01 08:00:00')
    expect(wrapper.text()).toContain('2026-10-01 09:30:00')
    // 演示账号隐藏 unknown 汇总与 unknown 行
    expect(wrapper.text()).toContain('确定人工缺陷')
    expect(wrapper.text()).not.toContain('未知状态缺陷')
    expect(wrapper.text()).not.toContain('未知 1')

    // 选中机构后修改日期范围，options 同步刷新为新日期窗口选项
    await wrapper.findAll('select')[0].setValue('H1')
    const dateInputs = wrapper.findAll('input.mock-date-picker')
    await dateInputs[0].setValue('2026-09-01')
    await dateInputs[1].setValue('2026-09-15')
    await flushPromises()
    expect(wrapper.findAll('select')[0].text()).toContain('H9')
    expect(reqSpy.mock.calls.length).toBeGreaterThanOrEqual(2)

    // AxiosError 提取中文错误
    vi.spyOn(ApiService, 'requestRaw').mockRejectedValueOnce(
      axiosErr(422, { detail: '日期跨度超过允许范围' }),
    )
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('日期跨度超过允许范围')
    expect(wrapper.text()).not.toContain('Request failed with status code 422')

    const lastSig = signals.at(-1)
    wrapper.unmount()
    expect(lastSig?.aborted).toBe(true)
  })

  it('RecordRemediationAnalysisPanel: 演示隔离隐藏 source_unknown/history_unknown 与卸载 abort', async () => {
    authUser.is_demo_account = true
    const signals: AbortSignal[] = []
    vi.spyOn(ApiService, 'requestRaw').mockImplementation(async (cfg) => {
      if (cfg.signal) signals.push(cfg.signal as AbortSignal)
      return okResponse({
        scope: { scene: 'running', defect_source: 'all' },
        contract_status: 'confirmed',
        assumptions: ['测试口径'],
        labels: [{ key: 'urged_rectified', label: '催办已整改', defect_total: 1, case_total: 1 }],
        state_counts: {
          not_dispatched: 1,
          source_unknown: 2,
          history_unknown: 3,
          pending_acceptance: 1,
        },
        total: 2,
        page: 1,
        page_size: 20,
        filter_label: null,
        items: [
          {
            institute_id: 'H1',
            patient_id: 'P1',
            visit_id: 'V1',
            scene: 'running',
            target_kind: 'canonical_defect',
            target_id: 'R1',
            target_label: '确定整改缺陷',
            root_job_id: 'J1',
            envelope_id: 'E1',
            source_known: true,
            source_reason: 'not_current_round',
            patient_name: '患者一',
            department: '内科',
            doctor: '医生一',
            labels: ['urged_rectified'],
            rectification_state: 'approved',
            rectification_id: 'rect1',
            assignee_name: '医生一',
            submission_event_id: 'ev1',
            submission_urge_ids: [],
            current_urge_ids: [],
            appeals: [],
            events: [],
          },
          {
            institute_id: 'H1',
            patient_id: 'P2',
            visit_id: 'V2',
            scene: 'running',
            target_kind: 'task_manual_defect',
            target_id: 'R2',
            target_label: '来源未知缺陷',
            root_job_id: 'J2',
            envelope_id: 'E2',
            source_known: false,
            source_reason: 'manual_source_missing',
            patient_name: '患者二',
            department: '内科',
            doctor: '医生二',
            labels: [],
            rectification_state: 'source_unknown',
            rectification_id: null,
            assignee_name: null,
            submission_event_id: null,
            submission_urge_ids: [],
            current_urge_ids: [],
            appeals: [],
            events: [],
          },
        ],
      })
    })

    const wrapper = mount(RecordRemediationAnalysisPanel, {
      props: { filters: { scene: 'running', defect_source: 'all' } },
      global: {
        stubs: {
          CaseRectificationCreate: true,
          'a-button': { template: '<button><slot /></button>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-drawer': { props: ['open'], template: '<aside v-if="open"><slot /></aside>' },
          'a-pagination': true,
        },
      },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('确定整改缺陷')
    expect(wrapper.text()).not.toContain('来源未知缺陷')
    expect(wrapper.text()).not.toContain('冻结来源未知')
    expect(wrapper.text()).not.toContain('历史不足')
    expect(wrapper.text()).not.toContain('非本轮冻结来源')

    const lastSig = signals.at(-1)
    wrapper.unmount()
    expect(lastSig?.aborted).toBe(true)
  })
})
