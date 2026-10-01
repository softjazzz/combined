import { isAxiosError } from 'axios'
import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'

export interface CommunicationSource {
  institute_id: string
  patient_id: string
  visit_id: string
  scene: 'running' | 'final'
  root_job_id: string
  envelope_id: string
}
export interface Communication extends CommunicationSource {
  id: string
  action: 'urge' | 'opinion' | 'withdraw'
  content: string
  recipient_id: string
  request_id: string
  related_event_id: string | null
  is_read: boolean | null
  read_at: string | null
  withdrawn: boolean
  department: string
  created_at: string
}
export interface CommunicationCandidates {
  source: CommunicationSource
  doctors: Array<{ id: string; name: string }>
  items: Communication[]
}
export interface CommunicationCreate extends CommunicationSource {
  action: Communication['action']
  content: string
  recipient_id: string
  request_id: string
  related_event_id?: string
}
export class CommunicationError extends Error {
  constructor(message: string, public status?: number) { super(message) }
  get unknown() { return this.status === undefined || this.status >= 500 }
}
async function request<T>(method: 'GET' | 'POST', path: string, data?: unknown): Promise<T> {
  try {
    const response = await ApiService.requestRaw<T>({ method, url: `/api/v1/case-communications${path}`, ...(data ? { data } : {}) })
    const payload = normalizeApiSuccess<T>(response.data)
    if (!payload.success || payload.data === undefined) throw new CommunicationError(payload.message || '病例沟通响应无法确认')
    return payload.data
  } catch (error) {
    if (error instanceof CommunicationError) throw error
    throw new CommunicationError(extractApiErrorMessageFromError(error, '病例沟通暂不可用'), isAxiosError(error) ? error.response?.status : undefined)
  }
}
export const getCommunicationCandidates = (source: Omit<CommunicationSource, 'envelope_id'>) => request<CommunicationCandidates>('POST', '/candidates', source)
export const createCommunication = (data: CommunicationCreate) => request<Communication>('POST', '', data)
export interface CommunicationInbox { items: Communication[]; page: number; page_size: number; total: number; has_more: boolean }
export const getCommunicationInbox = (page = 1, pageSize = 20) => request<CommunicationInbox>('GET', `/inbox?page=${page}&page_size=${pageSize}`)
export const readCommunication = (id: string) => request<Communication>('POST', `/${encodeURIComponent(id)}/read`)
export const getCommunication = (id: string) => request<Communication>('GET', `/${encodeURIComponent(id)}`)
