#!/usr/bin/env node

import { spawnSync } from 'node:child_process'
import { mkdirSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const args = process.argv.slice(2)
const runsArg = args.find((arg) => arg.startsWith('--runs='))
const runs = Math.max(1, Number.parseInt(runsArg?.split('=')[1] || '1', 10))
const visualize = args.includes('--visualize')

const appRoot = process.cwd()
const distJsDir = resolve(appRoot, 'dist', 'assets', 'js')
const reportDir = resolve(appRoot, 'docs', 'acceptance')
const viteBin = resolve(appRoot, 'node_modules', 'vite', 'bin', 'vite.js')
const now = new Date().toISOString().replace(/[:.]/g, '-')

function getTopChunks(limit = 15) {
  const files = readdirSync(distJsDir)
    .filter((file) => file.endsWith('.js'))
    .map((file) => {
      const fullPath = resolve(distJsDir, file)
      const size = statSync(fullPath).size
      return { name: file, size_bytes: size, size_kb: Number((size / 1024).toFixed(2)) }
    })
    .sort((a, b) => b.size_bytes - a.size_bytes)
    .slice(0, limit)
  return files
}

function median(values) {
  if (!values.length) return 0
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  if (sorted.length % 2 === 0) {
    return (sorted[mid - 1] + sorted[mid]) / 2
  }
  return sorted[mid]
}

const runResults = []
let lastBuildOutput = ''

for (let i = 1; i <= runs; i += 1) {
  const started = Date.now()
  const result = spawnSync(
    process.execPath,
    [viteBin, 'build', '--config', 'vite.config.mjs', '--configLoader', 'native'],
    {
    cwd: appRoot,
    encoding: 'utf8',
    env: {
      ...process.env,
      ANALYZE_VISUALIZER: visualize ? '1' : '0',
    },
    stdio: 'pipe',
  })
  const durationMs = Date.now() - started
  const output = `${result.stdout || ''}\n${result.stderr || ''}`.trim()
  lastBuildOutput = output
  if (result.error) {
    console.error(`[FAIL] build run ${i}/${runs} (${durationMs}ms)`)
    console.error(String(result.error.message || result.error))
    process.exit(1)
  }
  if (result.status !== 0) {
    console.error(`[FAIL] build run ${i}/${runs} (${durationMs}ms)`)
    console.error(output.split('\n').slice(-80).join('\n'))
    process.exit(result.status || 1)
  }

  const topChunks = getTopChunks()
  runResults.push({
    run: i,
    duration_ms: durationMs,
    duration_s: Number((durationMs / 1000).toFixed(2)),
    top_chunks: topChunks,
  })
  console.log(`[PASS] build run ${i}/${runs} (${(durationMs / 1000).toFixed(2)}s)`)
}

const durations = runResults.map((item) => item.duration_ms)
const report = {
  generated_at: new Date().toISOString(),
  runs,
  visualize,
  environment: {
    node: process.version,
    platform: process.platform,
    arch: process.arch,
  },
  summary: {
    min_ms: Math.min(...durations),
    max_ms: Math.max(...durations),
    median_ms: Math.round(median(durations)),
    average_ms: Math.round(durations.reduce((sum, item) => sum + item, 0) / durations.length),
    min_s: Number((Math.min(...durations) / 1000).toFixed(2)),
    max_s: Number((Math.max(...durations) / 1000).toFixed(2)),
    median_s: Number((median(durations) / 1000).toFixed(2)),
    average_s: Number((durations.reduce((sum, item) => sum + item, 0) / durations.length / 1000).toFixed(2)),
  },
  runs_detail: runResults,
  output_tail: lastBuildOutput.split('\n').slice(-60),
}

mkdirSync(reportDir, { recursive: true })
const reportPath = resolve(reportDir, `build-profile-${now}.json`)
const latestPath = resolve(reportDir, 'build-profile-latest.json')
writeFileSync(reportPath, JSON.stringify(report, null, 2), 'utf8')
writeFileSync(latestPath, JSON.stringify(report, null, 2), 'utf8')

console.log(`\nReport: ${reportPath}`)
console.log(
  `Summary: median=${report.summary.median_s}s, min=${report.summary.min_s}s, max=${report.summary.max_s}s`
)
