import type { QueueStatusCode, WorkflowStageKey } from '@/types/workflow'
import type { PatientRecord, WorkstationWorklistItem } from './types'
import { QUEUE_STATUS_LABEL_MAP, aggregatedStageWorkflows } from './workstationStageController'

export type BatchRuntimeStatus = 'running' | 'failed' | 'submitted'

export interface RuntimeStatusIdentity {
  instituteId?: string | null
  patientId?: string | null
  visitId: string
}

export type RuntimeStatusTarget = string | RuntimeStatusIdentity

function normalizeKeyPart(value?: string | null): string {
  return String(value ?? '').trim()
}

function parseRuntimeTarget(
  target: RuntimeStatusTarget,
  instituteId?: string | null,
  patientId?: string | null,
): { instituteId: string; patientId: string; visitId: string } {
  if (typeof target !== 'string') {
    return {
      instituteId: normalizeKeyPart(instituteId ?? target.instituteId),
      patientId: normalizeKeyPart(patientId ?? target.patientId),
      visitId: normalizeKeyPart(target.visitId),
    }
  }
  const raw = normalizeKeyPart(target)
  if (raw.startsWith('[') && raw.endsWith(']')) {
    try {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed) && parsed.length === 3) {
        return {
          instituteId: normalizeKeyPart(instituteId ?? parsed[0]),
          patientId: normalizeKeyPart(patientId ?? parsed[1]),
          visitId: normalizeKeyPart(parsed[2]),
        }
      }
    } catch {
      // 非合法 JSON 三键时按裸 visitId 兼容处理
    }
  }
  return {
    instituteId: normalizeKeyPart(instituteId),
    patientId: normalizeKeyPart(patientId),
    visitId: raw,
  }
}

export function runtimeStatusKey(
  stage: WorkflowStageKey | '',
  target: RuntimeStatusTarget,
  instituteId?: string | null,
  patientId?: string | null,
): string {
  const parsed = parseRuntimeTarget(target, instituteId, patientId)
  return `${stage || 'default'}::${parsed.instituteId}::${parsed.patientId}::${parsed.visitId}`
}

export function updateBatchRuntimeStatuses(
  current: Record<string, BatchRuntimeStatus>,
  stage: WorkflowStageKey | '',
  targets: RuntimeStatusTarget[],
  status: BatchRuntimeStatus,
): Record<string, BatchRuntimeStatus> {
  if (!targets.length) return current
  const next = { ...current }
  for (const target of targets) {
    next[runtimeStatusKey(stage, target)] = status
  }
  return next
}

export function updateSingleBatchRuntimeStatus(
  current: Record<string, BatchRuntimeStatus>,
  stage: WorkflowStageKey | '',
  target: RuntimeStatusTarget,
  status: BatchRuntimeStatus,
  identity?: { instituteId?: string | null; patientId?: string | null },
): Record<string, BatchRuntimeStatus> {
  return {
    ...current,
    [runtimeStatusKey(stage, target, identity?.instituteId, identity?.patientId)]: status,
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
  instituteId?: string | null
  patientId?: string | null
  fallback: string
  runtimeStatusMap: Record<string, BatchRuntimeStatus>
  record?: PatientRecord
  workflowType?: WorkstationWorklistItem['workflowType']
}): string {
  const {
    stage,
    visitId,
    instituteId,
    patientId,
    fallback,
    runtimeStatusMap,
    record,
    workflowType,
  } = params
  const effectiveInstituteId = normalizeKeyPart(instituteId ?? record?.instituteId)
  const effectivePatientId = normalizeKeyPart(patientId ?? record?.patientId)
  const effectiveVisitId = normalizeKeyPart(visitId || record?.visitId || record?.id)
  const exactKey = runtimeStatusKey(stage, {
    instituteId: effectiveInstituteId,
    patientId: effectivePatientId,
    visitId: effectiveVisitId,
  })
  const unscopedKey =
    effectiveInstituteId || effectivePatientId
      ? runtimeStatusKey(stage, effectiveVisitId)
      : ''
  const legacyKey = `${stage || 'default'}::${effectiveVisitId}`
  const runtimeStatus =
    runtimeStatusMap[exactKey] ??
    (unscopedKey ? runtimeStatusMap[unscopedKey] : undefined) ??
    runtimeStatusMap[legacyKey]
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
