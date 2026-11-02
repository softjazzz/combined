import { http } from '@/utils/http'

export interface QcRuntimeSettings {
  rabbitmq_enabled: boolean
  effective_mode: 'legacy' | 'rabbitmq'
  source: 'environment' | 'file'
  revision: number
  updated_at: string | null
  readiness: {
    ready: boolean
    gateway_checked: boolean
    checks: Record<'broker_config' | 'gateway_config' | 'publisher' | 'worker' | 'gateway', boolean>
  }
}

const path = '/api/v1/system/qc-runtime'
export async function getQcRuntimeSettings(signal: AbortSignal): Promise<QcRuntimeSettings> {
  return (await http.get<QcRuntimeSettings>(path, { signal })).data
}
export async function checkQcRuntimeSettings(signal: AbortSignal): Promise<QcRuntimeSettings> {
  return (await http.post<QcRuntimeSettings>(`${path}/check`, null, { signal })).data
}
export async function saveQcRuntimeSettings(
  enabled: boolean, revision: number, signal: AbortSignal,
): Promise<QcRuntimeSettings> {
  return (await http.put<QcRuntimeSettings>(path, {
    rabbitmq_enabled: enabled, expected_revision: revision,
  }, { signal })).data
}
