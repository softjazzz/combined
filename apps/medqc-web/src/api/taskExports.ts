/**
 * 全部任务CSV导出。
 *
 * 本模块只获取并校验文件，不创建下载链接。页面负责在确认请求仍为最新后触发下载，
 * 避免慢响应覆盖用户刚修改的筛选条件。
 */
import { isAxiosError } from 'axios'
import { ApiService } from '@/services/apiService'
import type { TaskListFilters } from '@/api/tasks'

const TASK_EXPORT_URL = '/api/v1/task-exports'
const DEFAULT_FILENAME = 'task-list.csv'
const CSV_CONTENT_TYPE = /^text\/csv(?:\s*;|$)/i

export type TaskExportFilters = Omit<TaskListFilters, 'tab'>

export type TaskExportResult =
  | { success: true; blob: Blob; filename: string }
  | { success: false; message: string; status?: number }

function headerValue(headers: unknown, name: string): string {
  if (!headers || typeof headers !== 'object') return ''
  const getter = Reflect.get(headers, 'get')
  if (typeof getter === 'function') {
    const value: unknown = Reflect.apply(getter, headers, [name])
    if (typeof value === 'string') return value
  }
  const target = name.toLowerCase()
  for (const [key, value] of Object.entries(headers as Record<string, unknown>)) {
    if (key.toLowerCase() === target && typeof value === 'string') return value
  }
  return ''
}

function safeFilename(value: string): string {
  const normalized = value
    .split('')
    .filter((character) => character.charCodeAt(0) > 31 && character.charCodeAt(0) !== 127)
    .join('')
    .split(/[\\/]/)
    .pop()
    ?.trim()
  return normalized && normalized !== '.' && normalized !== '..' ? normalized : DEFAULT_FILENAME
}

function filenameFromDisposition(disposition: string): string {
  const encoded = disposition.match(/(?:^|;)\s*filename\*\s*=\s*(?:UTF-8'[^']*')?([^;]+)/i)?.[1]
  if (encoded) {
    const raw = encoded.trim().replace(/^"|"$/g, '')
    try {
      return safeFilename(decodeURIComponent(raw))
    } catch {
      return DEFAULT_FILENAME
    }
  }
  const quoted = disposition.match(/(?:^|;)\s*filename\s*=\s*"([^"]*)"/i)?.[1]
  if (quoted) return safeFilename(quoted)
  const plain = disposition.match(/(?:^|;)\s*filename\s*=\s*([^;]+)/i)?.[1]
  return plain ? safeFilename(plain.trim()) : DEFAULT_FILENAME
}

function messageFromJson(value: unknown): string | undefined {
  if (typeof value === 'string') return value.trim() || undefined
  if (!value || typeof value !== 'object') return undefined
  const body = value as Record<string, unknown>
  for (const key of ['detail', 'error', 'message'] as const) {
    const candidate = body[key]
    if (typeof candidate === 'string' && candidate.trim()) return candidate.trim()
    if (candidate && typeof candidate === 'object') {
      const message = (candidate as Record<string, unknown>).message
      if (typeof message === 'string' && message.trim()) return message.trim()
    }
  }
  return undefined
}

async function messageFromBody(value: unknown): Promise<string | undefined> {
  if (value instanceof Blob) {
    if (value.size === 0) return undefined
    try {
      return messageFromJson(JSON.parse(await readBlobText(value)) as unknown)
    } catch {
      return undefined
    }
  }
  return messageFromJson(value)
}

async function readBlobText(blob: Blob): Promise<string> {
  const text = Reflect.get(blob, 'text')
  if (typeof text === 'function') {
    return String(await Reflect.apply(text, blob, []))
  }
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        resolve(reader.result)
        return
      }
      reject(new Error('Blob读取结果不是文本'))
    }
    reader.onerror = () => reject(reader.error || new Error('Blob读取失败'))
    reader.onabort = () => reject(new Error('Blob读取已中止'))
    reader.readAsText(blob, 'utf-8')
  })
}

function requestParams(filters: TaskExportFilters | undefined): TaskExportFilters {
  const params: TaskExportFilters = {}
  if (filters?.scene) params.scene = filters.scene
  if (filters?.status) params.status = filters.status
  if (filters?.keyword !== undefined && filters.keyword !== '') params.keyword = filters.keyword
  if (filters?.department) params.department = filters.department
  if (filters?.created_start) params.created_start = filters.created_start
  if (filters?.created_end) params.created_end = filters.created_end
  return params
}

/** 获取当前筛选下的全部任务CSV；调用方决定何时下载。 */
export async function exportTasksCsv(filters?: TaskExportFilters): Promise<TaskExportResult> {
  try {
    const response = await ApiService.requestRaw<Blob>({
      method: 'GET',
      url: TASK_EXPORT_URL,
      params: requestParams(filters),
      responseType: 'blob',
      timeout: 60000,
    })
    const contentType = headerValue(response.headers, 'content-type')
    if (
      response.status !== 200
      || !(response.data instanceof Blob)
      || response.data.size === 0
      || !CSV_CONTENT_TYPE.test(contentType)
    ) {
      const serverMessage = await messageFromBody(response.data)
      return {
        success: false,
        message: serverMessage || '服务端未返回有效的任务CSV文件',
        status: response.status,
      }
    }
    return {
      success: true,
      blob: response.data,
      filename: filenameFromDisposition(headerValue(response.headers, 'content-disposition')),
    }
  } catch (error) {
    const status = isAxiosError(error) ? error.response?.status : undefined
    const body = isAxiosError(error) ? error.response?.data : undefined
    const serverMessage = await messageFromBody(body)
    return {
      success: false,
      message: serverMessage || '导出任务列表失败，请稍后重试',
      ...(status === undefined ? {} : { status }),
    }
  }
}
