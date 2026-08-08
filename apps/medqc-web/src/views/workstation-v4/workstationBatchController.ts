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
  findBatchRecordByKey: (recordKey: string) => PatientRecord | null
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
    findBatchRecordByKey,
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

  const selectedRecordKeys = keys.map((key) => String(key || '').trim()).filter(Boolean)
  const recordsByVisitId = new Map<string, { recordKey: string; record: PatientRecord }>()
  let hasAmbiguousVisitIdentity = false
  for (const recordKey of selectedRecordKeys) {
    if (!recordKey) continue
    const record = findBatchRecordByKey(recordKey)
    const visitId = String(record?.visitId || record?.id || '').trim()
    if (!record || !visitId) continue
    const existing = recordsByVisitId.get(visitId)
    if (existing && existing.recordKey !== recordKey) {
      hasAmbiguousVisitIdentity = true
      break
    }
    if (existing) continue
    recordsByVisitId.set(visitId, { recordKey, record })
  }
  if (hasAmbiguousVisitIdentity) {
    message.error({
      key: 'workstation-v4-batch-extract',
      content: '选中病历存在同一住院号对应多个不同病历身份，暂无法确认批量处理对象。',
    })
    setSelectedWorkbenchKeys(selectedRecordKeys)
    return
  }
  const visitIds = [...recordsByVisitId.keys()]
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
    const failedRecordKeys: string[] = []
    for (const visitId of visitIds) {
      try {
        const batchRecord = recordsByVisitId.get(visitId)
        if (!batchRecord) throw new Error(`未找到病历 ${visitId}，无法继续批量处理`)
        const { record } = batchRecord

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
        const failedRecord = recordsByVisitId.get(visitId)
        if (failedRecord) failedRecordKeys.push(failedRecord.recordKey)
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
      setSelectedWorkbenchKeys(failedRecordKeys)
    } else {
      message.warning({
        key: messageKey,
        content: batchSuccessSummaryForStage(currentStageFilter, successCount, visitIds.length)
          .partial,
      })
      setSelectedWorkbenchKeys(failedRecordKeys)
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
