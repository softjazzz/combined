#!/usr/bin/env node
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { spawn, spawnSync } from 'node:child_process'
import http from 'node:http'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const PERF_DIR = __dirname
const DEFAULT_REPORT_DIR = path.resolve(path.join(__dirname, '..', '..', 'reports', 'perf'))
const K6_SCRIPT = path.join(PERF_DIR, 'medqc-perf-baseline.k6.js')
const MOCK_SCRIPT = path.join(PERF_DIR, 'mock-perf-api.mjs')

function parseArgs(argv) {
  const result = {
    baseUrl: process.env.BASE_URL || 'http://127.0.0.1:8001',
    vus: Number(process.env.VUS || '10'),
    duration: process.env.DURATION || '2m',
    authToken: process.env.AUTH_TOKEN || '',
    reportDir: process.env.PERF_REPORT_DIR || DEFAULT_REPORT_DIR,
    mock: false,
    mockPort: Number(process.env.MOCK_PORT || '0'),
    mockFailureRate: Number(process.env.MOCK_FAILURE_RATE || '0'),
    mockJitterMs: Number(process.env.MOCK_JITTER_MS || '0'),
    maxP95Ms: process.env.MAX_P95_MS ? Number(process.env.MAX_P95_MS) : null,
    maxErrorRate: process.env.MAX_ERROR_RATE ? Number(process.env.MAX_ERROR_RATE) : null,
    thinkTimeSeconds: Number(process.env.THINK_TIME_SECONDS || '0'),
  }

  for (let i = 2; i < argv.length; i += 1) {
    const arg = argv[i]
    if (arg === '--mock') {
      result.mock = true
      continue
    }
    const [key, rawValue] = arg.split('=')
    const value = rawValue ?? argv[i + 1]
    if (rawValue === undefined && value && !value.startsWith('--')) {
      i += 1
    }
    switch (key) {
      case '--base-url':
        result.baseUrl = String(value)
        break
      case '--vus':
        result.vus = Number(value)
        break
      case '--duration':
        result.duration = String(value)
        break
      case '--auth-token':
        result.authToken = String(value)
        break
      case '--report-dir':
        result.reportDir = String(value)
        break
      case '--mock-port':
        result.mockPort = Number(value)
        break
      case '--mock-failure-rate':
        result.mockFailureRate = Number(value)
        break
      case '--mock-jitter-ms':
        result.mockJitterMs = Number(value)
        break
      case '--max-p95-ms':
        result.maxP95Ms = Number(value)
        break
      case '--max-error-rate':
        result.maxErrorRate = Number(value)
        break
      case '--think-time-seconds':
        result.thinkTimeSeconds = Number(value)
        break
      default:
        break
    }
  }

  return result
}

function detectK6() {
  const probe = spawnSync('k6', ['version'], { stdio: 'ignore', shell: false })
  return probe.status === 0
}

function formatTsForFile(date) {
  return date.toISOString().replace(/[:.]/g, '-')
}

function parseDurationMs(duration) {
  const value = String(duration).trim()
  const match = value.match(/^(\d+(?:\.\d+)?)(ms|s|m|h)?$/)
  if (!match) {
    return 120000
  }
  const amount = Number(match[1])
  const unit = match[2] || 's'
  if (unit === 'ms') return amount
  if (unit === 's') return amount * 1000
  if (unit === 'm') return amount * 60 * 1000
  if (unit === 'h') return amount * 60 * 60 * 1000
  return amount * 1000
}

function percentile(sortedValues, percentileValue) {
  if (sortedValues.length === 0) {
    return 0
  }
  const index = Math.ceil((percentileValue / 100) * sortedValues.length) - 1
  const safeIndex = Math.min(Math.max(index, 0), sortedValues.length - 1)
  return sortedValues[safeIndex]
}

