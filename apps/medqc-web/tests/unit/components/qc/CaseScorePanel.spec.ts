import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ get: vi.fn(), list: vi.fn() }))
vi.mock('@/api/scoring', () => ({ getCaseScore: api.get, listScoringStandards: api.list }))
vi.mock('@/stores/auth', async () => {
  const { reactive } = await import('vue')
  const auth = reactive({ user: { id: 'user-1' } })
  return { useAuthStore: () => auth }
})

import CaseScorePanel from '@/components/qc/CaseScorePanel.vue'
import { useAuthStore } from '@/stores/auth'

const props = { instituteId: 'H1', patientId: 'P1', visitId: 'V1', scene: 'running' as const }

function scored(overrides: Record<string, unknown> = {}) {
  return {
    status: 'scored',
    scene: 'running',
    standard_id: 's1',
    standard_name: '运行病历评分标准',
    standard_updated_at: '2026-09-27T01:00:00',
    rule_set_key: 'luxian_0609_qc_v1',
    rule_set_version: '2026-06-09',
    job_id: 'job-1',
    score: 82.5,
    grade: '乙',
    veto_hit: false,
    base_score: 100,
    result_ref: {
      envelope_id: 'envelope-1',
      root_job_id: 'job-1',
      institute_id: 'H1',
      patient_id: 'P1',
      visit_id: 'V1',
      rule_set_key: 'luxian_0609_qc_v1',
      rule_set_version: '2026-06-09',
    },
    standard_ref: { standard_id: 's1', version_seq: 7, updated_at: '2026-09-27T01:00:00' },
    deductions: [
      { rule_id: 'LX0609-001', group_name: '病程记录', deduction: 5, is_veto: false },
      { rule_id: 'LX0609-002', group_name: '病程记录', deduction: 8, is_veto: false },
      { rule_id: 'LX0609-010', group_name: '首页', deduction: 7.5, is_veto: false },
    ],
    group_deductions: [
      { group_name: '病程记录', raw_deduction: 13, applied_deduction: 10, max_deduction: 10 },
      { group_name: '首页', raw_deduction: 7.5, applied_deduction: 7.5, max_deduction: null },
    ],
    unscored_rule_ids: [],
    ...overrides,
  }
}

function ok(data: unknown) {
  return { success: true, status: 200, data }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => {
    resolve = done
  })
  return { promise, resolve }
}

