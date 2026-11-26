/* eslint-disable vue/one-component-per-file */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, reactive, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const confirmedResultsOnlyRef = ref(false)

vi.mock('@/composables/useQcResultVisibility', () => ({
  useQcResultVisibility: () => ({
    confirmedResultsOnly: confirmedResultsOnlyRef,
  }),
}))

const hoisted = vi.hoisted(() => ({
  route: {
    path: '/workstation-v5/rules',
    params: { ruleId: 'LX0609-09-01-02' } as Record<string, string>,
    query: {} as Record<string, unknown>,
  },
  routerPush: vi.fn(),
  routerReplace: vi.fn((_loc?: { query?: Record<string, unknown> }) => Promise.resolve()),
  listValidationRules: vi.fn(),
  getValidationRule: vi.fn(),
  fetchSurgeryProcedureCatalog: vi.fn(),
  getEditableMedicalRecordDocuments: vi.fn(),
}))

const reactiveRoute = reactive(hoisted.route)

vi.mock('vue-router', () => ({
  useRoute: () => reactiveRoute,
  useRouter: () => ({
    push: hoisted.routerPush,
    replace: hoisted.routerReplace,
  }),
  onBeforeRouteLeave: vi.fn(),
}))

vi.mock('ant-design-vue', async (importOriginal) => {
  const actual = await importOriginal<typeof import('ant-design-vue')>()
  return {
    ...actual,
    message: {
      success: vi.fn(),
      error: vi.fn(),
      warning: vi.fn(),
      info: vi.fn(),
    },
  }
})

vi.mock('@/services/rule-validation-service', () => ({
  listValidationRules: hoisted.listValidationRules,
  getValidationRule: hoisted.getValidationRule,
  saveCaseAnswer: vi.fn(),
  startValidationRun: vi.fn(),
  concludeRule: vi.fn(),
}))

vi.mock('@/views/workstation-v4/surgery-catalog/service', () => ({
  fetchSurgeryProcedureCatalog: hoisted.fetchSurgeryProcedureCatalog,
}))

vi.mock('@/services/manual-case-sample-service', () => ({
  createManualTestMedicalRecord: vi.fn(),
  getEditableMedicalRecordDocuments: hoisted.getEditableMedicalRecordDocuments,
  getEditableMedicalRecordDocument: vi.fn(),
}))

import WorkstationRulesView from '@/views/workstation-v4/WorkstationRulesView.vue'
import RuleValidationListView from '@/views/workstation-v4/rule-validation/RuleValidationListView.vue'
import RuleValidationDetailView from '@/views/workstation-v4/rule-validation/RuleValidationDetailView.vue'
import RuleValidationNewCaseView from '@/views/workstation-v4/rule-validation/RuleValidationNewCaseView.vue'
import SurgeryProcedureCatalogView from '@/views/workstation-v4/components/SurgeryProcedureCatalogView.vue'
import QCRecordCompareWorkbench from '@/views/workstation-v4/semantic-rules/components/QCRecordCompareWorkbench.vue'
import SemanticRulesTableSection from '@/views/workstation-v4/semantic-rules/components/SemanticRulesTableSection.vue'
import SemanticRuleTestModal from '@/views/workstation-v4/semantic-rules/components/modals/SemanticRuleTestModal.vue'
import type { SemanticRuleItem } from '@/views/workstation-v4/semantic-rules/types'

const SRC_ROOT = resolve(__dirname, '../../src')
const readSrc = (relPath: string) => readFileSync(resolve(SRC_ROOT, relPath), 'utf8')

const passthrough = defineComponent({
  setup(_, { slots, attrs }) {
    return () => h('div', attrs, slots.default?.())
  },
})

const AButtonStub = defineComponent({
  inheritAttrs: false,
  props: { disabled: Boolean, loading: Boolean },
  emits: ['click'],
  setup(props, { slots, attrs, emit }) {
    return () =>
      h(
        'button',
        {
          type: 'button',
          ...attrs,
          disabled: props.disabled,
          onClick: (e: MouseEvent) => {
            if (!props.disabled) emit('click', e)
          },
        },
        slots.default?.(),
      )
  },
})

