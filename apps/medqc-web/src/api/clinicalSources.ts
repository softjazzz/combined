import { http } from '@/utils/http'

export type ClinicalSourceId = 'legacy_pg' | 'independent_cdm'
export type ClinicalSourceMode = 'fixed_donghua_cdm' | 'legacy_compat'
export interface ClinicalSourceOption {
  id: ClinicalSourceId
  name: string
  enabled: boolean
}
export interface ClinicalSourceOptions {
  mode?: ClinicalSourceMode
  default_source: ClinicalSourceId
  sources: ClinicalSourceOption[]
}
export interface ClinicalSourceSettings {
  version: number
  default_source: ClinicalSourceId
  legacy_name: string
  legacy_enabled: boolean
  cdm: {
    name: string
    enabled: boolean
    host: string
    port: number
    database: string
    username: string
  }
}
export interface ClinicalSourceCheck {
  connected: boolean
  ok: boolean
  read_only: boolean
  publication_ready: boolean | null
  dependencies: Array<{ table: string; required: boolean; status: string; missing_columns: string[] }>
}
interface Envelope<T> {
  success: boolean
  data: T
}
function unwrap<T>(value: Envelope<T>): T {
  if (value.success !== true || value.data == null) throw new Error('数据源接口未返回有效结果')
  return value.data
}
const base = '/api/v1/clinical-sources'
export const clinicalSourcesApi = {
  async options() {
    return unwrap((await http.get<Envelope<ClinicalSourceOptions>>(`${base}/options`)).data)
  },
  async configuration() {
    return unwrap((await http.get<Envelope<ClinicalSourceSettings>>(base)).data)
  },
  async save(value: ClinicalSourceSettings) {
    const saved = unwrap((await http.put<Envelope<ClinicalSourceSettings>>(base, value)).data)
    if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
      window.dispatchEvent(new Event('medqc:clinical-sources-saved'))
    }
    return saved
  },
  async check(value: ClinicalSourceSettings) {
    return unwrap(
      (
        await http.post<Envelope<ClinicalSourceCheck>>(
          `${base}/check`,
          value,
        )
      ).data,
    )
  },
}
