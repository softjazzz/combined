import { ApiService } from '@/services/apiService'
import { unwrapApiEnvelope, extractApiErrorMessageFromError } from '@/utils/api-envelope'

export type RectificationState = 'pending' | 'submitted' | 'approved' | 'rejected'
export type RectificationAction = 'submit' | 'approve' | 'reject' | 'urge'
export interface RectificationTarget {
  target_kind: 'canonical_defect' | 'task_manual_defect'
  target_id: string
  scene: 'running' | 'final' | 'outpatient_emergency'
  root_job_id: string
  envelope_id: string
}
export interface RectificationIdentity {
  institute_id: string
  patient_id: string
  visit_id: string
}
export interface Rectification extends RectificationTarget, RectificationIdentity {
  id: string
  creator_id: string
  assignee_id: string
  assignee_name: string
  requirement: string
  status: RectificationState
  version: number
  department: string
  submission: string | null
  review_comment: string | null
  updated_at: string
}
export interface RectificationDetail extends Rectification {
  events: Array<{
    id: string
    action: string
    comment: string
    created_at: string
    version: number
  }>
}
export interface RectificationCandidates {
  targets: Array<RectificationTarget & { label: string }>
  doctors: Array<{ id: string; name: string }>
  department: string
}
const base = '/api/v1/defect-rectifications'
async function request<T>(config: Parameters<typeof ApiService.requestRaw>[0]): Promise<T> {
  try {
    const response = await ApiService.requestRaw<T>(config)
    return unwrapApiEnvelope<T>(response.data)
  } catch (error) {
    throw new Error(extractApiErrorMessageFromError(error, '整改服务暂不可用，请刷新核对'))
  }
}
export const getRectificationCandidates = (identity: RectificationIdentity, job: string) =>
  request<RectificationCandidates>({
    url: `${base}/candidates`,
    method: 'GET',
    params: { ...identity, expected_job_id: job },
  })
export const createRectification = (
  data: RectificationIdentity & RectificationTarget & { assignee_id: string; requirement: string },
) => request<Rectification>({ url: base, method: 'POST', data })
export const listRectifications = (state?: RectificationState, page = 1) =>
  request<{ items: Rectification[]; total: number }>({
    url: base,
    method: 'GET',
    params: { state, page, page_size: 10 },
  })
export const getRectification = (id: string) =>
  request<RectificationDetail>({ url: `${base}/${encodeURIComponent(id)}`, method: 'GET' })
export const actOnRectification = (
  id: string,
  version: number,
  action: RectificationAction,
  comment: string,
) =>
  request<Rectification>({
    url: `${base}/${encodeURIComponent(id)}/actions`,
    method: 'POST',
    data: { version, action, comment },
  })
