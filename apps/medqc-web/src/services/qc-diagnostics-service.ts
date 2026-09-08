import { ApiService } from '@/services/apiService'

export interface DiagnosticSelection {
  job_id: string
  record_ref: string
  institute_id: string
  patient_id: string
  visit_id: string
}

export interface DiagnosticPreparation {
  token: string
  expires_in_seconds: number
  included: string[]
  excluded: string[]
  notice: string
  preview: {
    results: Array<{ rule_id: string; supported: boolean; current_findings: string | null }>
  }
}

const base = '/api/v1/qc/diagnostics/history'

export async function prepareDiagnostic(
  selection: DiagnosticSelection,
): Promise<DiagnosticPreparation> {
  const response = await ApiService.requestRaw<DiagnosticPreparation>({
    method: 'POST',
    url: `${base}/prepare`,
    data: selection,
    timeout: 60000,
  })
  return response.data
}

export async function downloadDiagnostic(token: string): Promise<Blob> {
  const response = await ApiService.requestRaw<Blob>({
    method: 'POST',
    url: `${base}/${encodeURIComponent(token)}/download`,
    data: { confirmed: true },
    responseType: 'blob',
    timeout: 60000,
  })
  return response.data
}

export async function discardDiagnostic(token: string): Promise<void> {
  await ApiService.requestRaw({ method: 'DELETE', url: `${base}/${encodeURIComponent(token)}` })
}
