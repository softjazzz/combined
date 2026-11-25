import fs from 'node:fs'
import path from 'node:path'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const hoisted = vi.hoisted(() => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
  routerReplace: vi.fn(),
  clinicalSources: {
    options: vi.fn(),
    configuration: vi.fn(),
    save: vi.fn(),
    check: vi.fn(),
  },
  dataPipelinesApi: {
    detail: vi.fn(),
    schedules: vi.fn(),
    saveDraft: vi.fn(),
    schedule: vi.fn(),
  },
  llmEndpointService: {
    load: vi.fn(),
    save: vi.fn(),
  },
  llmObservability: {
    getOverview: vi.fn(),
    getRecordCalls: vi.fn(),
  },
}))

const mockAuthState = reactive({
  isAuthenticated: true,
  user: { id: 'actor-1', is_demo_account: false },
  userRoles: ['super_admin'] as string[],
})

const mockRoute = reactive({
  query: {} as Record<string, string>,
})

vi.mock('vue-router', () => ({
  useRoute: () => mockRoute,
  useRouter: () => ({ replace: hoisted.routerReplace }),
  onBeforeRouteLeave: vi.fn(),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => mockAuthState,
}))

vi.mock('ant-design-vue', () => ({
  message: hoisted.message,
  Modal: { confirm: vi.fn() },
}))

vi.mock('@/utils/auth-token', () => ({
  getAccessToken: () => 'test-token',
}))

vi.mock('@/api/clinicalSources', () => ({
  clinicalSourcesApi: hoisted.clinicalSources,
}))

vi.mock('@/api/dataPipelines', () => ({
  dataPipelinesApi: hoisted.dataPipelinesApi,
}))

vi.mock('@/services/llmEndpointService', () => ({
  llmEndpointService: hoisted.llmEndpointService,
}))

vi.mock('@/services/llmObservability', () => ({
  getLlmObservabilityOverview: hoisted.llmObservability.getOverview,
  getLlmRecordCallAttempts: hoisted.llmObservability.getRecordCalls,
}))

import UserManagementView from '@/views/workstation/UserManagementView.vue'
import DataSyncConfigPage from '@/views/workstation-v4/DataSyncConfigPage.vue'
import WorkstationV2View from '@/views/workstation-v4/WorkstationV2View.vue'
import ClinicalSourceSettingsPanel from '@/views/workstation-v4/components/system-config/ClinicalSourceSettingsPanel.vue'
import SyncJobDetailDrawer from '@/views/workstation-v4/components/system-config/SyncJobDetailDrawer.vue'
import SyncScheduleDraftPanel from '@/views/workstation-v4/components/system-config/SyncScheduleDraftPanel.vue'
import LLMEndpointSettings from '@/components/LLMEndpointSettings.vue'
import ExcelUploadView from '@/views/workstation-v4/frontpage/components/ExcelUploadView.vue'
import FieldMappingStep from '@/views/workstation-v4/frontpage/components/FieldMappingStep.vue'
import CDMDataView from '@/views/workstation-v4/CDMDataView.vue'

const SRC_ROOT = path.resolve(__dirname, '../../src')

function readSrc(relPath: string): string {
  return fs.readFileSync(path.join(SRC_ROOT, relPath), 'utf-8')
}

const Slot = defineComponent({
  setup: (_, { slots }) => () => h('div', slots.default?.()),
})

const DrawerCaptureStub = defineComponent({
  props: {
    open: Boolean,
    width: [String, Number],
    title: { type: String, default: '' },
  },
  setup(props, { slots }) {
    return () =>
      h(
        'div',
        {
          'data-testid': 'captured-drawer',
          'data-open': String(Boolean(props.open)),
          'data-width': String(props.width ?? ''),
        },
        props.open ? slots.default?.() : [],
      )
  },
})

const ButtonStub = defineComponent({
  props: { disabled: Boolean, loading: Boolean },
  setup: (props, { slots, attrs }) => () =>
    h('button', { type: 'button', ...attrs, disabled: props.disabled }, slots.default?.()),
})

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(fetch).mockReset()
  mockAuthState.user = { id: 'actor-1', is_demo_account: false }
  mockAuthState.userRoles = ['super_admin']
  mockRoute.query = {}
})

