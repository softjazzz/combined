import { describe, expect, it, vi } from 'vitest'
import { ApiService } from '@/services/apiService'
import { parseFrontpageFormalScore, createScoringStandard } from '../scoring'
const score = { status: 'scored', score: 83, grade: '乙', veto_hit: false, standard_id: 'F1', standard_version_seq: 3, standard_updated_at: '2026-10-03T00:00:00Z', rule_set_key: 'frontpage_formal_v1', rule_set_version: '2026-10-03', reason_code: null, deductions: [], group_deductions: [], unscored_rule_ids: [] }
describe('本次首页配置评分API边界', () => {
  it('完整分数与精确标准版本原样搬运，不借用历史分数', () => {
    expect(parseFrontpageFormalScore(score)).toEqual(score)
    expect(parseFrontpageFormalScore({ ...score, score: 0 })).toMatchObject({ score: 0 })
  })
  it.each([undefined, {}, { ...score, score: null }, { ...score, standard_version_seq: null }, { ...score, status: 'unavailable', score: 100 }])('缺失或损坏回执保持未知', (value) => {
    expect(parseFrontpageFormalScore(value)).toBeNull()
  })
  it('未配置回执明确无分数', () => {
    expect(parseFrontpageFormalScore({ ...score, status: 'no_standard', score: null, grade: null, veto_hit: null, standard_id: null, standard_version_seq: null, standard_updated_at: null, deductions: null, group_deductions: null, unscored_rule_ids: null })).toMatchObject({ status: 'no_standard', score: null })
  })
  it('新建首页标准使用首页scene和真实FQ目录，不继承住院规则集', async () => {
    const spy = vi.spyOn(ApiService, 'requestRaw').mockResolvedValue({ status: 200, data: { success: true, data: {} } } as Awaited<ReturnType<typeof ApiService.requestRaw>>)
    await createScoringStandard({ name: '合成首页标准', scene: 'frontpage', rule_set_key: 'frontpage_formal_v1', base_score: 100, grade_bands: [{ name: '甲', min_score: 0, max_score: 100 }], veto_grade: '甲' })
    expect(spy.mock.calls[0][0].data).toMatchObject({ scene: 'frontpage', rule_set_key: 'frontpage_formal_v1' })
    spy.mockRestore()
  })
})
