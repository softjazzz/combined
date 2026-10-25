import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, unwrapApiEnvelope } from '@/utils/api-envelope'

export type AppealState = 'pending' | 'reviewing' | 'approved' | 'rejected' | 'withdrawn'
export type AppealAction = 'withdraw' | 'approve' | 'reject'
export interface ModernAppeal {
  id: string
  target_kind: 'canonical_defect' | 'task_manual_defect'
  target_id: string
  institute_id: string
  patient_id: string
  visit_id: string
  scene: 'running' | 'final'
  root_job_id: string
  envelope_id: string
  rule_set_key: string
  rule_set_version: string
  case_department: string
  appellant_id: string
  appellant_name: string
  reason: string
  status: AppealState
  resolution: string | null
  created_at: string
}
export interface AppealDetail extends ModernAppeal {
  events: Array<{
    id: string
    action: AppealAction
    reviewer_name: string
    comment: string
    created_at: string
  }>
}
export interface AppealList {
  items: ModernAppeal[]
  total: number
  pending_count: number
}
const base = '/api/v1/modern-appeals'
const states: AppealState[] = ['pending', 'reviewing', 'approved', 'rejected', 'withdrawn']
const actions: AppealAction[] = ['withdraw', 'approve', 'reject']
const object = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)
function validAppeal(value: unknown): value is ModernAppeal {
  return (
    object(value) &&
    [
      'id',
      'target_id',
      'institute_id',
      'patient_id',
      'visit_id',
      'root_job_id',
      'envelope_id',
      'rule_set_key',
      'rule_set_version',
      'case_department',
      'appellant_id',
      'appellant_name',
      'reason',
      'created_at',
    ].every((key) => typeof value[key] === 'string' && value[key].trim().length > 0) &&
    (value.target_kind === 'canonical_defect' || value.target_kind === 'task_manual_defect') &&
    (value.scene === 'running' || value.scene === 'final') &&
    states.some((state) => state === value.status) &&
    (value.resolution === null || typeof value.resolution === 'string')
  )
}
async function request(config: Parameters<typeof ApiService.requestRaw>[0]): Promise<unknown> {
  try {
    const response = await ApiService.requestRaw<unknown>(config)
    return unwrapApiEnvelope<unknown>(response.data)
  } catch (error) {
    throw new Error(extractApiErrorMessageFromError(error, '申诉服务暂不可用，请刷新核对'))
  }
}
function appeal(value: unknown): ModernAppeal {
  if (!validAppeal(value)) throw new Error('申诉来源或状态无效，请刷新核对')
  return value
}
export async function createModernAppeal(rectificationId: string, reason: string) {
  return appeal(
    await request({
      url: base,
      method: 'POST',
      data: { rectification_id: rectificationId, reason },
    }),
  )
}
export async function listModernAppeals(
  state?: AppealState | 'open',
  scene?: 'running' | 'final',
  page = 1,
): Promise<AppealList> {
  const value = await request({
    url: base,
    method: 'GET',
    params: { state, scene, page, page_size: 10 },
  })
  if (
    !object(value) ||
    !Array.isArray(value.items) ||
    !value.items.every(validAppeal) ||
    !Number.isSafeInteger(value.total) ||
    Number(value.total) < 0 ||
    !Number.isSafeInteger(value.pending_count) ||
    Number(value.pending_count) < 0
  )
    throw new Error('申诉待办数据无效，请刷新核对')
  return {
    items: value.items,
    total: Number(value.total),
    pending_count: Number(value.pending_count),
  }
}
export async function getModernAppeal(id: string): Promise<AppealDetail> {
  const value = await request({ url: `${base}/${encodeURIComponent(id)}`, method: 'GET' })
  const row = appeal(value)
  if (
    !object(value) ||
    !Array.isArray(value.events) ||
    !value.events.every(
      (event) =>
        object(event) &&
        ['id', 'reviewer_name', 'comment', 'created_at'].every(
          (key) => typeof event[key] === 'string',
        ) &&
        actions.some((action) => action === event.action),
    )
  )
    throw new Error('申诉历史无效，请刷新核对')
  return { ...row, events: value.events as AppealDetail['events'] }
}
export async function actOnModernAppeal(
  id: string,
  expectedStatus: AppealState,
  action: AppealAction,
  comment: string,
) {
  return appeal(
    await request({
      url: `${base}/${encodeURIComponent(id)}/actions`,
      method: 'POST',
      data: { expected_status: expectedStatus, action, comment },
    }),
  )
}
