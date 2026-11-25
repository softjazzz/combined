import { readFileSync } from 'node:fs'
import { defineComponent, h, ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { flushPromises, mount } from '@vue/test-utils'
import { AxiosHeaders } from 'axios'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/composables/useQcResultVisibility', () => ({
  useQcResultVisibility: () => ({ confirmedResultsOnly: ref(false) }),
}))

const serviceMocks = vi.hoisted(() => ({
  listSichuanWorkspaceBatchJobs: vi.fn(),
  getSichuanWorkspaceBatchJob: vi.fn(),
  getSichuanWorkspaceBatchJobDebugSnapshot: vi.fn(),
  exportSichuanWorkspaceBatchJob: vi.fn(),
}))

vi.mock('@/services/sichuan-rule-workspace-service', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/sichuan-rule-workspace-service')>()
  return {
    ...actual,
    listSichuanWorkspaceBatchJobs: (...args: unknown[]) =>
      serviceMocks.listSichuanWorkspaceBatchJobs(...args),
    getSichuanWorkspaceBatchJob: (...args: unknown[]) =>
      serviceMocks.getSichuanWorkspaceBatchJob(...args),
    getSichuanWorkspaceBatchJobDebugSnapshot: (...args: unknown[]) =>
      serviceMocks.getSichuanWorkspaceBatchJobDebugSnapshot(...args),
    exportSichuanWorkspaceBatchJob: (...args: unknown[]) =>
      serviceMocks.exportSichuanWorkspaceBatchJob(...args),
  }
})

import { clinicalSourcesApi } from '@/api/clinicalSources'
import { apiClient, ApiService } from '@/services/apiService'
import WorkstationLayout from '@/components/layout/WorkstationLayout.vue'
import WorkstationV4View from '@/views/workstation-v4/WorkstationV4View.vue'
import {
  resetClinicalSourceOptionsCache,
  usePatientRecords,
} from '@/views/workstation-v4/composables/usePatientRecords'
import { normalizeRecord } from '@/views/workstation-v4/normalize'
import {
  hospitalizationStatusLabel,
  resolvedHospitalizationStatus,
} from '@/views/workstation-v4/components/workbench/hospitalizationPresentation'
import RecordPoolPreviewPanel from '@/views/workstation-v4/components/workbench/RecordPoolPreviewPanel.vue'
import RecordPoolQcTaskHistory from '@/views/workstation-v4/components/workbench/RecordPoolQcTaskHistory.vue'
import SemanticRulesBatchResultDrawer from '@/views/workstation-v4/semantic-rules/components/SemanticRulesBatchResultDrawer.vue'

function makeResponse(data: unknown) {
  return {
    data,
    status: 200,
    statusText: 'OK',
    headers: new AxiosHeaders(),
    config: { headers: new AxiosHeaders() },
  }
}

const passthrough = (name: string, tag = 'div') =>
  defineComponent({
    name,
    setup(_props, { attrs, slots }) {
      return () => h(tag, attrs, [slots.title?.(), slots.default?.()])
    },
  })

