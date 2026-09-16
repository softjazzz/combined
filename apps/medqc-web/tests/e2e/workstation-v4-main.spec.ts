import { expect, test, type Page } from '@playwright/test'

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || process.env.BASE_URL || 'http://localhost:3000'
const LOGIN_URL = `${BASE_URL}/workstation-v5/login`
const WORKSTATION_URL = `${BASE_URL}/workstation-v5`

async function expectAnyVisible(page: Page, selectors: string[], label: string) {
  for (const selector of selectors) {
    const locator = page.locator(selector).first()
    if (await locator.isVisible().catch(() => false)) {
      return
    }
  }

  throw new Error(`Expected at least one visible selector for ${label}: ${selectors.join(', ')}`)
}

async function loginWithDemoAccount(page: Page) {
  await page.goto(LOGIN_URL)
  await expect(page.getByRole('heading', { name: '登录工作台' })).toBeVisible({ timeout: 15000 })

  const demoToggle = page.getByRole('button', { name: '演示账号快速登录' })
  if (await demoToggle.isVisible().catch(() => false)) {
    await demoToggle.click()
    const demoButton = page.getByRole('button').filter({ hasText: '功能演示账号' }).first()
    if (await demoButton.isVisible().catch(() => false)) {
      await Promise.all([
        page.waitForURL(/\/workstation-v5(?!\/login)(?:\?.*)?$/, { timeout: 20000 }),
        demoButton.click(),
      ])
      return
    }
  }

  await page.getByPlaceholder('请输入用户名 / 手机号 / 邮箱').fill('admin')
  await page.getByPlaceholder('请输入密码').fill('admin888')

  const roleSelect = page.locator('select')
  if (await roleSelect.count()) {
    await roleSelect.first().selectOption('admin')
  }

  await Promise.all([
    page.waitForURL(/\/workstation-v5(?!\/login)(?:\?.*)?$/, { timeout: 20000 }),
    page.getByRole('button', { name: /立即登录工作台/ }).click(),
  ])
}

async function waitForMainShell(page: Page) {
  await expect(page.getByText('批量工作台')).toBeVisible({ timeout: 20000 })
  await expect(page.getByText('优先处理池')).toBeVisible({ timeout: 20000 })
  await expect(page.getByText('工作台首页', { exact: true })).toBeVisible({ timeout: 20000 })
}

async function verifyStageEntry(
  page: Page,
  label: string,
  expectedUrlPart: string,
  expectedIndicators: string[],
) {
  await Promise.all([
    page.waitForURL(new RegExp(expectedUrlPart), { timeout: 15000 }),
    page.getByText(label, { exact: true }).click(),
  ])
  await expectAnyVisible(page, expectedIndicators, `stage ${label}`)
  await page.goto(WORKSTATION_URL)
  await waitForMainShell(page)
}

test.describe('Workstation V4 主链路', () => {
  test.setTimeout(120000)

  test('登录后主页面、阶段入口、详情和三标签可用', async ({ page }) => {
    await loginWithDemoAccount(page)
    await expect(page).toHaveURL(/\/workstation-v5(?!\/login)(?:\?.*)?$/, { timeout: 20000 })
    await waitForMainShell(page)

    await expect(page.getByText('待生成首页', { exact: true })).toBeVisible()
    await expect(page.getByText('待首页质控', { exact: true })).toBeVisible()
    await expect(page.getByText('待结算清单质控', { exact: true })).toBeVisible()

    await verifyStageEntry(page, '待生成首页', 'stage=frontpage_generate', [
      'text=待生成首页（参考草稿）',
      'text=当前筛选条件下暂无待生成首页病历',
      'button:has-text("生成草稿")',
      'button:has-text("批量生成参考首页")',
    ])
    await verifyStageEntry(page, '待首页质控', 'stage=frontpage_qc', [
      'text=待首页质控（正式数据）',
      'text=当前筛选条件下暂无待首页质控病历',
      'button:has-text("执行首页质控")',
      'button:has-text("批量首页质控")',
    ])
    await verifyStageEntry(page, '待结算清单质控', 'stage=settlement_qc', [
      'text=待结算清单质控（正式数据）',
      'text=当前筛选条件下暂无待结算清单质控病历',
      'button:has-text("执行结算质控")',
      'button:has-text("批量结算质控")',
    ])

    const openRecordLocator = page.locator(
      'button:has-text("查看详情"), button:has-text("立即处理")',
    )
    if (
      await openRecordLocator
        .first()
        .isVisible()
        .catch(() => false)
    ) {
      await openRecordLocator.first().click()

      await expect(page.getByRole('button', { name: '返回列表' })).toBeVisible({ timeout: 20000 })
      await expect(page.getByRole('button', { name: 'ICD 查询' })).toBeVisible({ timeout: 20000 })
      await expect(page.getByRole('button', { name: '病历详情' })).toBeVisible()
      await expect(page.getByRole('button', { name: '病案首页' })).toBeVisible()
      await expect(page.getByRole('button', { name: '结算清单' })).toBeVisible()

      await page.getByRole('button', { name: '病历详情' }).click()
      await expect(page.getByRole('button', { name: '返回列表' })).toBeVisible()

      await page.getByRole('button', { name: '病案首页' }).click()
      await expectAnyVisible(
        page,
        [
          'text=暂无病案首页数据',
          'button:has-text("生成首页草稿")',
          'button:has-text("保存到数据库")',
          'button:has-text("导出")',
        ],
        'frontpage tab',
      )

      await page.getByRole('button', { name: '结算清单' }).click()
      await expectAnyVisible(
        page,
        ['text=暂无结算清单数据', 'button:has-text("生成结算草稿")', 'button:has-text("执行质控")'],
        'settlement tab',
      )

      await page.getByRole('button', { name: '病历详情' }).click()
      await expect(page.getByRole('button', { name: '返回列表' })).toBeVisible()
    } else {
      await expectAnyVisible(
        page,
        ['text=当前筛选条件下暂无候选病历', 'text=暂无高优病历', 'text=当前筛选条件下暂无病历数据'],
        'empty workbench state',
      )
    }
  })
})
