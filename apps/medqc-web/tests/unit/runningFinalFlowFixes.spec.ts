import { defineComponent, h, ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { Popconfirm } from 'ant-design-vue'
import { AxiosHeaders } from 'axios'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/composables/useQcResultVisibility', () => ({
  useQcResultVisibility: () => ({ confirmedResultsOnly: ref(false) }),
}))

const workspaceMocks = vi.hoisted(() => ({
  createSichuanWorkspaceBatchJob: vi.fn(),
  getSichuanWorkspaceBatchJob: vi.fn(),
  exportFilteredLuxian0609RecordResults: vi.fn(),
  getLatestLuxian0609RecordResult: vi.fn(),
  listQcResultFeedbacks: vi.fn(),
  saveQcResultFeedback: vi.fn(),
}))

vi.mock('@/services/sichuan-rule-workspace-service', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/sichuan-rule-workspace-service')>()
  return {
    ...actual,
    createSichuanWorkspaceBatchJob: (...args: unknown[]) =>
      workspaceMocks.createSichuanWorkspaceBatchJob(...args),
    getSichuanWorkspaceBatchJob: (...args: unknown[]) =>
      workspaceMocks.getSichuanWorkspaceBatchJob(...args),
    exportFilteredLuxian0609RecordResults: (...args: unknown[]) =>
      workspaceMocks.exportFilteredLuxian0609RecordResults(...args),
    getLatestLuxian0609RecordResult: (...args: unknown[]) =>
      workspaceMocks.getLatestLuxian0609RecordResult(...args),
    listQcResultFeedbacks: (...args: unknown[]) => workspaceMocks.listQcResultFeedbacks(...args),
    saveQcResultFeedback: (...args: unknown[]) => workspaceMocks.saveQcResultFeedback(...args),
  }
})

import { clinicalSourcesApi } from '@/api/clinicalSources'
import { ApiService } from '@/services/apiService'
import {
  getEditableMedicalRecordDocument,
  getEditableMedicalRecordDocuments,
  HISTORICAL_SNAPSHOT_FALLBACK_NOTICE,
} from '@/services/manual-case-sample-service'
import WorkstationLayout from '@/components/layout/WorkstationLayout.vue'
import QcRecordResultListView from '@/views/workstation-v4/QcRecordResultListView.vue'
import QcRecordResultAnalysisPanel from '@/views/workstation-v4/components/qc/QcRecordResultAnalysisPanel.vue'
import QcRunSelectedControl from '@/views/workstation-v4/components/qc/QcRunSelectedControl.vue'
import QCRecordCompareWorkbench from '@/views/workstation-v4/semantic-rules/components/QCRecordCompareWorkbench.vue'
import { resetClinicalSourceOptionsCache } from '@/views/workstation-v4/composables/usePatientRecords'

enableAutoUnmount(afterEach)

