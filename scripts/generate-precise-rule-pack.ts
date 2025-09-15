#!/usr/bin/env node
/**
 * Generate rule import JSON from precise Markdown knowledge files (TypeScript).
 * Quick path: use drug common names to build name-based rule conditions.
 *
 * Usage:
 *   pnpm gen:precise
 *   pnpm gen:precise -- out=Yibao/generated/custom.json
 */

import fs from 'fs'
import path from 'path'

type Rule = {
  code: string
  name: string
  description?: string
  rule_type: string
  severity: 'info' | 'warn' | 'block'
  enabled: boolean
  conditions: any[]
  actions: Array<{ action_type: string; message_template: string; parameters?: Record<string, any> }>
  triggers: string[]
}

// Resolve project root regardless of build output location (scripts/dist)
// dist -> scripts -> repo root
const ROOT = path.resolve(__dirname, '..', '..')
const PRECISE_DIR = path.join(ROOT, 'Yibao', '医保规则_precise')
const OUTPUT_DIR = path.join(ROOT, 'Yibao', 'generated')

const FILES = {
  gender: '第一批-1.药品区分性别使用_precise.md',
  visit: '第四批 药品限就医方式_precise.md',
  child_only: '第一批-3.药品儿童专用_precise.md',
  child_limit: '第一批-4.药品限儿童使用_precise.md'
}

function readFileSafe(p: string): string {
  try { return fs.readFileSync(p, 'utf8') } catch { return '' }
}

