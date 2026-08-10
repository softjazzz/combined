import { message } from 'ant-design-vue'
import { extractApiErrorMessageFromError } from '@/utils/api-envelope'
import { createSichuanWorkspaceBatchJob } from '@/services/sichuan-rule-workspace-service'
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

interface RunRecordPoolQcParams {
  keys: string[]
  getBatchExtracting: () => boolean
  setBatchExtracting: (value: boolean) => void
  findBatchRecordByKey: (recordKey: string) => PatientRecord | null
  setSelectedWorkbenchKeys: (keys: string[]) => void
}

const RECORD_POOL_QC_MESSAGE_KEY = 'workstation-v4-record-pool-qc'

function recordPoolQcError(
  content: string,
  selectedRecordKeys: string[],
  setSelectedWorkbenchKeys: (keys: string[]) => void,
) {
  setSelectedWorkbenchKeys(selectedRecordKeys)
  message.error({
    key: RECORD_POOL_QC_MESSAGE_KEY,
    content,
  })
}

export async function runRecordPoolQc(params: RunRecordPoolQcParams): Promise<void> {
  const {
    keys,
    getBatchExtracting,
    setBatchExtracting,
    findBatchRecordByKey,
    setSelectedWorkbenchKeys,
  } = params
  if (getBatchExtracting()) return

  const selectedRecordKeys = Array.from(
    new Set(keys.map((key) => String(key || '').trim()).filter(Boolean)),
  )
  if (!selectedRecordKeys.length) return

  const recordRefs: Array<{ institute_id: string; patient_id: string; visit_id: string }> = []
  const identityOwners = new Map<string, string>()
  for (const recordKey of selectedRecordKeys) {
    const record = findBatchRecordByKey(recordKey)
    if (!record || String(record.recordKey || '').trim() !== recordKey) {
      recordPoolQcError(
        '选中病历身份已失效，请刷新列表后重新选择。',
        selectedRecordKeys,
        setSelectedWorkbenchKeys,
      )
      return
    }

    const instituteId = String(record.instituteId || '').trim()
    const patientId = String(record.patientId || '').trim()
    const visitId = String(record.visitId || '').trim()
    if (!instituteId || !patientId || !visitId) {
      recordPoolQcError(
        '选中病历缺少完整病例标识，暂不能启动质控。',
        selectedRecordKeys,
        setSelectedWorkbenchKeys,
      )
      return
    }

    const identityKey = JSON.stringify([instituteId, patientId, visitId])
    const existingOwner = identityOwners.get(identityKey)
    if (existingOwner && existingOwner !== recordKey) {
      recordPoolQcError(
        '选中病历存在身份冲突，暂不能启动批量质控。',
        selectedRecordKeys,
        setSelectedWorkbenchKeys,
      )
      return
    }
    identityOwners.set(identityKey, recordKey)
    recordRefs.push({
      institute_id: instituteId,
      patient_id: patientId,
      visit_id: visitId,
    })
  }

  setBatchExtracting(true)
  message.loading({
    key: RECORD_POOL_QC_MESSAGE_KEY,
    content: `正在创建 ${recordRefs.length} 份病历的质控任务…`,
    duration: 0,
  })
  try {
    const response = await createSichuanWorkspaceBatchJob({
      rule_set_key: 'luxian_0609_qc_v1',
      scope: 'all',
      date_field: 'admission',
      record_refs: recordRefs,
    })
    if (!response.success || !response.data) {
      recordPoolQcError(
        response.message || '质控任务创建失败，请稍后重试。',
        selectedRecordKeys,
        setSelectedWorkbenchKeys,
      )
      return
    }

    setSelectedWorkbenchKeys([])
    if (response.data.idempotency_reused) {
      message.info({
        key: RECORD_POOL_QC_MESSAGE_KEY,
        content: '相同质控任务已存在，正在继续执行质控',
      })
      return
    }
    message.success({
      key: RECORD_POOL_QC_MESSAGE_KEY,
      content: '质控任务已创建，正在执行质控',
    })
  } catch (error) {
    recordPoolQcError(
      extractApiErrorMessageFromError(error, '质控任务创建失败，请稍后重试。'),
      selectedRecordKeys,
      setSelectedWorkbenchKeys,
    )
  } finally {
    setBatchExtracting(false)
  }
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
