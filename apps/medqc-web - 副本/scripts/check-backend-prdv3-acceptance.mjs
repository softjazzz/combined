import { readFile } from 'node:fs/promises'
import path from 'node:path'

const root = process.cwd()

const checks = [
  {
    id: 'P1-DASHBOARD',
    file: 'backend/app/routers/dashboard_api.py',
    patterns: ['@router.get("/todo-stats")']
  },
  {
    id: 'P2-DEFECTS',
    file: 'backend/app/routers/defects.py',
    patterns: [
      '@router.post("/{defect_id}/urge")',
      '@router.post("/batch-action")',
      '@router.get("/export")'
    ]
  },
  {
    id: 'P3-EMR',
    file: 'backend/app/routers/emr_render.py',
    patterns: ['@router.get("/{record_id}/documents")', '@router.get("/{record_id}/render")']
  },
  {
    id: 'P4-TASKS',
    file: 'backend/app/routers/tasks.py',
    patterns: [
      '@router.post("")',
      '@router.post("/{task_id}/sample")',
      '@router.post("/{task_id}/assign")',
      '@router.get("/{task_id}/progress")'
    ]
  },
  {
    id: 'P7-RANKING',
    file: 'backend/app/routers/staff_ranking.py',
    patterns: ['@router.get("")']
  },
  {
    id: 'P8-SCORING-RULES',
    file: 'backend/app/routers/scoring_rules.py',
    patterns: [
      '@router.get("")',
      '@router.post("")',
      '@router.put("/{rule_id}")',
      '@router.delete("/{rule_id}")'
    ]
  },
  {
    id: 'P8-SCORING-CONFIG',
    file: 'backend/app/routers/scoring_config.py',
    patterns: ['@router.get("")', '@router.put("")', '@router.post("/preview")']
  },
  {
    id: 'MAIN-ROUTER-INCLUDE',
    file: 'backend/app/main.py',
    patterns: [
      'include_router(dashboard_api_router.router)',
      'include_router(defects_router.router)',
      'include_router(emr_render_router.router)',
      'include_router(tasks_router.router)',
      'include_router(staff_ranking_router.router)',
      'include_router(scoring_rules_router.router)',
      'include_router(scoring_config_router.router)'
    ]
  }
]

let failed = 0

for (const check of checks) {
  const absolutePath = path.join(root, check.file)
  const content = await readFile(absolutePath, 'utf8')
  const missing = check.patterns.filter((pattern) => !content.includes(pattern))

  if (missing.length > 0) {
    failed += 1
    console.error(`FAIL ${check.id}: missing ${missing.length} pattern(s) in ${check.file}`)
    for (const item of missing) {
      console.error(`  - ${item}`)
    }
  } else {
    console.log(`PASS ${check.id}`)
  }
}

if (failed > 0) {
  console.error(`\nBackend PRD v3 acceptance check failed (${failed} check group(s)).`)
  process.exit(1)
}

console.log('\nBackend PRD v3 acceptance check passed.')