describe('病历池切换流、任务抽屉隔离与在院状态兜底回归测试', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    resetClinicalSourceOptionsCache()
    window.history.replaceState({}, '', '/workstation-v5/worklist')
    const pinia = createPinia()
    setActivePinia(pinia)
  })

  afterEach(() => {
    vi.restoreAllMocks()
    resetClinicalSourceOptionsCache()
  })

  describe('1. P1 终末病历质控切回病历池：单次首屏请求与无空白过渡帧', () => {
    it('WorkstationLayout 移除 out-in 淡出空白过渡，并使用 router-view 插槽 route.path 作为同步 key', () => {
      const source = readFileSync('src/components/layout/WorkstationLayout.vue', 'utf8')
      expect(source).not.toContain('mode="out-in"')
      expect(source).not.toContain('<transition name="fade"')
      expect(source).not.toContain('.fade-enter-from')
      expect(source).not.toContain('.fade-leave-to')
      expect(source).toContain('v-slot="{ Component, route: currentRoute }"')
      expect(source).toContain(':key="currentRoute.path"')
    })

    it('病历池 → 终末病历质控 → 病历池切换时仅发出 1 次工作台列表请求且主区立即可见', async () => {
      vi.spyOn(clinicalSourcesApi, 'options').mockResolvedValue({
        mode: 'legacy_compat',
        default_source: 'legacy_pg',
        sources: [
          { id: 'legacy_pg', name: '原有数据源', enabled: true },
          { id: 'independent_cdm', name: '东华CDM', enabled: true },
        ],
      })
      const getRawSpy = vi.spyOn(ApiService, 'getRaw').mockResolvedValue(
        makeResponse({
          records: [
            {
              id: 'V-100',
              visit_id: 'V-100',
              record_key: '["H1","P1","V-100"]',
              institute_id: 'H1',
              patient_id: 'P1',
              name: '童世先',
              department: '内科',
              admission_date: '2026-09-14',
              discharge_date: '2026-09-21',
            },
          ],
          departments: [{ name: '全部科室', total: 1 }],
          doctors: [{ name: '全部主管医师', total: 1 }],
          total: 1,
          page: 1,
        }),
      )
      vi.spyOn(ApiService, 'postRaw').mockResolvedValue(
        makeResponse({
          records: [],
          qc_summary: { total_records: 1, ready_records: 0, status_counts: {} },
        }),
      )

      const FinalRecordsStub = defineComponent({
        name: 'FinalRecordsStub',
        template: '<section data-testid="final-records-page">终末病历质控</section>',
      })

      const pinia = createPinia()
      setActivePinia(pinia)

      const router = createRouter({
        history: createMemoryHistory(),
        routes: [
          {
            path: '/workstation-v5',
            component: WorkstationLayout,
            children: [
              { path: 'worklist', component: WorkstationV4View },
              { path: 'records/final', component: FinalRecordsStub },
            ],
          },
        ],
      })

      await router.push('/workstation-v5/worklist')
      await router.isReady()

      const wrapper = mount(WorkstationLayout, {
        global: {
          plugins: [pinia, router],
          stubs: {
            RuntimeBuildStatus: true,
            GlobalAssistantHost: true,
            WorkstationConfirmDialog: true,
            MqIcon: true,
            MqIconTile: true,
            ATooltip: passthrough('ATooltip'),
            ADropdown: passthrough('ADropdown'),
            APopover: passthrough('APopover'),
            AMenu: passthrough('AMenu'),
            AMenuItem: passthrough('AMenuItem'),
            AMenuDivider: true,
            WorkstationV4ListView: defineComponent({
              name: 'WorkstationV4ListView',
              template: '<section data-testid="record-pool-page">病历池</section>',
            }),
            WorkstationV4AssistView: true,
            CurrentMedicalRecordDrawer: true,
            WorkstationV4DetailView: true,
            WorkstationV4RulesView: true,
            AModal: true,
            ASegmented: true,
            ATextarea: true,
            AButton: true,
          },
        },
      })

      await flushPromises()
      expect(wrapper.find('[data-testid="record-pool-page"]').exists()).toBe(true)
      expect(getRawSpy).toHaveBeenCalledTimes(1)
      expect(getRawSpy).toHaveBeenLastCalledWith(
        '/api/medical-records/workstation',
        expect.objectContaining({
          source_id: 'legacy_pg',
          date_field: 'visit',
          page: 1,
          page_size: 15,
          qc_summary_mode: 'deferred',
        }),
        { signal: expect.any(AbortSignal) },
      )

      // 切到终末病历质控，再切回病历池
      getRawSpy.mockClear()
      await router.push('/workstation-v5/records/final')
      await flushPromises()
      expect(wrapper.find('[data-testid="final-records-page"]').exists()).toBe(true)
      expect(getRawSpy).not.toHaveBeenCalled()

      await router.push('/workstation-v5/worklist')
      await flushPromises()
      expect(wrapper.find('[data-testid="record-pool-page"]').exists()).toBe(true)
      // 必须严格只发 1 次列表请求（绝不重复发 2 次）
      expect(getRawSpy).toHaveBeenCalledTimes(1)
      expect(getRawSpy).toHaveBeenLastCalledWith(
        '/api/medical-records/workstation',
        expect.objectContaining({
          source_id: 'legacy_pg',
          date_field: 'visit',
          page: 1,
          page_size: 15,
          qc_summary_mode: 'deferred',
        }),
        { signal: expect.any(AbortSignal) },
      )

      wrapper.unmount()
    })

    it('聚合阶段队列（stage=frontpage_qc）首屏不冗余请求普通病历池列表，退出阶段模式后仅补发 1 次', async () => {
      vi.spyOn(clinicalSourcesApi, 'options').mockResolvedValue({
        mode: 'legacy_compat',
        default_source: 'legacy_pg',
        sources: [{ id: 'legacy_pg', name: '原有数据源', enabled: true }],
      })
      const getRawSpy = vi.spyOn(ApiService, 'getRaw').mockResolvedValue(
        makeResponse({ records: [], departments: [], doctors: [], total: 0, page: 1 }),
      )
      vi.spyOn(ApiService, 'postRaw').mockResolvedValue(
        makeResponse({ records: [], qc_summary: { total_records: 0 } }),
      )
      const stageGetSpy = vi.spyOn(apiClient, 'get').mockResolvedValue({
        data: { data: { items: [], total: 0, page: 1, page_size: 15 } },
      } as never)

      const router = createRouter({
        history: createMemoryHistory(),
        routes: [{ path: '/workstation-v5/worklist', component: WorkstationV4View }],
      })
      await router.push('/workstation-v5/worklist?stage=frontpage_qc')
      await router.isReady()

      const wrapper = mount(WorkstationV4View, {
        global: {
          plugins: [createPinia(), router],
          stubs: {
            WorkstationV4ListView: true,
            WorkstationV4AssistView: true,
            CurrentMedicalRecordDrawer: true,
            WorkstationV4DetailView: true,
            WorkstationV4RulesView: true,
            AModal: true,
            ASegmented: true,
            ATextarea: true,
            AButton: true,
          },
        },
      })

      await flushPromises()
      expect(stageGetSpy).toHaveBeenCalledTimes(1)
      expect(getRawSpy).not.toHaveBeenCalled()

      // 切回普通病历池（同 route.path 去掉 stage）时触发 1 次普通列表加载
      await router.push('/workstation-v5/worklist')
      await flushPromises()
      expect(getRawSpy).toHaveBeenCalledTimes(1)

      wrapper.unmount()
    })

    it('usePatientRecords 对与当前状态一致的 selectDept / selectDoctor 幂等忽略，不触发重复请求', async () => {
      vi.spyOn(clinicalSourcesApi, 'options').mockResolvedValue({
        mode: 'legacy_compat',
        default_source: 'legacy_pg',
        sources: [{ id: 'legacy_pg', name: '原有数据源', enabled: true }],
      })
      const getRawSpy = vi.spyOn(ApiService, 'getRaw').mockResolvedValue(
        makeResponse({ records: [], departments: [], doctors: [], total: 0, page: 1 }),
      )
      vi.spyOn(ApiService, 'postRaw').mockResolvedValue(
        makeResponse({ records: [], qc_summary: { total_records: 0 } }),
      )

      const records = usePatientRecords()
      await records.fetchData(1)
      expect(getRawSpy).toHaveBeenCalledTimes(1)

      // 重复触发默认「全部科室」「全部主管医师」不产生二次请求
      records.selectDept('全部科室')
      records.selectDoctor('全部主管医师')
      await flushPromises()
      expect(getRawSpy).toHaveBeenCalledTimes(1)

      // 实际切换科室与医师时正常发起后端查询
      records.selectDept('心内科')
      await flushPromises()
      expect(getRawSpy).toHaveBeenCalledTimes(2)

      records.selectDoctor('张医生')
      await flushPromises()
      expect(getRawSpy).toHaveBeenCalledTimes(3)
    })
  })

  describe('2. P1 任务详情抽屉返回文案与最近质控任务样本验证过滤', () => {
    it('RecordPoolQcTaskHistory 传递 exclude_validation=true，前端防御过滤样本验证任务，并传 back-label="返回病历池"', async () => {
      serviceMocks.listSichuanWorkspaceBatchJobs.mockResolvedValue({
        success: true,
        data: {
          total: 4,
          page: 1,
          page_size: 30,
          items: [
            {
              id: 'pool-job-1',
              rule_code: 'SC-BATCH',
              rule_name: '病历池常规质控任务',
              rule_set_key: 'luxian_0609_qc_v1',
              rule_set_name: '病历池质控任务 #1',
              task_origin: 'record_pool',
              is_sample_validation: false,
              scope: 'all',
              status: 'completed',
              total_records: 12,
              created_at: '2026-09-21T08:00:00Z',
            },
            {
              id: 'sample-job-flag',
              rule_code: 'LX0609',
              rule_name: '样本验证任务（布尔标记）',
              rule_set_key: 'luxian_0609_qc_v1',
              rule_set_name: '泸县0609样本池验证A',
              is_sample_validation: true,
              task_origin: 'sample_validation',
              scope: 'all',
              status: 'completed',
              total_records: 5,
            },
            {
              id: 'sample-job-origin',
              rule_code: 'LX0609',
              rule_name: '样本验证任务（来源标记）',
              rule_set_key: 'luxian_0609_qc_v1',
              rule_set_name: '泸县0609样本池验证B',
              task_origin: 'sample_validation',
              scope: 'all',
              status: 'completed',
              total_records: 5,
            },
            {
              id: 'sample-job-legacy-filter',
              rule_code: 'LX0609',
              rule_name: '样本验证任务（旧 filters 标记）',
              rule_set_key: 'luxian_0609_qc_v1',
              rule_set_name: '泸县0609样本池验证C',
              filters: { sample_pool_id: 'pool-xyz', source: 'manual_problem_sample_pool' },
              scope: 'all',
              status: 'completed',
              total_records: 5,
            },
          ],
        },
      })
      serviceMocks.getSichuanWorkspaceBatchJob.mockResolvedValue({
        success: true,
        data: {
          id: 'pool-job-1',
          rule_code: 'SC-BATCH',
          rule_name: '病历池常规质控任务',
          rule_set_key: 'luxian_0609_qc_v1',
          scope: 'all',
          status: 'completed',
        },
      })
      serviceMocks.getSichuanWorkspaceBatchJobDebugSnapshot.mockResolvedValue({
        success: true,
        data: { job_id: 'pool-job-1', status: 'completed', scope: 'all', rules: [] },
      })

      const wrapper = mount(RecordPoolQcTaskHistory, {
        global: {
          stubs: {
            AButton: passthrough('AButton', 'button'),
            ADrawer: passthrough('ADrawer'),
            ASpin: passthrough('ASpin'),
            AEmpty: passthrough('AEmpty'),
            SemanticRulesBatchResultDrawer: defineComponent({
              name: 'SemanticRulesBatchResultDrawer',
              props: { open: Boolean, backLabel: String, batchJobDetail: Object },
              setup(props) {
                return () =>
                  h('div', {
                    'data-testid': 'pool-result-drawer',
                    'data-open': String(props.open),
                    'data-back-label': props.backLabel || '',
                  })
              },
            }),
          },
        },
      })

      await wrapper.get('[data-testid="record-pool-qc-task-history-entry"]').trigger('click')
      await flushPromises()

      expect(serviceMocks.listSichuanWorkspaceBatchJobs).toHaveBeenCalledWith({
        page: 1,
        page_size: 30,
        exclude_validation: true,
      })

      const items = wrapper.findAll('.record-pool-task-history__item')
      expect(items).toHaveLength(1)
      expect(wrapper.text()).toContain('病历池质控任务 #1')
      expect(wrapper.text()).not.toContain('泸县0609样本池验证A')
      expect(wrapper.text()).not.toContain('泸县0609样本池验证B')
      expect(wrapper.text()).not.toContain('泸县0609样本池验证C')

      await items[0].trigger('click')
      await flushPromises()
      const drawer = wrapper.get('[data-testid="pool-result-drawer"]')
      expect(drawer.attributes('data-open')).toBe('true')
      expect(drawer.attributes('data-back-label')).toBe('返回病历池')

      wrapper.unmount()
    })

    it('SemanticRulesBatchResultDrawer 在传入 backLabel="返回病历池" 时展示病历池文案，缺省仍保留"返回样本验证"', () => {
      const commonProps = {
        open: true,
        batchJobDetail: null,
        batchJobDetailLoading: false,
        batchJobDebugSnapshot: null,
        batchJobDebugLoading: false,
        fetchBatchJobDebugSnapshot: vi.fn().mockResolvedValue(null),
        close: vi.fn(),
        exportBatchJobReport: vi.fn().mockResolvedValue(undefined),
        getBatchJobStatusTagClass: () => '',
        getBatchJobStatusText: () => '已完成',
        formatDateTime: (value?: string | null) => value || '-',
      }
      const stubs = {
        ADrawer: passthrough('ADrawer'),
        AButton: passthrough('AButton', 'button'),
        ADropdown: passthrough('ADropdown'),
        AMenu: passthrough('AMenu'),
        AMenuItem: passthrough('AMenuItem'),
        ATag: passthrough('ATag'),
        ARadioGroup: passthrough('ARadioGroup'),
        ARadioButton: passthrough('ARadioButton'),
        ASwitch: true,
        AInput: true,
        ASelect: true,
        AEmpty: true,
        MqIcon: true,
        RecordViewCloseIcon: true,
        BatchTaskFailureSummary: true,
        BatchResultOverview: true,
        TopIssueRulesCard: true,
        BatchRecordReviewPanel: true,
        QCRecordCompareWorkbench: true,
        CustomerQcResultDetailCard: true,
        QcRemediationSuggestion: true,
      }

      const poolDrawer = mount(SemanticRulesBatchResultDrawer, {
        props: { ...commonProps, backLabel: '返回病历池' },
        global: { stubs },
      })
      expect(poolDrawer.get('.drawer-back-button').text()).toContain('返回病历池')
      expect(poolDrawer.get('.drawer-back-button').text()).not.toContain('返回样本验证')
      poolDrawer.unmount()

      const validationDrawer = mount(SemanticRulesBatchResultDrawer, {
        props: commonProps,
        global: { stubs },
      })
      expect(validationDrawer.get('.drawer-back-button').text()).toContain('返回样本验证')
      validationDrawer.unmount()
    })
  })

  describe('3. P0 前端在院状态与住院天数兜底（存在明确出院日期时绝不标为在院或按今天虚算）', () => {
    it('normalizeRecord 遇非空 discharge_date 时强制归为 discharged 且按出入院差值计算 days', () => {
      const normalized = normalizeRecord({
        id: 'V-TONG',
        visit_id: 'V-TONG',
        name: '童世先',
        department: '内科',
        admission_date: '2026-09-14',
        discharge_date: '2026-09-21',
        hospitalization_status: 'inpatient',
        days: 92,
      })

      expect(normalized.dischargeDate).toBe('2026-09-21')
      expect(normalized.hospitalizationStatus).toBe('discharged')
      expect(normalized.days).toBe(7)

      const fromActive = normalizeRecord({
        id: 'V-CHENG',
        admission_date: '2026-09-21',
        discharge_datetime: '2026-09-21 15:30:00',
        hospitalization_status: 'active',
        stay_days: 78,
      })
      expect(fromActive.dischargeDate).toBe('2026-09-21')
      expect(fromActive.hospitalizationStatus).toBe('discharged')
      expect(fromActive.days).toBe(1)

      const genuineInpatient = normalizeRecord({
        id: 'V-KONG',
        admission_date: '2026-11-20',
        discharge_date: '-',
        hospitalization_status: 'active',
        days: 5,
      })
      expect(genuineInpatient.dischargeDate).toBe('')
      expect(genuineInpatient.hospitalizationStatus).toBe('inpatient')
      expect(genuineInpatient.days).toBe(5)
    })

    it('hospitalizationPresentation 与 RecordPoolPreviewPanel 存在出院日期时展示"已出院"和真实住院天数，不展示"已住 N 天"', () => {
      const staleRow = {
        id: 'record-tong',
        recordKey: '["H","P","V-TONG"]',
        patientName: '童世先',
        visitId: 'V-TONG',
        department: '神经内科',
        stageStatus: '待处理',
        riskReason: '',
        updatedAt: '2026-09-21',
        admissionDate: '2026-09-14',
        dischargeDate: '2026-09-21',
        hospitalizationStatus: 'inpatient' as const,
        isDemo: false,
      }

      expect(resolvedHospitalizationStatus(staleRow)).toBe('discharged')
      expect(hospitalizationStatusLabel(staleRow)).toBe('已出院')

      const preview = mount(RecordPoolPreviewPanel, {
        props: { row: staleRow },
      })
      const text = preview.text()
      expect(text).toContain('已出院')
      expect(text).toContain('7 天')
      expect(text).not.toContain('已住')
      preview.unmount()
    })
  })
})
