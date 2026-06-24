#!/usr/bin/env node
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runPerfBaseline } from './run-perf-baseline.mjs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const PERF_DIR = __dirname
const DEFAULT_REPORT_DIR = path.resolve(path.join(__dirname, '..', '..', 'reports', 'perf'))

function parseNumber(value, fallback) {
  const n = Number(value)
  return Number.isFinite(n) ? n : fallback
}

function formatTsForFile(date) {
  return date.toISOString().replace(/[:.]/g, '-')
}

function formatPercent(value) {
  return `${(value * 100).toFixed(2)}%`
}

function parseListOfInts(input, label) {
  const values = String(input || '')
    .split(',')
    .map((item) => Number(item.trim()))
    .filter((item) => Number.isFinite(item) && item > 0)

  if (!values.length) {
    throw new Error(`${label} must contain at least one positive integer`)
  }

  const deduped = [...new Set(values)]
  if (deduped.length !== values.length) {
    throw new Error(`${label} must not contain duplicate values: ${values.join(',')}`)
  }
  const sorted = [...deduped].sort((a, b) => a - b)
  if (sorted.some((value, index) => value !== deduped[index])) {
    throw new Error(`${label} must be strictly increasing and unique, received: ${deduped.join(',')}`)
  }

  return deduped
}

function parseArgs(argv) {
  const result = {
    baseUrl: process.env.BASE_URL || 'http://127.0.0.1:8001',
    authToken: process.env.AUTH_TOKEN || '',
    concurrencyLadder: parseListOfInts(process.env.CONCURRENCY_LADDER || '5,10,15', 'concurrency ladder'),
    stepDuration: process.env.STEP_DURATION || '2m',
    reportDir: process.env.PERF_REPORT_DIR || DEFAULT_REPORT_DIR,
    scenarioName: process.env.PERF_SCENARIO_NAME || 'medqc-release-capacity-mix',
    scenarioDescription:
      process.env.PERF_SCENARIO_DESCRIPTION ||
      'Core MedQC mix covering health, sync read/write, preflight and qc analyze paths.',
    maxP95Ms: process.env.MAX_P95_MS ? Number(process.env.MAX_P95_MS) : 500,
    maxErrorRate: process.env.MAX_ERROR_RATE ? Number(process.env.MAX_ERROR_RATE) : 0.01,
    safetyFactor: process.env.CAPACITY_SAFETY_FACTOR ? Number(process.env.CAPACITY_SAFETY_FACTOR) : 0.8,
    thinkTimeSeconds: Number(process.env.THINK_TIME_SECONDS || '0'),
    mock: false,
    mockPort: Number(process.env.MOCK_PORT || '0'),
    mockFailureRate: Number(process.env.MOCK_FAILURE_RATE || '0'),
    mockJitterMs: Number(process.env.MOCK_JITTER_MS || '0'),
    continueOnFail: false,
    outputPrefix: 'capacity-final',
  }

  for (let i = 2; i < argv.length; i += 1) {
    const arg = argv[i]
    if (arg === '--mock') {
      result.mock = true
      continue
    }
    if (arg === '--continue-on-fail') {
      result.continueOnFail = true
      continue
    }

    const [key, rawValue] = arg.split('=')
    const value = rawValue ?? argv[i + 1]
    if (rawValue === undefined && value && !String(value).startsWith('--')) {
      i += 1
    }

    switch (key) {
      case '--base-url':
        result.baseUrl = String(value)
        break
      case '--auth-token':
        result.authToken = String(value)
        break
      case '--concurrency-ladder':
        result.concurrencyLadder = parseListOfInts(String(value), 'concurrency ladder')
        break
      case '--step-duration':
        result.stepDuration = String(value)
        break
      case '--report-dir':
        result.reportDir = String(value)
        break
      case '--scenario-name':
        result.scenarioName = String(value)
        break
      case '--scenario-description':
        result.scenarioDescription = String(value)
        break
      case '--max-p95-ms':
        result.maxP95Ms = parseNumber(value, result.maxP95Ms)
        break
      case '--max-error-rate':
        result.maxErrorRate = parseNumber(value, result.maxErrorRate)
        break
      case '--safety-factor':
        result.safetyFactor = parseNumber(value, result.safetyFactor)
        break
      case '--think-time-seconds':
        result.thinkTimeSeconds = parseNumber(value, result.thinkTimeSeconds)
        break
      case '--mock-port':
        result.mockPort = parseNumber(value, result.mockPort)
        break
      case '--mock-failure-rate':
        result.mockFailureRate = parseNumber(value, result.mockFailureRate)
        break
      case '--mock-jitter-ms':
        result.mockJitterMs = parseNumber(value, result.mockJitterMs)
        break
      case '--output-prefix':
        result.outputPrefix = String(value)
        break
      default:
        break
    }
  }

  return result
}

