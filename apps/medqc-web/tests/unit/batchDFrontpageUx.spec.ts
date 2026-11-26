import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'

import type {
  FrontpageQcAnalytics,
  FrontpageQcFinding,
  FrontpageQcRecordDetail,
  FrontpageQcRecordItem,
  FrontpageQcRun,
} from '@/services/frontpage-qc-v2-service'

vi.mock('ant-design-vue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('ant-design-vue')>()),
  Modal: {
    name: 'Modal',
    props: ['open'],
    emits: ['cancel'],
    template: '<div v-if="open" class="modal-stub"><slot /></div>',
  },
  Pagination: {
    name: 'Pagination',
    props: ['current', 'pageSize', 'total', 'disabled'],
    emits: ['change'],
    template: '<nav class="pagination-stub" />',
  },
  DatePicker: {
    name: 'ADatePicker',
    props: ['value', 'id'],
    emits: ['update:value'],
    template:
      '<input :id="id" :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
  },
  message: {
    error: vi.fn(),
    success: vi.fn(),
  },
}))

vi.mock('@/views/workstation-v4/customer-sample-validation/batchExport', () => ({
  downloadBlob: vi.fn(),
}))

const testAuth = reactive({
  user: { id: 'global-admin', institute_id: '', roles: ['admin'], is_demo_account: false },
  userRoles: ['admin'],
})

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => testAuth,
}))

const svc = {
  listRecords: vi.fn(),
  getRecord: vi.fn(),
  getFilters: vi.fn(),
  getAnalytics: vi.fn(),
  createRun: vi.fn(),
  getRun: vi.fn(),
  cancelRun: vi.fn(),
  exportRecords: vi.fn(),
  listActive: vi.fn(),
  review: vi.fn(),
}

vi.mock('@/services/frontpage-qc-v2-service', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/frontpage-qc-v2-service')>()
  return {
    ...actual,
    listFrontpageQcRecords: (...a: unknown[]) => svc.listRecords(...a),
    getFrontpageQcRecord: (...a: unknown[]) => svc.getRecord(...a),
    getFrontpageQcFilters: (...a: unknown[]) => svc.getFilters(...a),
    getFrontpageQcAnalytics: (...a: unknown[]) => svc.getAnalytics(...a),
    createFrontpageQcRun: (...a: unknown[]) => svc.createRun(...a),
    getFrontpageQcRun: (...a: unknown[]) => svc.getRun(...a),
    cancelFrontpageQcRun: (...a: unknown[]) => svc.cancelRun(...a),
    exportFrontpageQcRecords: (...a: unknown[]) => svc.exportRecords(...a),
    listActiveFrontpageQcRuns: (...a: unknown[]) => svc.listActive(...a),
    reviewFrontpageQcFinding: (...a: unknown[]) => svc.review(...a),
  }
})

import FrontpageQcAnalysisPanel from '@/views/workstation-v4/frontpage-qc/FrontpageQcAnalysisPanel.vue'
import FrontpageQcPreview from '@/views/workstation-v4/frontpage-qc/FrontpageQcPreview.vue'
import FrontpageQcRecordTable from '@/views/workstation-v4/frontpage-qc/FrontpageQcRecordTable.vue'
import FrontpageQcRunBar from '@/views/workstation-v4/frontpage-qc/FrontpageQcRunBar.vue'
import FrontpageQcView from '@/views/workstation-v4/frontpage-qc/FrontpageQcView.vue'

const SRC_ROOT = resolve(__dirname, '../../src')
const STYLE_DIR = resolve(SRC_ROOT, 'views/workstation-v4/styles')

function readCss(path: string): string {
  return readFileSync(path, 'utf-8')
}

function parseHexRgb(hex: string): [number, number, number] {
  const clean = hex.trim().replace(/^#/, '')
  const value = Number.parseInt(clean, 16)
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255]
}

function blendRgba(
  fg: [number, number, number],
  alpha: number,
  bg: [number, number, number],
): [number, number, number] {
  return [
    Math.round(fg[0] * alpha + bg[0] * (1 - alpha)),
    Math.round(fg[1] * alpha + bg[1] * (1 - alpha)),
    Math.round(fg[2] * alpha + bg[2] * (1 - alpha)),
  ]
}

function relativeLuminance([r, g, b]: [number, number, number]): number {
  const toLinear = (channel: number) => {
    const s = channel / 255
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4)
  }
  return 0.2126 * toLinear(r) + 0.7152 * toLinear(g) + 0.0722 * toLinear(b)
}

