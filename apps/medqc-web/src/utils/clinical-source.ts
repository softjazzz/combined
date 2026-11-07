/** 普通病历固定东华；历史任务和已登记材料由后端专用路径解析。 */
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
  return 'independent_cdm'
}

export function setPageClinicalSource(_source: string): void {
  const url = new URL(window.location.href)
  if (url.pathname.includes('customer-sample-validation') || url.searchParams.has('job_id')) return
  url.searchParams.set('source_id', 'independent_cdm')
  window.history.replaceState(window.history.state, '', `${url.pathname}${url.search}${url.hash}`)
}
