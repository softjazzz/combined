import { ApiService } from './apiService'
import type { SyntheticCaseGoldenAnswer } from '@/views/workstation-v4/customer-sample-validation/types'

export type ValidationReview = { decision: 'accepted' | 'rejected'; note: string; reviewed_by: string; reviewed_at: string }
export type ValidationRun = { id: string; revision: number; answers: SyntheticCaseGoldenAnswer[]; job_id: string | null; created_at: string; state: string; reviews: ValidationReview[] }
export type ValidationState = { revision: number; answers: SyntheticCaseGoldenAnswer[]; runs: ValidationRun[]; rule_options: { rule_id: string; name: string; release_scope: string }[] }
export type ValidationResult = { run: ValidationRun; job_status: string; comparisons: (SyntheticCaseGoldenAnswer & { actual_status: string | null; comparison: string })[] }
const base = (id: string) => `/api/v1/qc/sample-pools/test-records/${encodeURIComponent(id)}/validation`
export const readValidation = (id: string) => ApiService.get<ValidationState>(base(id))
export const saveValidation = (id: string, revision: number, answers: SyntheticCaseGoldenAnswer[]) => ApiService.put<ValidationState>(base(id), { revision, answers })
export const startValidation = (id: string, revision: number) => ApiService.post<{ run_id: string; job_id: string }>(`${base(id)}/runs`, { revision })
export const readValidationResult = (id: string, run: string) => ApiService.get<ValidationResult>(`${base(id)}/runs/${encodeURIComponent(run)}`)
export const reviewValidation = (id: string, run: string, decision: string, note: string) => ApiService.post<ValidationResult>(`${base(id)}/runs/${encodeURIComponent(run)}/reviews`, { decision, note })