function contrastRatio(c1: [number, number, number], c2: [number, number, number]): number {
  const l1 = relativeLuminance(c1)
  const l2 = relativeLuminance(c2)
  return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05)
}

function extractCssVar(css: string, varName: string): string {
  const match = css.match(new RegExp(`${varName}:\\s*([^;]+);`))
  if (!match) throw new Error(`Missing CSS token ${varName}`)
  return match[1].trim()
}

function makeRecord(alias: string, overrides: Partial<FrontpageQcRecordItem> = {}): FrontpageQcRecordItem {
  const key = `H-TEST|P-${alias}|${alias}`
  return {
    institute_id: 'H-TEST',
    patient_id: `P-${alias}`,
    visit_id: alias,
    record_key: key,
    patient_name: `患者${alias}`,
    inpat_no: `ZY-${alias}`,
    mr_no: `MR-${alias}`,
    department: '心血管内科一病区',
    doctor: '',
    discharge_date: '2026-09-15',
    result: {
      id: `res-${alias}`,
      run_id: 'run-0',
      record_key: key,
      department: '心血管内科一病区',
      discharge_date: '2026-09-15',
      score: 88,
      grade: 'qualified',
      fail_count: 2,
      hint_count: 1,
      required_missing_count: 1,
      data_gap_count: 0,
      scorable_ratio: 1,
      completeness_rate: 0.95,
      ruleset_version: '2026.10.13',
      created_at: '2026-10-13T08:00:00',
    },
    ...overrides,
  }
}

function makeFinding(id: string): FrontpageQcFinding {
  return {
    id,
    rule_id: 'C-H21',
    rule_name: '手术者',
    group: 'completeness',
    section: 'diagnosis',
    severity: 'deduct',
    score_item: 'surgeon',
    verdict: 'fail',
    problem: '手术者未填写',
    reason: '',
    details: [{ field: '第1条手术 手术者', value: '', expected: '需填写', item_index: 0 }],
    deduction: 1,
    review_status: 'pending',
    review_note: '',
    reviewed_by: '',
    reviewed_at: null,
  }
}

function makeDetail(item: FrontpageQcRecordItem): FrontpageQcRecordDetail {
  const { result, ...rest } = item
  return {
    record: rest,
    result: result
      ? {
          ...result,
          item_scores: [],
          rule_verdicts: {},
          notes: [],
          findings: [makeFinding('f-1')],
        }
      : null,
    stale: false,
    frontpage: {
      basic: {},
      discharge_diagnoses: [],
      outpatient_diagnoses: [],
      pathology_diagnoses: [],
      surgeries: [],
      cost: null,
    },
  }
}

function makeAnalytics(): FrontpageQcAnalytics {
  return {
    summary: {
      records: 10,
      avg_score: 91.2,
      grades: { excellent: 6, qualified: 3, unqualified: 1 },
      issue_records: 4,
      hint_records: 2,
      required_missing_records: 1,
      data_gap_records: 1,
    },
    indicators: [
      { key: 'completeness', label: '首页填报完整率', numerator: 9, denominator: 10, rate: 0.9 },
      { key: 'diagnosis', label: '主要诊断编码准确率（较长标题测试换行对齐）', numerator: 8, denominator: 10, rate: 0.8 },
    ],
    top_rules: [
      { rule_id: 'C-H21', rule_name: '手术者', severity: 'deduct', group: 'completeness', section: 'diagnosis', records: 3, rate: 0.3 },
    ],
    top_hints: [],
    top_data_gaps: [],
    departments: [
      { department: '心血管内科一病区', records: 10, avg_score: 91.2, excellent_rate: 0.6, issue_records: 4 },
    ],
  }
}

function makeRun(overrides: Partial<FrontpageQcRun> = {}): FrontpageQcRun {
  return {
    id: 'run-1',
    status: 'running',
    ruleset_version: '2026.10.13',
    filters: { mode: 'filtered', department: '内科' },
    total_records: 10,
    processed_records: 3,
    success_count: 3,
    failed_count: 0,
    issue_records: 1,
    data_gap_records: 0,
    failed_records: [],
    error_message: null,
    cancel_requested: false,
    created_by: 'u-1',
    created_at: null,
    started_at: null,
    finished_at: null,
    updated_at: null,
    ...overrides,
  }
}

