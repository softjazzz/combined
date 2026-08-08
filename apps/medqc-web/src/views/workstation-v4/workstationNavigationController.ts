import { computed } from 'vue'
import type { ComputedRef } from 'vue'
import type { WorkflowStageKey } from '@/types/workflow'
import type { PatientRecord } from './types'

type DetailMainTab = 'records' | 'frontpage' | 'settlement'
type AssistTab = 'coding' | 'form' | 'cost'

interface OpenRecordForStageOptions {
  stage: WorkflowStageKey | ''
  record: PatientRecord
  openRecord: (record: PatientRecord) => void
  setPendingDetailMainTab: (tab: DetailMainTab) => void
  setDetailMainTab: (tab: DetailMainTab) => void
  setAssistPanelVisible: (visible: boolean) => void
  setAssistTab: (tab: AssistTab) => void
  ensureSettlementLoadedForSelectedRecord: () => Promise<void>
}

interface CreateDetailNavigationOptions {
  getSelectedRecord: () => PatientRecord | null
  getFilteredRecords: () => PatientRecord[]
  openRecord: (record: PatientRecord) => void
  backToList: () => void
  clearPanels: () => void
}

export function findRecordById(
  records: PatientRecord[],
  recordId: string,
): PatientRecord | undefined {
  return (
    records.find((item) => item.recordKey === recordId) ||
    records.find((item) => item.id === recordId)
  )
}

export function openRecordForStage(options: OpenRecordForStageOptions) {
  const {
    stage,
    record,
    openRecord,
    setPendingDetailMainTab,
    setDetailMainTab,
    setAssistPanelVisible,
    setAssistTab,
    ensureSettlementLoadedForSelectedRecord,
  } = options

  if (stage === 'frontpage_generate' || stage === 'coding_qc' || stage === 'frontpage_qc') {
    setPendingDetailMainTab('frontpage')
  } else if (stage === 'settlement_qc') {
    setPendingDetailMainTab('settlement')
  } else {
    setPendingDetailMainTab('records')
  }

  openRecord(record)

  if (stage === 'frontpage_generate') {
    setDetailMainTab('frontpage')
    return
  }
  if (stage === 'coding_qc') {
    setDetailMainTab('frontpage')
    setAssistPanelVisible(true)
    setAssistTab('coding')
    return
  }
  if (stage === 'frontpage_qc') {
    setDetailMainTab('frontpage')
    setAssistPanelVisible(true)
    setAssistTab('form')
    return
  }
  if (stage === 'settlement_qc') {
    setDetailMainTab('settlement')
    setAssistPanelVisible(true)
    setAssistTab('cost')
    void ensureSettlementLoadedForSelectedRecord()
    return
  }
  setDetailMainTab('records')
}

export function createDetailNavigation(options: CreateDetailNavigationOptions): {
  currentRecordIndex: ComputedRef<number>
  goToPrevRecord: () => void
  goToNextRecord: () => void
  goBackToList: () => void
} {
  const { getSelectedRecord, getFilteredRecords, openRecord, backToList, clearPanels } = options

  const currentRecordIndex = computed(() => {
    const selectedRecord = getSelectedRecord()
    if (!selectedRecord) return -1
    const filteredRecords = getFilteredRecords()
    const selectedKey = selectedRecord.recordKey || selectedRecord.id
    return filteredRecords.findIndex((item) => (item.recordKey || item.id) === selectedKey)
  })

  const goToPrevRecord = () => {
    const idx = currentRecordIndex.value
    if (idx <= 0) return
    const filteredRecords = getFilteredRecords()
    openRecord(filteredRecords[idx - 1])
  }

  const goToNextRecord = () => {
    const filteredRecords = getFilteredRecords()
    const idx = currentRecordIndex.value
    if (idx < 0 || idx >= filteredRecords.length - 1) return
    openRecord(filteredRecords[idx + 1])
  }

  const goBackToList = () => {
    backToList()
    clearPanels()
  }

  return { currentRecordIndex, goToPrevRecord, goToNextRecord, goBackToList }
}
