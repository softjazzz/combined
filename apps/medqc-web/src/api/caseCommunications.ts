import { isAxiosError } from 'axios'
import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'

export interface CommunicationIdentity {
  institute_id: string
  patient_id: string
  visit_id: string
  root_job_id: string
}
export interface CommunicationSource extends CommunicationIdentity {
  scene: 'running' | 'final'
  envelope_id: string
  rule_set_key: string
  rule_set_version: string
}
export interface Communication extends CommunicationSource {
  id: string
  actor_id: string
  action: 'urge' | 'opinion' | 'withdraw'
  content: string
  recipient_id: string
  request_id: string
  related_event_id: string | null
  notification_id: string
  is_read: boolean
  read_at: string | null
  withdrawn: boolean
  department: string
  created_at: string
}
export interface CommunicationDetail extends Communication {
  history: Communication[]
}
export interface CommunicationCandidates {
  source: CommunicationSource
  department: string
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
export interface CommunicationInbox {
  items: Communication[]
  page: number
  page_size: number
  total: number
  has_more: boolean
}
export class CommunicationError extends Error {
  constructor(
    message: string,
    public status?: number,
  ) {
    super(message)
  }
  get unknown() {
    return this.status === undefined || this.status >= 500
  }
}
async function request<T>(method: 'GET' | 'POST', path: string, data?: unknown): Promise<T> {
  try {
    const response = await ApiService.requestRaw<T>({
      method,
      url: `/api/v1/case-communications${path}`,
      ...(data ? { data } : {}),
    })
    const payload = normalizeApiSuccess<T>(response.data)
    if (!payload.success || payload.data === undefined)
      throw new CommunicationError(payload.message || '病历沟通响应无法确认')
    return payload.data
  } catch (error) {
    if (error instanceof CommunicationError) throw error
    throw new CommunicationError(
      extractApiErrorMessageFromError(error, '病历沟通暂不可用'),
      isAxiosError(error) ? error.response?.status : undefined,
    )
  }
}
export const getCommunicationCandidates = ({
  institute_id,
  patient_id,
  visit_id,
  root_job_id,
}: CommunicationIdentity) =>
  request<CommunicationCandidates>('POST', '/candidates', {
    institute_id,
    patient_id,
    visit_id,
    root_job_id,
  })
export const createCommunication = (data: CommunicationCreate) =>
  request<Communication>('POST', '', data)
export const getCommunicationInbox = (page = 1, pageSize = 20) =>
  request<CommunicationInbox>('GET', `/inbox?page=${page}&page_size=${pageSize}`)
export const readCommunication = (id: string) =>
  request<CommunicationDetail>('POST', `/${encodeURIComponent(id)}/read`)
export const getCommunication = (id: string) =>
  request<CommunicationDetail>('GET', `/${encodeURIComponent(id)}`)
