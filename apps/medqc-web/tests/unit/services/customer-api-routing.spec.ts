import { afterEach, describe, expect, it, vi } from 'vitest'
import { SemanticRulesService } from '@/services/semantic-rules-service'
import { MedicalRecordPersistenceService } from '@/services/medical-record-persistence-service'

vi.mock('@/utils/auth-token', () => ({ getAccessToken: () => 'test-customer-token' }))

afterEach(() => {
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
})

describe('客户包服务请求地址', () => {
  it.each([
    { configured: '', expected: '' },
    {
      configured: 'https://customer.example.test/backend',
      expected: 'https://customer.example.test/backend',
    },
  ])('生产请求遵循同源配置或显式地址 $configured', async ({ configured, expected }) => {
    vi.stubEnv('DEV', false)
    vi.stubEnv('VITE_API_USE_SAME_ORIGIN', 'true')
    vi.stubEnv('VITE_API_BASE_URL', configured)
    vi.stubGlobal('window', {
      location: { hostname: '192.168.20.10', protocol: 'http:' },
    })
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, data: {}, id: 'test-record' }),
    })
    vi.stubGlobal('fetch', fetchMock)
    await new SemanticRulesService().getEngineStats()
    expect(fetchMock).toHaveBeenLastCalledWith(
      `${expected}/api/v1/semantic-rules/stats`,
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({ Authorization: 'Bearer test-customer-token' }),
      }),
    )
    await new MedicalRecordPersistenceService().createMedicalRecord({
      record_name: '合成测试',
      patient_info: { name: '合成测试' },
      department: '测试科室',
      primary_diagnosis: '',
    })
    expect(fetchMock).toHaveBeenLastCalledWith(
      `${expected}/api/medical-records`,
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: 'Bearer test-customer-token' }),
      }),
    )
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