const AModalStub = defineComponent({
  props: { open: Boolean },
  setup(props, { slots }) {
    return () => (props.open ? h('div', { class: 'a-modal-stub' }, slots.default?.()) : null)
  },
})

const RouterLinkStub = defineComponent({
  props: ['to'],
  setup(props, { slots, attrs }) {
    return () => h('a', { ...attrs, 'data-to': JSON.stringify(props.to) }, slots.default?.())
  },
})

const demoRule: SemanticRuleItem = {
  rule_id: 'SC-001',
  rule_code: 'SC-001',
  name: '入院记录完成时效性检查',
  description: '入院记录应在 24 小时内完成',
  category: '入院记录',
  complexity: '低复杂度',
  defect_level: '严重缺陷',
  score_deduction: 3,
  applicable_documents: ['admission_record'],
  medical_domain: '通用',
  requires_rag: false,
  requires_cot: false,
}

beforeEach(() => {
  vi.clearAllMocks()
  confirmedResultsOnlyRef.value = false
  reactiveRoute.path = '/workstation-v5/rules'
  reactiveRoute.params = { ruleId: 'LX0609-09-01-02' }
  reactiveRoute.query = {}
  hoisted.routerReplace.mockImplementation((loc?: { query?: Record<string, unknown> }) => {
    if (loc?.query) reactiveRoute.query = { ...loc.query }
    return Promise.resolve()
  })
  hoisted.listValidationRules.mockResolvedValue({ success: true, data: { items: [] } })
  hoisted.getValidationRule.mockResolvedValue({
    success: true,
    data: {
      rule: {
        rule_id: 'LX0609-09-01-02',
        name: '抢救记录完整性',
        source_document: '抢救记录',
        release_scope: 'acceptance_only',
        policy_summary: '口径',
      },
      stage: 'preparing',
      cases: [],
      coverage: {
        counts: {
          compliant: { synthetic: 0, real_copy: 0 },
          non_compliant: { synthetic: 0, real_copy: 0 },
          not_applicable: { synthetic: 0, real_copy: 0 },
          data_gap: { synthetic: 0, real_copy: 0 },
        },
        gaps: [],
        acceptance_cases: 0,
      },
      runs: [],
      latest_run_rows: [],
      acceptance_blockers: [],
      regression_gaps: [],
      events: [],
    },
  })
  hoisted.fetchSurgeryProcedureCatalog.mockResolvedValue({
    version: '2026-v1',
    total: 10,
    page: 1,
    page_size: 20,
    summary: { total: 10, surgery: 6, level_four_surgery: 2, operation: 4 },
    policy: {
      level_priority: '以手术分级目录为准',
      conditional_level_four: '特殊情形按四级判定',
      category_boundary: '区分手术与非手术操作',
    },
    filter_options: { categories: ['手术'], levels: ['四级'], sources: [] },
    items: [],
  })
  hoisted.getEditableMedicalRecordDocuments.mockResolvedValue({
    success: true,
    data: { documents: [] },
  })
})

