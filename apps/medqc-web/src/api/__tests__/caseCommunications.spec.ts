import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  CommunicationError,
  getCommunication,
  createCommunication,
  getCommunicationCandidates,
  readCommunication,
} from '@/api/caseCommunications'

const mocks = vi.hoisted(() => ({ raw: vi.fn() }))
vi.mock('@/services/apiService', () => ({ ApiService: { requestRaw: mocks.raw } }))
const source = {
  institute_id: 'H',
  patient_id: 'P',
  visit_id: 'V',
  scene: 'running' as const,
  root_job_id: 'J',
  envelope_id: 'E',
  rule_set_key: 'K',
  rule_set_version: '1',
}
beforeEach(() => vi.clearAllMocks())
describe('病历沟通API合同', () => {
  it('候选只发送三坐标和任务，不从上游对象携带页面场景', async () => {
    mocks.raw.mockResolvedValue({ data: { success: true, data: { source } } })
    const upstream = { ...source, scene: 'final' as const }
    await getCommunicationCandidates(upstream)
    expect(mocks.raw).toHaveBeenCalledWith({
      method: 'POST',
      url: '/api/v1/case-communications/candidates',
      data: { institute_id: 'H', patient_id: 'P', visit_id: 'V', root_job_id: 'J' },
    })
  })
  it('保留完整冻结版本及指定收件人', async () => {
    const body = {
      ...source,
      recipient_id: 'doc',
      action: 'urge' as const,
      request_id: 'request',
      content: '催办',
    }
    mocks.raw.mockResolvedValue({ data: { success: true, data: { ...body, id: 'event' } } })
    await createCommunication(body)
    expect(mocks.raw).toHaveBeenCalledWith({
      method: 'POST',
      url: '/api/v1/case-communications',
      data: body,
    })
  })
  it('精确编码事件ID并保留统一响应', async () => {
    mocks.raw.mockResolvedValue({ data: { success: true, data: { id: 'event' } } })
    await getCommunication('a/b')
    await readCommunication('a/b')
    expect(mocks.raw.mock.calls[0][0].url).toBe('/api/v1/case-communications/a%2Fb')
    expect(mocks.raw.mock.calls[1][0].url).toBe('/api/v1/case-communications/a%2Fb/read')
  })
  it('拒绝明确失败响应并将未知网络结果保留为未知', async () => {
    mocks.raw.mockResolvedValueOnce({ data: { success: false, message: '未保存' } })
    await expect(getCommunicationCandidates(source)).rejects.toBeInstanceOf(CommunicationError)
    mocks.raw.mockRejectedValueOnce(new Error('network'))
    try {
      await getCommunication('event')
    } catch (error) {
      expect(error).toBeInstanceOf(CommunicationError)
      expect((error as CommunicationError).unknown).toBe(true)
    }
  })
})
