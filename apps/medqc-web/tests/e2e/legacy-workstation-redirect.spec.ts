import { expect, test } from '@playwright/test'

for (const path of [
  '/workstation-v2/drg/pre',
  '/demo/lx33/frontpage-demo',
  '/dashboard/records/final',
  '/dashboard/medical-records/R-1/legacy',
]) {
  test(`${path} 将未登录访问转到工作台登录页`, async ({ page }) => {
    await page.goto(`${path}?source=legacy-link#recent`)

    await expect(page).toHaveURL((url) =>
      url.pathname === '/workstation-v5/login' &&
      url.searchParams.get('redirect') === '/workstation-v5?source=legacy-link#recent',
    )
  })
}