describe('T1-Batch 4: 1. 消除 5 处嵌套 <main> 地标', () => {
  const fiveFiles = [
    'views/workstation-v4/components/SurgeryProcedureCatalogView.vue',
    'views/workstation-v4/rule-validation/RuleValidationListView.vue',
    'views/workstation-v4/rule-validation/RuleValidationDetailView.vue',
    'views/workstation-v4/rule-validation/RuleValidationNewCaseView.vue',
    'views/workstation-v4/semantic-rules/components/QCRecordCompareWorkbench.vue',
  ]

  it.each(fiveFiles)('%s 源码中不再包含嵌套 <main> 标签', (relPath) => {
    const src = readSrc(relPath)
    expect(src).not.toMatch(/<main\b/i)
    expect(src).not.toMatch(/<\/main>/i)
  })

  it('5 个视图组件渲染后均不产出 <main> 元素', async () => {
    const commonStubs = {
      'a-button': AButtonStub,
      'a-input': passthrough,
      'a-select': passthrough,
      'a-select-option': passthrough,
      'a-table': passthrough,
      'a-empty': passthrough,
      'a-alert': passthrough,
      'a-spin': passthrough,
      'a-modal': AModalStub,
      'a-textarea': passthrough,
      'a-date-picker': passthrough,
      'a-radio-group': passthrough,
      'a-radio': passthrough,
      RouterLink: RouterLinkStub,
      CaseAnswerModal: true,
      CaseReviewDrawer: true,
      ApprovalModal: true,
      RegressionComparison: true,
      ReadonlyMedicalDocumentDirectory: true,
      SingleRecordQcResultPanel: true,
      HospitalLoading: true,
    }

    const w1 = mount(SurgeryProcedureCatalogView, { global: { stubs: commonStubs } })
    const w2 = mount(RuleValidationListView, { global: { stubs: commonStubs } })
    const w3 = mount(RuleValidationDetailView, { global: { stubs: commonStubs } })
    const w4 = mount(RuleValidationNewCaseView, { global: { stubs: commonStubs } })
    const w5 = mount(QCRecordCompareWorkbench, {
      props: { visitId: 'V1', issues: [], providedDocuments: [] },
      global: { stubs: commonStubs },
    })
    await flushPromises()

    for (const wrapper of [w1, w2, w3, w4, w5]) {
      expect(wrapper.find('main').exists()).toBe(false)
      expect(wrapper.find('section').exists()).toBe(true)
      wrapper.unmount()
    }
  })
})

