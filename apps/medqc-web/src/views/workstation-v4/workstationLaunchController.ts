import type {
  WorkstationLaunchAction,
  WorkstationLaunchContext,
  WorkflowStageKey,
} from '@/types/workflow'
import type { PatientRecord } from './types'
import { findRecordById, RECORD_RESELECTION_MESSAGE } from './workstationNavigationController'

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

  // 质控类入口只定位到对应面板并展示已有结果，不自动发起质控（编码质控会调用大模型），
  // 由用户在面板中点击“开始分析”显式触发。
  if (ctx.action === 'qc_coding') {
    params.setDetailMainTab('frontpage')
    params.setAssistPanelVisible(true)
    params.setAssistTab('coding')
    return
  }

  if (ctx.action === 'qc_frontpage') {
    params.setDetailMainTab('frontpage')
    params.setAssistPanelVisible(true)
    params.setAssistTab('form')
    return
  }

  if (ctx.action === 'qc_settlement') {
    params.setDetailMainTab('settlement')
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

  const targetRecord = findRecordById(params.allRecords, ctx.record_id, {
    ignoreCaseForLegacyId: true,
  })
  if (!targetRecord) {
    params.showWarning(RECORD_RESELECTION_MESSAGE)
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
