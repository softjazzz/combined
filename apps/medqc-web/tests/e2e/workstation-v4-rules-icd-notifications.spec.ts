import { expect, test, type Page } from '@playwright/test'

async function loginToWorkstationV4(page: Page) {
  await page.goto('/workstation-v5/login')
  await expect(page.getByRole('heading', { name: '登录工作台' })).toBeVisible()

  await page.getByPlaceholder('请输入用户名 / 手机号 / 邮箱').fill('admin')
  await page.getByPlaceholder('请输入密码').fill('admin888')
  await page.locator('select').selectOption('admin')
  await page.getByRole('button', { name: '立即登录工作台' }).click()

  await expect(page).not.toHaveURL(/\/workstation-v5\/login/)
  await expect(page.getByText('病案工作台 V4')).toBeVisible()
}

async function openAndAssertRulesTab(
  page: Page,
  tab: 'coding' | 'frontpage' | 'settlement',
  heading: string,
  searchPlaceholder: string,
) {
  await page.goto(`/workstation-v5/rules?tab=${tab}`)

  await expect(page.getByRole('heading', { name: heading })).toBeVisible()
  await expect(page.getByPlaceholder(searchPlaceholder)).toBeVisible()
  await expect(page.getByText('规则名称', { exact: true })).toBeVisible()
  await expect(page.getByText('状态', { exact: true })).toBeVisible()
  await expect(page.getByText('风险', { exact: true })).toBeVisible()
  await expect(page.getByText('近7天命中', { exact: true })).toBeVisible()

  if (tab === 'coding') {
    await expect(page.getByRole('button', { name: '新建规则' })).toBeVisible()
    await expect(page.getByRole('button', { name: '发布变更' })).toBeVisible()
    await expect(page.getByText('规则类型', { exact: true })).toBeVisible()
  } else if (tab === 'frontpage') {
    await expect(page.getByText('规则分类', { exact: true })).toBeVisible()
    await expect(page.getByText('病历文书类型', { exact: true })).toBeVisible()
  } else {
    await expect(page.getByText('规则分类', { exact: true })).toBeVisible()
  }

  await expect(page.locator('body')).not.toContainText('加载失败')
}

test.describe('Workstation V4 rules / ICD / notifications', () => {
  test.beforeEach(async ({ page }) => {
    await loginToWorkstationV4(page)
  })

  test('rules pages load for coding, frontpage, and settlement tabs', async ({ page }) => {
    await openAndAssertRulesTab(page, 'coding', '编码质控规则管理', '搜索规则名/编码/条件关键词')

    await openAndAssertRulesTab(page, 'frontpage', '首页质控规则管理', '搜索规则名/字段名/规则编号')

    await openAndAssertRulesTab(
      page,
      'settlement',
      '结算清单质控规则管理',
      '搜索规则名/字段名/规则编号',
    )
  })

  test('icd page exposes search and a usable tree/result area', async ({ page }) => {
    await page.goto('/workstation-v5/icd')

    await expect(page.getByText('ICD 智能检索')).toBeVisible()
    await expect(page.getByPlaceholder('输入诊断名称或 ICD-10 编码...')).toBeVisible()
    await expect(page.getByRole('button', { name: '临床版 ICD-10' })).toBeVisible()
    await expect(page.getByRole('button', { name: '医保版 2.0' })).toBeVisible()
    await expect(page.getByRole('button', { name: '疾病诊断' })).toBeVisible()
    await expect(page.getByRole('button', { name: '手术操作 (ICD-9)' })).toBeVisible()

    await expect(page.getByText(/编码目录|暂无编码数据/)).toBeVisible()

    const searchInput = page.getByPlaceholder('输入诊断名称或 ICD-10 编码...')
    await searchInput.fill('高血压')
    await searchInput.press('Enter')

    await expect(page.getByText(/编码搜索结果|未找到匹配/)).toBeVisible()
  })

  test('main workstation exposes notification entry and notification panel content', async ({
    page,
  }) => {
    await page.goto('/workstation-v5')

    await expect(page.getByText('优先处理池')).toBeVisible()
    await expect(page.getByText('批量工作台')).toBeVisible()

    const assistTrigger = page.getByRole('button', { name: '分析面板' })
    await expect(assistTrigger).toBeVisible()
    await assistTrigger.click()

    const assistPanel = page.locator('.assist-panel')
    await expect(assistPanel.getByText('智能分析面板')).toBeVisible()

    const messageTab = assistPanel.getByRole('button', { name: '消息' })
    await expect(messageTab).toBeVisible()
    await messageTab.click()

    await expect(assistPanel.getByRole('button', { name: '全部已读' })).toBeVisible()
    await expect(
      assistPanel.getByText(/通知消息|暂无消息|当天暂无问题集中点|消息概览待接入/),
    ).toBeVisible()
  })
})