describe('T1-Batch 4: 2. 1280px–1440px 布局防溢出与挤压', () => {
  it('RuleValidationNewCaseView 与 rule-validation.css 断点提升至 1360px 且支持折行', () => {
    const newCaseSrc = readSrc('views/workstation-v4/rule-validation/RuleValidationNewCaseView.vue')
    const rvCss = readSrc('views/workstation-v4/rule-validation/styles/rule-validation.css')

    expect(newCaseSrc).toMatch(/@media\s*\(max-width:\s*1360px\)\s*\{[\s\S]*?\.nc-layout\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\);/)
    expect(newCaseSrc).toMatch(/\.nc-doc__head\s*\{[\s\S]*?flex-wrap:\s*wrap;/)
    expect(newCaseSrc).toMatch(/\.nc-grid\s+\.mq-input[\s\S]*?min-width:\s*0;/)

    expect(rvCss).toMatch(/\.rv-steps\s*\{[\s\S]*?flex-wrap:\s*wrap;/)
    expect(rvCss).toMatch(/@media\s*\(max-width:\s*1360px\)\s*\{[\s\S]*?\.rv-steps\s*\{[\s\S]*?flex-wrap:\s*wrap;/)
    expect(rvCss).toMatch(/@media\s*\(max-width:\s*1360px\)\s*\{[\s\S]*?\.rv-step__copy\s*\{[\s\S]*?white-space:\s*normal;/)
  })

  it('SurgeryProcedureCatalogView 收紧 1280px 筛选栏、成组操作按钮与表格列宽（无强制横滚）', () => {
    const src = readSrc('views/workstation-v4/components/SurgeryProcedureCatalogView.vue')
    const styleBlock = src.slice(src.indexOf('<style scoped>'), src.indexOf('</style>'))

    expect(src).toContain('class="filter-actions"')
    expect(src).toContain(':scroll="{ x: 840 }"')
    expect(src).not.toContain(':scroll="{ x: 1020 }"')

    // v7.1 覆盖位于 @media 之前，避免覆盖响应式断点
    const v71Idx = styleBlock.indexOf('v7.1 液态玻璃覆盖')
    const firstMediaIdx = styleBlock.search(/@media\s*\(/)
    expect(v71Idx).toBeGreaterThan(0)
    expect(firstMediaIdx).toBeGreaterThan(v71Idx)
    expect(styleBlock).toMatch(/@media\s*\(max-width:\s*1360px\)/)
  })

  it('CustomQCExperienceView 1280px–1440px 左栏筛选网格独立展开关键词行防止压扁输入框', () => {
    const src = readSrc('views/workstation-v4/CustomQCExperienceView.vue')
    expect(src).toContain('class="custom-qc-record-filters"')
    expect(src).toContain('class="custom-qc-record-filters__keyword-row"')
    expect(src).not.toContain('lg:grid-cols-[160px_220px_1fr_auto]')
    expect(src).toMatch(/@media\s*\(max-width:\s*1440px\)\s*\{[\s\S]*?\.custom-qc-record-filters__keyword-row\s*\{[\s\S]*?grid-column:\s*1\s*\/\s*-1;[\s\S]*?minmax\(180px,\s*1fr\)/)
  })

  it('semantic-rules-table.css 与 SemanticRulesTableSection.vue 收紧 1280px 筛选与固定列宽', () => {
    const css = readSrc('views/workstation-v4/semantic-rules/components/styles/semantic-rules-table.css')
    const vueSrc = readSrc('views/workstation-v4/semantic-rules/components/SemanticRulesTableSection.vue')

    expect(css).toMatch(/@media\s*\(max-width:\s*1360px\)\s*\{[\s\S]*?\.query-input[\s\S]*?\.query-select/)
    expect(vueSrc).toMatch(/key:\s*'index',\s*width:\s*52/)
    expect(vueSrc).toMatch(/key:\s*'rule_id',\s*width:\s*142/)
    expect(vueSrc).toMatch(/key:\s*'release_scope',\s*width:\s*92/)
    expect(vueSrc).toMatch(/key:\s*'applicable_documents',\s*width:\s*116/)
    expect(vueSrc).toMatch(/key:\s*'execution_status',\s*width:\s*96/)
  })
})

describe('T1-Batch 4: 3. CSS 冲突、!important 与固定列透明穿透清理', () => {
  it('WorkstationRulesView 为固定列设置实色背景并消除非 scoped 样式污染', () => {
    const src = readSrc('views/workstation-v4/WorkstationRulesView.vue')
    expect(src).not.toMatch(/<style(?:\s+[^>]*)?>[\s\S]*?workstation-v4-view\.css/)
    expect(src).not.toMatch(/<style\s*>/)
    expect(src).toMatch(/\.ant-table-cell-fix-left[\s\S]*?\.ant-table-cell-fix-right\)\s*\{\s*background:\s*var\(--mq-bg-surface\);/)
    expect(src).not.toMatch(/\.ant-table-cell-fix-left[^{]*\{[^}]*background:\s*transparent/)
  })

  it('SurgeryProcedureCatalogView 移除反向覆写胶囊按钮的 border-radius: 8px !important', () => {
    const src = readSrc('views/workstation-v4/components/SurgeryProcedureCatalogView.vue')
    expect(src).not.toMatch(/border-radius:\s*8px\s*!important/)
    expect(src).toMatch(/\.filter-bar\s*:deep\(\.ant-btn\)\s*\{[\s\S]*?border-radius:\s*999px;/)
  })

  it('CustomRuleWorkspaceView 移除硬编码 #f5f5f7 并复用 --mq-* token', () => {
    const src = readSrc('views/rules/CustomRuleWorkspaceView.vue')
    expect(src).not.toContain('#f5f5f7')
    expect(src).toContain('--panel-bg: var(--mq-glass-bg)')
    expect(src).toContain('--ink-strong: var(--mq-text-primary)')
    expect(src).toContain('--ink-subtle: var(--mq-text-tertiary)')
  })
})

describe('T1-Batch 4: 4. WCAG AA 对比度与键盘/读屏无障碍', () => {
  const contrastFiles = [
    'views/rules/CustomRuleWorkspaceView.vue',
    'views/workstation-v4/semantic-rules/components/modals/SemanticRuleDetailModal.vue',
    'views/workstation-v4/semantic-rules/components/modals/SemanticRuleTestModal.vue',
    'views/workstation-v4/components/SurgeryProcedureCatalogView.vue',
  ]

  it.each(contrastFiles)('%s 不存在低对比度灰字（0.38–0.46）并使用 --mq-text-* token', (relPath) => {
    const src = readSrc(relPath)
    expect(src).not.toMatch(/rgba\(\s*29,\s*29,\s*31,\s*0\.(?:3\d?|4\d?)\s*\)/)
    expect(src).toContain('var(--mq-text-tertiary)')
    expect(src).toContain('var(--mq-text-secondary)')
  })

  it('semantic-rules-table.css 移除 font-size: 0 + color: transparent + ::before 下拉文字覆写黑客写法', () => {
    const css = readSrc('views/workstation-v4/semantic-rules/components/styles/semantic-rules-table.css')
    expect(css).not.toMatch(/font-size:\s*0\b/)
    expect(css).not.toMatch(/(?<![-\w])color:\s*transparent\b/)
    expect(css).not.toMatch(/\.ant-select-selection-item\)::before/)
  })

  it('WorkstationRulesView 补齐 tablist/tab aria-controls、tabpanel 及方向键导航', async () => {
    reactiveRoute.query = { tab: 'coding' }
    const wrapper = mount(WorkstationRulesView, {
      global: {
        stubs: {
          CodingRulesTab: { template: '<div data-testid="panel-coding" />' },
          FrontpageRulesTab: { template: '<div data-testid="panel-frontpage" />' },
          SettlementRulesTab: { template: '<div data-testid="panel-settlement" />' },
          WorkstationSemanticRulesView: { template: '<div data-testid="panel-semantic" />' },
        },
      },
    })
    await flushPromises()

    const tabs = wrapper.findAll('[role="tab"]')
    expect(tabs).toHaveLength(4)
    expect(tabs[0].attributes('aria-selected')).toBe('true')
    expect(tabs[0].attributes('aria-controls')).toBe('rules-tabpanel-coding')
    expect(tabs[0].attributes('tabindex')).toBe('0')
    expect(tabs[1].attributes('tabindex')).toBe('-1')

    const panel = wrapper.get('[role="tabpanel"]')
    expect(panel.attributes('id')).toBe('rules-tabpanel-coding')
    expect(panel.attributes('aria-labelledby')).toBe('rules-tab-coding')

    // ArrowRight 切到 frontpage
    await tabs[0].trigger('keydown', { key: 'ArrowRight' })
    await flushPromises()
    expect(wrapper.get('[role="tabpanel"]').attributes('id')).toBe('rules-tabpanel-frontpage')
    expect(tabs[1].attributes('aria-selected')).toBe('true')

    // End 切到 semantic
    await tabs[1].trigger('keydown', { key: 'End' })
    await flushPromises()
    expect(tabs[3].attributes('aria-selected')).toBe('true')

    // ArrowLeft 回到 settlement
    await tabs[3].trigger('keydown', { key: 'ArrowLeft' })
    await flushPromises()
    expect(tabs[2].attributes('aria-selected')).toBe('true')

    // Home 回到 coding
    await tabs[2].trigger('keydown', { key: 'Home' })
    await flushPromises()
    expect(tabs[0].attributes('aria-selected')).toBe('true')

    wrapper.unmount()
  })

  it('RuleValidationListView 补齐 tablist/tab aria-controls、tabpanel 及方向键导航', async () => {
    const wrapper = mount(RuleValidationListView, {
      global: {
        stubs: {
          'a-alert': passthrough,
          'a-input': passthrough,
          'a-spin': passthrough,
          RouterLink: RouterLinkStub,
        },
      },
    })
    await flushPromises()

    const tabs = wrapper.findAll('[role="tab"]')
    expect(tabs).toHaveLength(3)
    expect(tabs[0].attributes('aria-selected')).toBe('true')
    expect(tabs[0].attributes('aria-controls')).toBe('rv-scope-panel-pending')
    expect(tabs[0].attributes('tabindex')).toBe('0')
    expect(tabs[1].attributes('tabindex')).toBe('-1')

    const panel = wrapper.get('[role="tabpanel"]')
    expect(panel.attributes('id')).toBe('rv-scope-panel-pending')
    expect(panel.attributes('aria-labelledby')).toBe('rv-scope-tab-pending')

    await tabs[0].trigger('keydown', { key: 'ArrowRight' })
    await flushPromises()
    expect(tabs[1].attributes('aria-selected')).toBe('true')
    expect(wrapper.get('[role="tabpanel"]').attributes('id')).toBe('rv-scope-panel-released')

    await tabs[1].trigger('keydown', { key: 'ArrowLeft' })
    await flushPromises()
    expect(tabs[0].attributes('aria-selected')).toBe('true')

    await tabs[0].trigger('keydown', { key: 'End' })
    await flushPromises()
    expect(tabs[2].attributes('aria-selected')).toBe('true')
    expect(wrapper.get('[role="tabpanel"]').attributes('id')).toBe('rv-scope-panel-all')

    wrapper.unmount()
  })

  it('SurgeryProcedureCatalogView、SemanticRulesTableSection、SemanticRuleTestModal 原生 <button> 补齐 type="button" 与 aria-pressed', async () => {
    const catalog = mount(SurgeryProcedureCatalogView, {
      global: {
        stubs: {
          'a-button': AButtonStub,
          'a-input': passthrough,
          'a-select': passthrough,
          'a-select-option': passthrough,
          'a-table': passthrough,
          'a-empty': passthrough,
        },
      },
    })
    await flushPromises()

    const summaryButtons = catalog.findAll('.summary-strip button')
    expect(summaryButtons).toHaveLength(4)
    for (const btn of summaryButtons) {
      expect(btn.attributes('type')).toBe('button')
      expect(['true', 'false']).toContain(btn.attributes('aria-pressed'))
    }
    expect(summaryButtons[0].attributes('aria-pressed')).toBe('true')
    await summaryButtons[1].trigger('click')
    await flushPromises()
    expect(summaryButtons[1].attributes('aria-pressed')).toBe('true')
    expect(summaryButtons[0].attributes('aria-pressed')).toBe('false')
    catalog.unmount()

    const tableSection = mount(SemanticRulesTableSection, {
      props: {
        loading: false,
        rules: [demoRule],
        total: 1,
        ruleSetKey: '',
        ruleSetOptions: [],
        keywordInput: '',
        complexity: '',
        defectLevel: '',
        documentType: '',
        complexityOptions: [],
        defectOptions: [],
        documentOptions: [],
        pagination: { current: 1, pageSize: 10, total: 1 },
      },
      global: {
        stubs: {
          ProQueryBar: passthrough,
          ProStandardTable: defineComponent({
            props: ['columns', 'dataSource'],
            template:
              '<div><template v-for="c in columns" :key="c.key"><slot name="bodyCell" :column="c" :record="dataSource[0]" :index="0" /></template></div>',
          }),
          'a-button': AButtonStub,
          'a-input': passthrough,
          'a-select': defineComponent({
            setup(_, { attrs, slots }) {
              return () => h('select', attrs, slots.default?.())
            },
          }),
          'a-select-option': passthrough,
          RouterLink: RouterLinkStub,
        },
      },
    })
    expect(tableSection.get('button.rule-main-title').attributes('type')).toBe('button')
    expect(tableSection.find('select[aria-label="切换规则集"]').exists()).toBe(true)
    tableSection.unmount()

    const testModal = mount(SemanticRuleTestModal, {
      props: {
        open: true,
        rule: demoRule,
        exampleType: 'negative',
        medicalText: '病历内容',
        loading: false,
        result: null,
      },
      global: {
        stubs: {
          'a-modal': AModalStub,
          'a-button': AButtonStub,
          'a-textarea': passthrough,
          'a-alert': passthrough,
        },
      },
    })
    const toggleButtons = testModal.findAll('.test-example-switch button')
    expect(toggleButtons).toHaveLength(2)
    expect(toggleButtons[0].attributes('type')).toBe('button')
    expect(toggleButtons[1].attributes('type')).toBe('button')
    expect(toggleButtons[0].attributes('aria-pressed')).toBe('true')
    expect(toggleButtons[1].attributes('aria-pressed')).toBe('false')
    testModal.unmount()
  })
})
