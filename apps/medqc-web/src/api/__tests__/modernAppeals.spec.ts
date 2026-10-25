import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  actOnModernAppeal,
  createModernAppeal,
  getModernAppeal,
  listModernAppeals,
} from '../modernAppeals'
const raw = vi.hoisted(() => vi.fn())
vi.mock('@/services/apiService', () => ({ ApiService: { requestRaw: raw } }))
const row = {
  id: 'A',
  target_kind: 'canonical_defect',
  target_id: 'R',
  institute_id: 'I',
  patient_id: 'P',
  visit_id: 'V',
  scene: 'final',
  root_job_id: 'J',
  envelope_id: 'E',
  rule_set_key: 'K',
  rule_set_version: '1',
  case_department: '内科',
  appellant_id: 'D',
  appellant_name: '医生',
  reason: '合成原因',
  status: 'pending',
  resolution: null,
  created_at: '2026-10-24',
}
beforeEach(() => raw.mockReset())
describe('现代申诉接口', () => {
  it('创建不接受客户端伪造角色与来源，审核传CAS状态', async () => {
    raw.mockResolvedValue({ data: { data: row, success: true } })
    await createModernAppeal('task', '合成理由')
    expect(raw).toHaveBeenLastCalledWith(
      expect.objectContaining({ data: { rectification_id: 'task', reason: '合成理由' } }),
    )
    await actOnModernAppeal('A', 'pending', 'approve', '合成意见')
    expect(raw).toHaveBeenLastCalledWith(
      expect.objectContaining({
        data: { expected_status: 'pending', action: 'approve', comment: '合成意见' },
      }),
    )
  })
  it.each(['envelope_id', 'rule_set_version', 'case_department'])(
    '来源缺失%s不当成有效申诉',
    async (key) => {
      raw.mockResolvedValue({ data: { ...row, [key]: null } })
      await expect(createModernAppeal('task', '合成理由')).rejects.toThrow('来源或状态无效')
    },
  )
  it('待办错误不退化零，非法历史不当成已验收', async () => {
    raw.mockResolvedValueOnce({ data: { items: [], total: 0, pending_count: null } })
    await expect(listModernAppeals()).rejects.toThrow('待办数据无效')
    raw.mockResolvedValueOnce({ data: { ...row, events: [{ action: 'unknown' }] } })
    await expect(getModernAppeal('A')).rejects.toThrow('历史无效')
  })
})