describe('Fix 1: 全局网格横滚 & 注册审批 textarea 压扁修复', () => {
  it('mq-components.css 与 account-management.css 约束网格最小宽与 textarea 高度', () => {
    const mqCss = readSrc('styles/mq-components.css')
    expect(mqCss).toMatch(/\.mq-page\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)/s)
    expect(mqCss).toMatch(/\.mq-card\s*\{[^}]*min-width:\s*0/s)
    expect(mqCss).toMatch(
      /textarea\.mq-input\s*\{[^}]*height:\s*auto;[^}]*min-height:\s*88px;[^}]*padding:\s*8px 12px;[^}]*resize:\s*vertical;/s,
    )

    const accountCss = readSrc('views/workstation-v4/styles/account-management.css')
    expect(accountCss).toMatch(/\.accounts-panel\s*\{[^}]*min-width:\s*0;[^}]*max-width:\s*100%/s)
    expect(accountCss).toMatch(/\.accounts-table\s*\{[^}]*max-width:\s*100%;[^}]*overflow-x:\s*auto/s)
  })
})

describe('Fix 2: 消除 3 处嵌套 <main> 地标', () => {
  it('UserManagementView 与 DataSyncConfigPage 根节点使用 <section> 且无嵌套 <main>', () => {
    const userWrapper = mount(UserManagementView, {
      global: { stubs: { AccountManagementPanel: true } },
    })
    expect(userWrapper.element.tagName).toBe('SECTION')
    expect(userWrapper.find('main').exists()).toBe(false)
    userWrapper.unmount()

    const configWrapper = mount(DataSyncConfigPage, {
      global: {
        stubs: {
          ClinicalSourceSettingsPanel: true,
          DataPipelineSettingsPanel: true,
          FrontpageExtractionSettingsPanel: true,
          AccountManagementPanel: true,
          LLMApiConfig: true,
          DailyQcSchedulePanel: true,
          QcRuntimeSettingsPanel: true,
          LlmPerformanceObservabilityPanel: true,
          ConnectionStudio: true,
          SyncRunPanel: true,
          'a-modal': true,
        },
      },
    })
    expect(configWrapper.element.tagName).toBe('SECTION')
    expect(configWrapper.find('main').exists()).toBe(false)
    configWrapper.unmount()
  })

  it('WorkstationV2View 在 embedded 模式下将 .ws-v2-main 渲染为 <section>，独立模式保留 <main>', () => {
    const stubs = {
      ExcelUploadView: true,
      CodingOptimizationDrawer: true,
      QCAlertPanel: true,
      'a-button': ButtonStub,
      'a-menu': Slot,
      'a-menu-item': Slot,
      'a-menu-divider': true,
      'a-sub-menu': Slot,
    }

    const embeddedWrapper = mount(WorkstationV2View, {
      props: { embedded: true, initialView: 'upload' },
      global: { stubs },
    })
    expect(embeddedWrapper.get('.ws-v2-main').element.tagName).toBe('SECTION')
    expect(embeddedWrapper.find('main').exists()).toBe(false)
    embeddedWrapper.unmount()

    const standaloneWrapper = mount(WorkstationV2View, {
      props: { embedded: false, initialView: 'upload' },
      global: { stubs },
    })
    expect(standaloneWrapper.get('.ws-v2-main').element.tagName).toBe('MAIN')
    standaloneWrapper.unmount()
  })
})

