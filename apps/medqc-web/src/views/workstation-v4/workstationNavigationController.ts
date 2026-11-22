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
  showWarning?: (message: string) => void
}

export const RECORD_RESELECTION_MESSAGE = '无法唯一定位病历，请从列表重新选择'

type RecordIdentity = Pick<PatientRecord, 'instituteId' | 'patientId' | 'visitId' | 'recordKey'>

function readCompleteRecordKey(value: string): string[] | undefined {
  if (!value.trimStart().startsWith('[')) return
  try {
    const parts: unknown = JSON.parse(value)
    if (
      Array.isArray(parts) &&
      parts.length === 3 &&
      parts.every((part): part is string => typeof part === 'string' && Boolean(part.trim()))
    ) {
      return parts.map((part) => part.trim())
    }
  } catch {
    return undefined
  }
}

export function getCompleteRecordKey(record: RecordIdentity): string | undefined {
  const coordinates = [record.instituteId, record.patientId, record.visitId].map((part) =>
    part?.trim(),
  )
  if (coordinates.every(Boolean)) return JSON.stringify(coordinates)
  const keyParts = readCompleteRecordKey(record.recordKey || '')
  if (keyParts && coordinates.every((part, index) => !part || part === keyParts[index])) {
    return JSON.stringify(keyParts)
  }
}

export function getRecordNavigationKey(record: PatientRecord): string {
  return getCompleteRecordKey(record) || record.id || record.visitId || ''
}

export function findRecordById(
  records: PatientRecord[],
  recordId: string,
  { ignoreCaseForLegacyId = false } = {},
): PatientRecord | undefined {
  const requested = recordId.trim()
  if (!requested) return undefined

  const keyParts = readCompleteRecordKey(requested)
  if (requested.startsWith('[') && !keyParts) return undefined
  const key = keyParts ? JSON.stringify(keyParts) : undefined
  const normalizeLegacyId = (value?: string) => {
    const trimmed = value?.trim()
    return ignoreCaseForLegacyId ? trimmed?.toLowerCase() : trimmed
  }
  const legacyId = normalizeLegacyId(requested)
  const matches = records.filter((record) =>
    key
      ? getCompleteRecordKey(record) === key
      : normalizeLegacyId(record.id) === legacyId || normalizeLegacyId(record.visitId) === legacyId,
  )
  return matches.length === 1 ? matches[0] : undefined
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
  recordCount: ComputedRef<number>
  goToPrevRecord: () => void
  goToNextRecord: () => void
  goBackToList: () => void
} {
  const { getSelectedRecord, getFilteredRecords, openRecord, backToList, clearPanels, showWarning } =
    options

  const navigationRecords = computed(() => {
    const selected = getSelectedRecord()
    if (!selected) return []
    return getFilteredRecords().filter((record) => record.sourceId === selected.sourceId)
  })

  const currentRecordIndex = computed(() => {
    const selected = getSelectedRecord()
    if (!selected) return -1
    const records = navigationRecords.value
    const record = findRecordById(records, getRecordNavigationKey(selected))
    return record ? records.indexOf(record) : -1
  })

  const recordCount = computed(() =>
    currentRecordIndex.value < 0 ? 0 : navigationRecords.value.length,
  )

  const goToOffset = (offset: number) => {
    const index = currentRecordIndex.value
    if (index < 0) return
    const records = navigationRecords.value
    const next = records[index + offset]
    if (!next) return
    const record = findRecordById(records, getRecordNavigationKey(next))
    if (record) openRecord(record)
    else showWarning?.(RECORD_RESELECTION_MESSAGE)
  }

  const goBackToList = () => {
    backToList()
    clearPanels()
  }

  return {
    currentRecordIndex,
    recordCount,
    goToPrevRecord: () => goToOffset(-1),
    goToNextRecord: () => goToOffset(1),
    goBackToList,
  }
}
