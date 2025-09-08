import type { SupabaseClient } from '@supabase/supabase-js'

let currentSupabase: SupabaseClient | null = null

export function setSupabase(client: SupabaseClient | null): void {
  currentSupabase = client
}

export function getSupabase(): SupabaseClient | null {
  return currentSupabase
}


