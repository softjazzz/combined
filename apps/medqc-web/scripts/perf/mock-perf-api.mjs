#!/usr/bin/env node
import http from 'node:http'
import { URL } from 'node:url'

const port = Number(process.env.MOCK_PORT || '18080')
const failureRate = Number(process.env.MOCK_FAILURE_RATE || '0')
const jitterMs = Number(process.env.MOCK_JITTER_MS || '0')

const endpointLatencies = {
  '/api/v1/health': 20,
  '/api/v1/sync/status': 35,
  '/api/v1/sync/preflight': 50,
  '/api/v1/sync/trigger': 120,
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function json(res, statusCode, payload) {
  const body = JSON.stringify(payload)
  res.writeHead(statusCode, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(body),
    'X-Trace-ID': `mock-${Math.random().toString(16).slice(2, 10)}`,
  })
  res.end(body)
}

function success(data, message) {
  const payload = {
    success: true,
    data,
    trace_id: `mock-${Math.random().toString(16).slice(2, 10)}`,
  }
  if (message) {
    payload.message = message
  }
  return payload
}

function hashCode(text) {
  let hash = 0
  for (let i = 0; i < text.length; i += 1) {
    hash = (hash << 5) - hash + text.charCodeAt(i)
    hash |= 0
  }
  return hash
}

function maybeFail(pathname) {
  if (failureRate <= 0) {
    return false
  }
  const slot = Math.abs(hashCode(pathname) % 1000) / 1000
  return slot < failureRate
}

const server = http.createServer(async (req, res) => {
  const parsed = new URL(req.url || '/', `http://${req.headers.host || '127.0.0.1'}`)
  const pathname = parsed.pathname
  const baseDelay = endpointLatencies[pathname] ?? 25
  const delay = baseDelay + (jitterMs > 0 ? Math.floor(Math.random() * jitterMs) : 0)

  await sleep(delay)

  if (maybeFail(pathname)) {
    json(res, 500, {
      success: false,
      error: 'mock failure injected',
      code: 'MOCK_FAILURE',
      trace_id: `mock-${Math.random().toString(16).slice(2, 10)}`,
    })
    return
  }

  if (req.method === 'GET' && pathname === '/api/v1/health') {
    json(res, 200, success({ status: 'ok', service: 'medqc-web-mock' }))
    return
  }

  if (req.method === 'GET' && pathname === '/api/v1/sync/status') {
    json(res, 200, success({
      pg_sync: { is_running: false, last_sync_status: 'success' },
      mongo_sync: { is_running: false, connected: true },
    }))
    return
  }

  if (req.method === 'POST' && pathname === '/api/v1/sync/preflight') {
    json(res, 200, success({
      source: 'mongo',
      tier: 'all',
      executable: true,
      blockers: [],
      warnings: [],
      estimated_impact: 18,
      risk_level: 'low',
    }))
    return
  }

  if (req.method === 'POST' && pathname === '/api/v1/sync/trigger') {
    json(res, 200, success({
      success: true,
      run_id: `mock-run-${Date.now()}`,
      results: {
        tier1: { discovered: 3 },
        tier2: { synced: 8 },
        tier3: { synced: 4 },
      },
    }))
    return
  }

  if (req.method === 'POST' && pathname.startsWith('/api/v1/qc/analyze/')) {
    json(res, 200, success({
      analysis_id: `mock-analysis-${Date.now()}`,
      status: 'completed',
      record_id: pathname.split('/').pop(),
    }))
    return
  }

  json(res, 404, {
    success: false,
    error: `not found: ${pathname}`,
    code: 'NOT_FOUND',
    trace_id: `mock-${Math.random().toString(16).slice(2, 10)}`,
  })
})

server.listen(port, '127.0.0.1', () => {
  const address = server.address()
  const actualPort = address && typeof address !== 'string' ? address.port : port
  process.stdout.write(`MOCK_PERF_API_READY http://127.0.0.1:${actualPort}\n`)
})

function shutdown() {
  server.close(() => process.exit(0))
}

process.on('SIGINT', shutdown)
process.on('SIGTERM', shutdown)
