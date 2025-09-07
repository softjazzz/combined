import { query, buildQuery } from '@health-qc/web-utils'
import { supabase } from './supabase'

export async function listMedicalRecords() {
  const base = supabase.from('yibao_medical_records').select('*', { count: 'exact' })
  const q = buildQuery(base, { page: 1, pageSize: 20, sortBy: 'created_at', sortOrder: 'desc' })
  return query(() => q)
}