describe('Batch D UX-1 & UX-2: 1280px–1440px 双栏断点、分页折行、工具栏尺寸与表样式无 !important', () => {
  it('frontpage-qc.css 提前在 max-width: 1440px 收窄预览至 340px、允许分页折行、统一控件高度与日期/科室宽度', () => {
    const css = readCss(resolve(STYLE_DIR, 'frontpage-qc.css'))

    // 1440px 断点提前将右侧预览收窄为 340px，避免 1281-1366px 跳回 400px
    const mq1440 = css.match(/@media\s*\(max-width:\s*1440px\)\s*\{[\s\S]*?\n\}/)
    expect(mq1440).not.toBeNull()
    expect(mq1440![0]).toMatch(/\.fpqc-split\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s+340px/)

    // 分页条支持 flex-wrap: wrap
    expect(css).toMatch(/\.fpqc-list__pager\s*\{[^}]*flex-wrap:\s*wrap/)

    // 日期框放宽至 136px 并统一高度与内边距
    expect(css).toMatch(/\.fpqc-toolbar__date-picker\s*\{[^}]*width:\s*136px/)

    // 科室下拉采用 min-width: 136px; max-width: 180px
    expect(css).toMatch(/select\.fpqc-toolbar__dept\s*\{[^}]*min-width:\s*136px[^}]*max-width:\s*180px/)

    // 页头分段控件与按钮高度统一为 --mq-control-height (36px)，消除 34px/38px 错位
    expect(css).toMatch(/\.fpqc-page\s+\.mq-page-head__actions\s+\.mq-segmented\s*\{[^}]*height:\s*var\(--mq-control-height,\s*36px\)/)
    expect(css).toMatch(/\.fpqc-page\s+\.mq-page-head__actions\s+\.mq-btn\s*\{[^}]*height:\s*var\(--mq-control-height,\s*36px\)/)
  })

  it('frontpage-qc-table.css 消除所有 !important，并在 <=1440px / <=1280px 收紧内边距且允许问题徽标折行', () => {
    const css = readCss(resolve(STYLE_DIR, 'frontpage-qc-table.css'))

    expect(css).not.toContain('!important')
    expect(css).toMatch(/\.mq-table\.fpqc-table\s+th\.fpqc-table__check/)
    expect(css).toMatch(/\.mq-table\.fpqc-table\s+th\.fpqc-table__num/)
    expect(css).toMatch(/\.fpqc-table__issues-list\s*\{[^}]*flex-wrap:\s*wrap/)
    expect(css).toMatch(/@media\s*\(max-width:\s*1440px\)/)
    expect(css).toMatch(/@media\s*\(max-width:\s*1280px\)/)
  })
})

describe('Batch D UX-3: 分析页吸顶表头、rank-row 盒模型与指标卡对齐', () => {
  it('frontpage-qc-analysis.css 覆盖 overflow: visible、收紧单元格内边距、修复 rank-row 盒模型与指标卡底部对齐', () => {
    const css = readCss(resolve(STYLE_DIR, 'frontpage-qc-analysis.css'))

    expect(css).toMatch(/\.fpqc-analysis__table\s*\{[^}]*overflow:\s*visible/)
    expect(css).toMatch(/\.fpqc-analysis__table\s+td,\s*\.fpqc-analysis__table\s+th\s*\{[^}]*padding-right:\s*12px[^}]*padding-left:\s*12px/)
    expect(css).toMatch(/@media\s*\(max-width:\s*1440px\)\s*\{[\s\S]*?padding-right:\s*10px[\s\S]*?padding-left:\s*10px/)
    expect(css).toMatch(/\.fpqc-analysis__rank-row\s*\{[^}]*width:\s*calc\(100%\s*\+\s*16px\)[^}]*box-sizing:\s*border-box/)
    expect(css).toMatch(/\.fpqc-analysis__indicator\s+strong\s*\{[^}]*margin-top:\s*auto/)
  })

  it('FrontpageQcAnalysisPanel 渲染科室排名链接带 title 提示', async () => {
    svc.getAnalytics.mockResolvedValueOnce(makeAnalytics())
    const wrapper = mount(FrontpageQcAnalysisPanel, {
      props: { filters: { data_scope: 'home', department: '', start_date: '', end_date: '' }, refreshKey: 0 },
    })
    await flushPromises()

    const deptBtn = wrapper.get('[data-testid="fpqc-drill-department"]')
    expect(deptBtn.attributes('title')).toBe('心血管内科一病区')
    wrapper.unmount()
  })
})

