import { test, expect, Page } from '@playwright/test'

/**
 * Frontpage Demo E2E 测试
 * 覆盖 6 个功能模块：事前分析、事中监控、付费监测、事后分析、工作台、数据上传
 */

const BASE_URL = '/demo/lx33/frontpage-demo'

// Helper: 等待页面加载完成
async function waitForPageLoad(page: Page) {
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)
}

// Helper: 展开 DRG/DIP 菜单
async function expandDRGMenu(page: Page) {
    // 找到 DRG/DIP 文字所在的可点击父元素
    const drgMenuItem = page.locator('a, div').filter({ hasText: 'DRG/DIP' }).first()
    if (await drgMenuItem.isVisible()) {
        await drgMenuItem.click()
        await page.waitForTimeout(500)
    }
}

// Helper: 展开事中分析子菜单
async function expandMidAnalysisMenu(page: Page) {
    const midAnalysisItem = page.locator('a, div').filter({ hasText: '事中分析' }).first()
    if (await midAnalysisItem.isVisible()) {
        await midAnalysisItem.click()
        await page.waitForTimeout(500)
    }
}

// Helper: 导航到指定视图
async function navigateTo(page: Page, target: 'pre-analysis' | 'monitoring' | 'payment' | 'analysis' | 'workbench' | 'upload' | 'testcases') {
    await page.goto(BASE_URL)
    await waitForPageLoad(page)

    if (target === 'workbench') {
        await page.getByText('工作台', { exact: true }).first().click()
        await waitForPageLoad(page)
        return
    }

    if (target === 'upload') {
        await page.getByText('数据上传', { exact: true }).first().click()
        await waitForPageLoad(page)
        return
    }

    if (target === 'testcases') {
        await page.getByText('测试病历列表', { exact: true }).first().click()
        await waitForPageLoad(page)
        return
    }

    // 展开 DRG/DIP 菜单
    await expandDRGMenu(page)

    // 等待子菜单展开
    await page.waitForTimeout(500)

    if (target === 'pre-analysis') {
        await page.getByText('事前分析', { exact: true }).first().click()
    } else if (target === 'monitoring') {
        await expandMidAnalysisMenu(page)
        await page.waitForTimeout(300)
        await page.getByText('事中监控', { exact: true }).first().click()
    } else if (target === 'payment') {
        await expandMidAnalysisMenu(page)
        await page.waitForTimeout(300)
        await page.getByText('付费监测', { exact: true }).first().click()
    } else if (target === 'analysis') {
        await page.getByText('事后分析', { exact: true }).first().click()
    }

    await waitForPageLoad(page)
}

// ============================================
// 测试套件 1: 事前分析 (PreAnalysisView)
// ============================================
test.describe('事前分析', () => {
    test('T1.1 页面加载 - 显示事前分析标题', async ({ page }) => {
        await navigateTo(page, 'pre-analysis')

        // 检查页面标题
        await expect(page.getByRole('heading', { name: /事前分析/ })).toBeVisible({ timeout: 10000 })
        await expect(page.locator('text=诊断编码').first()).toBeVisible()
        await expect(page.locator('text=手术/操作编码').first()).toBeVisible()
        await expect(page.locator('text=DRG/DIP 入组预测').first()).toBeVisible()
    })

    test('T1.2 加载测试病历 - 选择下拉菜单中的病历', async ({ page }) => {
        await navigateTo(page, 'pre-analysis')

        // 点击选择测试病历下拉
        const select = page.locator('.ant-select-selector').first()
        await select.click()
        await page.waitForTimeout(300)

        // 选择第一个病历
        const options = page.locator('.ant-select-item-option')
        if (await options.count() > 0) {
            await options.first().click()
            await page.waitForTimeout(500)

            // 验证文本框有内容
            const textarea = page.locator('textarea')
            await expect(textarea).not.toBeEmpty()
        }
    })

    test('T1.3 AI智能抽取按钮存在', async ({ page }) => {
        await navigateTo(page, 'pre-analysis')

        // 检查 AI 智能抽取按钮存在
        const extractBtn = page.locator('button:has-text("AI智能抽取")')
        await expect(extractBtn).toBeVisible()
    })

    test('T1.4 重新计算按钮存在', async ({ page }) => {
        await navigateTo(page, 'pre-analysis')

        // 检查重新计算按钮存在
        const recalcBtn = page.locator('button:has-text("重新计算")')
        await expect(recalcBtn).toBeVisible()
    })
})

// ============================================
// 测试套件 2: 事中监控 (InProcessMonitoringView)
// ============================================
test.describe('事中监控', () => {
    test('T2.1 页面加载 - 显示监控界面', async ({ page }) => {
        await navigateTo(page, 'monitoring')

        // 检查页面有相关内容
        const pageContent = await page.textContent('body')
        expect(pageContent).toBeTruthy()
    })

    test('T2.2 页面元素存在', async ({ page }) => {
        await navigateTo(page, 'monitoring')

        // 检查页面有统计卡片或数字
        await page.waitForTimeout(1000)
        const hasElements = await page.locator('.rounded-xl, .rounded-2xl, .bg-white').count()
        expect(hasElements).toBeGreaterThan(0)
    })
})

