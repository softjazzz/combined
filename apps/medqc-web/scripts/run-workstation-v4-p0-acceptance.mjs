#!/usr/bin/env node

import { spawnSync } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const args = new Set(process.argv.slice(2))
const skipBuild = args.has('--skip-build')

const reportDir = resolve(process.cwd(), 'docs', 'acceptance')
mkdirSync(reportDir, { recursive: true })
const pythonBin = process.env.PYTHON_BIN || 'python'

const report = {
  generated_at: new Date().toISOString(),
  scope: ['4.1.2', '6.2.2'],
  skip_build: skipBuild,
  steps: [],
}

function runStep(name, command, args, cwd) {
  const startedAt = Date.now()
  try {
    const result = spawnSync(command, args, {
      cwd,
      encoding: 'utf8',
      stdio: 'pipe'
    })
    const output = `${result.stdout || ''}\n${result.stderr || ''}`.trim()
    if (result.status !== 0) {
      throw new Error(output || `${command} exited with code ${result.status}`)
    }
    const durationMs = Date.now() - startedAt
    report.steps.push({
      name,
      command: `${command} ${(args || []).join(' ')}`.trim(),
      cwd,
      status: 'passed',
      duration_ms: durationMs,
      output_tail: output.split('\n').slice(-20).join('\n'),
    })
    console.log(`[PASS] ${name} (${durationMs}ms)`)
  } catch (error) {
    const durationMs = Date.now() - startedAt
    report.steps.push({
      name,
      command: `${command} ${(args || []).join(' ')}`.trim(),
      cwd,
      status: 'failed',
      duration_ms: durationMs,
      output_tail: String(error?.stdout || error?.stderr || error?.message || '').split('\n').slice(-40).join('\n'),
    })
    console.error(`[FAIL] ${name} (${durationMs}ms)`)
  }
}

const webRoot = process.cwd()
const backendRoot = resolve(webRoot, 'backend')

runStep(
  'Type Check',
  process.execPath,
  [resolve(webRoot, 'node_modules', 'vue-tsc', 'bin', 'vue-tsc.js'), '--noEmit', '--pretty', 'false'],
  webRoot,
)

if (!skipBuild) {
  runStep('Build', 'npm', ['run', 'build'], webRoot)
} else {
  report.steps.push({
    name: 'Build',
    command: 'npm run build',
    cwd: webRoot,
    status: 'skipped',
    duration_ms: 0,
    output_tail: 'Skipped by --skip-build',
  })
  console.log('[SKIP] Build')
}

runStep(
  'Backend P0 Unit Tests',
  pythonBin,
  ['-m', 'pytest', '-q', 'tests/unit/test_drg_config_router.py', 'tests/unit/test_notifications_overview_router.py'],
  backendRoot,
)

const passedCount = report.steps.filter((s) => s.status === 'passed').length
const failedCount = report.steps.filter((s) => s.status === 'failed').length
const skippedCount = report.steps.filter((s) => s.status === 'skipped').length

report.summary = {
  passed: passedCount,
  failed: failedCount,
  skipped: skippedCount,
  overall: failedCount === 0 ? 'passed' : 'failed',
}

const outputPath = resolve(reportDir, `workstation-v4-p0-acceptance-${Date.now()}.json`)
writeFileSync(outputPath, JSON.stringify(report, null, 2), 'utf8')

console.log(`\nReport: ${outputPath}`)
console.log(`Summary: passed=${passedCount}, failed=${failedCount}, skipped=${skippedCount}`)

process.exit(failedCount === 0 ? 0 : 1)
