import type { ClinicalSourceId, ClinicalSourceMode } from '@/api/clinicalSources'

let activeClinicalSourceMode: ClinicalSourceMode = 'fixed_donghua_cdm'
let activeCompatClinicalSource: ClinicalSourceId = 'legacy_pg'

function isClinicalSourceId(value: string | null | undefined): value is ClinicalSourceId {
  return value === 'legacy_pg' || value === 'independent_cdm'
}

export function setClinicalSourceMode(
  mode?: ClinicalSourceMode,
  activeSource?: ClinicalSourceId,
): void {
  activeClinicalSourceMode = mode === 'legacy_compat' ? 'legacy_compat' : 'fixed_donghua_cdm'
  if (activeClinicalSourceMode === 'legacy_compat' && isClinicalSourceId(activeSource)) {
    activeCompatClinicalSource = activeSource
  }
}

export function resetClinicalSourceMode(): void {
  activeClinicalSourceMode = 'fixed_donghua_cdm'
  activeCompatClinicalSource = 'legacy_pg'
}

/** 普通病历默认固定东华；仅在后端显式开启 legacy_compat 时按页签来源透传；历史任务和已登记材料由后端专用路径解析。 */
export function clinicalSourceForRequest(url?: string, method = 'GET'): string | undefined {
  if (!url || typeof window === 'undefined') return undefined
  if (!/^\/api\/(?:v1\/)?(?:medical-records|emr|records|qc\/sichuan)(?:\/|$)/u.test(url))
    return undefined
  const request = new URL(url, window.location.origin)
  if (method.toUpperCase() === 'GET' && [
    '/api/v1/qc/sichuan/workspace/rule-sets',
    '/api/v1/qc/sichuan/workspace/batch-jobs',
  ].includes(request.pathname)) return undefined
  if (request.pathname.includes('/workspace/batch-jobs/') || request.searchParams.has('job_id')) return undefined
  if (window.location.pathname.includes('customer-sample-validation')) return undefined
  if (activeClinicalSourceMode === 'legacy_compat') {
    const pageSource = new URLSearchParams(window.location.search).get('source_id')
    return isClinicalSourceId(pageSource) ? pageSource : activeCompatClinicalSource
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
