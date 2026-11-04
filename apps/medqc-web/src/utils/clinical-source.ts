/** 来源属于当前页面，禁止通过localStorage在不同页签间隐式切换。 */
export function clinicalSourceForRequest(url?: string): string | undefined {
  if (!url || typeof window === 'undefined') return undefined
  if (!/^\/api\/(?:v1\/)?(?:medical-records|emr|records|qc\/sichuan)(?:\/|$)/u.test(url))
    return undefined
  if (window.location.pathname.includes('customer-sample-validation')) return 'legacy_pg'
  const source = new URLSearchParams(window.location.search).get('source_id')
  return source === 'legacy_pg' || source === 'independent_cdm' ? source : undefined
}

export function setPageClinicalSource(source: string): void {
  const url = new URL(window.location.href)
  url.searchParams.set('source_id', source)
  window.history.replaceState(window.history.state, '', `${url.pathname}${url.search}${url.hash}`)
}
