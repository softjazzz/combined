import type { DocItem, PatientRecord } from './types'

export function getRecordVisitKey(record?: PatientRecord | null): string {
  return String(record?.visitId || record?.id || '').trim()
}

export function isRecordDischarged(record?: PatientRecord | null): boolean {
  return Boolean(record?.dischargeDate && record.dischargeDate.trim() !== '')
}

export function hasExtractableFrontpageSource(
  record?: PatientRecord | null,
  documents: DocItem[] = [],
  combinedMedicalText = '',
): boolean {
  if (combinedMedicalText.trim()) return true

  if (
    documents.some((doc) => {
      const hasExplicitContent = Boolean(doc.has_content && doc.content?.trim())
      const hasLengthOnlyContent = Boolean(doc.has_content && doc.length > 0)
      return hasExplicitContent || hasLengthOnlyContent
    })
  ) {
    return true
  }

  return Boolean(record?.hasAdmission)
}

export function canGenerateFrontpageDraft(
  record?: PatientRecord | null,
  documents: DocItem[] = [],
  combinedMedicalText = '',
): boolean {
  return Boolean(
    getRecordVisitKey(record) &&
      hasExtractableFrontpageSource(record, documents, combinedMedicalText),
  )
}

export function getFrontpageDraftDisabledReason(
  record?: PatientRecord | null,
  documents: DocItem[] = [],
  combinedMedicalText = '',
): string {
  if (!getRecordVisitKey(record)) return '请选择病历后生成首页草稿'
  if (!hasExtractableFrontpageSource(record, documents, combinedMedicalText)) {
    return '缺少可抽取文书，暂不能生成首页草稿'
  }
  return ''
}

export function canGenerateSettlementDraft(
  record?: PatientRecord | null,
  hasExistingSettlement = false,
): boolean {
  return isRecordDischarged(record) && !hasExistingSettlement
}
