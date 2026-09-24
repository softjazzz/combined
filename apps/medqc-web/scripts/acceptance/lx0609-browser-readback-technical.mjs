/** 仅用合成载荷验证 V5 页面读取链；不构成客户病例或 PostgreSQL 验收。 */
import { existsSync, readFileSync } from 'node:fs'
import { chromium } from 'playwright'

const baseUrl = process.env.MEDQC_BROWSER_BASE_URL || 'http://127.0.0.1:3001'
const fixturePath = process.env.MEDQC_LX0609_BROWSER_FIXTURE_IN
const backendFixture = fixturePath ? JSON.parse(readFileSync(fixturePath, 'utf8')) : null
if (backendFixture && backendFixture.fixture_kind !== 'synthetic_sqlite_http') {
  throw new Error('浏览器技术回读只接受隔离 SQLite HTTP 测试生成的合成产物')
}
const expectedItem = backendFixture?.latest?.data?.items?.[0]
if (backendFixture && (!expectedItem || backendFixture.detail?.data?.items?.[0]?.rule_id !== expectedItem.rule_id)) {
  throw new Error('后端技术产物缺少匹配的 latest/detail 结果')
}
const visitId = backendFixture ? 'visit-1' : 'visit-synthetic'
const instituteId = backendFixture ? 'inst-1' : 'institute-synthetic'
const patientId = backendFixture ? 'patient-1' : 'patient-synthetic'
const recordRef = backendFixture?.latest?.data?.record_ref || 'synthetic-record-ref'
const resultStatus = expectedItem?.status || 'non_compliant'
const requests = []
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

try {
  await page.addInitScript(() => {
    const payload = btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 }))
    localStorage.setItem('medqc_access_token', `synthetic.${payload}.signature`)
  })
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url())
    if (!url.pathname.startsWith('/api/')) return route.continue()
    requests.push(`${route.request().method()} ${url.pathname}${url.search}`)
    if (url.pathname === '/api/v1/auth/me') {
      return route.fulfill({ json: { id: 'technical-check', display_name: '技术验证', roles: ['admin'] } })
    }
    if (url.pathname === '/api/medical-records/workstation') {
      return route.fulfill({ json: { data: {
        records: [{
          id: 'technical-record', record_key: recordRef, visit_id: visitId,
          institute_id: instituteId, patient_id: patientId,
          name: '合成病例', department: '合成科室', hospitalization_status: 'inpatient',
          admission_date: '2026-09-20', latest_qc_summary: {
            status: 'ready', completed_at: '2026-09-25T10:00:00+08:00',
            total_rule_count: 1, status_counts: { [resultStatus]: 1 },
          },
        }],
        total: 1, page: 1, qc_summary: {
          total_records: 1, ready_records: 1, status_counts: { [resultStatus]: 1 },
        },
      } } })
    }
    if (url.pathname === `/api/v1/qc/sichuan/workspace/records/${visitId}/latest-result`) {
      if (backendFixture) return route.fulfill({ json: backendFixture.latest })
      return route.fulfill({ json: { success: true, data: {
        schema_version: 'lx0609-single-record-result-v1', state: 'ready',
        reason_code: 'result_ready', record_ref: 'synthetic-record-ref', job_id: 'synthetic-job',
        rule_set_key: 'luxian_0609', items: [{
          rule_id: 'LX0609-09-01-01', rule_name: '抢救记录：及时完成',
          source_document: '抢救记录', status: 'non_compliant', reason_code: 'synthetic_reason',
          conclusion: '合成质控结论，仅验证读取展示。',
          suggestion: '合成修改建议，仅验证读取展示。', evidence: [],
        }],
        expected_rule_count: 1, result_rule_count: 1, is_complete: true,
        missing_rule_ids: [], conflicting_rule_ids: [],
      } } })
    }
    return route.fulfill({ json: { success: true, data: {} } })
  })

  await page.goto(`${baseUrl}/workstation-v5/records/running`, { waitUntil: 'domcontentloaded' })
  await page.locator('[data-testid="preview-item"]').waitFor({ timeout: 15000 }).catch(async (error) => {
    console.error(JSON.stringify({ url: page.url(), requests, body: (await page.locator('body').innerText()).slice(0, 3000) }))
    throw error
  })
  const item = page.locator('[data-testid="preview-item"]').first()
  const text = await item.innerText()
  const expectedConclusion = expectedItem?.conclusion || '合成质控结论'
  const expectedSuggestion = expectedItem?.suggestion || '合成修改建议'
  if (!text.includes(expectedConclusion) || !text.includes(expectedSuggestion)) {
    throw new Error(`已保存结果未原样展示：${text}`)
  }
  const expectedStatusLabel = resultStatus === 'compliant' ? '合规' : '确定问题'
  if (!text.includes(expectedStatusLabel)) {
    throw new Error(`已保存状态未显示：${resultStatus} / ${text}`)
  }
  if (backendFixture) {
    const keys = ['rule_id', 'status', 'reason_code', 'conclusion', 'suggestion', 'customer_display_facts']
    const detailItem = backendFixture.detail.data.items[0]
    if (keys.some((key) => JSON.stringify(detailItem[key]) !== JSON.stringify(expectedItem[key]))) {
      throw new Error('后端 latest/detail 与同一 Canonical 结果不一致')
    }
  }
  if (page.url().includes('/login')) throw new Error('页面被重定向到登录页')
  const latestRequests = requests.filter((request) => request.includes('/latest-result'))
  if (latestRequests.length !== 1) throw new Error(`latest-result 读取次数异常：${latestRequests.length}`)
  if (!latestRequests[0].includes(`institute_id=${instituteId}`) ||
      !latestRequests[0].includes(`patient_id=${patientId}`)) {
    throw new Error(`latest-result 丢失病历三坐标：${latestRequests[0]}`)
  }
  console.log(JSON.stringify({ ok: true, url: page.url(), latestRequests, previewText: text }))
} finally {
  await browser.close()
}