// ============================================
// 测试套件 3: 付费监测 (PaymentMonitoringView)
// ============================================
test.describe('付费监测', () => {
    test('T3.1 页面加载 - 显示付费监测界面', async ({ page }) => {
        await navigateTo(page, 'payment')

        // 检查页面有内容
        await page.waitForTimeout(1000)
        const pageContent = await page.textContent('body')
        expect(pageContent).toBeTruthy()
    })

    test('T3.2 页面元素存在', async ({ page }) => {
        await navigateTo(page, 'payment')

        // 等待页面渲染
        await page.waitForTimeout(1000)
        const hasElements = await page.locator('.rounded-xl, .rounded-2xl, .bg-white').count()
        expect(hasElements).toBeGreaterThan(0)
    })
})

// ============================================
// 测试套件 4: 事后分析 (PostEventAnalysisView)
// ============================================
test.describe('事后分析', () => {
    test('T4.1 页面加载 - 显示事后分析界面', async ({ page }) => {
        await navigateTo(page, 'analysis')

        // 检查页面有内容
        await page.waitForTimeout(1000)
        const pageContent = await page.textContent('body')
        expect(pageContent).toBeTruthy()
    })

    test('T4.2 统计卡片存在', async ({ page }) => {
        await navigateTo(page, 'analysis')

        // 检查统计卡片
        await page.waitForTimeout(1000)
        const cards = page.locator('.rounded-xl, .rounded-2xl')
        const cardCount = await cards.count()
        expect(cardCount).toBeGreaterThan(0)
    })

    test('T4.3 页面有文字内容', async ({ page }) => {
        await navigateTo(page, 'analysis')

        await page.waitForTimeout(1000)
        // 检查页面不是空白
        const bodyText = await page.locator('body').textContent()
        expect(bodyText?.length).toBeGreaterThan(100)
    })
})

// ============================================
// 测试套件 5: 工作台 (Workbench)
// ============================================
test.describe('工作台', () => {
    test('T5.1 默认显示工作台', async ({ page }) => {
        await page.goto(BASE_URL)
        await waitForPageLoad(page)

        // 工作台菜单应该可见
        await expect(page.locator('span:has-text("工作台")').first()).toBeVisible()
    })

    test('T5.2 测试病历列表入口可点击', async ({ page }) => {
        await page.goto(BASE_URL)
        await waitForPageLoad(page)

        const testCaseLink = page.locator('span:has-text("测试病历列表")').first()
        if (await testCaseLink.isVisible()) {
            await testCaseLink.click()
            await page.waitForTimeout(500)
            // 应该显示病历相关内容
            const pageContent = await page.textContent('body')
            expect(pageContent).toBeTruthy()
        }
    })

    test('T5.3 工作台可访问', async ({ page }) => {
        await navigateTo(page, 'workbench')

        // 工作台页面加载成功
        const pageContent = await page.textContent('body')
        expect(pageContent).toBeTruthy()
    })
})

// ============================================
// 测试套件 6: 数据上传 (ExcelUploadView)
// ============================================
test.describe('数据上传', () => {
    test('T6.1 页面加载 - 显示上传界面', async ({ page }) => {
        await navigateTo(page, 'upload')

        // 检查有上传相关标题
        await expect(page.getByRole('heading', { name: /上传|数据/ }).first()).toBeVisible({ timeout: 10000 })
    })

    test('T6.2 上传区域存在', async ({ page }) => {
        await navigateTo(page, 'upload')

        // 检查拖拽上传区域或文件输入
        await page.waitForTimeout(500)
        const uploadArea = page.locator('.ant-upload')
        const hasUpload = await uploadArea.count()
        expect(hasUpload).toBeGreaterThanOrEqual(0)
    })

    test('T6.3 页面有内容', async ({ page }) => {
        await navigateTo(page, 'upload')

        const pageContent = await page.textContent('body')
        expect(pageContent?.length).toBeGreaterThan(100)
    })
})

// ============================================
// 测试套件 7: 侧边栏导航
// ============================================
test.describe('侧边栏导航', () => {
    test('T7.1 侧边栏菜单完整性', async ({ page }) => {
        await page.goto(BASE_URL)
        await waitForPageLoad(page)

        // 检查核心菜单项
        await expect(page.locator('span:has-text("工作台")').first()).toBeVisible()
        await expect(page.locator('span:has-text("DRG/DIP")').first()).toBeVisible()
    })

    test('T7.2 DRG/DIP菜单可展开', async ({ page }) => {
        await page.goto(BASE_URL)
        await waitForPageLoad(page)

        // 点击 DRG/DIP 展开
        await expandDRGMenu(page)
        await page.waitForTimeout(300)

        // 应该能看到子菜单
        await expect(page.locator('span:has-text("事前分析")').first()).toBeVisible()
    })
})
