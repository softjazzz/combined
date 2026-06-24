#!/usr/bin/env node

import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const args = process.argv.slice(2)
const argMap = new Map()
for (const arg of args) {
  const [k, v] = arg.split('=')
  if (k?.startsWith('--')) argMap.set(k.slice(2), v ?? 'true')
}

const baseUrl = argMap.get('base-url') || 'http://127.0.0.1:8001'
const startDate = argMap.get('start-date') || '2026-01-01'
const endDate = argMap.get('end-date') || '2026-03-24'
const timestamp = new Date().toISOString().replaceAll(':', '-')
const outDir = resolve(process.cwd(), 'docs', 'acceptance', `6.3.1-${timestamp}`)
mkdirSync(outDir, { recursive: true })

const report = {
  generated_at: new Date().toISOString(),
  base_url: baseUrl,
  scope: '6.3.1',
  checks: [],
  artifacts: {},
  overall: 'failed',
}

function pushCheck(name, passed, detail, evidence = '') {
  report.checks.push({ name, passed, detail, evidence })
}

function validateRequiredFields(payload) {
  const requiredLevels = ['hospital', 'department', 'ward', 'attending_group', 'person']
  const requiredKpis = [
    'drg_dip_group_count',
    'cmi',
    'cost_consumption_index',
    'time_consumption_index',
    'low_risk_mortality_rate',
    'avg_los',
    'avg_cost',
    'insurance_profit_loss',
  ]

  const missingLevels = requiredLevels.filter((k) => !payload?.levels?.[k])
  const missingKpis = requiredKpis.filter((k) => payload?.kpis?.[k] === undefined)

  pushCheck(
    '层级完整性',
    missingLevels.length === 0,
    missingLevels.length ? `缺失层级: ${missingLevels.join(', ')}` : '五级层级字段齐全',
    'response.levels',
  )
  pushCheck(
    '指标完整性',
    missingKpis.length === 0,
    missingKpis.length ? `缺失指标: ${missingKpis.join(', ')}` : '关键指标字段齐全',
    'response.kpis',
  )
}

async function fetchJson(url) {
  const res = await fetch(url)
  const text = await res.text()
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${text}`)
  }
  return JSON.parse(text)
}

async function downloadFile(url, fileName) {
  const res = await fetch(url)
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`HTTP ${res.status}: ${body}`)
  }
  const arr = new Uint8Array(await res.arrayBuffer())
  const outputPath = resolve(outDir, fileName)
  writeFileSync(outputPath, arr)
  return outputPath
}

async function main() {
  const query = new URLSearchParams({
    dimension: 'hospital',
    start_date: startDate,
    end_date: endDate,
  })
  const analysisUrl = `${baseUrl}/api/v1/drg/analysis?${query.toString()}`
  try {
    const body = await fetchJson(analysisUrl)
    const payload = body.data ?? body
    writeFileSync(resolve(outDir, '6.3.1-kpi-snapshot.json'), JSON.stringify(payload, null, 2), 'utf8')
    report.artifacts.snapshot = '6.3.1-kpi-snapshot.json'

    pushCheck('分析接口可用性', true, 'GET /api/v1/drg/analysis 返回成功', analysisUrl)
    validateRequiredFields(payload)

    const exportFormats = ['excel', 'pdf', 'docx']
    for (const format of exportFormats) {
      const ext = format === 'excel' ? 'xlsx' : format
      const exportUrl = `${baseUrl}/api/v1/drg/analysis/export/${format}?${query.toString()}`
      try {
        const fileName = `6.3.1-sample.${ext}`
        const filePath = await downloadFile(exportUrl, fileName)
        report.artifacts[format] = fileName
        pushCheck(`${format.toUpperCase()} 导出`, true, `导出成功`, filePath)
      } catch (error) {
        pushCheck(`${format.toUpperCase()} 导出`, false, String(error?.message || error), exportUrl)
      }
    }
  } catch (error) {
    pushCheck('分析接口可用性', false, String(error?.message || error), analysisUrl)
  }

  report.overall = report.checks.every((item) => item.passed) ? 'passed' : 'failed'
  writeFileSync(resolve(outDir, '6.3.1-acceptance-report.json'), JSON.stringify(report, null, 2), 'utf8')

  const md = [
    '# 6.3.1 招标严格口径验收报告',
    '',
    `- 生成时间: ${report.generated_at}`,
    `- 基础地址: ${report.base_url}`,
    `- 结果: ${report.overall}`,
    '',
    '## 条款映射结果',
    '',
    ...report.checks.map(
      (item) =>
        `- [${item.passed ? 'x' : ' '}] ${item.name}: ${item.detail}${item.evidence ? `（证据: ${item.evidence}）` : ''}`,
    ),
    '',
    '## 产物',
    '',
    `- 指标快照: ${report.artifacts.snapshot || '未产出'}`,
    `- Excel: ${report.artifacts.excel || '未产出'}`,
    `- PDF: ${report.artifacts.pdf || '未产出'}`,
    `- DOCX: ${report.artifacts.docx || '未产出'}`,
    '',
    '## 说明',
    '',
    '- DOCX 作为招标 doc 等价交付。',
    '- 若样本缺失导致个别指标不可算，需在报告中体现失败项，不做静默降级。',
  ].join('\n')

  writeFileSync(resolve(outDir, '6.3.1-acceptance-report.md'), md, 'utf8')
  console.log(`6.3.1 acceptance artifacts: ${outDir}`)
  console.log(`overall=${report.overall}`)
  process.exit(report.overall === 'passed' ? 0 : 1)
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})