async function ensureDir(dir) {
  await fs.mkdir(dir, { recursive: true })
}

async function runBaselineStep(config, vus, stepDir) {
  const result = await runPerfBaseline({
    ...config,
    vus,
    duration: config.stepDuration,
    reportDir: stepDir,
  })
  return {
    report: result.report,
    raw: result.raw,
    reportJsonPath: result.reportJsonPath,
    reportMdPath: result.reportMdPath,
    exitCode: 0,
  }
}

function buildStepEvaluation(stepReport, threshold) {
  const report = stepReport.report || {}
  const metrics = report.metrics || {}
  const qps = Number(metrics.qps || 0)
  const p95Ms = Number(metrics.p95_ms || 0)
  const errorRate = Number(metrics.error_rate || 0)
  const violations = []

  if (Number.isFinite(threshold.maxP95Ms) && p95Ms > threshold.maxP95Ms) {
    violations.push(`P95 ${p95Ms.toFixed(2)}ms > threshold ${threshold.maxP95Ms}ms`)
  }
  if (Number.isFinite(threshold.maxErrorRate) && errorRate > threshold.maxErrorRate) {
    violations.push(`error rate ${formatPercent(errorRate)} > threshold ${formatPercent(threshold.maxErrorRate)}`)
  }

  const passed = violations.length === 0

  return {
    vus: Number(metrics.concurrency || report.config?.vus || 0),
    duration: report.config?.duration || threshold.stepDuration,
    base_url: report.config?.baseUrl || null,
    qps,
    p95_ms: p95Ms,
    error_rate: errorRate,
    requests: Number(metrics.requests || 0),
    failed_requests: Number(metrics.failed_requests || 0),
    passed,
    violations,
    report_json: stepReport.reportJsonPath,
    report_md: stepReport.reportMdPath,
    baseline_engine: report.engine || 'unknown',
  }
}

function getFailureConditionSummary(step) {
  if (!step) {
    return ['未找到满足阈值的稳定档位']
  }
  return step.violations.length ? step.violations : []
}

function renderMarkdown(report) {
  const rows = report.steps
    .map(
      (step, index) => `| ${index + 1} | ${step.vus} | ${step.qps.toFixed(2)} | ${step.p95_ms.toFixed(2)} | ${(step.error_rate * 100).toFixed(2)}% | ${step.passed ? 'PASS' : 'FAIL'} | ${step.violations.join('<br>') || '-' } |`
    )
    .join('\n')

  const applicableConditions = report.final.applicable_conditions.map((item) => `- ${item}`).join('\n')
  const failureConditions = report.final.failure_conditions.map((item) => `- ${item}`).join('\n')

  return `# P2-QA-02 Final Capacity Commitment Report

## Run Information

| Field | Value |
| --- | --- |
| Scenario | ${report.scenario.name} |
| Scenario Description | ${report.scenario.description} |
| Base URL | ${report.base_url} |
| Auth Token Provided | ${report.auth_token_provided ? 'Yes' : 'No'} |
| Concurrency Ladder | ${report.concurrency_ladder.join(', ')} |
| Step Duration | ${report.step_duration} |
| Thresholds | P95 <= ${report.thresholds.max_p95_ms} ms, Error Rate <= ${(report.thresholds.max_error_rate * 100).toFixed(2)}% |
| Safety Factor | ${report.thresholds.safety_factor} |

## Step Results

| Step | VUs | QPS | P95 (ms) | Error Rate | Result | Violations |
| --- | --- | --- | --- | --- | --- | --- |
${rows}

## Final Commitment

| Field | Value |
| --- | --- |
| Stable VUs | ${report.final.stable_vus ?? 'n/a'} |
| Stable QPS | ${report.final.stable_qps.toFixed(2)} |
| Capacity Commitment QPS | ${report.final.capacity_commitment_qps} |
| Final Status | ${report.final.status} |
| Selected From | ${report.final.selected_step_index ?? 'n/a'} |

## Applicable Conditions

${applicableConditions}

## Failure Conditions

${failureConditions}

## Evidence

| Item | Path |
| --- | --- |
| Summary JSON | ${report.summary_json} |
| Markdown Report | ${report.summary_md} |
| Step Reports | ${report.steps.map((step) => step.report_json).join('<br>')} |
`
}

