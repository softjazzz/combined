#!/usr/bin/env node
import 'dotenv/config'
import { createClient } from '@supabase/supabase-js'
import { writeFileSync } from 'fs'
import { join } from 'path'

async function main() {
  const url = process.env.VITE_SUPABASE_URL
  const key = process.env.VITE_SUPABASE_ANON_KEY
  if (!url || !key) {
    console.error('Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY in environment')
    process.exit(1)
  }
  const supabase = createClient(url, key)

  // 1) document_category_config
  const { data: categories, error: catErr } = await supabase
    .from('document_category_config')
    .select('*')
    .order('sort_order')

  if (catErr) {
    console.error('document_category_config query error:', catErr.message)
  }

  const active = (categories || []).filter((c: any) => c.is_active)

  // 2) qc_rules distribution by primary_document_category
  const { data: rules, error: ruleErr } = await supabase
    .from('qc_rules')
    .select('primary_document_category')

  if (ruleErr) {
    console.error('qc_rules query error:', ruleErr.message)
  }

  const counts: Record<string, number> = {}
  ;(rules || []).forEach((r: any) => {
    const cat = r.primary_document_category
    if (cat) counts[cat] = (counts[cat] || 0) + 1
  })

  const report = {
    supabase_url_prefix: url.slice(0, 40) + '...'
      , categories_total: (categories || []).length
      , categories_active: active.length
      , categories_list: (categories || []).map((c: any) => ({
          category_code: c.category_code,
          category_name: c.category_name,
          is_active: c.is_active,
          sort_order: c.sort_order
        }))
      , rules_total: (rules || []).length
      , primary_document_category_counts: counts
  }

  const outPath = join(process.cwd(), 'scripts', 'report-qc-stats.out.json')
  writeFileSync(outPath, JSON.stringify(report, null, 2), 'utf-8')
  console.log('WROTE', outPath)
}

main().catch((e) => {
  console.error('report-qc-stats failed:', e)
  try {
    const outPath = join(process.cwd(), 'scripts', 'report-qc-stats.out.json')
    writeFileSync(outPath, JSON.stringify({ error: String(e) }, null, 2), 'utf-8')
  } catch {}
  process.exit(1)
})

