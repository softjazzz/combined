import type { QueueStatusCode, WorkflowStageKey } from '@/types/workflow'
import type { PatientRecord, WorkstationWorklistItem } from './types'
import { QUEUE_STATUS_LABEL_MAP, aggregatedStageWorkflows } from './workstationStageController'

export type BatchRuntimeStatus = 'running' | 'failed' | 'submitted'

export function runtimeStatusKey(stage: WorkflowStageKey | '', visitId: string): string {
  return `${stage || 'default'}::${String(visitId || '').trim()}`
}

export function updateBatchRuntimeStatuses(
  current: Record<string, BatchRuntimeStatus>,
  stage: WorkflowStageKey | '',
  visitIds: string[],
  status: BatchRuntimeStatus,
): Record<string, BatchRuntimeStatus> {
  if (!visitIds.length) return current
  const next = { ...current }
  for (const visitId of visitIds) {
    next[runtimeStatusKey(stage, visitId)] = status
  }
  return next
}

export function updateSingleBatchRuntimeStatus(
  current: Record<string, BatchRuntimeStatus>,
  stage: WorkflowStageKey | '',
  visitId: string,
  status: BatchRuntimeStatus,
): Record<string, BatchRuntimeStatus> {
  return {
    ...current,
    [runtimeStatusKey(stage, visitId)]: status,
  }
}

function runtimeStatusLabel(stage: WorkflowStageKey | '', status: BatchRuntimeStatus): string {
  if (status === 'failed') return '执行失败'
  if (status === 'submitted') return '已提交'
  if (stage === 'frontpage_generate') return '生成中'
  return '质控中'
}

function isQueueStatusCode(status: string): status is QueueStatusCode {
  return (
    status === 'unknown' ||
    status === 'pending' ||
    status === 'running' ||
    status === 'succeeded' ||
    status === 'failed'
  )
}

function resolveQueueStatusLabel(
  stage: WorkflowStageKey | '',
  status: QueueStatusCode,
  workflowType?: WorkstationWorklistItem['workflowType'],
): string {
  if (stage === 'frontpage_generate') {
    return QUEUE_STATUS_LABEL_MAP.frontpage_generate[status]
  }
  const workflow =
    workflowType ||
    (stage && aggregatedStageWorkflows[stage] ? aggregatedStageWorkflows[stage] : undefined)
  if (workflow) {
    return QUEUE_STATUS_LABEL_MAP[workflow][status]
  }
  return status
}

export function resolveStageStatus(params: {
  stage: WorkflowStageKey | ''
  visitId: string
  fallback: string
  runtimeStatusMap: Record<string, BatchRuntimeStatus>
  record?: PatientRecord
  workflowType?: WorkstationWorklistItem['workflowType']
}): string {
  const { stage, visitId, fallback, runtimeStatusMap, record, workflowType } = params
  const runtimeStatus = runtimeStatusMap[runtimeStatusKey(stage, visitId)]
  if (runtimeStatus) {
    return runtimeStatusLabel(stage, runtimeStatus)
  }
  if (stage === 'frontpage_generate') {
    if (isQueueStatusCode(fallback)) {
      return resolveQueueStatusLabel(stage, fallback)
    }
    if (record?.hasFrontpageDraft || record?.frontpageDraftUpdatedAt) return '已生成'
    return QUEUE_STATUS_LABEL_MAP.frontpage_generate.pending
  }
  if (isQueueStatusCode(fallback)) {
    return resolveQueueStatusLabel(stage, fallback, workflowType)
  }
  return fallback
}
