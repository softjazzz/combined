import { http } from '@/utils/http'
import { getAccessToken } from '@/utils/auth-token'
import { isClinicalSourceModeInitialized, setClinicalSourceMode } from '@/utils/clinical-source'

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

let inFlightSourceModeInit: Promise<void> | null = null

/**
 * 首次进入任意工作台子页（如直接打开或刷新 /qc-feedback-demo）时，按会话同步一次后端临床来源模式，
 * 避免未先访问病历池时前端沿用默认 fixed_donghua_cdm 错发 X-Clinical-Source: independent_cdm。
 */
export async function ensureClinicalSourceModeInitialized(): Promise<void> {
  if (isClinicalSourceModeInitialized()) return
  if (typeof window === 'undefined' || !getAccessToken()) return
  if (inFlightSourceModeInit) return inFlightSourceModeInit
  inFlightSourceModeInit = (async () => {
    try {
      const options = await clinicalSourcesApi.options()
      if (!options) return
      const mode: ClinicalSourceMode =
        options.mode === 'legacy_compat' ? 'legacy_compat' : 'fixed_donghua_cdm'
      const enabledSources = Array.isArray(options.sources)
        ? options.sources.filter((item) => item?.enabled)
        : []
      const defaultEnabled = enabledSources.find((item) => item.id === options.default_source)
      const activeSource: ClinicalSourceId =
        defaultEnabled?.id ?? enabledSources[0]?.id ?? options.default_source ?? 'legacy_pg'
      setClinicalSourceMode(mode, activeSource)
    } catch {
      // 拉取来源模式失败时保持默认策略，不阻断页面主流程
    } finally {
      inFlightSourceModeInit = null
    }
  })()
  return inFlightSourceModeInit
}
