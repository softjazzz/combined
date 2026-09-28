import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'

const BASE_URL = '/api/v1/document-definitions'
const XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

export const DOCUMENT_DEFINITION_IMPORT_MAX_BYTES = 2 * 1024 * 1024
export const DOCUMENT_DEFINITION_IMPORT_TEMPLATE_FILENAME = 'V3.6-document-definition-import-template.xlsx'

export interface DocumentDefinition {
  id: string
  code: string
  name: string
  category: string
  template_content: string
  import_batch_id: string
  created_by: string
  created_at: string
}

export interface DocumentDefinitionPage {
  items: DocumentDefinition[]
  total: number
  page: number
  page_size: number
}

export interface DocumentDefinitionImportProblem {
  sheet: string
  row: number
  field: string
  code: string
  message: string
}

export interface DocumentDefinitionImportResult {
  import_batch_id: string
  imported_count: number
  items: DocumentDefinition[]
}

export type ApiResult<T> = { success: true; data: T } | { success: false; message: string }
export type ImportResult =
  | { success: true; data: DocumentDefinitionImportResult; resultUnknown: false; problems: [] }
  | { success: false; message: string; resultUnknown: boolean; problems: DocumentDefinitionImportProblem[] }

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function isDefinition(value: unknown): value is DocumentDefinition {
  if (!isRecord(value)) return false
  return ['id', 'code', 'name', 'category', 'template_content', 'import_batch_id', 'created_by', 'created_at']
    .every((key) => typeof value[key] === 'string')
}

function normalizePage(value: unknown): DocumentDefinitionPage | null {
  if (!isRecord(value)
    || !Array.isArray(value.items)
    || !value.items.every(isDefinition)
    || typeof value.total !== 'number'
    || !Number.isInteger(value.total)
    || value.total < 0
    || typeof value.page !== 'number'
    || !Number.isInteger(value.page)
    || value.page < 1
    || typeof value.page_size !== 'number'
    || !Number.isInteger(value.page_size)
    || value.page_size < 1) return null
  return value as unknown as DocumentDefinitionPage
}

export async function listDocumentDefinitions(params: { page: number; page_size: number; q?: string }): Promise<ApiResult<DocumentDefinitionPage>> {
  const q = params.q?.trim() || ''
  if (q.length > 200) return { success: false, message: '文书名称不能超过 200 个字符' }
  const requestParams = { page: params.page, page_size: params.page_size, ...(q ? { q } : {}) }
  try {
    const response = await ApiService.requestRaw({ method: 'GET', url: BASE_URL, params: requestParams })
    const normalized = normalizeApiSuccess<unknown>(response.data)
    const data = normalized.success ? normalizePage(normalized.data) : null
    return data
      ? { success: true, data }
      : { success: false, message: normalized.message || '文书定义列表返回格式异常' }
  } catch (error) {
    return { success: false, message: extractApiErrorMessageFromError(error, '读取文书定义失败') }
  }
}

function headerValue(headers: unknown, name: string): string {
  if (!isRecord(headers)) return ''
  const getter = Reflect.get(headers, 'get')
  if (typeof getter === 'function') {
    const value: unknown = Reflect.apply(getter, headers, [name])
    if (typeof value === 'string') return value
  }
  const target = name.toLowerCase()
  const entry = Object.entries(headers).find(([key]) => key.toLowerCase() === target)
  return typeof entry?.[1] === 'string' ? entry[1] : ''
}

export async function downloadDocumentDefinitionImportTemplate(): Promise<ApiResult<Blob>> {
  try {
    const response = await ApiService.requestRaw<Blob>({
      method: 'GET', url: `${BASE_URL}/import-template`, responseType: 'blob', timeout: 60000,
    })
    const contentType = headerValue(response.headers, 'content-type') || response.data?.type || ''
    if (!(response.data instanceof Blob) || response.data.size === 0 || !contentType.includes(XLSX_MIME)) {
      return { success: false, message: '服务端未返回有效的文书定义 XLSX 模板' }
    }
    return { success: true, data: response.data }
  } catch (error) {
    return { success: false, message: extractApiErrorMessageFromError(error, '下载文书定义模板失败') }
  }
}

function importProblems(error: unknown): DocumentDefinitionImportProblem[] {
  if (!isRecord(error) || !isRecord(error.response) || !isRecord(error.response.data)) return []
  const detail = isRecord(error.response.data.detail) ? error.response.data.detail : null
  if (!detail || !Array.isArray(detail.problems)) return []
  return detail.problems.filter((problem): problem is DocumentDefinitionImportProblem => (
    isRecord(problem)
    && typeof problem.sheet === 'string'
    && typeof problem.row === 'number'
    && Number.isInteger(problem.row)
    && problem.row >= 0
    && typeof problem.field === 'string'
    && typeof problem.code === 'string'
    && typeof problem.message === 'string'
  ))
}

function importErrorMessage(error: unknown, fallback: string): string {
  if (isRecord(error) && isRecord(error.response) && isRecord(error.response.data)) {
    const detail = isRecord(error.response.data.detail) ? error.response.data.detail : null
    if (detail && typeof detail.message === 'string' && detail.message.trim()) return detail.message.trim()
  }
  return extractApiErrorMessageFromError(error, fallback)
}

function normalizeImport(value: unknown): DocumentDefinitionImportResult | null {
  if (!isRecord(value)
    || typeof value.import_batch_id !== 'string'
    || !value.import_batch_id.trim()
    || typeof value.imported_count !== 'number'
    || !Number.isInteger(value.imported_count)
    || value.imported_count < 1
    || !Array.isArray(value.items)
    || value.items.length !== value.imported_count
    || !value.items.every(isDefinition)) return null
  return value as unknown as DocumentDefinitionImportResult
}

export async function importDocumentDefinitions(file: File): Promise<ImportResult> {
  if (!file.name.toLowerCase().endsWith('.xlsx')) {
    return { success: false, message: '仅支持 .xlsx 文书定义模板', resultUnknown: false, problems: [] }
  }
  if (file.size > DOCUMENT_DEFINITION_IMPORT_MAX_BYTES) {
    return { success: false, message: '文件不能超过 2 MiB', resultUnknown: false, problems: [] }
  }
  const form = new FormData()
  form.append('file', file)
  try {
    const response = await ApiService.requestRaw({
      method: 'POST', url: `${BASE_URL}/import`, data: form, timeout: 120000,
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    const normalized = normalizeApiSuccess<unknown>(response.data)
    const data = normalized.success ? normalizeImport(normalized.data) : null
    if (!data) {
      return {
        success: false,
        message: '服务端未返回可确认的导入结果，请刷新列表核对，不要盲目重试',
        resultUnknown: true,
        problems: [],
      }
    }
    return { success: true, data, resultUnknown: false, problems: [] }
  } catch (error) {
    const status = isRecord(error) && isRecord(error.response) && typeof error.response.status === 'number'
      ? error.response.status : undefined
    const isConfirmedRejection = status === 401 || status === 403 || status === 409 || status === 422
    return {
      success: false,
      message: isConfirmedRejection
        ? importErrorMessage(error, '文书定义导入被拒绝')
        : '导入结果无法确认，请刷新列表核对，不要盲目重试',
      resultUnknown: !isConfirmedRejection,
      problems: importProblems(error),
    }
  }
}
