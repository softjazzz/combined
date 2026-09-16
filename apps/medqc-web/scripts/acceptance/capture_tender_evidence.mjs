import { spawn, spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { chromium } from 'playwright'

const ROOT = process.cwd()
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || process.env.BASE_URL || 'http://127.0.0.1:3000'
const BACKEND_URL = process.env.QC_BACKEND_BASE_URL || 'http://127.0.0.1:8001'
const EVIDENCE_DIR = path.resolve(ROOT, 'test-results/tender-evidence')
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

const evidence = []

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function isFrontendReady() {
  try {
    const res = await fetch(`${BASE_URL}/workstation-v5/login`, { method: 'GET' })
    return res.ok
  } catch {
    return false
  }
}

async function isBackendReady() {
  try {
    const res = await fetch(`${BACKEND_URL}/api/v1/health`, { method: 'GET' })
    return res.ok
  } catch {
    return false
  }
}

async function waitForReady(check, label, timeoutMs = 120000) {
  const startedAt = Date.now()
  while (Date.now() - startedAt < timeoutMs) {
    if (await check()) return
    await sleep(1000)
  }
  throw new Error(`${label} 未在 ${timeoutMs}ms 内就绪`)
}

function stopChildProcessTree(child) {
  if (!child?.pid) return
  if (process.platform === 'win32') {
    spawnSync('cmd.exe', ['/c', 'taskkill', '/PID', String(child.pid), '/T', '/F'], { stdio: 'ignore' })
  } else {
    child.kill('SIGTERM')
  }
  child.stdout?.destroy()
  child.stderr?.destroy()
}

function stopOwnedPortListeners(startedBackend, startedFrontend) {
  if (process.platform !== 'win32') return
  const ports = [
    startedBackend ? 8001 : null,
    startedFrontend ? 3000 : null,
  ].filter(Boolean)
  if (!ports.length) return
  const portList = ports.join(',')
  spawnSync(
    'powershell.exe',
    [
      '-NoProfile',
      '-Command',
      `Get-NetTCPConnection -LocalPort ${portList} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }`,
    ],
    { stdio: 'ignore' },
  )
}

async function ensureBackend() {
  if (await isBackendReady()) return null

  const child = spawn(
    'python',
    ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8001', '--timeout-keep-alive', '5'],
    {
      cwd: path.join(ROOT, 'backend'),
      shell: process.platform === 'win32',
      stdio: ['ignore', 'pipe', 'pipe'],
      env: {
        ...process.env,
        JWT_SECRET: process.env.JWT_SECRET || 'dev-secret',
        PYTHONIOENCODING: 'utf-8',
      },
    },
  )
  child.stdout.on('data', (chunk) => process.stdout.write(`[backend] ${chunk}`))
  child.stderr.on('data', (chunk) => process.stderr.write(`[backend] ${chunk}`))
  await waitForReady(isBackendReady, `后端服务 ${BACKEND_URL}`)
  return child
}

async function ensureFrontend() {
  if (await isFrontendReady()) return null

  const child = spawn('npm', ['run', 'dev'], {
    cwd: ROOT,
    shell: process.platform === 'win32',
    stdio: ['ignore', 'pipe', 'pipe'],
  })
  child.stdout.on('data', (chunk) => process.stdout.write(`[vite] ${chunk}`))
  child.stderr.on('data', (chunk) => process.stderr.write(`[vite] ${chunk}`))
  await waitForReady(isFrontendReady, `前端服务 ${BASE_URL}`)
  return child
}

async function login() {
  const res = await fetch(`${BASE_URL}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ account: 'admin@medqc.com', password: 'admin888' }),
  })
  if (!res.ok) {
    throw new Error(`登录失败 ${res.status}: ${await res.text()}`)
  }
  return res.json()
}

async function newAuthenticatedPage(browser) {
  const auth = await login()
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  page.setDefaultTimeout(30000)
  await page.goto(`${BASE_URL}/workstation-v5/login`, { waitUntil: 'domcontentloaded' })
  await page.evaluate((authPayload) => {
    localStorage.setItem('medqc_access_token', authPayload.access_token)
    localStorage.setItem('medqc_refresh_token', authPayload.refresh_token)
    localStorage.setItem('medqc_authenticated', 'true')
    localStorage.setItem(
      'auth_user',
      JSON.stringify({
        id: 'admin',
        email: 'admin@medqc.com',
        display_name: '系统管理员',
        roles: ['admin', 'qc_manager'],
      }),
    )
  }, auth)
  return page
}

async function waitForBodyText(page, pattern, timeoutMs = 30000) {
  const source = pattern instanceof RegExp ? pattern.source : String(pattern)
  await page.waitForFunction(
    (regexSource) => new RegExp(regexSource).test(document.body?.innerText || ''),
    source,
    { timeout: timeoutMs },
  )
}

async function assertNoSensitiveTerms(page) {
  const text = (await page.locator('body').innerText()).toLowerCase()
  const hits = SENSITIVE_TERMS.filter((term) => text.includes(term))
  if (hits.length) {
    throw new Error(`页面暴露敏感字段: ${hits.join(', ')} at ${page.url()}`)
  }
}

async function capture(page, clause, title, fileName) {
  await assertNoSensitiveTerms(page)
  const screenshotPath = path.join(EVIDENCE_DIR, fileName)
  await page.screenshot({ path: screenshotPath, fullPage: true })
  evidence.push({
    clause,
    title,
    route: page.url(),
    screenshot: path.relative(ROOT, screenshotPath).split(path.sep).join('/'),
  })
}

async function openRecordDetailIfAvailable(page) {
  await page.goto(`${BASE_URL}/workstation-v5/worklist`, { waitUntil: 'domcontentloaded' })
  await waitForBodyText(page, /病历池|批量工作台|病历池列表/)
  const openRecord = page.locator('button:has-text("查看详情"), button:has-text("立即处理")').first()
  if (await openRecord.isVisible().catch(() => false)) {
    await openRecord.click()
    await waitForBodyText(page, /病历详情|病案首页|结算清单/)
  }
}

async function run() {
  fs.mkdirSync(EVIDENCE_DIR, { recursive: true })
  const backend = await ensureBackend()
  const frontend = await ensureFrontend()
  const chromeCandidates = [
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
  ]
  const executablePath = chromeCandidates.find((candidate) => fs.existsSync(candidate))
  const browser = await chromium.launch({
    headless: true,
    ...(executablePath ? { executablePath } : {}),
  })
  try {
    const page = await newAuthenticatedPage(browser)

    await openRecordDetailIfAvailable(page)
    await capture(page, '3.1.1', '病案首页与结算清单入口', '3.1.1-frontpage-settlement.png')

    await page.goto(`${BASE_URL}/workstation-v5/rules?tab=coding`, { waitUntil: 'domcontentloaded' })
    await waitForBodyText(page, /编码质控规则管理|质控规则管理/)
    await capture(page, '3.3.1,3.4.1', '规则管理与 ICD 编码规范内涵质控', '3.3.1-3.4.1-rules.png')

    await page.goto(`${BASE_URL}/workstation-v5`, { waitUntil: 'domcontentloaded' })
    await page.getByTestId('qc-agent-home-entry').click()
    await page.getByTestId('qc-agent-message-input').fill('二型糖尿病怎么编码')
    await page.getByTestId('qc-agent-send-button').click()
    await page.waitForSelector('.qc-agent-icd-overview', { timeout: 30000 })
    await capture(page, '3.5.1', '智能编码助手结果', '3.5.1-icd-chatbot.png')

    await page.goto(`${BASE_URL}/workstation-v5`, { waitUntil: 'domcontentloaded' })
    await waitForBodyText(page, /质控首页概览|高优先级任务|病案问题/)
    await capture(page, '3.4.3,4.1.2', '工作台问题概览', '3.4.3-4.1.2-overview.png')

    await page.goto(`${BASE_URL}/workstation-v5/drg/pre`, { waitUntil: 'domcontentloaded' })
    await waitForBodyText(page, /事前分析|预判结果|抽取结果/)
    await capture(page, '6.1.1,6.2.1', '事前分析与预入组', '6.1.1-6.2.1-pre.png')

    await page.goto(`${BASE_URL}/workstation-v5/grouper`, { waitUntil: 'domcontentloaded' })
    await waitForBodyText(page, /分组器|本地化|CHS-DRG|DIP/)
    await capture(page, '6.2.2', '分组器本地化配置', '6.2.2-grouper.png')

    await page.goto(`${BASE_URL}/workstation-v5/drg/payment`, { waitUntil: 'domcontentloaded' })
    await waitForBodyText(page, /付费监测|预计支付|盈亏|支付率/)
    await capture(page, '6.2.3', '医保付费监测', '6.2.3-payment.png')

    await page.goto(`${BASE_URL}/workstation-v5/drg/post`, { waitUntil: 'domcontentloaded' })
    await waitForBodyText(page, /事后分析|分析维度|导出报告/)
    await capture(page, '6.3.1', 'DRG/DIP 综合分析', '6.3.1-post-analysis.png')

    fs.writeFileSync(
      EVIDENCE_REPORT,
      JSON.stringify(
        {
          generated_at: new Date().toISOString(),
          base_url: BASE_URL,
          sensitive_terms: SENSITIVE_TERMS,
          evidence_count: evidence.length,
          evidence,
        },
        null,
        2,
      ) + '\n',
      'utf-8',
    )
    console.log(`tender e2e evidence captured: ${evidence.length} screenshots`)
    console.log(EVIDENCE_REPORT)
  } finally {
    stopChildProcessTree(backend)
    stopChildProcessTree(frontend)
    stopOwnedPortListeners(Boolean(backend), Boolean(frontend))
    await Promise.race([browser.close(), sleep(5000)]).catch(() => {})
  }
}

run()
  .then(() => {
    process.exit(0)
  })
  .catch((error) => {
    fs.mkdirSync(EVIDENCE_DIR, { recursive: true })
    fs.writeFileSync(
      EVIDENCE_REPORT,
      JSON.stringify(
        {
          generated_at: new Date().toISOString(),
          base_url: BASE_URL,
          sensitive_terms: SENSITIVE_TERMS,
          evidence_count: evidence.length,
          evidence,
          error: error instanceof Error ? error.message : String(error),
        },
        null,
        2,
      ) + '\n',
      'utf-8',
    )
    console.error(error)
    process.exit(1)
  })