describe('Batch D UX-4: 预览区固定患者头并消除双滚动条', () => {
  it('frontpage-qc-preview.css 仅下方明细区滚动，外层 overflow: hidden 且头部 flex-shrink: 0', () => {
    const css = readCss(resolve(STYLE_DIR, 'frontpage-qc-preview.css'))

    expect(css).toMatch(/\.fpqc-preview\s*\{[^}]*display:\s*flex[^}]*flex-direction:\s*column[^}]*overflow:\s*hidden/)
    expect(css).toMatch(/\.fpqc-preview__head\s*\{[^}]*flex-shrink:\s*0/)
    expect(css).toMatch(/\.fpqc-preview__body\s*\{[^}]*flex:\s*1\s+1\s+auto[^}]*min-height:\s*0[^}]*overflow-y:\s*auto/)
  })

  it('FrontpageQcPreview 将患者头固定在滚动体之外，明细与问题卡位于 fpqc-preview-body 内', async () => {
    const rec = makeRecord('P1')
    svc.getRecord.mockResolvedValueOnce(makeDetail(rec))

    const wrapper = mount(FrontpageQcPreview, {
      props: { record: rec, refreshKey: 0, runBusy: false },
    })
    await flushPromises()

    const head = wrapper.get('header.fpqc-preview__head')
    const body = wrapper.get('[data-testid="fpqc-preview-body"]')

    expect(head.text()).toContain('患者P1')
    expect(head.get('[data-testid="fpqc-preview-score"]').text()).toBe('88')
    expect(body.find('header.fpqc-preview__head').exists()).toBe(false)
    expect(body.find('dl.fpqc-preview__facts').exists()).toBe(true)
    expect(body.find('[data-testid="fpqc-finding"]').exists()).toBe(true)
    wrapper.unmount()
  })
})

