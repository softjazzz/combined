import { supabase } from '@/lib/supabase'

const SUPABASE_URL: string = (import.meta as any).env?.VITE_SUPABASE_URL || ''
const ANON_KEY: string = (import.meta as any).env?.VITE_SUPABASE_ANON_KEY || ''

export function functionsBaseUrl(): string {
  const base = (SUPABASE_URL || '').replace(/\/$/, '')
  return `${base}/functions/v1`
}

export async function getAuthHeader(): Promise<Record<string, string>> {
  try {
    const { data } = await supabase.auth.getSession()
    const token = data?.session?.access_token || ANON_KEY
    return { Authorization: `Bearer ${token}` }
  } catch {
    return { Authorization: `Bearer ${ANON_KEY}` }
  }
}

export function functionUrl(name: string): string {
  return `${functionsBaseUrl()}/${name}`
}

export async function functionsGet(path: string): Promise<any> {
  const headers = await getAuthHeader()
  const url = `${functionsBaseUrl()}${path.startsWith('/') ? path : '/' + path}`
  const res = await fetch(url, { headers })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function functionsPost(path: string, body: any): Promise<any> {
  const headers = { ...(await getAuthHeader()), 'Content-Type': 'application/json' }
  const url = `${functionsBaseUrl()}${path.startsWith('/') ? path : '/' + path}`
  const res = await fetch(url, { method: 'POST', headers, body: JSON.stringify(body) })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}


