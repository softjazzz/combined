import fs from 'node:fs'
import path from 'node:path'
import { flushPromises, mount } from '@vue/test-utils'
import { ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import QcDiagnosticExport from '@/components/qc/QcDiagnosticExport.vue'
import QcRecordReviewPreview from '@/views/workstation-v4/components/qc/QcRecordReviewPreview.vue'
import type { QcRecordResultRow } from '@/views/workstation-v4/components/qc/QcRecordResultTable.vue'
import type { SingleRecordQcResultPayload } from '@/views/workstation-v4/customer-sample-validation/single-record-result-model'

const { getLatestResult } = vi.hoisted(() => ({
  getLatestResult: vi.fn(),
}))

const confirmedOnlyState = ref(true)

vi.mock('@/composables/useQcResultVisibility', () => ({
  useQcResultVisibility: () => ({
    confirmedResultsOnly: confirmedOnlyState,
  }),
}))

vi.mock('@/services/sichuan-rule-workspace-service', () => ({
  getLatestLuxian0609RecordResult: getLatestResult,
}))

vi.mock('@/components/qc/CaseCommunicationPanel.vue', () => ({
  default: {
    props: ['instituteId', 'patientId', 'visitId', 'scene', 'jobId'],
    template: '<div data-testid="case-communication-entry" />',
  },
}))

const runningQcRefinedCssPath = path.resolve(
  __dirname,
  '../../src/views/workstation-v4/styles/running-qc-refined.css',
)
const previewVuePath = path.resolve(
  __dirname,
  '../../src/views/workstation-v4/components/qc/QcRecordReviewPreview.vue',
)

const sampleRow: QcRecordResultRow = {
  recordKey: '["H-1","P-1","V-1001"]',
  instituteId: 'H-1',
  patientId: 'P-1',
  visitId: 'V-1001',
  patientName: '张敏',
  department: '重症医学科',
  resultStatus: 'priority',
  resultLabel: '需优先复核',
  issueSummary: '确定问题 2',
  latestQcTime: '2026-08-12 11:30',
}

function makeReadyPayload(): SingleRecordQcResultPayload {
  return {
    schema_version: 'lx0609-single-record-result-v1',
    state: 'ready',
    reason_code: '',
    record_ref: 'authorized-record',
    job_id: 'job-layout-1',
    expected_rule_count: 1,
    result_rule_count: 1,
    is_complete: true,
    items: [
      {
        rule_id: 'LX0609-01-01-01',
        rule_name: '入院记录：缺少签名',
        status: 'non_compliant',
        conclusion: '入院记录未见经治医师签名',
        source_document: '入院记录',
      },
    ],
  }
}

function extractMediaBlock(css: string, mediaHeader: string): string {
  const start = css.indexOf(mediaHeader)
  if (start === -1) return ''
  const openBrace = css.indexOf('{', start)
  if (openBrace === -1) return ''
  let depth = 0
  for (let i = openBrace; i < css.length; i += 1) {
    if (css[i] === '{') depth += 1
    else if (css[i] === '}') {
      depth -= 1
      if (depth === 0) return css.slice(openBrace + 1, i)
    }
  }
  return ''
}

function extractRuleNumber(block: string, selectorFragment: string, prop: string): number {
  const escapedSelector = selectorFragment.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const ruleRegex = new RegExp(`${escapedSelector}[^{]*\\{([^}]*)\\}`, 'g')
  let matchedValue = Number.NaN
  let match: RegExpExecArray | null
  while ((match = ruleRegex.exec(block)) !== null) {
    const body = match[1] ?? ''
    const propRegex = new RegExp(`${prop}\\s*:\\s*(\\d+(?:\\.\\d+)?)px`)
    const propMatch = propRegex.exec(body)
    if (propMatch) matchedValue = Number(propMatch[1])
  }
  return matchedValue
}

describe('Running & Final QC layout fixes (1280×800 / 1366×860 / 1440×900)', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    )
    confirmedOnlyState.value = true
    getLatestResult.mockReset()
    getLatestResult.mockResolvedValue({ success: true, data: makeReadyPayload() })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('P1 #5a: eliminates 760px table min-width overflow and keeps the action column fully visible across 1280 / 1366 / 1440', () => {
    const css = fs.readFileSync(runningQcRefinedCssPath, 'utf-8')

    // 1) Compact review table overrides child min-width: 760px with fluid 100% fixed layout
    expect(css).toContain(
      '.running-qc-apple :deep(.qc-record-result-table--compact-review .qc-record-result-table__table)',
    )
    expect(css).toContain('width: 100%;')
    expect(css).toContain('min-width: 0;')
    expect(css).toContain('table-layout: fixed;')
    // Patient column clears child min-width: 180px so flexible allocation never triggers horizontal scroll
    expect(css).toContain(
      '.running-qc-apple :deep(.qc-record-result-table--compact-review .qc-record-result-table__table th:nth-child(2))',
    )

    // 2) Verify responsive split & column width budgets leave generous patient width with zero overflow
    const media1440 = extractMediaBlock(css, '@media (max-width: 1440px)')
    const media1380 = extractMediaBlock(css, '@media (max-width: 1380px)')
    const media1300 = extractMediaBlock(css, '@media (max-width: 1300px)')

    expect(media1440).toContain('grid-template-columns: minmax(0, 1fr) 320px;')
    expect(media1380).toContain('grid-template-columns: minmax(0, 1fr) 308px;')
    expect(media1300).toContain('grid-template-columns: minmax(0, 1fr) 296px;')

    const siderAndScrollbar = 254 + 17
    const viewportChecks = [
      {
        label: '1440x900',
        viewportWidth: 1440,
        pagePadX: 32,
        previewWidth: 320,
        splitGap: 12,
        listPadAndBorderX: 22,
        fixedCols: [
          extractRuleNumber(media1440, 'th:nth-child(1)', 'width'),
          extractRuleNumber(media1440, 'th:nth-child(3)', 'width'),
          extractRuleNumber(media1440, 'th:nth-child(4)', 'width'),
          extractRuleNumber(media1440, 'th:nth-child(5)', 'width'),
          extractRuleNumber(media1440, 'th:nth-child(6)', 'width'),
        ],
      },
      {
        label: '1366x860',
        viewportWidth: 1366,
        pagePadX: 28,
        previewWidth: 308,
        splitGap: 12,
        listPadAndBorderX: 18,
        fixedCols: [
          extractRuleNumber(media1440, 'th:nth-child(1)', 'width'),
          extractRuleNumber(media1380, 'th:nth-child(3)', 'width'),
          extractRuleNumber(media1380, 'th:nth-child(4)', 'width'),
          extractRuleNumber(media1380, 'th:nth-child(5)', 'width'),
          extractRuleNumber(media1380, 'th:nth-child(6)', 'width'),
        ],
      },
      {
        label: '1280x800',
        viewportWidth: 1280,
        pagePadX: 24,
        previewWidth: 296,
        splitGap: 10,
        listPadAndBorderX: 18,
        fixedCols: [
          extractRuleNumber(media1300, 'th:nth-child(1)', 'width'),
          extractRuleNumber(media1300, 'th:nth-child(3)', 'width'),
          extractRuleNumber(media1300, 'th:nth-child(4)', 'width'),
          extractRuleNumber(media1300, 'th:nth-child(5)', 'width'),
          extractRuleNumber(media1300, 'th:nth-child(6)', 'width'),
        ],
      },
    ]

    for (const check of viewportChecks) {
      const containerWidth =
        check.viewportWidth -
        siderAndScrollbar -
        check.pagePadX -
        check.previewWidth -
        check.splitGap -
        check.listPadAndBorderX
      const fixedSum = check.fixedCols.reduce((acc, width) => acc + width, 0)
      const actionWidth = check.fixedCols[4]!
      const deptWidth = check.fixedCols[1]!
      const patientWidth = containerWidth - fixedSum

      expect(Number.isFinite(fixedSum), `${check.label} fixed widths parsed`).toBe(true)
      // Action column fits both 「查看病历」 and 「查看结果」 pills cleanly
      expect(actionWidth, `${check.label} action width`).toBeGreaterThanOrEqual(140)
      // Department column remains readable without over-truncation
      expect(deptWidth, `${check.label} department width`).toBeGreaterThanOrEqual(88)
      // Flexible patient / visitId column retains ample width so total table never overflows container
      expect(patientWidth, `${check.label} patient width`).toBeGreaterThanOrEqual(165)
    }
  })

  it('P1 #5b: opens the Excel export dropdown to the right (left: 0; right: auto) when toolbar wraps at <= 1480px so sidebar never clips it', () => {
    const css = fs.readFileSync(runningQcRefinedCssPath, 'utf-8')
    const media1480 = extractMediaBlock(css, '@media (max-width: 1480px)')
    const media1100 = extractMediaBlock(css, '@media (max-width: 1100px)')

    // Toolbar creates clean stacking context with visible overflow for dropdowns
    expect(css).toContain('.running-qc-apple .qc-record-result-list-view__toolbar')
    expect(css).toContain('overflow: visible;')
    expect(css).toContain('z-index: 40;')

    // At 1280 / 1366 / 1440 (covered by <= 1480px), dropdown anchors to left edge of trigger
    expect(media1480).toContain('.running-qc-apple .qc-record-result-list-view__export-options')
    expect(media1480).toContain('left: 0;')
    expect(media1480).toContain('right: auto;')
    expect(media1480).toContain('max-width: min(260px, calc(100vw - 32px));')

    // At <= 1100px, toolbar actions right-align so dropdown flips back to right: 0; left: auto
    expect(media1100).toContain('.running-qc-apple .qc-record-result-list-view__export-options')
    expect(media1100).toContain('right: 0;')
    expect(media1100).toContain('left: auto;')
  })

  it('P1 #5c: keeps 「复核预览」 title and 「查看完整质控结果」 button on a single non-wrapping row in both demo and full modes', async () => {
    const css = fs.readFileSync(runningQcRefinedCssPath, 'utf-8')
    const previewSource = fs.readFileSync(previewVuePath, 'utf-8')

    // CSS guarantees single-row flex-wrap: nowrap header row and nowrap title/button
    expect(previewSource).toContain('.preview-heading-main')
    expect(previewSource).toContain('flex-wrap: nowrap;')
    expect(previewSource).toContain('white-space: nowrap;')
    expect(css).toContain('.running-qc-apple :deep(.preview-heading-main)')
    expect(css).toContain('flex-wrap: nowrap;')
    expect(css).toContain('.running-qc-apple :deep(.preview-heading h2)')

    // Customer / demo mode (confirmedResultsOnly = true): single heading row, no diagnostic export row
    confirmedOnlyState.value = true
    const demoWrapper = mount(QcRecordReviewPreview, {
      props: { row: sampleRow, carePhase: 'inpatient' },
      global: { stubs: { 'a-button': true, 'a-modal': true, 'a-alert': true, 'a-checkbox': true } },
    })
    await flushPromises()

    const demoHeadingMain = demoWrapper.get('.preview-heading .preview-heading-main')
    expect(demoHeadingMain.find('.preview-heading-title h2').text()).toBe('复核预览')
    expect(demoHeadingMain.find('.preview-primary-action .full-result-button').text()).toContain(
      '查看完整质控结果',
    )
    expect(demoWrapper.find('.preview-heading-actions').exists()).toBe(false)
    await demoHeadingMain.get('.full-result-button').trigger('click')
    expect(demoWrapper.emitted('open-full')).toEqual([[sampleRow.recordKey]])
    demoWrapper.unmount()

    // Full / admin mode (confirmedResultsOnly = false): primary button still shares row 1 with title,
    // while diagnostic export lives in its own secondary row so it never pushes the primary CTA down
    confirmedOnlyState.value = false
    const fullWrapper = mount(QcRecordReviewPreview, {
      props: { row: sampleRow, carePhase: 'discharged' },
      global: { stubs: { 'a-button': true, 'a-modal': true, 'a-alert': true, 'a-checkbox': true } },
    })
    await flushPromises()

    const fullHeadingMain = fullWrapper.get('.preview-heading .preview-heading-main')
    expect(fullHeadingMain.find('.preview-heading-title h2').text()).toBe('复核预览')
    expect(fullHeadingMain.find('.preview-primary-action .full-result-button').exists()).toBe(true)
    expect(fullHeadingMain.findComponent(QcDiagnosticExport).exists()).toBe(false)
    expect(
      fullWrapper.get('.preview-heading .preview-heading-actions').findComponent(QcDiagnosticExport).exists(),
    ).toBe(true)
    fullWrapper.unmount()
  })
})