describe('Fix 3: 1280px–1440px 响应式布局、Drawer 宽度与上传/映射滚动', () => {
  it('SyncJobDetailDrawer / SyncScheduleDraftPanel / LLMEndpointSettings 均使用 min(Npx, 100vw)', async () => {
    hoisted.dataPipelinesApi.detail.mockResolvedValue({
      job_id: 'job-1',
      status: 'succeeded',
      request: { start_date: '2026-01-01', end_date: '2026-01-02', plan_version: 1 },
      units: [],
    })
    const jobWrapper = mount(SyncJobDetailDrawer, {
      props: { jobId: 'job-1', canRetry: false },
      global: {
        stubs: {
          'a-drawer': DrawerCaptureStub,
          'a-alert': true,
          'a-button': ButtonStub,
          'a-empty': true,
        },
      },
    })
    expect(jobWrapper.get('[data-testid="captured-drawer"]').attributes('data-width')).toBe(
      'min(720px, 100vw)',
    )
    jobWrapper.unmount()

    const draftWrapper = mount(SyncScheduleDraftPanel, {
      props: {
        catalog: {
          interfaces: ['mr'],
          session: { permissions: ['schedule'], features: { schedule_drafts: true } },
        } as any,
      },
      global: {
        stubs: {
          'a-drawer': DrawerCaptureStub,
          'a-alert': true,
          'a-button': ButtonStub,
          'a-select': true,
        },
      },
    })
    expect(draftWrapper.get('[data-testid="captured-drawer"]').attributes('data-width')).toBe(
      'min(640px, 100vw)',
    )
    draftWrapper.unmount()

    const endpointWrapper = mount(LLMEndpointSettings, {
      global: {
        stubs: {
          'a-drawer': DrawerCaptureStub,
          'a-alert': true,
          'a-button': ButtonStub,
          'a-form': Slot,
          'a-form-item': Slot,
          'a-select': true,
          'a-switch': true,
          'a-input': true,
          'a-input-password': true,
          'a-checkbox': true,
        },
      },
    })
    expect(endpointWrapper.get('[data-testid="captured-drawer"]').attributes('data-width')).toBe(
      'min(560px, 100vw)',
    )
    endpointWrapper.unmount()
  })

  it('system-config / LlmPerformanceObservability / upload / CDM 响应式断点与滚动容器正确', () => {
    const sysCss = readSrc('views/workstation-v4/styles/system-config.css')
    expect(sysCss).toMatch(/\.mq-segmented\s*\{[^}]*flex-shrink:\s*1;[^}]*flex-wrap:\s*wrap;/s)
    expect(sysCss).toContain('@media (max-width: 1360px)')

    const obsVue = readSrc(
      'views/workstation-v4/components/system-config/LlmPerformanceObservabilityPanel.vue',
    )
    expect(obsVue).toContain('width="min(860px, 100vw)"')
    expect(obsVue).toContain('@media (max-width: 1440px)')
    expect(obsVue).toMatch(/\.llm-observability__billing\s*\{[^}]*auto-fit/s)
    expect(obsVue).toContain('.llm-observability__link:focus-visible')
    expect(obsVue).toContain('var(--mq-text-secondary)')
    expect(obsVue).toContain('var(--mq-text-tertiary)')

    const wsV2Vue = readSrc('views/workstation-v4/WorkstationV2View.vue')
    expect(wsV2Vue).toMatch(/\.ws-v2-main\s*\{[^}]*overflow-y:\s*auto/s)

    const uploadCss = readSrc('views/workstation-v4/styles/data-upload.css')
    expect(uploadCss).toMatch(/\.upload-workstation\s*\{[^}]*overflow-y:\s*auto/s)
    expect(uploadCss).toMatch(/\.upload-dropzone:focus-visible/)

    const cdmVue = readSrc('views/workstation-v4/CDMDataView.vue')
    expect(cdmVue).toMatch(
      /@media \(max-width:\s*1400px\)\s*\{[^}]*repeat\(auto-fit,\s*minmax\(180px,\s*1fr\)\)[\s\S]*200px minmax\(0,\s*1fr\)[\s\S]*repeat\(2,\s*minmax\(0,\s*1fr\)\)/,
    )
    expect(cdmVue).toMatch(/\.cost-total\s*\{[^}]*grid-column:\s*1\s*\/\s*-1/s)
  })
})