function makeResponse(data: unknown, status = 200) {
  return {
    data,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    headers: new AxiosHeaders(),
    config: { headers: new AxiosHeaders() },
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

const passthrough = (name: string, tag = 'div') =>
  defineComponent({
    name,
    setup(_props, { attrs, slots }) {
      return () => h(tag, attrs, [slots.title?.(), slots.default?.()])
    },
  })

describe('运行/终末质控前端流转修复回归测试', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    resetClinicalSourceOptionsCache()
    window.sessionStorage.clear()
    window.history.replaceState({}, '', '/workstation-v5/records/running')
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      configurable: true,
      value: (query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: () => undefined,
        removeListener: () => undefined,
        addEventListener: () => undefined,
        removeEventListener: () => undefined,
        dispatchEvent: () => false,
      }),
    })
    const pinia = createPinia()
    setActivePinia(pinia)
    workspaceMocks.listQcResultFeedbacks.mockResolvedValue({ success: true, data: [] })
  })

  afterEach(() => {
    vi.restoreAllMocks()
    resetClinicalSourceOptionsCache()
  })

  describe('1. P0 #1 原文核对/完整结果抽屉快照未保留平滑回退与中文说明', () => {
    it('manual-case-sample-service 透传后端回退标记并将 409 historical_material_snapshot_not_retained 映射为中文', async () => {
      const requestSpy = vi.spyOn(ApiService, 'requestRaw')
      requestSpy.mockResolvedValueOnce(
        makeResponse({
          success: true,
          data: {
            visit_id: '2641480',
            material_source_fallback: true,
            material_source_fallback_reason: 'historical_material_snapshot_not_retained',
            material_source_view: 'current',
            material_source_notice: HISTORICAL_SNAPSHOT_FALLBACK_NOTICE,
            documents: [
              {
                key: 'admission_record::adm-1',
                document_id: 'adm-1',
                document_type: 'admission_record',
                title: '入院记录',
                execution_domain: 'admission',
                has_content: true,
                content: '',
              },
            ],
          },
        }),
      )

      const fallbackOk = await getEditableMedicalRecordDocuments('2641480', {
        institute_id: 'H1',
        patient_id: 'P1',
        visit_id: '2641480',
        job_id: 'job-old',
        record_ref: 'rec_1',
        view: 'summary',
        document_scope: 'clinical',
        fallback_to_current: true,
      })

      expect(requestSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          url: '/api/v1/emr/2641480/documents',
          skipErrorToast: true,
          params: expect.objectContaining({
            job_id: 'job-old',
            record_ref: 'rec_1',
            document_scope: 'clinical',
            fallback_to_current: true,
          }),
        }),
      )
      expect(fallbackOk.success).toBe(true)
      expect(fallbackOk.data?.material_source_fallback).toBe(true)
      expect(fallbackOk.data?.material_source_view).toBe('current')
      expect(fallbackOk.data?.material_source_notice).toBe(HISTORICAL_SNAPSHOT_FALLBACK_NOTICE)
      expect(fallbackOk.data?.documents).toHaveLength(1)

      // 409 错误映射：绝不裸显英文错误码
      requestSpy.mockRejectedValueOnce({
        response: {
          status: 409,
          data: { detail: 'historical_material_snapshot_not_retained' },
        },
      })
      const conflictRes = await getEditableMedicalRecordDocuments('2641480', {
        job_id: 'job-old',
        view: 'summary',
        document_scope: 'clinical',
      })
      expect(conflictRes.success).toBe(false)
      expect(conflictRes.status).toBe(409)
      expect(conflictRes.errorCode).toBe('historical_material_snapshot_not_retained')
      expect(conflictRes.message).not.toContain('historical_material_snapshot_not_retained')
      expect(conflictRes.message).toContain('冻结原文快照')

      requestSpy.mockRejectedValueOnce({
        response: {
          status: 409,
          data: { detail: 'historical_material_snapshot_not_retained' },
        },
      })
      const renderConflict = await getEditableMedicalRecordDocument(
        '2641480',
        {
          key: 'adm-1',
          source_document_id: 'adm-1',
          document_type: 'admission_record',
          title: '入院记录',
          execution_domain: 'admission',
          content: '',
        },
        { job_id: 'job-old' },
      )
      expect(renderConflict.success).toBe(false)
      expect(renderConflict.message).not.toContain('historical_material_snapshot_not_retained')
      expect(renderConflict.message).toContain('冻结原文快照')
    })

    it('QCRecordCompareWorkbench 携带 fallback_to_current=true，后端 200 回退时展示中文提示且正常阅读文书与医嘱', async () => {
      const requestSpy = vi.spyOn(ApiService, 'requestRaw')
      requestSpy
        // 1. /documents clinical summary -> 200 fallback
        .mockResolvedValueOnce(
          makeResponse({
            success: true,
            data: {
              visit_id: '2641480',
              material_source_fallback: true,
              material_source_fallback_reason: 'historical_material_snapshot_not_retained',
              material_source_view: 'current',
              material_source_notice: HISTORICAL_SNAPSHOT_FALLBACK_NOTICE,
              documents: [
                {
                  key: 'admission_record::adm-1',
                  document_id: 'adm-1',
                  document_type: 'admission_record',
                  title: '入院记录',
                  execution_domain: 'admission',
                  has_content: true,
                  content: '',
                },
              ],
            },
          }),
        )
        // 2. /render 入院记录正文 -> 200
        .mockResolvedValueOnce(
          makeResponse({
            success: true,
            data: {
              content: '范世英当前最新入院记录正文',
              metadata: {
                doc_key: 'admission_record::adm-1',
                doc_type: 'admission_record',
                doc_name: '入院记录',
              },
              render_blocks: [],
            },
          }),
        )
        // 3. /documents orders -> 200 fallback
        .mockResolvedValueOnce(
          makeResponse({
            success: true,
            data: {
              visit_id: '2641480',
              material_source_fallback: true,
              documents: [
                {
                  key: 'order::1',
                  document_id: 'order-1',
                  document_type: 'inpat_drug_order',
                  title: '阿司匹林肠溶片',
                  order_item: '阿司匹林肠溶片',
                  has_content: true,
                  content: '阿司匹林肠溶片 100mg qd',
                },
              ],
            },
          }),
        )

      const wrapper = mount(QCRecordCompareWorkbench, {
        props: {
          visitId: '2641480',
          instituteId: 'H1',
          patientId: 'P2641480',
          jobId: 'job-legacy-409',
          recordRef: 'rec_safe_2641480',
          sourceView: 'saved',
          lazyResultDocuments: true,
          issues: [],
          singleRecordItems: [
            {
              rule_id: 'LX0609-01-01-01',
              rule_name: '入院记录完整性',
              status: 'non_compliant',
              evidence: [],
            },
          ],
        },
      })

      await flushPromises()

      expect(requestSpy).toHaveBeenNthCalledWith(
        1,
        expect.objectContaining({
          url: '/api/v1/emr/2641480/documents',
          params: expect.objectContaining({
            job_id: 'job-legacy-409',
            record_ref: 'rec_safe_2641480',
            view: 'summary',
            document_scope: 'clinical',
            fallback_to_current: true,
          }),
        }),
      )
      expect(requestSpy).toHaveBeenNthCalledWith(
        2,
        expect.objectContaining({
          url: '/api/v1/emr/2641480/render',
          params: expect.objectContaining({
            job_id: 'job-legacy-409',
            record_ref: 'rec_safe_2641480',
            fallback_to_current: true,
          }),
        }),
      )

      expect(wrapper.get('[data-testid="record-compare-fallback-notice"]').text()).toContain(
        '未保留冻结原文快照',
      )
      expect(wrapper.text()).toContain('范世英当前最新入院记录正文')
      expect(wrapper.text()).not.toContain('historical_material_snapshot_not_retained')

      // 点击加载医嘱同样携带 fallback_to_current=true
      await wrapper.get('[data-testid="record-narrow-load-orders"]').trigger('click')
      await flushPromises()
      expect(requestSpy).toHaveBeenNthCalledWith(
        3,
        expect.objectContaining({
          url: '/api/v1/emr/2641480/documents',
          params: expect.objectContaining({
            document_scope: 'orders',
            fallback_to_current: true,
          }),
        }),
      )
      expect(wrapper.text()).not.toContain('historical_material_snapshot_not_retained')
    })

    it('兜底防御：若后端仍返回 409 historical_material_snapshot_not_retained，前端自动回退 source_view=current 并展示中文说明', async () => {
      const requestSpy = vi.spyOn(ApiService, 'requestRaw')
      requestSpy
        .mockRejectedValueOnce({
          response: {
            status: 409,
            data: { detail: 'historical_material_snapshot_not_retained' },
          },
        })
        .mockResolvedValueOnce(
          makeResponse({
            success: true,
            data: {
              visit_id: '2641480',
              documents: [
                {
                  key: 'admission_record::adm-current',
                  document_id: 'adm-current',
                  document_type: 'admission_record',
                  title: '入院记录',
                  content: '兜底回退读取到的当前病历原文',
                },
              ],
            },
          }),
        )

      const wrapper = mount(QCRecordCompareWorkbench, {
        props: {
          visitId: '2641480',
          instituteId: 'H1',
          patientId: 'P2641480',
          jobId: 'job-strict-409',
          recordRef: 'rec_strict',
          sourceView: 'saved',
          lazyResultDocuments: true,
          issues: [],
          singleRecordItems: [],
        },
      })

      await flushPromises()

      expect(requestSpy).toHaveBeenCalledTimes(2)
      expect(requestSpy).toHaveBeenNthCalledWith(
        2,
        expect.objectContaining({
          url: '/api/v1/emr/2641480/documents',
          params: expect.objectContaining({
            source_view: 'current',
            view: 'full',
            visit_id: '2641480',
          }),
        }),
      )
      expect(requestSpy.mock.calls[1]?.[0]?.params).not.toHaveProperty('job_id')
      expect(wrapper.get('[data-testid="record-compare-fallback-notice"]').text()).toContain(
        '未保留冻结原文快照',
      )
      expect(wrapper.text()).toContain('兜底回退读取到的当前病历原文')
      expect(wrapper.text()).not.toContain('historical_material_snapshot_not_retained')
    })
  })

  describe('2. P1 #4 运行质控切入终末质控单请求与「结果分析」Tab 无取消重发', () => {
    it('路由从运行病历质控切到终末病历质控再切至「结果分析」Tab，各接口仅发 1 次干净请求且无取消信号', async () => {
      const optionsSpy = vi.spyOn(clinicalSourcesApi, 'options').mockResolvedValue({
        mode: 'legacy_compat',
        default_source: 'legacy_pg',
        sources: [
          { id: 'legacy_pg', name: '原有数据源', enabled: true },
          { id: 'independent_cdm', name: '东华CDM', enabled: true },
        ],
      })

      const workstationSignals: AbortSignal[] = []
      const summarySignals: AbortSignal[] = []
      const getRawSpy = vi.spyOn(ApiService, 'getRaw').mockImplementation(async (url, params, config) => {
        if (url === '/api/medical-records/workstation') {
          if (config?.signal) workstationSignals.push(config.signal as AbortSignal)
          const isDischarged = params?.hospital_status === 'discharged'
          return makeResponse({
            records: [
              {
                id: isDischarged ? 'V-FIN-1' : 'V-RUN-1',
                visit_id: isDischarged ? 'V-FIN-1' : 'V-RUN-1',
                record_key: isDischarged ? '["H1","P2","V-FIN-1"]' : '["H1","P1","V-RUN-1"]',
                institute_id: 'H1',
                patient_id: isDischarged ? 'P2' : 'P1',
                name: isDischarged ? '范世英' : '孔祥斌',
                department: '内科',
                admission_date: '2026-03-29',
                discharge_date: isDischarged ? '2026-04-05' : '',
              },
            ],
            departments: [{ name: '全部科室', total: 1 }],
            doctors: [{ name: '全部主管医师', total: 1 }],
            total: 1,
            page: 1,
          })
        }
        if (url === '/api/v1/workstation/qc-result-analysis/luxian-0609') {
          return makeResponse({
            data: {
              scope: {
                care_phase: params?.care_phase || 'discharged',
                department: null,
                doctor: null,
                rule_id: null,
                result_status: null,
                completed_from: null,
                completed_to: null,
              },
              kpis: {
                scoped_record_total: 47,
                ready_record_total: 44,
                unavailable_result_total: 0,
              },
              status_distribution: [{ status: 'non_compliant', count: 12 }],
              rule_distribution: [],
              physician_distribution: [],
              selected_rule: null,
              record_page: { page: 1, page_size: 20, total: 0, items: [] },
            },
          })
        }
        return makeResponse({ data: {} })
      })

      const postRawSpy = vi.spyOn(ApiService, 'postRaw').mockImplementation(async (_url, _body, config) => {
        if (config?.signal) summarySignals.push(config.signal as AbortSignal)
        return makeResponse({
          records: [],
          qc_summary: { total_records: 1, ready_records: 1, status_counts: {} },
        })
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
              {
                path: 'records/running',
                component: QcRecordResultListView,
                props: { carePhase: 'inpatient' },
              },
              {
                path: 'records/final',
                component: QcRecordResultListView,
                props: { carePhase: 'discharged' },
              },
            ],
          },
        ],
      })

      await router.push('/workstation-v5/records/running')
      await router.isReady()

      const RouterRoot = defineComponent({
        name: 'RouterRoot',
        template: '<router-view />',
      })

      const wrapper = mount(RouterRoot, {
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
            QcRecordResultTable: true,
            QcRecordReviewPreview: true,
            QcRunSelectedControl: true,
            QCRecordResultComparisonDrawer: true,
            CurrentMedicalRecordDrawer: true,
            ADatePicker: true,
            Pagination: true,
            RangePicker: true,
          },
        },
      })

      await flushPromises()
      expect(optionsSpy).toHaveBeenCalledTimes(1)
      expect(
        getRawSpy.mock.calls.filter(([url]) => url === '/api/medical-records/workstation'),
      ).toHaveLength(1)

      // 切入终末病历质控：options 命中缓存不再重复发，workstation(discharged) 与 qc-summary 各仅发 1 次
      getRawSpy.mockClear()
      postRawSpy.mockClear()
      workstationSignals.length = 0
      summarySignals.length = 0

      await router.push('/workstation-v5/records/final')
      await flushPromises()

      expect(optionsSpy).toHaveBeenCalledTimes(1)
      const finalListCalls = getRawSpy.mock.calls.filter(
        ([url]) => url === '/api/medical-records/workstation',
      )
      expect(finalListCalls).toHaveLength(1)
      expect(finalListCalls[0]?.[1]).toEqual(
        expect.objectContaining({
          hospital_status: 'discharged',
          date_field: 'discharge',
          source_id: 'legacy_pg',
          page: 1,
        }),
      )
      expect(postRawSpy).toHaveBeenCalledTimes(1)
      expect(workstationSignals.every((signal) => !signal.aborted)).toBe(true)
      expect(summarySignals.every((signal) => !signal.aborted)).toBe(true)

      // 切到「结果分析」Tab：qc-result-analysis/luxian-0609 仅发 1 次干净请求
      getRawSpy.mockClear()
      await wrapper.get('[data-testid="qc-result-view-analysis"]').trigger('click')
      await flushPromises()

      const analysisCalls = getRawSpy.mock.calls.filter(
        ([url]) => url === '/api/v1/workstation/qc-result-analysis/luxian-0609',
      )
      expect(analysisCalls).toHaveLength(1)
      expect(analysisCalls[0]?.[1]).toEqual(
        expect.objectContaining({
          care_phase: 'discharged',
          page: 1,
          page_size: 20,
        }),
      )

      // 重复点击当前已激活的「结果分析」Tab 不得触发重发
      await wrapper.get('[data-testid="qc-result-view-analysis"]').trigger('click')
      await flushPromises()
      expect(
        getRawSpy.mock.calls.filter(
          ([url]) => url === '/api/v1/workstation/qc-result-analysis/luxian-0609',
        ),
      ).toHaveLength(1)
    })

    it('QcRecordResultAnalysisPanel 在途相同查询去重，且同值 carePhase 不触发重发', async () => {
      const pending = deferred<ReturnType<typeof makeResponse>>()
      const getRawSpy = vi.spyOn(ApiService, 'getRaw').mockReturnValue(pending.promise)

      const wrapper = mount(QcRecordResultAnalysisPanel, {
        props: { carePhase: 'discharged' },
        global: {
          stubs: { ADatePicker: true },
        },
      })

      expect(getRawSpy).toHaveBeenCalledTimes(1)

      // 同值 props 更新不应重复发请求
      await wrapper.setProps({ carePhase: 'discharged' })
      expect(getRawSpy).toHaveBeenCalledTimes(1)

      pending.resolve(
        makeResponse({
          data: {
            scope: {
              care_phase: 'discharged',
              department: null,
              doctor: null,
              rule_id: null,
              result_status: null,
              completed_from: null,
              completed_to: null,
            },
            kpis: { scoped_record_total: 10, ready_record_total: 8, unavailable_result_total: 0 },
            status_distribution: [],
            rule_distribution: [],
            physician_distribution: [],
            selected_rule: null,
            record_page: { page: 1, page_size: 20, total: 0, items: [] },
          },
        }),
      )
      await flushPromises()
      expect(getRawSpy).toHaveBeenCalledTimes(1)
    })
  })

  describe('3. P1 #6 质控所选二次确认防误触', () => {
    const sampleRefs = [{ institute_id: 'H1', patient_id: 'P1', visit_id: 'V1' }]

    it('勾选 1 条后点击「质控所选」先弹确认提示，取消不触发，确认后才提交执行', async () => {
      workspaceMocks.createSichuanWorkspaceBatchJob.mockResolvedValue({
        success: true,
        data: { id: 'job-confirm-1', status: 'queued' },
      })
      workspaceMocks.getSichuanWorkspaceBatchJob.mockResolvedValue({
        success: true,
        data: { id: 'job-confirm-1', status: 'completed' },
      })

      const wrapper = mount(QcRunSelectedControl, {
        props: {
          carePhase: 'discharged',
          sourceId: 'legacy_pg',
          recordRefs: sampleRefs,
          selectedCount: 1,
        },
      })

      // 首次点击仅弹出二次确认，绝不立即提交任务
      await wrapper.get('[data-testid="run-selected-qc-trigger"]').trigger('click')
      await flushPromises()

      const popconfirm = wrapper.getComponent(Popconfirm)
      expect(popconfirm.props('open')).toBe(true)
      expect(popconfirm.props('title')).toBe('将对已勾选的 1 份病历执行质控，是否继续？')
      expect(workspaceMocks.createSichuanWorkspaceBatchJob).not.toHaveBeenCalled()

      // 点击取消不触发质控
      popconfirm.vm.$emit('cancel')
      await flushPromises()
      expect(popconfirm.props('open')).toBe(false)
      expect(workspaceMocks.createSichuanWorkspaceBatchJob).not.toHaveBeenCalled()

      // 再次点击并确认执行
      await wrapper.get('[data-testid="run-selected-qc-trigger"]').trigger('click')
      await flushPromises()
      expect(popconfirm.props('open')).toBe(true)

      popconfirm.vm.$emit('confirm')
      await flushPromises()

      expect(popconfirm.props('open')).toBe(false)
      expect(workspaceMocks.createSichuanWorkspaceBatchJob).toHaveBeenCalledTimes(1)
      expect(workspaceMocks.createSichuanWorkspaceBatchJob).toHaveBeenCalledWith({
        rule_set_key: 'luxian_0609_qc_v1',
        scope: 'final',
        date_field: 'discharge',
        record_refs: sampleRefs,
      })
      expect(wrapper.emitted('results-updated')).toHaveLength(1)
      expect(wrapper.emitted('completed')).toHaveLength(1)
    })

    it('取消勾选或切换质控阶段时自动关闭已打开的二次确认气泡', async () => {
      const wrapper = mount(QcRunSelectedControl, {
        props: {
          carePhase: 'discharged',
          sourceId: 'legacy_pg',
          recordRefs: sampleRefs,
          selectedCount: 1,
        },
      })

      await wrapper.get('[data-testid="run-selected-qc-trigger"]').trigger('click')
      await flushPromises()
      const popconfirm = wrapper.getComponent(Popconfirm)
      expect(popconfirm.props('open')).toBe(true)

      await wrapper.setProps({ recordRefs: [], selectedCount: 0 })
      await flushPromises()
      expect(popconfirm.props('open')).toBe(false)
      expect(workspaceMocks.createSichuanWorkspaceBatchJob).not.toHaveBeenCalled()
    })
  })
})
