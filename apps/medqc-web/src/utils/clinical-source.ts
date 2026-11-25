import type { ClinicalSourceId, ClinicalSourceMode } from '@/api/clinicalSources'

let activeClinicalSourceMode: ClinicalSourceMode = 'fixed_donghua_cdm'
let activeCompatClinicalSource: ClinicalSourceId = 'legacy_pg'
let clinicalSourceModeInitialized = false

function isClinicalSourceId(value: string | null | undefined): value is ClinicalSourceId {
  return value === 'legacy_pg' || value === 'independent_cdm'
}

export function isClinicalSourceModeInitialized(): boolean {
  return clinicalSourceModeInitialized
}

export function setClinicalSourceMode(
  mode?: ClinicalSourceMode,
  activeSource?: ClinicalSourceId,
): void {
  clinicalSourceModeInitialized = true
  activeClinicalSourceMode = mode === 'legacy_compat' ? 'legacy_compat' : 'fixed_donghua_cdm'
  if (activeClinicalSourceMode === 'legacy_compat' && isClinicalSourceId(activeSource)) {
    activeCompatClinicalSource = activeSource
  }
}

export function resetClinicalSourceMode(): void {
  clinicalSourceModeInitialized = false
  activeClinicalSourceMode = 'fixed_donghua_cdm'
  activeCompatClinicalSource = 'legacy_pg'
}

const ORDINARY_CLINICAL_API_RE =
  /^\/api\/(?:v1\/)?(?:medical-records|emr|records|qc\/sichuan)(?:\/|$)/u
const FALLBACK_AWARE_CLINICAL_API_RE =
  /^\/api\/v1\/(?:workstation|frontpage-qc|quality-reports|core-system-reports|custom-qc\/workspace)(?:\/|\?|$)/u

/** 普通病历默认固定东华；仅在后端显式开启 legacy_compat 时按页签来源透传；历史任务和已登记材料由后端专用路径解析。 */
export function clinicalSourceForRequest(url?: string, method = 'GET'): string | undefined {
  if (!url || typeof window === 'undefined') return undefined
  const isOrdinaryClinicalPath = ORDINARY_CLINICAL_API_RE.test(url)
  const isFallbackAwareClinicalPath = FALLBACK_AWARE_CLINICAL_API_RE.test(url)
  if (!isOrdinaryClinicalPath && !isFallbackAwareClinicalPath) return undefined
  const request = new URL(url, window.location.origin)
  if (isOrdinaryClinicalPath) {
    if (
      method.toUpperCase() === 'GET' &&
      [
        '/api/v1/qc/sichuan/workspace/rule-sets',
        '/api/v1/qc/sichuan/workspace/batch-jobs',
      ].includes(request.pathname)
    ) {
      return undefined
    }
    if (request.pathname.includes('/workspace/batch-jobs/') || request.searchParams.has('job_id')) {
      return undefined
    }
  }
  if (window.location.pathname.includes('customer-sample-validation')) return undefined
  if (activeClinicalSourceMode === 'legacy_compat') {
    const pageSource = new URLSearchParams(window.location.search).get('source_id')
    return isClinicalSourceId(pageSource) ? pageSource : activeCompatClinicalSource
  }
  if (isFallbackAwareClinicalPath) {
    // 默认 fixed_donghua_cdm 模式下，workstation / frontpage-qc / quality-reports / core-system-reports / custom-qc/workspace 不强加未请求 header，
    // 以保留本地无 CDM 时的 legacy_snapshot 安全回退；仅当 URL 显式指定 independent_cdm 时透传。
    const requestSource = request.searchParams.get('source_id')
    const pageSource = new URLSearchParams(window.location.search).get('source_id')
    if (requestSource === 'independent_cdm' || (!requestSource && pageSource === 'independent_cdm')) {
      return 'independent_cdm'
    }
    return undefined
  }
  return 'independent_cdm'
}

export function setPageClinicalSource(source: string): void {
  const url = new URL(window.location.href)
  if (url.pathname.includes('customer-sample-validation') || url.searchParams.has('job_id')) return
  const target: ClinicalSourceId =
    activeClinicalSourceMode === 'legacy_compat' && isClinicalSourceId(source)
      ? source
      : 'independent_cdm'
  if (activeClinicalSourceMode === 'legacy_compat') {
    activeCompatClinicalSource = target
  }
  url.searchParams.set('source_id', target)
  window.history.replaceState(window.history.state, '', `${url.pathname}${url.search}${url.hash}`)
}