function normalizeName(name: string): string {
  return (name || '').trim().replace(/^["'“”‘’\s]+|["'“”‘’\s]+$/g, '')
}

function parseMarkdownTable(md: string, requiredHeader: string): Array<Record<string, string>> {
  const lines = md.split(/\r?\n/)
  let headerIdx = -1
  let headers: string[] = []
  const rows: Array<Record<string, string>> = []

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    if (headerIdx === -1) {
      if (line.includes('|') && line.includes(requiredHeader)) {
        headers = line.split('|').map(s => s.trim()).filter(Boolean)
        headerIdx = i
        i += 1
      }
      continue
    }
    if (!line.includes('|')) break
    const cols = line.split('|').map(s => s.trim())
    if (cols.length < headers.length) continue
    const obj: Record<string, string> = {}
    for (let j = 0; j < headers.length && j < cols.length; j++) {
      obj[headers[j]] = cols[j]
    }
    rows.push(obj)
  }
  return rows
}

function extractNames(md: string): string[] {
  // Robust regex extraction: | 序号 | 药品通用名 | ...
  const names: string[] = []
  const re = /\|\s*\d+\s*\|\s*([^|]+)\|/g
  let m: RegExpExecArray | null
  while ((m = re.exec(md))) {
    const name = normalizeName(m[1])
    if (!name) continue
    if (['是', '否', '—', '-', 'N/A'].includes(name)) continue
    names.push(name)
  }
  return Array.from(new Set(names))
}

function unique(arr: string[]): string[] { return Array.from(new Set(arr.filter(Boolean))) }

function splitGender(names: string[]) {
  const femaleKw = ['妇', '阴道', '子宫', '乳', '雌', '调经', '月经', '痛经', '更年期', '宫颈', '避孕', '外阴']
  const maleKw = ['前列腺', '勃起', '雄激素', '睾', '阴茎', '精子']
  const female: string[] = []
  const male: string[] = []
  const unknown: string[] = []
  for (const n of names) {
    const hasF = femaleKw.some(k => n.includes(k))
    const hasM = maleKw.some(k => n.includes(k))
    if (hasF && !hasM) female.push(n)
    else if (hasM && !hasF) male.push(n)
    else unknown.push(n)
  }
  return { female: unique(female), male: unique(male), unknown: unique(unknown) }
}

function splitVisit(md: string) {
  const rows = parseMarkdownTable(md, '药品通用名')
  const inpatient: string[] = []
  const outpatient: string[] = []
  const unknown: string[] = []
  for (const r of rows) {
    const values = Object.values(r).map(String)
    const name = normalizeName((values[1] as string) || (values[0] as string) || '')
    const text = values.join(' ')
    if (!name) continue
    if (text.includes('住院')) inpatient.push(name)
    else if (text.includes('门诊')) outpatient.push(name)
    else unknown.push(name)
  }
  return { inpatient: unique(inpatient), outpatient: unique(outpatient), unknown: unique(unknown) }
}

function buildRule(params: {
  code: string
  name: string
  rule_type: string
  severity: 'info' | 'warn' | 'block'
  names: string[]
  predicate: (names: string[]) => any[]
  message: string
  enabled?: boolean
}): Rule {
  const { code, name, rule_type, severity, names, predicate, message, enabled = true } = params
  return {
    code,
    name,
    description: `自动从 precise 知识库生成。共 ${names.length} 个药品名称（名称匹配）。`,
    rule_type,
    severity,
    enabled,
    conditions: predicate(names),
    actions: [
      { action_type: severity === 'block' ? 'intercept' : 'warn', message_template: message, parameters: {} }
    ],
    triggers: ['order.drug.submit']
  }
}

function predicateNameIn(namesExpr: string[]): any[] {
  return [
    { fact: 'order.drug_name', op: 'in', value: namesExpr, description: '药品名称匹配（precise名称）' }
  ]
}

function main() {
  if (!fs.existsSync(OUTPUT_DIR)) fs.mkdirSync(OUTPUT_DIR, { recursive: true })

  const mdGender = readFileSafe(path.join(PRECISE_DIR, FILES.gender))
  const mdVisit = readFileSafe(path.join(PRECISE_DIR, FILES.visit))
  const mdChildOnly = readFileSafe(path.join(PRECISE_DIR, FILES.child_only))
  const mdChildLimit = readFileSafe(path.join(PRECISE_DIR, FILES.child_limit))

  const genderNames = extractNames(mdGender)
  const { female: femaleNames, male: maleNames, unknown: unknownGender } = splitGender(genderNames)

  const { inpatient: inpatientNames, outpatient: outpatientNames, unknown: unknownVisit } = splitVisit(mdVisit)

  const childOnlyNames = unique([ ...extractNames(mdChildOnly), ...extractNames(mdChildLimit) ])

  const rules: Rule[] = []

  if (femaleNames.length) {
    rules.push(buildRule({
      code: 'DRUG_GENDER_FEMALE_ONLY',
      name: '药品限女性使用（名称匹配）',
      rule_type: 'drug_gender',
      severity: 'warn',
      names: femaleNames,
      predicate: (names) => [
        { fact: 'patient.gender', op: '==', value: 'M', description: '当前为男性' },
        ...predicateNameIn(names)
      ],
      message: '【提醒】{order.drug_name} 限女性使用，当前患者为男性，请确认是否继续。'
    }))
  }

  if (maleNames.length) {
    rules.push(buildRule({
      code: 'DRUG_GENDER_MALE_ONLY',
      name: '药品限男性使用（名称匹配）',
      rule_type: 'drug_gender',
      severity: 'warn',
      names: maleNames,
      predicate: (names) => [
        { fact: 'patient.gender', op: '==', value: 'F', description: '当前为女性' },
        ...predicateNameIn(names)
      ],
      message: '【提醒】{order.drug_name} 限男性使用，当前患者为女性，请确认是否继续。'
    }))
  }

  if (inpatientNames.length) {
    rules.push(buildRule({
      code: 'DRUG_VISIT_INPATIENT_ONLY',
      name: '药品限住院使用（名称匹配）',
      rule_type: 'visit_type',
      severity: 'block',
      names: inpatientNames,
      predicate: (names) => [
        { fact: 'visit.type', op: '==', value: 'OUTPATIENT', description: '当前为门诊' },
        ...predicateNameIn(names)
      ],
      message: '【拦截】{order.drug_name} 限住院患者使用，门诊不可开具。'
    }))
  }

  if (outpatientNames.length) {
    rules.push(buildRule({
      code: 'DRUG_VISIT_OUTPATIENT_ONLY',
      name: '药品限门诊使用（名称匹配）',
      rule_type: 'visit_type',
      severity: 'block',
      names: outpatientNames,
      predicate: (names) => [
        { fact: 'visit.type', op: '==', value: 'INPATIENT', description: '当前为住院' },
        ...predicateNameIn(names)
      ],
      message: '【拦截】{order.drug_name} 限门诊患者使用，住院不可开具。'
    }))
  }

  if (childOnlyNames.length) {
    rules.push(buildRule({
      code: 'DRUG_CHILDREN_ONLY',
      name: '药品儿童专用/限儿童（名称匹配）',
      rule_type: 'drug_age',
      severity: 'warn',
      names: childOnlyNames,
      predicate: (names) => [
        { fact: 'patient.age', op: '>', value: 14, description: '大于儿童年龄限制' },
        ...predicateNameIn(names)
      ],
      message: '【提醒】{order.drug_name} 为儿童专用/限儿童使用，当前患者年龄 {patient.age} 岁，请确认是否继续。'
    }))
  }

  const argOut = process.argv.find(a => a.startsWith('out='))?.split('=')[1]
  const outPath = argOut ? path.resolve(argOut) : path.join(OUTPUT_DIR, 'rule-pack-from-precise.json')
  fs.writeFileSync(outPath, JSON.stringify(rules, null, 2), 'utf8')

  const report = {
    counts: {
      female: femaleNames.length,
      male: maleNames.length,
      unknownGender: unknownGender.length,
      inpatient: inpatientNames.length,
      outpatient: outpatientNames.length,
      unknownVisit: unknownVisit.length,
      child: childOnlyNames.length
    },
    notes: [
      'unknownGender/unknownVisit 列表未进入规则，请人工复核并补充关键词或编码映射。'
    ]
  }
  if (!fs.existsSync(OUTPUT_DIR)) fs.mkdirSync(OUTPUT_DIR, { recursive: true })
  fs.writeFileSync(path.join(OUTPUT_DIR, 'rule-pack-from-precise.report.json'), JSON.stringify(report, null, 2), 'utf8')

  // eslint-disable-next-line no-console
  console.log('[generate-precise-rule-pack] TS Done.')
  console.log(' Output:', outPath)
  console.log(' Report:', path.join(OUTPUT_DIR, 'rule-pack-from-precise.report.json'))
}

main()
