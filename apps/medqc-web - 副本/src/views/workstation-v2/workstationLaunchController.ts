import type {
  WorkstationLaunchAction,
  WorkstationLaunchContext,
  WorkflowStageKey,
} from '@/types/workflow'
import type { PatientRecord } from './types'

interface HandleWorkstationLaunchParams {
  routeQuery: Record<string, unknown>
  allRecords: PatientRecord[]
  validLaunchActions: WorkstationLaunchAction[]
  validStages: WorkflowStageKey[]
  handledLaunchKey: string
  launchHandling: boolean
  setHandledLaunchKey: (value: string) => void
  setLaunchHandling: (value: boolean) => void
  clearLaunchQueryParams: () => void
  openRecord: (record: PatientRecord) => void
  setDetailMainTab: (tab: 'records' | 'frontpage' | 'settlement') => void
  setAssistPanelVisible: (visible: boolean) => void
  setAssistTab: (tab: 'coding' | 'form' | 'cost') => void
  nextTick: () => Promise<void>
  handleGenerateFrontpage: () => void
  runCodingQc: () => void
  runFormQc: () => void
  isDischarged: boolean
  runSettlementQc: () => Promise<void>
  getSettlementLoading: () => boolean
  showWarning: (message: string) => void
}

function parseLaunchContext(
  routeQuery: Record<string, unknown>,
  validLaunchActions: WorkstationLaunchAction[],
  validStages: WorkflowStageKey[],
): WorkstationLaunchContext | null {
  const source = String(routeQuery.source || '').trim()
  const recordId = String(routeQuery.record_id || '').trim()
  const actionRaw = String(routeQuery.action || '').trim()
  if (!recordId || source !== 'dashboard') return null
  if (!validLaunchActions.includes(actionRaw as WorkstationLaunchAction)) return null
  const ctx: WorkstationLaunchContext = {
    record_id: recordId,
    action: actionRaw as WorkstationLaunchAction,
    source: 'dashboard',
  }
  const taskId = String(routeQuery.task_id || '').trim()
  if (taskId) ctx.task_id = taskId
  const stage = String(routeQuery.from_stage || '').trim()
  if (validStages.includes(stage as WorkflowStageKey)) {
    ctx.from_stage = stage as WorkflowStageKey
  }
  return ctx
}

function launchKeyOf(ctx: WorkstationLaunchContext): string {
  return [ctx.record_id, ctx.action, ctx.task_id || '', ctx.from_stage || ''].join('|')
}

function findRecordForLaunch(allRecords: PatientRecord[], recordId: string): PatientRecord | null {
  const target = recordId.trim().toLowerCase()
  if (!target) return null
  const matched = allRecords.find((record: PatientRecord) => {
    const candidateIds = [
      String(record.id || '')
        .trim()
        .toLowerCase(),
      String(record.visitId || '')
        .trim()
        .toLowerCase(),
      String((record as any).record_id || '')
        .trim()
        .toLowerCase(),
      String((record as any).task_id || '')
        .trim()
        .toLowerCase(),
    ]
    return candidateIds.includes(target)
  })
  return matched || null
}

async function waitForSettlementReady(
  getSettlementLoading: () => boolean,
  timeoutMs = 6000,
): Promise<void> {
  if (!getSettlementLoading()) return
  const started = Date.now()
  while (getSettlementLoading() && Date.now() - started < timeoutMs) {
    await new Promise((resolve) => window.setTimeout(resolve, 120))
  }
}

async function executeLaunchAction(
  ctx: WorkstationLaunchContext,
  record: PatientRecord,
  params: HandleWorkstationLaunchParams,
) {
  params.openRecord(record)
  await params.nextTick()

  if (ctx.action === 'open_record') {
    params.setDetailMainTab('records')
    return
  }

  if (ctx.action === 'generate_frontpage') {
    params.setDetailMainTab('frontpage')
    await params.nextTick()
    params.handleGenerateFrontpage()
    return
  }

  if (ctx.action === 'qc_coding') {
    params.setDetailMainTab('frontpage')
    params.setAssistPanelVisible(true)
    params.setAssistTab('coding')
    await params.nextTick()
    params.runCodingQc()
    return
  }

  if (ctx.action === 'qc_frontpage') {
    params.setDetailMainTab('frontpage')
    params.setAssistPanelVisible(true)
    params.setAssistTab('form')
    await params.nextTick()
    params.runFormQc()
    return
  }

  if (ctx.action === 'qc_settlement') {
    params.setDetailMainTab('settlement')
    await params.nextTick()
    if (!params.isDischarged) {
      params.showWarning('当前病历未出院，暂不可执行结算质控')
      return
    }
    await waitForSettlementReady(params.getSettlementLoading)
    await params.runSettlementQc()
    params.setAssistPanelVisible(true)
    params.setAssistTab('cost')
  }
}

export async function handleWorkstationLaunchFlow(
  params: HandleWorkstationLaunchParams,
): Promise<void> {
  const ctx = parseLaunchContext(params.routeQuery, params.validLaunchActions, params.validStages)
  if (!ctx) {
    params.setHandledLaunchKey('')
    return
  }
  if (!params.allRecords.length || params.launchHandling) return

  const key = launchKeyOf(ctx)
  if (params.handledLaunchKey === key) return

  const targetRecord = findRecordForLaunch(params.allRecords, ctx.record_id)
  if (!targetRecord) {
    params.showWarning('未找到目标病历，已取消自动联动')
    params.setHandledLaunchKey(key)
    params.clearLaunchQueryParams()
    return
  }

  params.setLaunchHandling(true)
  try {
    await executeLaunchAction(ctx, targetRecord, params)
    params.setHandledLaunchKey(key)
    params.clearLaunchQueryParams()
  } finally {
    params.setLaunchHandling(false)
  }
}
