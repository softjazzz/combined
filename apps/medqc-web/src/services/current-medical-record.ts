import { getEditableMedicalRecordDocuments } from './manual-case-sample-service'

export function loadCurrentMedicalRecord(
  visitId: string,
  identity: { instituteId?: string; patientId?: string },
) {
  const id = visitId.trim()
  return getEditableMedicalRecordDocuments(id, {
    institute_id: identity.instituteId?.trim() || undefined,
    patient_id: identity.patientId?.trim() || undefined,
    visit_id: id,
    source_view: 'current',
    view: 'full',
  })
}