describe('CaseScorePanel', () => {
  beforeEach(() => {
    api.get.mockReset()
    api.list
      .mockReset()
      .mockResolvedValue(
        ok({
          items: [
            {
              id: 's2',
              name: '另一运行标准',
              scene: 'running',
              status: 'active',
              rule_set_key: 'luxian_0609_qc_v1',
            },
          ],
        }),
      )
  })

  it('显式选择仅重读本病例分数，失败不退回默认，切病例恢复默认', async () => {
    api.get
      .mockResolvedValueOnce(ok(scored()))
      .mockResolvedValueOnce({ success: false, status: 422, message: '评分标准已失效' })
      .mockResolvedValueOnce(ok(scored()))
    const wrapper = mount(CaseScorePanel, { props })
    await flushPromises()
    await wrapper.get('[data-testid="case-score-standard"]').setValue('s2')
    await flushPromises()
    expect(api.get.mock.calls[1][0].standard_id).toBe('s2')
    expect(wrapper.text()).toContain('评分标准已失效')
    expect(api.get).toHaveBeenCalledTimes(2)
    await wrapper.setProps({ visitId: 'V2' })
    await flushPromises()
    expect(api.get.mock.calls[2][0]).not.toHaveProperty('standard_id')
    expect(
      (wrapper.get('[data-testid="case-score-standard"]').element as HTMLSelectElement).value,
    ).toBe('')
    wrapper.unmount()
  })

  it('快速切换标准时旧重算不能覆盖新选择', async () => {
    const old = deferred<ReturnType<typeof ok>>()
    api.get
      .mockResolvedValueOnce(ok(scored()))
      .mockReturnValueOnce(old.promise)
      .mockResolvedValueOnce(ok(scored({ score: 94 })))
    const wrapper = mount(CaseScorePanel, { props })
    await flushPromises()
    await wrapper.get('[data-testid="case-score-standard"]').setValue('s2')
    await wrapper.get('[data-testid="case-score-standard"]').setValue('')
    await flushPromises()
    old.resolve(ok(scored({ standard_id: 's2', score: 50 })))
    await flushPromises()
    expect(wrapper.get('[data-testid="case-score-value"]').text()).toBe('94')
    wrapper.unmount()
  })

  it('场景或账号切换复位标准并废弃旧选择响应', async () => {
    const old = deferred<ReturnType<typeof ok>>()
    api.get
      .mockResolvedValueOnce(ok(scored()))
      .mockReturnValueOnce(old.promise)
      .mockResolvedValue(ok(scored({ scene: 'final', score: 91 })))
    const wrapper = mount(CaseScorePanel, { props })
    await flushPromises()
    await wrapper.get('[data-testid="case-score-standard"]').setValue('s2')
    await wrapper.setProps({ scene: 'final' })
    await flushPromises()
    old.resolve(ok(scored({ standard_id: 's2', score: 40 })))
    await flushPromises()
    expect(api.get.mock.calls[2][0]).toMatchObject({ scene: 'final' })
    expect(api.get.mock.calls[2][0]).not.toHaveProperty('standard_id')
    expect(wrapper.get('[data-testid="case-score-value"]').text()).toBe('91')
    useAuthStore().user!.id = 'user-2'
    await flushPromises()
    expect(api.get).toHaveBeenCalledTimes(4)
    expect(api.get.mock.calls[3][0]).not.toHaveProperty('standard_id')
    wrapper.unmount()
  })

  it('按三坐标与场景读取，显示得分、等级与按项目组的扣分明细', async () => {
    api.get.mockResolvedValueOnce(ok(scored()))
    const wrapper = mount(CaseScorePanel, { props })
    await flushPromises()

    expect(api.get).toHaveBeenCalledWith({
      institute_id: 'H1',
      patient_id: 'P1',
      visit_id: 'V1',
      scene: 'running',
    })
    expect(wrapper.get('[data-testid="case-score-value"]').text()).toBe('82.5')
    expect(wrapper.get('[data-testid="case-score-grade"]').text()).toBe('乙')
    expect(wrapper.find('[data-testid="case-score-veto"]').exists()).toBe(false)
    const groups = wrapper.findAll('[data-testid="case-score-group"]')
    expect(groups).toHaveLength(2)
    expect(groups[0].text()).toContain('病程记录')
    expect(groups[0].text()).toContain('扣 10 分')
    expect(groups[0].find('[data-testid="case-score-group-capped"]').text()).toContain('原扣 13')
    expect(groups[0].findAll('[data-testid="case-score-deduction"]')).toHaveLength(2)
    expect(groups[1].find('[data-testid="case-score-group-capped"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="case-score-basis"]').text()).toContain('运行病历评分标准')
    expect(wrapper.get('[data-testid="case-score-standard-version"]').text()).toBe('标准版本 v7')
    expect(wrapper.find('[data-testid="case-score-unscored"]').exists()).toBe(false)
  })

  it('历史响应缺少引用仍显示只读分数，不伪造标准版本或申诉入口', async () => {
    api.get.mockResolvedValueOnce(ok(scored({ result_ref: null, standard_ref: null })))
    const wrapper = mount(CaseScorePanel, { props })
    await flushPromises()

    expect(wrapper.get('[data-testid="case-score-value"]').text()).toBe('82.5')
    expect(wrapper.find('[data-testid="case-score-standard-version"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="case-score-appeal"]').exists()).toBe(false)
  })

  it('标准引用与顶层锚点不一致时不展示为可信版本', async () => {
    api.get.mockResolvedValueOnce(
      ok(
        scored({
          standard_ref: { standard_id: 's1', version_seq: 8, updated_at: '2026-09-27T02:00:00' },
        }),
      ),
    )
    const wrapper = mount(CaseScorePanel, { props })
    await flushPromises()

    expect(wrapper.get('[data-testid="case-score-value"]').text()).toBe('82.5')
    expect(wrapper.find('[data-testid="case-score-standard-version"]').exists()).toBe(false)
  })

  it('畸形标准引用只隐藏版本，不破坏已有只读分数', async () => {
    api.get.mockResolvedValueOnce(
      ok(
        scored({
          standard_ref: { standard_id: 7, version_seq: '7', updated_at: null },
        }),
      ),
    )
    const wrapper = mount(CaseScorePanel, { props })
    await flushPromises()

    expect(wrapper.get('[data-testid="case-score-value"]').text()).toBe('82.5')
    expect(wrapper.find('[data-testid="case-score-standard-version"]').exists()).toBe(false)
  })

  it('命中否决时标记单项否决，并列出未配置扣分的确定问题', async () => {
    api.get.mockResolvedValueOnce(
      ok(
        scored({
          grade: '丙',
          veto_hit: true,
          deductions: [
            { rule_id: 'LX0609-030', group_name: '核心制度', deduction: 0, is_veto: true },
          ],
          group_deductions: [
            { group_name: '核心制度', raw_deduction: 0, applied_deduction: 0, max_deduction: null },
          ],
          unscored_rule_ids: ['LX0609-040', 'LX0609-041'],
        }),
      ),
    )
    const wrapper = mount(CaseScorePanel, { props })
    await flushPromises()
    expect(wrapper.get('[data-testid="case-score-veto"]').text()).toContain('丙')
    expect(wrapper.text()).toContain('单项否决')
    const unscored = wrapper.get('[data-testid="case-score-unscored"]').text()
    expect(unscored).toContain('以下确定问题未配置扣分')
    expect(unscored).toContain('LX0609-040')
    expect(unscored).toContain('LX0609-041')
  })

  it.each([
    [{ status: 'no_standard', scene: 'running' }, 'case-score-no-standard', '未配置评分标准'],
    [
      { status: 'no_result', scene: 'running', result_state: 'not_run', standard_id: 's1' },
      'case-score-no-result',
      '暂无可计分的质控结果',
    ],
  ])('%o 显示对应说明且不显示分数', async (data, testId, text) => {
    api.get.mockResolvedValueOnce(ok(data))
    const wrapper = mount(CaseScorePanel, { props })
    await flushPromises()
    expect(wrapper.get(`[data-testid="${testId}"]`).text()).toContain(text)
    expect(wrapper.find('[data-testid="case-score-value"]').exists()).toBe(false)
  })

  it('403 时整块隐藏并通知父级', async () => {
    api.get.mockResolvedValueOnce({ success: false, status: 403, message: '没有权限' })
    const wrapper = mount(CaseScorePanel, { props })
    await flushPromises()
    expect(wrapper.find('[data-testid="case-score"]').exists()).toBe(false)
    expect(wrapper.emitted('forbidden')).toHaveLength(1)
  })

  it('读取失败可重试，不显示伪造分数；scored 缺分数视为数据不完整', async () => {
    api.get
      .mockResolvedValueOnce({
        success: false,
        status: 503,
        message: '评分服务暂不可用，请稍后重试',
      })
      .mockResolvedValueOnce(ok(scored({ score: null })))
      .mockResolvedValueOnce(ok(scored()))
    const wrapper = mount(CaseScorePanel, { props })
    await flushPromises()
    expect(wrapper.get('[data-testid="case-score-error"]').text()).toContain('评分服务暂不可用')
    expect(wrapper.find('[data-testid="case-score-value"]').exists()).toBe(false)

    await wrapper.get('[data-testid="case-score-retry"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="case-score-error"]').text()).toContain('不完整')

    await wrapper.get('[data-testid="case-score-retry"]').trigger('click')
    await flushPromises()
    expect(api.get).toHaveBeenCalledTimes(3)
    expect(wrapper.get('[data-testid="case-score-value"]').text()).toBe('82.5')
  })

  it('三坐标切换后丢弃迟到响应', async () => {
    const first = deferred<unknown>()
    api.get.mockReturnValueOnce(first.promise).mockResolvedValueOnce(
      ok(
        scored({
          score: 60,
          grade: '丙',
          standard_ref: { standard_id: 's1', version_seq: 8, updated_at: '2026-09-27T01:00:00' },
        }),
      ),
    )
    const wrapper = mount(CaseScorePanel, { props })
    await wrapper.setProps({ visitId: 'V2' })
    await flushPromises()
    first.resolve(
      ok(
        scored({
          score: 99,
          grade: '甲',
          standard_ref: { standard_id: 's1', version_seq: 9, updated_at: '2026-09-27T01:00:00' },
        }),
      ),
    )
    await flushPromises()
    expect(api.get).toHaveBeenLastCalledWith({
      institute_id: 'H1',
      patient_id: 'P1',
      visit_id: 'V2',
      scene: 'running',
    })
    expect(wrapper.get('[data-testid="case-score-value"]').text()).toBe('60')
    expect(wrapper.get('[data-testid="case-score-grade"]').text()).toBe('丙')
    expect(wrapper.get('[data-testid="case-score-standard-version"]').text()).toBe('标准版本 v8')
  })

  it('组件卸载后废弃仍在途的响应', async () => {
    const pending = deferred<unknown>()
    api.get.mockReturnValueOnce(pending.promise)
    const wrapper = mount(CaseScorePanel, { props })

    wrapper.unmount()
    pending.resolve({ success: false, status: 403, message: '没有权限' })
    await flushPromises()

    expect(wrapper.emitted('forbidden')).toBeUndefined()
  })
})