function waitForMockServer(config) {
  return new Promise((resolve, reject) => {
    const env = {
      ...process.env,
      MOCK_PORT: String(config.mockPort),
      MOCK_FAILURE_RATE: String(config.mockFailureRate),
      MOCK_JITTER_MS: String(config.mockJitterMs),
    }
    const child = spawn(process.execPath, [MOCK_SCRIPT], {
      env,
      stdio: ['ignore', 'pipe', 'pipe'],
      shell: false,
    })

    let resolved = false
    let buffer = ''
    child.stdout.setEncoding('utf8')
    child.stdout.on('data', (chunk) => {
      buffer += chunk
      process.stdout.write(chunk)
      const marker = 'MOCK_PERF_API_READY '
      const idx = buffer.indexOf(marker)
      if (!resolved && idx >= 0) {
        const line = buffer.slice(idx + marker.length).split(/\r?\n/)[0].trim()
        resolved = true
        resolve({ child, baseUrl: line })
      }
    })
    child.stderr.on('data', (chunk) => process.stderr.write(chunk))
    child.on('error', reject)
    child.on('exit', (code) => {
      if (!resolved) {
        reject(new Error(`mock server exited before ready (code=${code})`))
      }
    })
  })
}

function startInlineMockServer(config) {
  const failureRate = Number(config.mockFailureRate || 0)
  const jitterMs = Number(config.mockJitterMs || 0)
  const endpointLatencies = {
    '/api/v1/health': 20,
    '/api/v1/sync/status': 35,
    '/api/v1/sync/preflight': 50,
    '/api/v1/sync/trigger': 120,
  }
  const port = Number(config.mockPort || 0)

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms))
  }
  function nextTraceId() {
    return `mock-${Math.random().toString(16).slice(2, 10)}`
  }
  function json(res, statusCode, payload) {
    const body = JSON.stringify(payload)
    res.writeHead(statusCode, {
      'Content-Type': 'application/json; charset=utf-8',
      'Content-Length': Buffer.byteLength(body),
      'X-Trace-ID': nextTraceId(),
    })
    res.end(body)
  }
  function success(data, message) {
    const payload = { success: true, data, trace_id: nextTraceId() }
    if (message) payload.message = message
    return payload
  }
  function maybeFail(pathname) {
    if (failureRate <= 0) return false
    return Math.random() < failureRate
  }

  const server = http.createServer(async (req, res) => {
    const requestUrl = new URL(req.url || '/', `http://${req.headers.host || '127.0.0.1'}`)
    const pathname = requestUrl.pathname
    const baseDelay = endpointLatencies[pathname] ?? 25
    const delay = baseDelay + (jitterMs > 0 ? Math.floor(Math.random() * jitterMs) : 0)
    await sleep(delay)

    if (maybeFail(pathname)) {
      json(res, 500, { success: false, error: 'mock failure injected', code: 'MOCK_FAILURE', trace_id: nextTraceId() })
      return
    }
    if (req.method === 'GET' && pathname === '/api/v1/health') {
      json(res, 200, success({ status: 'ok', service: 'medqc-web-mock-inline' }))
      return
    }
    if (req.method === 'GET' && pathname === '/api/v1/sync/status') {
      json(res, 200, success({ pg_sync: { is_running: false }, mongo_sync: { is_running: false, connected: true } }))
      return
    }
    if (req.method === 'POST' && pathname === '/api/v1/sync/preflight') {
      json(res, 200, success({ executable: true, blockers: [], warnings: [] }))
      return
    }
    if (req.method === 'POST' && pathname === '/api/v1/sync/trigger') {
      json(res, 200, success({ run_id: `mock-run-${Date.now()}` }))
      return
    }
    if (req.method === 'POST' && pathname.startsWith('/api/v1/qc/analyze/')) {
      json(res, 200, success({ analysis_id: `mock-analysis-${Date.now()}`, status: 'completed' }))
      return
    }
    json(res, 404, { success: false, error: `not found: ${pathname}`, code: 'NOT_FOUND', trace_id: nextTraceId() })
  })

  return new Promise((resolve, reject) => {
    server.on('error', reject)
    server.listen(port, '127.0.0.1', () => {
      const addr = server.address()
      const actualPort = addr && typeof addr !== 'string' ? addr.port : port
      const baseUrl = `http://127.0.0.1:${actualPort}`
      console.log(`MOCK_PERF_API_READY ${baseUrl} (inline)`)
      resolve({
        child: {
          kill: () => server.close(),
        },
        baseUrl,
      })
    })
  })
}

async function ensureDir(dir) {
  await fs.mkdir(dir, { recursive: true })
}

