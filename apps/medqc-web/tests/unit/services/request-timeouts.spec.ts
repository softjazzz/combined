import { expect, it, vi } from 'vitest'
import { ApiService, apiClient } from '@/services/apiService'
import {
  getLatestLuxian0609RecordResult,
  requestLuxian0609RemediationDraft,
} from '@/services/sichuan-rule-workspace-service'
import {
  getEditableMedicalRecordDocument,
  getEditableMedicalRecordDocuments,
} from '@/services/manual-case-sample-service'

it('登录、规则工作区、整改草稿和可编辑文书保留各自超时', async () => {
  const requests: { url?: string; timeout?: number }[] = []
  const originalAdapter = apiClient.defaults.adapter
  const loginLog = vi.spyOn(console, 'log').mockImplementation(() => undefined)
  apiClient.defaults.adapter = async (config) => {
    requests.push({ url: config.url, timeout: config.timeout })
    return {
      config,
      data: {
        documents: [{ doc_type: 'admission_record', document_id: 'test-doc', content: '合成文书' }],
      },
      headers: {},
      status: 200,
      statusText: 'OK',
    }
  }

  try {
    const record = { instituteId: 'test-institute', patientId: 'test-patient', visitId: 'test-visit' }
    await ApiService.login({ account: 'test-account', password: 'synthetic-only' })
    await getLatestLuxian0609RecordResult(record)
    await requestLuxian0609RemediationDraft(record, 'test-rule')
    const list = await getEditableMedicalRecordDocuments(record.visitId)
    const document = list.data?.documents[0]
    if (!document) throw new Error('缺少测试文书')
    await getEditableMedicalRecordDocument(record.visitId, document)

    const resultUrl = '/api/v1/qc/sichuan/workspace/records/test-visit/latest-result'
    expect(requests).toEqual([
      { url: '/api/v1/auth/login', timeout: 15000 },
      { url: resultUrl, timeout: 60000 },
      { url: `${resultUrl}/remediation-draft`, timeout: 120000 },
      { url: '/api/v1/emr/test-visit/documents', timeout: 90000 },
      { url: '/api/v1/emr/test-visit/render', timeout: 90000 },
    ])
  } finally {
    apiClient.defaults.adapter = originalAdapter
    loginLog.mockRestore()
  }
})
