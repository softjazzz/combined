import { expect, test, type Page } from '@playwright/test'

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || process.env.BASE_URL || 'http://localhost:3000'

test.use({
  baseURL: BASE_URL,
})

async function loginToWorkstationV4(page: Page) {
  await page.goto('/workstation-v5/login')
  await expect(page.getByRole('heading', { name: '登录工作台' })).toBeVisible()

  await page.getByPlaceholder('请输入用户名 / 手机号 / 邮箱').fill('admin')
  await page.getByPlaceholder('请输入密码').fill('admin888')
  await page.locator('select').selectOption('admin')
  await page.getByRole('button', { name: '立即登录工作台' }).click()

  await expect(page).toHaveURL(/\/workstation-v5(\/|$)/)
  await expect(page.getByText('病案工作台 V4')).toBeVisible()
}

test.describe('Workstation V4 admin pages', () => {
  test.beforeEach(async ({ page }) => {
    await loginToWorkstationV4(page)
  })

  test('system-config page is reachable and shows extraction settings', async ({ page }) => {
    await page.goto('/workstation-v5/system-config')

    await expect(page.getByText('数据同步配置')).toBeVisible()
    await expect(page.getByText('首页抽取设置')).toBeVisible()

    const extractionTab = page.getByRole('tab', { name: '首页抽取设置' })
    await expect(extractionTab).toBeVisible()
    await extractionTab.click()

    await expect(page.getByText('SQL 预填充')).toBeVisible()
    await expect(page.getByText('LLM 补缺')).toBeVisible()
    await expect(page.getByText('允许强制重抽')).toBeVisible()
    await expect(page.getByText('显示演示病历')).toBeVisible()
  })

  test('data page is reachable and shows schema or stats content', async ({ page }) => {
    await page.goto('/workstation-v5/data')

    await expect(page.getByText('病案总数')).toBeVisible()
    await expect(page.getByText('表浏览')).toBeVisible()
    await expect(page.getByText('CDM 数据表')).toBeVisible()
    await expect(page.getByText('结构', { exact: true }).first()).toBeVisible()
    await expect(page.getByText('数据', { exact: true }).first()).toBeVisible()
  })

  test('grouper page is reachable and shows core tabs', async ({ page }) => {
    await page.goto('/workstation-v5/grouper')

    await expect(page.getByText('医保分组器')).toBeVisible()
    await expect(page.getByText('CHS-DRG')).toBeVisible()
    await expect(page.getByText('CN-DRG')).toBeVisible()
    await expect(page.getByText('DIP 分组')).toBeVisible()

    await page
      .getByRole('button', { name: /CN-DRG/ })
      .first()
      .click()
    await expect(page.getByText('CN-DRG')).toBeVisible()
  })

  test('optional drg subpage is reachable', async ({ page }) => {
    await page.goto('/workstation-v5/drg/pre')

    await expect(page).toHaveURL(/\/workstation-v5\/drg\/pre/)
    await expect(page.locator('body')).toContainText(/事前分析|DRG\/DIP|分组|监控/)
  })
})
