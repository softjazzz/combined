import { query, buildQuery } from '@health-qc/web-utils'
import { getSupabase } from '@health-qc/web-utils'

export async function listMedicalRecords() {
  const supabase = getSupabase()
  if (!supabase) {
    return { success: false, error: { message: 'Supabase 未初始化' } } as any
  }
  const base = supabase.from('yibao_medical_records').select('*', { count: 'exact' })
  const q = buildQuery(base, { page: 1, pageSize: 20, sortBy: 'created_at', sortOrder: 'desc' })
  return query(() => q)
}


