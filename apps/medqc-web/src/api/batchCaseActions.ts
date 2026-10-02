import { ApiService } from '@/services/apiService'
import { normalizeApiSuccess, extractApiErrorMessageFromError } from '@/utils/api-envelope'
import { isAxiosError } from 'axios'
import type { CaseRecordReviewIdentity, CaseRecordReviewView, CaseRecordReviewSubmitResult } from './recordReviews'
import type { CommunicationSource } from './caseCommunications'
import { CommunicationError } from './caseCommunications'

export interface BatchCaseIdentity extends CaseRecordReviewIdentity { scene: 'running' | 'final' }
export interface PreparedBatchCase {
  review: CaseRecordReviewView
  source: CommunicationSource
  doctors: Array<{ id: string; name: string }>
}
async function request<T>(path: string, data: unknown): Promise<T> {
  try {
    const response = await ApiService.requestRaw<T>({ method: 'POST', url: `/api/v1/record-reviews/case/batch-item/${path}`, data })
    const result = normalizeApiSuccess<T>(response.data)
    if (!result.success || !result.data) throw new CommunicationError(result.message || '操作结果无法确认')
    return result.data
  } catch (error) {
    if (error instanceof CommunicationError) throw error
    throw new CommunicationError(extractApiErrorMessageFromError(error, '病历操作暂不可用'), isAxiosError(error) ? error.response?.status : undefined)
  }
}
export const prepareBatchCase = (identity: BatchCaseIdentity) => request<PreparedBatchCase>('prepare', identity)
export const approveBatchCase = (payload: BatchCaseIdentity & { job_id: string; envelope_id: string; request_id: string }) => request<CaseRecordReviewSubmitResult>('approve', payload)
