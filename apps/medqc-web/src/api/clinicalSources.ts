import { http } from '@/utils/http'

export type ClinicalSourceId = 'legacy_pg' | 'independent_cdm'
export interface ClinicalSourceOption {
  id: ClinicalSourceId
  name: string
  enabled: boolean
}
export interface ClinicalSourceOptions {
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
    return unwrap((await http.put<Envelope<ClinicalSourceSettings>>(base, value)).data)
  },
  async check(value: ClinicalSourceSettings) {
    return unwrap(
      (
        await http.post<Envelope<{ connected: boolean; read_only: boolean }>>(
          `${base}/check`,
          value,
        )
      ).data,
    )
  },
}
