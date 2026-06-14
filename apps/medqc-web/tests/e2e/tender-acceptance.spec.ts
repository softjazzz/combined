import fs from 'node:fs'
import path from 'node:path'
import { expect, test, type Page } from '@playwright/test'

const EVIDENCE_DIR = path.resolve('test-results/tender-evidence')
const EVIDENCE_REPORT = path.join(EVIDENCE_DIR, 'e2e-evidence-report.json')
const SENSITIVE_TERMS = [
  'raw_response',
  'medical_text',
  'documents',
  'embedding',
  'prompt',
  'record_content',
  'internal_data',
]

type EvidenceEntry = {
  clause: string
  title: string
  route: string
  screenshot: string
}

const evidenceEntries: EvidenceEntry[] = []

test.describe.configure({ mode: 'serial' })

async function loginToWorkstationV4(page: Page) {
  await page.goto('/workstation-v4/login')
  await expect(page.getByRole('heading', { name: '登录工作台' })).toBeVisible({ timeout: 15000 })

  await page.getByPlaceholder('请输入用户名 / 手机号 / 邮箱').fill('admin')
  await page.getByPlaceholder('请输入密码').fill('admin888')

  const roleSelect = page.locator('select')
  if ((await roleSelect.count()) > 0) {
    await roleSelect.first().selectOption('admin')
  }

  await Promise.all([
    page.waitForURL(/\/workstation-v4(?!\/login)(?:\?.*)?$/, { timeout: 20000 }),
    page.getByRole('button', { name: /立即登录工作台/ }).click(),
  ])
}

async function assertNoSensitiveTerms(page: Page) {
  const bodyText = (await page.locator('body').innerText()).toLowerCase()
  for (const term of SENSITIVE_TERMS) {
    expect(bodyText, `页面不应暴露敏感字段 ${term}`).not.toContain(term)
  }
}

async function captureEvidence(page: Page, clause: string, title: string, fileName: string) {
  await assertNoSensitiveTerms(page)
  const screenshot = path.join(EVIDENCE_DIR, fileName)
  await page.screenshot({ path: screenshot, fullPage: true })
  evidenceEntries.push({
    clause,
    title,
    route: page.url(),
    screenshot: path.relative(process.cwd(), screenshot).split(path.sep).join('/'),
  })
}

async function openRecordDetailIfAvailable(page: Page) {
  await page.goto('/workstation-v4/worklist')
  await expect(page.locator('body')).toContainText(/病历池|批量工作台|病历池列表/, {
    timeout: 20000,
  })

  const openRecord = page
    .locator('button:has-text("查看详情"), button:has-text("立即处理")')
    .first()
  if (await openRecord.isVisible().catch(() => false)) {
    await openRecord.click()
    await expect(page.locator('body')).toContainText(/病历详情|病案首页|结算清单/, {
      timeout: 20000,
    })
  }
}

test.beforeAll(() => {
  fs.mkdirSync(EVIDENCE_DIR, { recursive: true })
})

test.afterAll(() => {
  fs.writeFileSync(
    EVIDENCE_REPORT,
    JSON.stringify(
      {
        generated_at: new Date().toISOString(),
        sensitive_terms: SENSITIVE_TERMS,
        evidence_count: evidenceEntries.length,
        evidence: evidenceEntries,
      },
      null,
      2,
    ) + '\n',
    'utf-8',
  )
})

test.describe('投标功能核心页面截图验收', () => {
  test.beforeEach(async ({ page }) => {
    await loginToWorkstationV4(page)
  })

  test('3.1.1 病案首页与结算清单入口截图', async ({ page }) => {
    await openRecordDetailIfAvailable(page)
    await captureEvidence(page, '3.1.1', '病案首页与结算清单入口', '3.1.1-frontpage-settlement.png')
  })

  test('3.3.1 与 3.4.1 质控规则和 ICD 编码规范内涵质控截图', async ({ page }) => {
    await page.goto('/workstation-v4/rules?tab=coding')
    await expect(page.locator('body')).toContainText(/编码质控规则管理|质控规则管理/, {
      timeout: 20000,
    })
    await captureEvidence(
      page,
      '3.3.1,3.4.1',
      '规则管理与 ICD 编码规范内涵质控',
      '3.3.1-3.4.1-rules.png',
    )
  })

  test('3.5.1 智能编码与病案智能助手截图', async ({ page }) => {
    await page.goto('/workstation-v4')
    await page.getByTestId('qc-agent-home-entry').click()
    await page.getByTestId('qc-agent-message-input').fill('二型糖尿病怎么编码')
    await page.getByTestId('qc-agent-send-button').click()
    await page.waitForSelector('.qc-agent-icd-overview', { timeout: 30000 })
    await expect(page.locator('body')).toContainText(/ICD 候选检索|候选编码/)
    await captureEvidence(page, '3.5.1', '智能编码助手结果', '3.5.1-icd-chatbot.png')
  })

  test('3.4.3 与 4.1.2 完整性校验和问题概览截图', async ({ page }) => {
    await page.goto('/workstation-v4')
    await expect(page.locator('body')).toContainText(/质控首页概览|高优先级任务|病案问题/)
    await captureEvidence(page, '3.4.3,4.1.2', '工作台问题概览', '3.4.3-4.1.2-overview.png')
  })

  test('6.1.1 与 6.2.1 事前分析预入组截图', async ({ page }) => {
    await page.goto('/workstation-v4/drg/pre')
    await expect(page.locator('body')).toContainText(/事前分析|预判结果|抽取结果/, {
      timeout: 20000,
    })
    await captureEvidence(page, '6.1.1,6.2.1', '事前分析与预入组', '6.1.1-6.2.1-pre.png')
  })

  test('6.2.2 分组器本地化配置截图', async ({ page }) => {
    await page.goto('/workstation-v4/grouper')
    await expect(page.locator('body')).toContainText(/分组器|本地化|CHS-DRG|DIP/)
    await captureEvidence(page, '6.2.2', '分组器本地化配置', '6.2.2-grouper.png')
  })

  test('6.2.3 医保付费监测截图', async ({ page }) => {
    await page.goto('/workstation-v4/drg/payment')
    await expect(page.locator('body')).toContainText(/付费监测|预计支付|盈亏|支付率/, {
      timeout: 20000,
    })
    await captureEvidence(page, '6.2.3', '医保付费监测', '6.2.3-payment.png')
  })

  test('6.3.1 DRG/DIP 综合分析与导出截图', async ({ page }) => {
    await page.goto('/workstation-v4/drg/post')
    await expect(page.locator('body')).toContainText(/事后分析|分析维度|导出报告/, {
      timeout: 20000,
    })
    await captureEvidence(page, '6.3.1', 'DRG/DIP 综合分析', '6.3.1-post-analysis.png')
  })
})
