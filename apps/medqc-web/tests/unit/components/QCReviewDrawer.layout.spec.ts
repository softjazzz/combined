import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const source = readFileSync(resolve(process.cwd(), 'src/components/qc/QCReviewDrawer.vue'), 'utf8')

function cssBlock(selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = source.match(new RegExp(`${escaped}\\s*\\{([\\s\\S]*?)\\n\\}`, 'm'))
  return match?.[1] ?? ''
}

describe('QCReviewDrawer layout', () => {
  it('将质控问题列表滚动容器放在 a-spin 外层', () => {
    expect(source).toContain('<div class="review-issues__body">')
    expect(source).toContain('class="review-issues__spin"')
    expect(source).not.toMatch(/<a-spin[\s\S]{0,160}class="review-issues__body"/)
  })

  it('外层抽屉保持页面级纵向滚动', () => {
    const drawerBody = cssBlock('.qc-review-drawer :deep(.ant-drawer-body)')
    const shell = cssBlock('.review-shell')
    const workspace = cssBlock('.review-workspace')

    expect(drawerBody).toContain('overflow-y: auto')
    expect(drawerBody).toContain('overflow-x: hidden')
    expect(drawerBody).not.toMatch(/^\s*overflow:\s*hidden/m)
    expect(shell).toMatch(/^\s*height:\s*auto;/m)
    expect(shell).toContain('min-height: calc(100vh - 48px)')
    expect(shell).toContain('overflow: visible')
    expect(shell).not.toMatch(/^\s*height:\s*calc\(100vh - 48px\)/m)
    expect(workspace).toContain('min-height: 0')
    expect(workspace).not.toMatch(/^\s*overflow:\s*hidden/m)
  })

  it('右侧质控问题列表拥有独立滚动区域', () => {
    const issueBodyGroup = source.match(
      /\.review-sidebar__list,\s*\.review-content__body,\s*\.review-issues__body\s*\{([\s\S]*?)\n\}/m,
    )?.[1]
    const spin = cssBlock('.review-issues__spin')
    const spinContainer = cssBlock('.review-issues__spin :deep(.ant-spin-container)')
    const panelGroup = source.match(
      /\.review-sidebar,\s*\.review-content,\s*\.review-issues\s*\{([\s\S]*?)\n\}/m,
    )?.[1]

    expect(issueBodyGroup).toContain('overflow-y: auto')
    expect(issueBodyGroup).toContain('overflow-x: hidden')
    expect(panelGroup).toContain('max-height: calc(100vh - 260px)')
    expect(source).toMatch(/\.review-issues\s*\{\s*min-height:\s*360px;/)
    expect(spin).toContain('min-height: 100%')
    expect(spinContainer).toContain('min-height: 100%')
  })

  it('1440 以下仍限制质控问题面板高度', () => {
    const responsiveIssues = source.match(
      /@media \(max-width: 1440px\) \{[\s\S]*?\.review-issues\s*\{([\s\S]*?)\n {2}\}/,
    )?.[1]

    expect(responsiveIssues).toContain('grid-column: 1 / -1')
    expect(responsiveIssues).toContain('max-height: min(520px, 55vh)')
  })

  it('保留并渲染 Bundle 返回的检验报告明细', () => {
    expect(source).toContain('report_items: Array.isArray(source.report_items)')
    expect(source).toContain('report_metadata:')
    expect(source).toContain('data-testid="qc-review-report-content"')
    expect(source).toContain('v-for="(item, index) in currentDocReportItems"')
    expect(source).toContain('<th>检验项目</th>')
    expect(source).toContain('<th>结果提示</th>')
    expect(source).toContain('buildMedicalReportMetadataRows(')
    expect(source).toContain('<dt>检查建议</dt>')
  })
})