async function runNodeFallback(config) {
  const { performance } = await import('node:perf_hooks')
  function ensureOk(response, label) {
    if (!response.ok) {
      throw new Error(`${label} failed with status ${response.status}`)
    }
    return response
  }
  const requests = [
    async () => ensureOk(await fetch(`${config.baseUrl}/api/v1/health`), 'health'),
    async () => {
      ensureOk(await fetch(`${config.baseUrl}/api/v1/sync/status`), 'sync_status')
      ensureOk(
        await fetch(`${config.baseUrl}/api/v1/sync/preflight`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(config.authToken ? { Authorization: `Bearer ${config.authToken}` } : {}),
          },
          body: JSON.stringify({ source: 'mongo', tier: 'all', tables: ['mr', 'diagnosis'] }),
        }),
        'sync_preflight'
      )
      return ensureOk(
        await fetch(`${config.baseUrl}/api/v1/sync/trigger`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(config.authToken ? { Authorization: `Bearer ${config.authToken}` } : {}),
          },
          body: JSON.stringify({ source: 'mongo', tier: 'all', sync_date: new Date().toISOString().slice(0, 10) }),
        }),
        'sync_trigger'
      )
    },
    async () =>
      ensureOk(
        await fetch(`${config.baseUrl}/api/v1/qc/analyze/${`perf-record-${Math.random().toString(16).slice(2, 10)}`}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(config.authToken ? { Authorization: `Bearer ${config.authToken}` } : {}),
          },
          body: JSON.stringify({ content: '患者因胸痛入院，现病史完整。', department: '心内科' }),
        }),
        'qc_analyze'
      ),
  ]

  const durations = []
  let totalRequests = 0
  let failedRequests = 0
  const endAt = performance.now() + parseDurationMs(config.duration)

  async function worker() {
    while (performance.now() < endAt) {
      const pick = requests[Math.floor(Math.random() * requests.length)]
      const start = performance.now()
      try {
        const response = await pick()
        totalRequests += 1
        if (!response.ok) {
          failedRequests += 1
        }
      } catch {
        totalRequests += 1
        failedRequests += 1
      } finally {
        durations.push(performance.now() - start)
      }
    }
  }

  await Promise.all(Array.from({ length: Math.max(1, config.vus) }, () => worker()))

  const sorted = durations.slice().sort((a, b) => a - b)
  const avg = durations.length ? durations.reduce((sum, value) => sum + value, 0) / durations.length : 0
  return {
    engine: 'node-fallback',
    config,
    metrics: {
      http_reqs: { count: totalRequests, rate: totalRequests / (parseDurationMs(config.duration) / 1000) },
      http_req_failed: { rate: totalRequests ? failedRequests / totalRequests : 0 },
      http_req_duration: { avg, 'p(95)': percentile(sorted, 95), min: sorted[0] || 0, max: sorted[sorted.length - 1] || 0 },
    },
  }
}

function summarizeMetrics(summary, config) {
  const metrics = summary.metrics || {}
  const reqs = metrics.http_reqs || {}
  const failed = metrics.http_req_failed || {}
  const duration = metrics.http_req_duration || {}
  const qps = Number(reqs.rate || 0)
  const p95 = Number(duration['p(95)'] || duration.p95 || 0)
  const errorRate = Number(failed.rate || 0)
  const passP95 = config.maxP95Ms == null ? null : p95 <= config.maxP95Ms
  const passErr = config.maxErrorRate == null ? null : errorRate <= config.maxErrorRate
  const capacityCommitment = config.maxP95Ms == null || config.maxErrorRate == null ? null : Math.floor(qps * 0.8)

  return {
    timestamp: new Date().toISOString(),
    engine: summary.engine || 'k6',
    config: {
      baseUrl: config.baseUrl,
      vus: config.vus,
      duration: config.duration,
      authTokenProvided: Boolean(config.authToken),
      mock: config.mock,
      mockPort: config.mockPort,
      maxP95Ms: config.maxP95Ms,
      maxErrorRate: config.maxErrorRate,
      thinkTimeSeconds: config.thinkTimeSeconds,
    },
    metrics: {
      qps,
      p95_ms: p95,
      error_rate: errorRate,
      concurrency: config.vus,
      requests: Number(reqs.count || 0),
      failed_requests: Number(failed.count || 0),
    },
    capacity_commitment: {
      value_qps: capacityCommitment,
      method: 'stable_qps * 0.8 safety factor',
      pass_p95: passP95,
      pass_error_rate: passErr,
    },
  }
}

function printSummary(report) {
  console.log('')
  console.log('=== Perf Baseline Summary ===')
  console.log(`engine=${report.engine}`)
  console.log(`base_url=${report.config.baseUrl}`)
  console.log(`vus=${report.config.vus}`)
  console.log(`duration=${report.config.duration}`)
  console.log(`qps=${report.metrics.qps.toFixed(2)}`)
  console.log(`p95_ms=${report.metrics.p95_ms.toFixed(2)}`)
  console.log(`error_rate=${(report.metrics.error_rate * 100).toFixed(2)}%`)
  console.log(`capacity_commitment_qps=${report.capacity_commitment.value_qps ?? 'n/a'}`)
}

function renderMarkdown(report) {
  return `# Perf Baseline Report

| Field | Value |
| --- | --- |
| Engine | ${report.engine} |
| Base URL | ${report.config.baseUrl} |
| Concurrency | ${report.metrics.concurrency} |
| Duration | ${report.config.duration} |
| QPS | ${report.metrics.qps.toFixed(2)} |
| P95 (ms) | ${report.metrics.p95_ms.toFixed(2)} |
| Error Rate | ${(report.metrics.error_rate * 100).toFixed(2)}% |
| Capacity Commitment QPS | ${report.capacity_commitment.value_qps ?? 'n/a'} |
`
}

export async function runPerfBaseline(config) {
  await ensureDir(config.reportDir)

  const reportStamp = formatTsForFile(new Date())
  const reportJson = path.join(config.reportDir, `perf-baseline-${reportStamp}.json`)
  const reportMd = path.join(config.reportDir, `perf-baseline-${reportStamp}.md`)
  const summaryExport = path.join(config.reportDir, `perf-baseline-${reportStamp}.k6.json`)

  let mockProcess = null
  try {
    if (config.mock) {
      let mock
      try {
        mock = await waitForMockServer(config)
      } catch (error) {
        console.warn(`mock child process failed (${error?.code || error?.message}), switching to inline mock server`)
        mock = await startInlineMockServer(config)
      }
      mockProcess = mock.child
      config.baseUrl = mock.baseUrl
    }

    let summary
    if (spawnSync('k6', ['version'], { stdio: 'ignore', shell: false }).status === 0) {
      const env = {
        ...process.env,
        BASE_URL: config.baseUrl,
        VUS: String(config.vus),
        DURATION: config.duration,
        AUTH_TOKEN: config.authToken,
        THINK_TIME_SECONDS: String(config.thinkTimeSeconds),
      }
      const child = spawn('k6', ['run', '--summary-export', summaryExport, K6_SCRIPT], {
        env,
        stdio: 'inherit',
        shell: false,
      })
      const exitCode = await new Promise((resolve) => child.on('exit', resolve))
      if (exitCode !== 0) {
        console.warn(`k6 exited with code ${exitCode}, continuing to summarize export when available`)
      }
      const raw = await fs.readFile(summaryExport, 'utf8')
      summary = JSON.parse(raw)
      summary.engine = 'k6'
      summary.config = config
    } else {
      console.log('k6 not found on PATH, falling back to Node load generator.')
      summary = await runNodeFallback(config)
    }

    const report = summarizeMetrics(summary, config)
    printSummary(report)
    await fs.writeFile(reportJson, JSON.stringify({ report, raw: summary }, null, 2), 'utf8')
    await fs.writeFile(reportMd, renderMarkdown(report), 'utf8')
    console.log(`report_json=${reportJson}`)
    console.log(`report_md=${reportMd}`)
    return {
      report,
      raw: summary,
      reportJsonPath: reportJson,
      reportMdPath: reportMd,
      summaryExport,
    }
  } finally {
    if (mockProcess) {
      mockProcess.kill('SIGTERM')
    }
  }
}

async function main() {
  const config = parseArgs(process.argv)
  await runPerfBaseline(config)
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    console.error(error)
    process.exit(1)
  })
}
