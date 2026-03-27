import http from 'k6/http'
import { check, sleep } from 'k6'

const BASE_URL = (__ENV.BASE_URL || 'http://127.0.0.1:8001').replace(/\/$/, '')
const AUTH_TOKEN = __ENV.AUTH_TOKEN || ''

const headers = {
  'Content-Type': 'application/json',
  'X-Perf-Run': 'medqc-perf-baseline',
}

if (AUTH_TOKEN) {
  headers.Authorization = `Bearer ${AUTH_TOKEN}`
}

function randomId(prefix) {
  return `${prefix}-${__VU}-${__ITER}-${Math.random().toString(16).slice(2, 10)}`
}

function requestOptions(tags) {
  return {
    headers,
    tags,
    timeout: __ENV.TIMEOUT || '30s',
  }
}

function assertOk(res, expectedName) {
  return check(res, {
    [`${expectedName} status is 2xx`]: (r) => r.status >= 200 && r.status < 300,
    [`${expectedName} has body`]: (r) => typeof r.body === 'string' && r.body.length > 0,
  })
}

function callHealth() {
  const res = http.get(`${BASE_URL}/api/v1/health`, requestOptions({ endpoint: 'health' }))
  assertOk(res, 'health')
}

function callSyncChain() {
  const statusRes = http.get(`${BASE_URL}/api/v1/sync/status`, requestOptions({ endpoint: 'sync_status' }))
  assertOk(statusRes, 'sync_status')

  const preflightRes = http.post(
    `${BASE_URL}/api/v1/sync/preflight`,
    JSON.stringify({
      source: 'mongo',
      tier: 'all',
      tables: ['mr', 'diagnosis', 'mr_surgery'],
    }),
    requestOptions({ endpoint: 'sync_preflight' })
  )
  assertOk(preflightRes, 'sync_preflight')

  const triggerRes = http.post(
    `${BASE_URL}/api/v1/sync/trigger`,
    JSON.stringify({
      source: 'mongo',
      tier: 'all',
      sync_date: new Date().toISOString().slice(0, 10),
    }),
    requestOptions({ endpoint: 'sync_trigger' })
  )
  assertOk(triggerRes, 'sync_trigger')
}

function callQcAnalyze() {
  const recordId = randomId('perf-record')
  const res = http.post(
    `${BASE_URL}/api/v1/qc/analyze/${recordId}`,
    JSON.stringify({
      content: '患者因胸痛入院，现病史完整，辅助检查可见轻度异常。',
      department: '心内科',
      options: {
        strict_mode: false,
      },
    }),
    requestOptions({ endpoint: 'qc_analyze' })
  )
  assertOk(res, 'qc_analyze')
}

export const options = {
  vus: Number(__ENV.VUS || 10),
  duration: __ENV.DURATION || '2m',
  thresholds: {},
  discardResponseBodies: false,
}

const scenarios = [
  { name: 'health', weight: 2 },
  { name: 'sync_chain', weight: 5 },
  { name: 'qc_analyze', weight: 3 },
]

function pickScenario() {
  const total = scenarios.reduce((sum, item) => sum + item.weight, 0)
  let cursor = Math.random() * total
  for (const item of scenarios) {
    cursor -= item.weight
    if (cursor <= 0) {
      return item.name
    }
  }
  return scenarios[scenarios.length - 1].name
}

export default function () {
  const scenario = pickScenario()

  if (scenario === 'health') {
    callHealth()
  } else if (scenario === 'sync_chain') {
    callSyncChain()
  } else {
    callQcAnalyze()
  }

  sleep(Number(__ENV.THINK_TIME_SECONDS || 0))
}
