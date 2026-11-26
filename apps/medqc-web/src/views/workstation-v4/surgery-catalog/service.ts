import { ApiService, type ApiRequestConfig } from '@/services/apiService'

export interface SurgeryProcedureCatalogItem {
  code: string
  name: string
  category: string
  effective_level: string
  raw_level: string
  source: string
  source_label: string
}

export interface SurgeryProcedureCatalogQuery {
  keyword?: string
  category?: string
  effectiveLevel?: string
  source?: string
  page: number
  pageSize: number
}

export interface SurgeryProcedureCatalogData {
  version: string
  policy: {
    level_priority: string
    conditional_level_four: string
    category_boundary: string
  }
  summary: {
    total: number
    surgery: number
    operation: number
    level_four_surgery: number
  }
  filter_options: {
    categories: string[]
    levels: string[]
    sources: Array<{ value: string; label: string }>
  }
  items: SurgeryProcedureCatalogItem[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

function unwrapCatalogData(payload: unknown): SurgeryProcedureCatalogData {
  const envelope =
    payload && typeof payload === 'object' ? (payload as Record<string, unknown>) : {}
  const data = envelope.data && typeof envelope.data === 'object' ? envelope.data : envelope
  return data as unknown as SurgeryProcedureCatalogData
}

export async function fetchSurgeryProcedureCatalog(
  query: SurgeryProcedureCatalogQuery,
  config?: ApiRequestConfig,
): Promise<SurgeryProcedureCatalogData> {
  const response = await ApiService.getRaw(
    '/api/v1/qc/sichuan/surgery-procedure-catalog',
    {
      keyword: query.keyword?.trim() || undefined,
      category: query.category || undefined,
      effective_level: query.effectiveLevel || undefined,
      source: query.source || undefined,
      page: query.page,
      page_size: query.pageSize,
    },
    config,
  )
  return unwrapCatalogData(response.data)
}
