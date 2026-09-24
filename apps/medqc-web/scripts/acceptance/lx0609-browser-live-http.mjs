/** 合成 SQLite 服务经真实 HTTP/Vite 代理送入 V5 页面；不拦截浏览器 API。 */
import { existsSync } from 'node:fs'
import { chromium } from 'playwright'

const baseUrl = process.env.MEDQC_BROWSER_BASE_URL || 'http://127.0.0.1:3001'
const visitId = 'visit-1'
const instituteId = 'inst-1'
const patientId = 'patient-1'
const latestPath = `/api/v1/qc/sichuan/workspace/records/${visitId}/latest-result?institute_id=${instituteId}&patient_id=${patientId}`
const detailPath = '/api/v1/qc/sichuan/workspace/batch-jobs/job-live-http-004'

async function readJson(path) {
  const response = await fetch(new URL(path, baseUrl))
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`)
  return response.json()
}

const latest = await readJson(latestPath)
const detail = await readJson(detailPath)
const expected = latest?.data?.items?.[0]
const detailItem = detail?.data?.items?.[0]
if (latest?.data?.state !== 'ready' || latest?.data?.data_origin !== 'canonical_result_envelope' ||
    !expected || !detailItem || detail?.data?.items?.length !== 1) {
  throw new Error(`正式 HTTP 结果未就绪：${JSON.stringify({ latest, detail }).slice(0, 800)}`)
}
const keys = ['rule_id', 'status', 'reason_code', 'conclusion', 'suggestion', 'customer_display_facts']
for (const key of keys) {
  if (JSON.stringify(expected[key]) !== JSON.stringify(detailItem[key])) {
    throw new Error(`latest/detail 的 ${key} 不一致`)
  }
}
if (expected.rule_id !== 'LX0609-09-01-01' || expected.status !== 'compliant') {
  throw new Error('正式 HTTP 未返回预期的原始 004 合成结果')
}

const chromeCandidates = [
  process.env.MEDQC_BROWSER_CHROME_PATH,
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
].filter(Boolean)
const executablePath = chromeCandidates.find((candidate) => existsSync(candidate))
const browser = await chromium.launch({
  ...(executablePath ? { executablePath } : {}),
  headless: true,
  args: ['--no-sandbox'],
})
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
const requests = []

try {
  await page.addInitScript(() => {
    const payload = btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 }))
    localStorage.setItem('medqc_access_token', `synthetic.${payload}.signature`)
  })
  page.on('request', (request) => {
    if (request.url().includes('/api/')) requests.push(request.url())
  })
  await page.goto(`${baseUrl}/workstation-v5/records/running`, { waitUntil: 'domcontentloaded' })
  const preview = page.locator('[data-testid="preview-item"]').first()
  await preview.waitFor({ timeout: 20000 }).catch(async (error) => {
    console.error(JSON.stringify({ url: page.url(), requests, body: (await page.locator('body').innerText()).slice(0, 2200) }))
    throw error
  })
  const text = await preview.innerText()
  if (!text.includes(expected.conclusion) || !text.includes(expected.suggestion) || !text.includes('合规')) {
    throw new Error(`V5 页面没有原样展示 Canonical 文案与状态：${text}`)
  }
  if (page.url().includes('/login')) throw new Error('页面被重定向到登录页')
  const latestRequests = requests.filter((url) => url.includes('/latest-result'))
  if (latestRequests.length !== 1 ||
      !latestRequests[0].includes(`institute_id=${instituteId}`) ||
      !latestRequests[0].includes(`patient_id=${patientId}`)) {
    throw new Error(`页面 latest-result 请求次数或三坐标异常：${JSON.stringify(latestRequests)}`)
  }
  console.log(JSON.stringify({
    ok: true,
    evidence: 'synthetic_sqlite_to_real_http_to_v5_without_browser_interception',
    ruleId: expected.rule_id,
    status: expected.status,
    latestRequests,
    previewText: text,
  }))
} finally {
  await browser.close()
}
