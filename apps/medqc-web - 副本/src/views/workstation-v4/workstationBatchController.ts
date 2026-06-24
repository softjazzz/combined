import { message } from 'ant-design-vue'
import { extractApiErrorMessageFromError } from '@/utils/api-envelope'
import type { WorkflowStageKey } from '@/types/workflow'
import type { PatientRecord } from './types'
import {
  requestFrontpageDraft as requestFrontpageDraftAction,
  persistBatchFrontpageDraft as persistBatchFrontpageDraftAction,
  requestCodingQc as requestCodingQcAction,
  requestFrontpageQc as requestFrontpageQcAction,
  requestSettlementQc as requestSettlementQcAction,
  createBatchSummaryNotification as createBatchSummaryNotificationAction,
} from './workstationActions'
import {
  currentBatchActionText as currentBatchActionTextForStage,
  batchSuccessSummary as batchSuccessSummaryForStage,
} from './workstationBatchActions'

type BatchRuntimeStatus = 'running' | 'failed' | 'submitted'

interface RunBatchExtractParams {
  keys: string[]
  currentStageFilter: WorkflowStageKey | ''
  isStageQueueMode: boolean
  isAggregatedStageMode: boolean
  getBatchExtracting: () => boolean
  setBatchExtracting: (value: boolean) => void
  findBatchRecordByVisitId: (visitId: string) => PatientRecord | null
  setBatchRuntimeStatus: (
    stage: WorkflowStageKey | '',
    visitIds: string[],
    status: BatchRuntimeStatus,
  ) => void
  setSingleBatchRuntimeStatus: (
    stage: WorkflowStageKey | '',
    visitId: string,
    status: BatchRuntimeStatus,
  ) => void
  setSelectedWorkbenchKeys: (keys: string[]) => void
  fetchAssistNotifications: () => Promise<void>
  refreshActiveWorklist: () => Promise<void>
  refreshData: () => Promise<void>
  refreshSelectedSnapshots: () => Promise<void>
}

export async function runBatchExtract(params: RunBatchExtractParams): Promise<void> {
  const {
    keys,
    currentStageFilter,
    isStageQueueMode,
    isAggregatedStageMode,
    getBatchExtracting,
    setBatchExtracting,
    findBatchRecordByVisitId,
    setBatchRuntimeStatus,
    setSingleBatchRuntimeStatus,
    setSelectedWorkbenchKeys,
    fetchAssistNotifications,
    refreshActiveWorklist,
    refreshData,
    refreshSelectedSnapshots,
  } = params

  if (!keys.length || getBatchExtracting()) return
  if (!isStageQueueMode) return

  const visitIds = Array.from(new Set(keys.map((key) => String(key || '').trim()).filter(Boolean)))
  if (!visitIds.length) return
  const stage = currentStageFilter
  setBatchRuntimeStatus(stage, visitIds, 'running')

  const messageKey = 'workstation-v4-batch-extract'
  const summary = batchSuccessSummaryForStage(currentStageFilter, 0, visitIds.length)
  setBatchExtracting(true)
  message.loading({
    key: messageKey,
    content: currentBatchActionTextForStage(currentStageFilter, visitIds.length),
    duration: 0,
  })

  let successCount = 0
  let highRiskCount = 0
  const failedVisitIds: string[] = []
  let firstError = ''

  try {
    for (const visitId of visitIds) {
      try {
        const record = findBatchRecordByVisitId(visitId)
        if (!record) {
          throw new Error(`未找到病历 ${visitId}，无法继续批量处理`)
        }

        if (currentStageFilter === 'frontpage_generate') {
          const result = await requestFrontpageDraftAction(visitId)
          await persistBatchFrontpageDraftAction(record, result.draft)
          highRiskCount += result.highRiskCount || 0
          setSingleBatchRuntimeStatus(stage, visitId, 'submitted')
        } else {
          let result: { persistence: any; totalIssues: number; highRiskCount: number } | null = null
          if (currentStageFilter === 'coding_qc') {
            result = await requestCodingQcAction(record)
          } else if (currentStageFilter === 'frontpage_qc') {
            result = await requestFrontpageQcAction(record)
          } else if (currentStageFilter === 'settlement_qc') {
            result = await requestSettlementQcAction(record)
          } else {
            throw new Error('当前阶段未配置批量动作')
          }
          highRiskCount += Number(result?.highRiskCount || 0)
          setSingleBatchRuntimeStatus(stage, visitId, 'submitted')
        }
        successCount += 1
      } catch (error) {
        failedVisitIds.push(visitId)
        setSingleBatchRuntimeStatus(stage, visitId, 'failed')
        if (!firstError) {
          firstError = extractApiErrorMessageFromError(error, summary.failure)
        }
      }
    }

    if (failedVisitIds.length === 0) {
      message.success({
        key: messageKey,
        content: batchSuccessSummaryForStage(currentStageFilter, successCount, visitIds.length)
          .success,
      })
      setSelectedWorkbenchKeys([])
    } else if (successCount === 0) {
      message.error({
        key: messageKey,
        content:
          firstError ||
          batchSuccessSummaryForStage(currentStageFilter, successCount, visitIds.length).failure,
      })
      setSelectedWorkbenchKeys(failedVisitIds)
    } else {
      message.warning({
        key: messageKey,
        content: batchSuccessSummaryForStage(currentStageFilter, successCount, visitIds.length)
          .partial,
      })
      setSelectedWorkbenchKeys(failedVisitIds)
    }

    if (visitIds.length > 0) {
      try {
        await createBatchSummaryNotificationAction({
          workflowType: currentStageFilter as
            | 'frontpage_generate'
            | 'coding_qc'
            | 'frontpage_qc'
            | 'settlement_qc',
          totalCount: visitIds.length,
          successCount,
          failedCount: failedVisitIds.length,
          highRiskCount,
        })
      } catch (error) {
        console.warn('创建批量汇总消息失败:', error)
      }
    }

    if (successCount > 0 || failedVisitIds.length > 0) {
      await fetchAssistNotifications()
    }
    if (successCount > 0) {
      if (isAggregatedStageMode) {
        await refreshActiveWorklist()
      } else {
        await refreshData()
      }
      await refreshSelectedSnapshots()
    }
  } finally {
    setBatchExtracting(false)
  }
}