describe('Batch D UX-5: 语义标签、WCAG AA 对比度与键盘/屏幕阅读器无障碍', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    testAuth.user = { id: 'global-admin', institute_id: '', roles: ['admin'], is_demo_account: false }
    testAuth.userRoles = ['admin']
    const r1 = makeRecord('A01')
    svc.listRecords.mockResolvedValue({ items: [r1], total: 1, page: 1, page_size: 15 })
    svc.getRecord.mockResolvedValue(makeDetail(r1))
    svc.getFilters.mockResolvedValue({ departments: ['心血管内科一病区', '外科'], home_institute: 'H-HOME' })
    svc.getAnalytics.mockResolvedValue(makeAnalytics())
    svc.listActive.mockResolvedValue({ items: [] })
  })

  it('tokens-v2.css 四项语义/弱文字颜色在各自底色上均达到 WCAG AA >= 4.5:1', () => {
    const css = readCss(resolve(SRC_ROOT, 'styles/tokens-v2.css'))
    const white = parseHexRgb('#ffffff')
    const pageBg = parseHexRgb(extractCssVar(css, '--mq-bg-page'))
    const glassOnPage = blendRgba(white, 0.62, pageBg)

    const successText = parseHexRgb(extractCssVar(css, '--mq-success-text'))
    const dangerText = parseHexRgb(extractCssVar(css, '--mq-danger-text'))
    const warningText = parseHexRgb(extractCssVar(css, '--mq-warning-text'))
    const tertiaryText = parseHexRgb(extractCssVar(css, '--mq-text-tertiary'))

    const successBgOnPage = blendRgba([52, 199, 89], 0.12, pageBg)
    const dangerBgOnPage = blendRgba([255, 59, 48], 0.1, pageBg)
    const warningBgOnPage = blendRgba([255, 149, 0], 0.1, pageBg)
    const neutralBgOnPage = blendRgba([118, 128, 160], 0.12, pageBg)

    expect(contrastRatio(successText, white)).toBeGreaterThanOrEqual(4.5)
    expect(contrastRatio(successText, successBgOnPage)).toBeGreaterThanOrEqual(4.5)

    expect(contrastRatio(dangerText, white)).toBeGreaterThanOrEqual(4.5)
    expect(contrastRatio(dangerText, dangerBgOnPage)).toBeGreaterThanOrEqual(4.5)

    expect(contrastRatio(warningText, white)).toBeGreaterThanOrEqual(4.5)
    expect(contrastRatio(warningText, warningBgOnPage)).toBeGreaterThanOrEqual(4.5)

    expect(contrastRatio(tertiaryText, white)).toBeGreaterThanOrEqual(4.5)
    expect(contrastRatio(tertiaryText, glassOnPage)).toBeGreaterThanOrEqual(4.5)
    expect(contrastRatio(tertiaryText, neutralBgOnPage)).toBeGreaterThanOrEqual(4.5)
  })

  it('FrontpageQcView 根节点改为 section 无嵌套 main，科室下拉带动态 title，错误与成功提示拆分 role="alert"/role="status"', async () => {
    const wrapper = mount(FrontpageQcView)
    await flushPromises()

    // 根节点是 section，页面内不存在嵌套 <main>
    const root = wrapper.get('[data-testid="frontpage-qc-view"]')
    expect(root.element.tagName).toBe('SECTION')
    expect(wrapper.find('main').exists()).toBe(false)

    // 科室下拉含动态 title 与专用类名
    const deptSelect = wrapper.get('[aria-label="科室筛选"]')
    expect(deptSelect.classes()).toContain('fpqc-toolbar__dept')
    expect(deptSelect.attributes('title')).toBe('全部科室')
    await deptSelect.setValue('心血管内科一病区')
    expect(deptSelect.attributes('title')).toBe('心血管内科一病区')

    // 导出失败展示 role="alert" 的醒目错误提示，而非普通 status 文本
    svc.exportRecords.mockRejectedValueOnce(new Error('当前范围内没有已质控的首页'))
    await wrapper.get('[data-testid="fpqc-export-filtered"]').trigger('click')
    await flushPromises()

    const errorAlert = wrapper.get('[data-testid="fpqc-page-error"]')
    expect(errorAlert.attributes('role')).toBe('alert')
    expect(errorAlert.classes()).toContain('fpqc-page__notice--error')
    expect(errorAlert.text()).toContain('当前范围内没有已质控的首页')
    expect(wrapper.find('[data-testid="fpqc-page-notice"]').exists()).toBe(false)

    // 导出成功后清除错误并展示 role="status" 成功提示
    svc.exportRecords.mockResolvedValueOnce(new Blob(['ok']))
    await wrapper.get('[data-testid="fpqc-export-filtered"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="fpqc-page-error"]').exists()).toBe(false)
    const statusNotice = wrapper.get('[data-testid="fpqc-page-notice"]')
    expect(statusNotice.attributes('role')).toBe('status')
    expect(statusNotice.text()).toContain('已开始下载')

    wrapper.unmount()
  })

  it('FrontpageQcRecordTable 行带 aria-selected，支持 Space/Enter 选择且复选框单元格拦截 keydown 冒泡', async () => {
    const r1 = makeRecord('R1')
    const r2 = makeRecord('R2')
    const wrapper = mount(FrontpageQcRecordTable, {
      props: {
        rows: [r1, r2],
        selected: [],
        activeKey: r1.record_key,
        emptyMessage: '',
      },
    })

    const rows = wrapper.findAll('[data-testid="fpqc-record-row"]')
    expect(rows[0].attributes('aria-selected')).toBe('true')
    expect(rows[1].attributes('aria-selected')).toBe('false')

    // Space 键选择第二行
    await rows[1].trigger('keydown.space')
    expect(wrapper.emitted('select')).toEqual([[r2.record_key]])

    // 在复选框单元格内按 Space / Enter 不得冒泡触发行 select
    const checkCell = rows[1].get('td.fpqc-table__check')
    const checkbox = checkCell.get('input[type="checkbox"]')
    await checkbox.trigger('keydown.space')
    await checkbox.trigger('keydown.enter')
    expect(wrapper.emitted('select')).toHaveLength(1)

    // 问题徽标容器支持紧凑折行
    expect(rows[0].find('td.fpqc-table__issues .fpqc-table__issues-list').exists()).toBe(true)

    wrapper.unmount()
  })

  it('FrontpageQcRunBar 仅状态文本节点带 aria-live="polite"，避免 1.5s 轮询反复播报整条进度栏', () => {
    const wrapper = mount(FrontpageQcRunBar, {
      props: {
        run: makeRun({ processed_records: 4, total_records: 10, error_message: '部分病历异常' }),
        error: '轮询重连中',
        cancelling: false,
      },
    })

    const bar = wrapper.get('[data-testid="fpqc-run-bar"]')
    expect(bar.attributes('aria-live')).toBeUndefined()
    expect(bar.attributes('role')).toBeUndefined()

    const liveNodes = wrapper.findAll('[aria-live]')
    expect(liveNodes).toHaveLength(1)
    expect(liveNodes[0].attributes('data-testid')).toBe('fpqc-run-status')
    expect(liveNodes[0].attributes('aria-live')).toBe('polite')
    expect(liveNodes[0].attributes('role')).toBe('status')

    // 报错说明使用 role="alert"
    const alerts = wrapper.findAll('[role="alert"]')
    expect(alerts).toHaveLength(2)

    wrapper.unmount()
  })
})