describe('Fix 4: 对比度与键盘无障碍补齐', () => {
  it('DataSyncConfigPage 支持 tablist ArrowLeft/ArrowRight 键盘导航并与 tabpanel 关联', async () => {
    const wrapper = mount(DataSyncConfigPage, {
      attachTo: document.body,
      global: {
        stubs: {
          ClinicalSourceSettingsPanel: true,
          DataPipelineSettingsPanel: true,
          FrontpageExtractionSettingsPanel: true,
          AccountManagementPanel: true,
          LLMApiConfig: true,
          DailyQcSchedulePanel: true,
          QcRuntimeSettingsPanel: true,
          LlmPerformanceObservabilityPanel: true,
          ConnectionStudio: true,
          SyncRunPanel: true,
          'a-modal': true,
        },
      },
    })
    await flushPromises()

    const tabs = wrapper.findAll('[role="tab"]')
    expect(tabs.length).toBeGreaterThanOrEqual(4)
    expect(tabs[0].attributes('aria-selected')).toBe('true')
    expect(tabs[0].attributes('tabindex')).toBe('0')
    expect(tabs[1].attributes('tabindex')).toBe('-1')

    const initialPanel = wrapper.get('[role="tabpanel"]')
    expect(initialPanel.attributes('id')).toBe(tabs[0].attributes('aria-controls'))
    expect(initialPanel.attributes('aria-labelledby')).toBe(tabs[0].attributes('id'))

    await tabs[0].trigger('keydown', { key: 'ArrowRight' })
    await flushPromises()
    expect(tabs[1].attributes('aria-selected')).toBe('true')
    expect(tabs[1].attributes('tabindex')).toBe('0')
    const secondPanel = wrapper.get('[role="tabpanel"]')
    expect(secondPanel.attributes('id')).toBe(tabs[1].attributes('aria-controls'))
    expect(secondPanel.attributes('aria-labelledby')).toBe(tabs[1].attributes('id'))

    await tabs[1].trigger('keydown', { key: 'ArrowLeft' })
    await flushPromises()
    expect(tabs[0].attributes('aria-selected')).toBe('true')

    wrapper.unmount()
  })

  it('ClinicalSourceSettingsPanel 错误提示使用 role="alert" 并具备告警样式与输入框 focus-visible', async () => {
    hoisted.clinicalSources.configuration.mockRejectedValueOnce(new Error('network error'))
    const wrapper = mount(ClinicalSourceSettingsPanel)
    await flushPromises()

    const alertEl = wrapper.get('[role="alert"]')
    expect(alertEl.text()).toContain('无法读取数据源配置')
    expect(alertEl.classes()).toContain('source-notice--error')
    wrapper.unmount()

    const sourceText = readSrc(
      'views/workstation-v4/components/system-config/ClinicalSourceSettingsPanel.vue',
    )
    expect(sourceText).toContain('input:focus-visible')
  })

  it('FrontpageExtractionSettingsPanel 与 FieldMappingStep 修正低对比度灰字，FieldMappingStep 去 opacity: 0.7 且补返回按钮属性', async () => {
    const fpSrc = readSrc(
      'views/workstation-v4/components/system-config/FrontpageExtractionSettingsPanel.vue',
    )
    expect(fpSrc).toContain('var(--mq-text-tertiary)')
    expect(fpSrc).toContain('var(--mq-text-secondary)')
    expect(fpSrc).not.toContain('rgba(29, 29, 31, 0.42)')

    const fmSrc = readSrc('views/workstation-v4/frontpage/components/FieldMappingStep.vue')
    expect(fmSrc).not.toMatch(/\.mapping-row-unmapped\s*\{[^}]*opacity:\s*0\.7/s)
    expect(fmSrc).toContain('var(--mq-text-tertiary)')

    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ready: false, suggested_mappings: {}, standard_fields: {} }),
    } as Response)

    const wrapper = mount(FieldMappingStep, {
      props: {
        fileId: 'f-1',
        fileName: 'test.xlsx',
        rowCount: 1,
        columns: ['科室'],
        sampleData: [{ 科室: '内科' }],
      },
      global: {
        stubs: {
          'a-progress': true,
          'a-tag': Slot,
          'a-spin': true,
          'a-select': Slot,
          'a-select-option': true,
          'a-alert': true,
          'a-button': ButtonStub,
        },
      },
    })
    await flushPromises()

    const backBtn = wrapper.get('.mapping-back-btn')
    expect(backBtn.attributes('type')).toBe('button')
    expect(backBtn.attributes('aria-label')).toBeTruthy()
    await backBtn.trigger('click')
    expect(wrapper.emitted('back')).toHaveLength(1)
    wrapper.unmount()
  })

  it('ExcelUploadView 可点击区域支持键盘 Enter/Space，图标按钮补 aria-label 与 type="button"', async () => {
    const wrapper = mount(ExcelUploadView, {
      global: { stubs: { MqIcon: true, FieldMappingStep: true } },
    })

    const dropzone = wrapper.get('.upload-dropzone')
    expect(dropzone.attributes('tabindex')).toBe('0')
    expect(dropzone.attributes('role')).toBe('button')

    const fileInputEl = wrapper.get('input[type="file"]').element as HTMLInputElement
    const clickSpy = vi.spyOn(fileInputEl, 'click').mockImplementation(() => {})
    await dropzone.trigger('keydown.enter')
    await dropzone.trigger('keydown.space')
    expect(clickSpy).toHaveBeenCalledTimes(2)

    const refreshBtn = wrapper.get('.upload-refresh-btn')
    expect(refreshBtn.attributes('type')).toBe('button')
    expect(refreshBtn.attributes('aria-label')).toBeTruthy()
    wrapper.unmount()
  })

  it('CDMDataView 可点击卡片/切换/表签支持 tabindex="0" 与 Enter/Space 键盘交互', async () => {
    mockAuthState.userRoles = ['admin']
    hoisted.clinicalSources.options.mockResolvedValue({
      default_source: 'legacy_pg',
      sources: [{ id: 'legacy_pg', enabled: true, name: '传统库' }],
    })
    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input)
      if (url.endsWith('/stats')) return { ok: true, status: 200, json: async () => ({ total_records: 2 }) } as Response
      if (url.endsWith('/list')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            items: [
              { institute_id: 'H1', patient_id: 'P1', visit_id: 'V1', name: '张一', mr_no: 'M1' },
              { institute_id: 'H1', patient_id: 'P2', visit_id: 'V2', name: '李二', mr_no: 'M2' },
            ],
          }),
        } as Response
      }
      if (url.endsWith('/departments')) return { ok: true, status: 200, json: async () => ['内科'] } as Response
      if (url.endsWith('/schema')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            total_tables: 2,
            tables: [
              { name: 'mr', label: '病案首页', column_count: 1, columns: [{ name: 'mr_no', type: 'text' }] },
              { name: 'diagnosis', label: '诊断', column_count: 1, columns: [{ name: 'diag', type: 'text' }] },
            ],
          }),
        } as Response
      }
      if (url.includes('/frontpage/')) {
        const name = url.includes('P2') ? '李二' : '张一'
        return { ok: true, status: 200, json: async () => ({ name, diagnoses: [] }) } as Response
      }
      if (url.includes('/table-data/')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({ columns: ['mr_no'], items: [{ mr_no: 'M1' }], total: 1, page: 1, page_size: 50 }),
        } as Response
      }
      throw new Error(`Unexpected url: ${url}`)
    })

    const wrapper = mount(CDMDataView, {
      global: {
        stubs: {
          'a-button': ButtonStub,
          'a-alert': true,
          'a-tag': Slot,
          'a-modal': true,
          'a-spin': true,
          'a-badge': true,
          'a-tabs': Slot,
          'a-tab-pane': Slot,
        },
      },
    })
    await flushPromises()

    const toggles = wrapper.findAll('.toggle-btn')
    expect(toggles[0].attributes('tabindex')).toBe('0')
    expect(toggles[1].attributes('tabindex')).toBe('0')
    await toggles[1].trigger('keydown.enter')
    await flushPromises()
    expect(toggles[1].classes()).toContain('active')

    const tableTabs = wrapper.findAll('.table-tab')
    expect(tableTabs[1].attributes('tabindex')).toBe('0')
    await tableTabs[1].trigger('keydown.space')
    await flushPromises()
    expect(tableTabs[1].classes()).toContain('active')

    const patientCards = wrapper.findAll('.patient-card')
    expect(patientCards[1].attributes('tabindex')).toBe('0')
    await patientCards[1].trigger('keydown.enter')
    await flushPromises()
    expect(patientCards[1].classes()).toContain('active')
    expect(wrapper.text()).toContain('李二 — 病案详情')

    wrapper.unmount()
  })
})
