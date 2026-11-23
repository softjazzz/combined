import { EXTENDED_REQUEST_TIMEOUT_MS, STANDARD_REQUEST_TIMEOUT_MS } from '@/config/requestTimeouts'
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
    timeout: EXTENDED_REQUEST_TIMEOUT_MS,
  })
  return response.data
}

export async function downloadDiagnostic(token: string): Promise<Blob> {
  const response = await ApiService.requestRaw<Blob>({
    method: 'POST',
    url: `${base}/${encodeURIComponent(token)}/download`,
    data: { confirmed: true },
    responseType: 'blob',
    timeout: EXTENDED_REQUEST_TIMEOUT_MS,
  })
  return response.data
}

export async function discardDiagnostic(token: string): Promise<void> {
  await ApiService.requestRaw({ method: 'DELETE', url: `${base}/${encodeURIComponent(token)}` })
}

export interface DiagnosticCaptureStatus {
  state: 'running' | 'ready' | 'failed' | 'unavailable'
  capture_completeness?: 'complete' | 'partial'
  missing_components?: string[]
  included?: string[]
  size_bytes?: number
  notice?: string
  error_code?: string
}

const captureBase = '/api/v1/qc/diagnostics/capture'

export async function startDiagnosticCapture(
  selection: DiagnosticSelection,
): Promise<{ job_id: string }> {
  const response = await ApiService.requestRaw<{ job_id: string }>({
    method: 'POST',
    url: `${captureBase}/start`,
    data: selection,
    timeout: EXTENDED_REQUEST_TIMEOUT_MS,
  })
  return response.data
}

export async function getDiagnosticCapture(jobId: string): Promise<DiagnosticCaptureStatus> {
  const response = await ApiService.requestRaw<DiagnosticCaptureStatus>({
    method: 'GET',
    url: `${captureBase}/${encodeURIComponent(jobId)}`,
    timeout: STANDARD_REQUEST_TIMEOUT_MS,
  })
  return response.data
}

export async function downloadDiagnosticCapture(jobId: string): Promise<Blob> {
  const response = await ApiService.requestRaw<Blob>({
    method: 'POST',
    url: `${captureBase}/${encodeURIComponent(jobId)}/download`,
    data: { confirmed: true },
    responseType: 'blob',
    timeout: EXTENDED_REQUEST_TIMEOUT_MS,
  })
  return response.data
}