function buildReport(config, steps) {
  const stableSteps = steps.filter((step) => step.passed)
  const selectedStep = stableSteps[stableSteps.length - 1] || null
  const stableQps = selectedStep ? selectedStep.qps : 0
  const capacityCommitmentQps = selectedStep ? Math.floor(stableQps * config.safetyFactor) : 0
  const status = selectedStep ? 'pass' : 'fail'
  const firstFailure = steps.find((step) => !step.passed) || null
  const failureConditions = firstFailure
    ? getFailureConditionSummary(firstFailure)
    : ['本次阶梯未出现阈值失效，但容量承诺仍只对已验证的最高稳定档位有效。']
  const actualBaseUrl = steps.find((step) => step.base_url)?.base_url || config.baseUrl

  return {
    timestamp: new Date().toISOString(),
    scenario: {
      name: config.scenarioName,
      description: config.scenarioDescription,
      request_mix: [
        { scenario: 'health', weight: 2, detail: 'GET /api/v1/health' },
        {
          scenario: 'sync_chain',
          weight: 5,
          detail: 'GET /api/v1/sync/status -> POST /api/v1/sync/preflight -> POST /api/v1/sync/trigger',
        },
        {
          scenario: 'qc_analyze',
          weight: 3,
          detail: 'POST /api/v1/qc/analyze/{record_id}',
        },
      ],
    },
    base_url: actualBaseUrl,
    auth_token_provided: Boolean(config.authToken),
    concurrency_ladder: config.concurrencyLadder,
    step_duration: config.stepDuration,
    thresholds: {
      max_p95_ms: config.maxP95Ms,
      max_error_rate: config.maxErrorRate,
      safety_factor: config.safetyFactor,
    },
    steps,
    final: {
      status,
      stable_vus: selectedStep ? selectedStep.vus : null,
      stable_qps: stableQps,
      capacity_commitment_qps: capacityCommitmentQps,
      selected_step_index: selectedStep ? steps.indexOf(selectedStep) + 1 : null,
      applicable_conditions: [
        'Base URL, auth token, build version and request mix must remain unchanged from this run.',
        'The same threshold policy must be applied: P95 and error rate must both stay within bounds.',
        'Use the same step duration and evaluate only the last stable step that passes all thresholds.',
        'Real environment results take precedence over mock or local runs for final sign-off.',
      ],
      failure_conditions: failureConditions,
    },
  }
}

function printSummary(report) {
  console.log('')
  console.log('=== Final Capacity Commitment Summary ===')
  console.log(`scenario=${report.scenario.name}`)
  console.log(`base_url=${report.base_url}`)
  console.log(`concurrency_ladder=${report.concurrency_ladder.join(',')}`)
  console.log(`step_duration=${report.step_duration}`)
  console.log(`stable_vus=${report.final.stable_vus ?? 'n/a'}`)
  console.log(`stable_qps=${report.final.stable_qps.toFixed(2)}`)
  console.log(`capacity_commitment_qps=${report.final.capacity_commitment_qps}`)
  console.log(`status=${report.final.status}`)
}

async function main() {
  const config = parseArgs(process.argv)
  await ensureDir(config.reportDir)

  const runStamp = formatTsForFile(new Date())
  const runDir = path.join(config.reportDir, `${config.outputPrefix}-${runStamp}`)
  const stepDirRoot = path.join(runDir, 'steps')
  await ensureDir(stepDirRoot)

  const steps = []
  for (let index = 0; index < config.concurrencyLadder.length; index += 1) {
    const vus = config.concurrencyLadder[index]
    const stepDir = path.join(stepDirRoot, `step-${String(index + 1).padStart(2, '0')}-vus-${vus}`)
    await ensureDir(stepDir)
    const stepReport = await runBaselineStep(config, vus, stepDir)
    const evaluated = buildStepEvaluation(stepReport, {
      maxP95Ms: config.maxP95Ms,
      maxErrorRate: config.maxErrorRate,
      stepDuration: config.stepDuration,
    })
    steps.push(evaluated)
    if (!evaluated.passed && !config.continueOnFail) {
      break
    }
  }

  const report = buildReport(config, steps)
  const summaryJson = path.join(runDir, 'capacity-final-summary.json')
  const summaryMd = path.join(runDir, 'capacity-final-report.md')
  report.summary_json = summaryJson
  report.summary_md = summaryMd

  const markdown = renderMarkdown(report)
  await fs.writeFile(summaryJson, JSON.stringify(report, null, 2), 'utf8')
  await fs.writeFile(summaryMd, markdown, 'utf8')

  printSummary(report)
  console.log(`summary_json=${summaryJson}`)
  console.log(`summary_md=${summaryMd}`)
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
