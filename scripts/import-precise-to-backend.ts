#!/usr/bin/env node
/**
 * Import precise-generated rule pack into the mock backend used by yibao-web.
 * Effectively copies Yibao/generated/rule-pack-from-precise.json
 * to apps/yibao-web/backend/medical_rules.json so the mock API serves it.
 */
import fs from 'fs'
import path from 'path'

const ROOT = path.resolve(__dirname, '..', '..')
const GENERATED = path.join(ROOT, 'Yibao', 'generated', 'rule-pack-from-precise.json')
const BACKEND_DIR = path.join(ROOT, 'apps', 'yibao-web', 'backend')
const TARGET = path.join(BACKEND_DIR, 'medical_rules.json')

function main() {
  if (!fs.existsSync(GENERATED)) {
    console.error(`[import-precise] Generated rule pack not found: ${GENERATED}`)
    process.exit(1)
  }
  if (!fs.existsSync(BACKEND_DIR)) {
    console.error(`[import-precise] Backend directory not found: ${BACKEND_DIR}`)
    process.exit(1)
  }
  const data = fs.readFileSync(GENERATED, 'utf8')
  // Basic validation: should be an array
  let arr: any
  try { arr = JSON.parse(data) } catch { arr = null }
  if (!Array.isArray(arr)) {
    console.error('[import-precise] Rule pack is not a JSON array.')
    process.exit(1)
  }
  fs.writeFileSync(TARGET, JSON.stringify(arr, null, 2), 'utf8')
  console.log(`[import-precise] Imported ${arr.length} rules into ${TARGET}`)
}

main()

