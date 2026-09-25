import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ModernCaseQcReadOnlyPanel from '../ModernCaseQcReadOnlyPanel.vue'
import type {
  ModernCaseQcDefect,
  ModernCaseQcSnapshot,
  ModernCaseQcSourceKey,
} from '@/api/modernCaseQcResult'

const SOURCE: ModernCaseQcSourceKey = 'frontpage_formal_qc'

/** 合成数据：不包含任何真实患者信息，字段与后端客户可见投影一致。 */
function buildSnapshot(overrides: Partial<ModernCaseQcSnapshot> = {}): ModernCaseQcSnapshot {
  return {
    identity_status: 'verified',
    source_key: SOURCE,
    institute_id: 'institute-synthetic',
    patient_id: 'patient-synthetic',
    visit_id: 'visit-synthetic',
    latest_qc_result: {
      id: 'result-latest',
      rule_set: 'lx0609-v1',
      overall_score: 86.5,
      grade: 'B',
      defect_count: 2,
      analysis_date: '2026-01-02T00:00:00',
      created_at: '2026-01-02T03:04:05Z',
    },
    recent_results: [
      {
        id: 'result-older',
        rule_set: 'lx0609-v1',
        overall_score: 90,
        grade: 'A',
        defect_count: 1,
        analysis_date: '2026-01-01T00:00:00',
        created_at: '2026-01-01T01:00:00Z',
      },
    ],
    active_defects: [
      {
        id: 'defect-active',
        rule_code: 'LX0609-001',
        rule_name: '示例规则-时限',
        description: '示例活跃缺陷描述',
        severity: 'major',
        category: 'timeliness',
        location: '示例文书·示例字段',
        suggestion: '示例补充建议',
        status: 'open',
      },
    ],
    current_result_defects: [
      {
        id: 'defect-current',
        rule_code: 'LX0609-002',
        rule_name: '示例规则-完整性',
        description: '示例本次缺陷描述',
        severity: 'minor',
        status: 'completed',
      },
    ],
    // 分页元数据：与后端信封一致，夹具必须补齐，避免把「没给元数据」当成「已加载完」。
    active_defects_has_more: false,
    active_defects_next_offset: null,
    current_result_defects_has_more: false,
    current_result_defects_next_offset: null,
    latest_notification: {
      id: 'notice-1',
      type: 'defect_assigned',
      title: '示例通知标题',
      content: '示例通知内容',
      severity: 'warning',
      is_read: false,
      read_at: null,
      created_at: '2026-01-03T05:00:00Z',
    },
    ...overrides,
  }
}

function mountPanel(
  props: Partial<{
    snapshot: ModernCaseQcSnapshot | null
    loading: boolean
    error: string | null
    sourceKey: ModernCaseQcSourceKey
    activeDefectsLoadingMore: boolean
    activeDefectsLoadMoreError: string | null
    currentResultDefectsLoadingMore: boolean
    currentResultDefectsLoadMoreError: string | null
  }> = {},
) {
  return mount(ModernCaseQcReadOnlyPanel, {
    props: {
      snapshot: null,
      loading: false,
      error: null,
      sourceKey: SOURCE,
      ...props,
    },
  })
}

/** 合成缺陷：只用于计数与分页按钮，不含真实患者信息。 */
function buildDefects(prefix: string, count: number, startAt = 1): ModernCaseQcDefect[] {
  return Array.from({ length: count }, (_, index) => ({
    id: `${prefix}-${startAt + index}`,
    rule_code: `LX0609-${startAt + index}`,
    rule_name: `${prefix}-item-${startAt + index}`,
    description: `${prefix}-item-${startAt + index}`,
    severity: 'major',
    status: 'open',
  }))
}

describe('ModernCaseQcReadOnlyPanel', () => {
  it('加载中只提示读取状态，不提前给出空结果或通过文案', () => {
    const wrapper = mountPanel({ loading: true })

    expect(wrapper.find('[data-role="loading"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('正在读取质控结果')
    expect(wrapper.text()).not.toContain('暂无已核验质控结果')
    expect(wrapper.text()).not.toContain('通过')
    expect(wrapper.findAll('button')).toHaveLength(0)
  })

  it('503 等失败时明确不可用并可重试', async () => {
    const wrapper = mountPanel({ error: '质控快照接口返回非 200 状态：503' })

    expect(wrapper.find('[data-role="error"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('质控结果暂不可用')
    expect(wrapper.text()).toContain('503')
    expect(wrapper.text()).not.toContain('暂无已核验质控结果')

    const retry = wrapper.find('.case-qc-panel__retry')
    expect(retry.exists()).toBe(true)
    await retry.trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
  })

  it('没有快照时显示空结果文案，且不得暗示通过', () => {
    const wrapper = mountPanel({ snapshot: null })

    expect(wrapper.find('[data-role="empty"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('暂无已核验质控结果')
    expect(wrapper.text()).not.toContain('通过')
    expect(wrapper.text()).not.toContain('合格')
    expect(wrapper.findAll('button')).toHaveLength(0)
  })

  it('快照存在但没有已核验结果时同样显示空结果文案', () => {
    const wrapper = mountPanel({
      snapshot: buildSnapshot({
        latest_qc_result: null,
        recent_results: [],
        active_defects: [],
        current_result_defects: [],
        latest_notification: null,
      }),
    })

    expect(wrapper.find('[data-section="latest-result"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('暂无已核验质控结果')
    expect(wrapper.text()).not.toContain('通过')
  })

  it('最新结果按后端客户可见字段投影，不出现整屏破折号与功能说明文案', () => {
    const wrapper = mountPanel({ snapshot: buildSnapshot() })

    const facts = wrapper
      .findAll('[data-section="latest-result"] .case-qc-panel__fact')
      .map((item) => [item.find('dt').text(), item.find('dd').text()] as const)

    expect(facts[0]).toEqual(['结果编号', 'result-latest'])
    expect(facts[1]).toEqual(['规则集', 'lx0609-v1'])
    expect(facts[2]).toEqual(['综合得分', '86.5'])
    expect(facts[3]).toEqual(['等级', 'B'])
    expect(facts[4]).toEqual(['缺陷数', '2'])
    expect(facts[5]).toEqual(['分析日期', '2026-01-02'])
    expect(facts[6][0]).toBe('生成时间')
    expect(facts[6][1]).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/)
    expect(facts[6][1]).not.toContain('T03:04:05Z')

    expect(wrapper.text()).not.toContain('本页仅查看')
    expect(wrapper.text()).not.toContain('数据来自已核验')
  })

  it('区分最新结果、当前活跃缺陷、本次结果缺陷、历史与通知', () => {
    const wrapper = mountPanel({ snapshot: buildSnapshot() })

    const activeSection = wrapper.find('[data-section="active-defects"]')
    expect(activeSection.text()).toContain('当前活跃缺陷')
    expect(activeSection.text()).toContain('1 项')
    expect(activeSection.text()).toContain('示例活跃缺陷描述')
    expect(activeSection.text()).toContain('LX0609-001')
    expect(activeSection.text()).toContain('示例补充建议')
    expect(activeSection.text()).not.toContain('示例本次缺陷描述')

    const currentSection = wrapper.find('[data-section="current-result-defects"]')
    expect(currentSection.text()).toContain('本次结果缺陷')
    expect(currentSection.text()).toContain('1 项')
    expect(currentSection.text()).toContain('示例本次缺陷描述')
    expect(currentSection.text()).toContain('completed')
    expect(currentSection.text()).not.toContain('示例活跃缺陷描述')

    const history = wrapper.find('[data-section="recent-results"]')
    expect(history.text()).toContain('最近执行历史')
    expect(history.text()).toContain('result-older')
    expect(history.text()).toContain('90')
    expect(history.text()).toContain('2026-01-01')

    const notice = wrapper.find('[data-section="latest-notification"]')
    expect(notice.text()).toContain('示例通知标题')
    expect(notice.text()).toContain('示例通知内容')
    expect(notice.text()).toContain('warning')
  })

  it('空缺陷与空历史使用中性空态，不渲染写操作', () => {
    const wrapper = mountPanel({
      snapshot: buildSnapshot({
        recent_results: [],
        active_defects: [],
        current_result_defects: [],
        latest_notification: null,
      }),
    })

    expect(wrapper.find('[data-section="active-defects"]').text()).toContain('暂无未关闭缺陷')
    expect(wrapper.find('[data-section="current-result-defects"]').text()).toContain(
      '本次结果未记录缺陷',
    )
    expect(wrapper.find('[data-section="recent-results"]').text()).toContain('暂无更早的执行记录')
    expect(wrapper.find('[data-section="latest-notification"]').text()).toContain('暂无通知')

    expect(wrapper.findAll('button')).toHaveLength(0)
    for (const forbidden of ['运行质控', '编辑', '保存', '提交', '删除', '标记已整改', '导出']) {
      expect(wrapper.text()).not.toContain(forbidden)
    }
  })
})

describe('ModernCaseQcReadOnlyPanel 缺陷分页反例（元数据派生）', () => {
  it('已加载计数不得冒充总数：两组都写「已加载 N 项」', () => {
    const wrapper = mountPanel({
      snapshot: buildSnapshot({
        active_defects: buildDefects('active', 20),
        current_result_defects: buildDefects('current', 2),
        active_defects_has_more: true,
        active_defects_next_offset: 20,
      }),
    })

    const activeCount = wrapper.get('[data-role="active-defects-count"]')
    expect(activeCount.text()).toContain('已加载 20 项')
    // 「20 项」是总数口径，分页后只代表已加载条数，必须显式区分。
    expect(activeCount.text().trim()).not.toBe('20 项')

    const currentCount = wrapper.get('[data-role="current-result-defects-count"]')
    expect(currentCount.text()).toContain('已加载 2 项')
    expect(currentCount.text().trim()).not.toBe('2 项')
  })

  it('只有 has_more 的组渲染加载更多，且点击按组发出 load-more', async () => {
    const wrapper = mountPanel({
      snapshot: buildSnapshot({
        active_defects: buildDefects('active', 20),
        current_result_defects: buildDefects('current', 1),
        active_defects_has_more: true,
        active_defects_next_offset: 20,
      }),
    })

    expect(wrapper.find('[data-role="load-more-active"]').exists()).toBe(true)
    expect(wrapper.find('[data-role="load-more-current"]').exists()).toBe(false)

    await wrapper.get('[data-role="load-more-active"]').trigger('click')
    expect(wrapper.emitted('load-more')).toEqual([['active']])
  })

  it('当前结果缺陷组可独立加载更多，不触碰活跃缺陷组', async () => {
    const wrapper = mountPanel({
      snapshot: buildSnapshot({
        active_defects: buildDefects('active', 1),
        current_result_defects: buildDefects('current', 20),
        current_result_defects_has_more: true,
        current_result_defects_next_offset: 20,
      }),
    })

    expect(wrapper.find('[data-role="load-more-active"]').exists()).toBe(false)
    await wrapper.get('[data-role="load-more-current"]').trigger('click')
    expect(wrapper.emitted('load-more')).toEqual([['current']])
  })

  it('空数组但仍有更多时不得显示「无缺陷」空态', () => {
    const wrapper = mountPanel({
      snapshot: buildSnapshot({
        active_defects: [],
        current_result_defects: [],
        active_defects_has_more: true,
        active_defects_next_offset: 0,
        current_result_defects_has_more: true,
        current_result_defects_next_offset: 0,
      }),
    })

    // length===0 只说明「还没加载到」，不能等同「无缺陷」。
    expect(wrapper.get('[data-section="active-defects"]').text()).not.toContain('暂无未关闭缺陷')
    expect(wrapper.get('[data-section="current-result-defects"]').text()).not.toContain(
      '本次结果未记录缺陷',
    )
    expect(wrapper.find('[data-role="load-more-active"]').exists()).toBe(true)
    expect(wrapper.find('[data-role="load-more-current"]').exists()).toBe(true)
  })

  it('加载更多失败保留已加载条目并提示重试，绝不回退成「无缺陷」空态', () => {
    const wrapper = mountPanel({
      snapshot: buildSnapshot({
        active_defects: buildDefects('active', 20),
        current_result_defects: buildDefects('current', 1),
        active_defects_has_more: true,
        active_defects_next_offset: 20,
      }),
      activeDefectsLoadMoreError: '加载更多失败，请重试',
    })

    const activeSection = wrapper.get('[data-section="active-defects"]')
    expect(activeSection.text()).not.toContain('暂无未关闭缺陷')
    expect(activeSection.text()).toContain('已加载 20 项')
    expect(activeSection.text()).toContain('active-item-20')

    expect(wrapper.get('[data-role="load-more-active-error"]').text()).toContain('加载更多失败')
    expect(wrapper.get('[data-role="load-more-active"]').text()).toContain('重新加载')
    // 另一组没有失败，不应串台显示错误。
    expect(wrapper.find('[data-role="load-more-current-error"]').exists()).toBe(false)
  })

  it('加载更多进行中显示加载态，且不误判为空缺陷', () => {
    const wrapper = mountPanel({
      snapshot: buildSnapshot({
        active_defects: buildDefects('active', 20),
        current_result_defects: buildDefects('current', 1),
        active_defects_has_more: true,
        active_defects_next_offset: 20,
      }),
      activeDefectsLoadingMore: true,
    })

    expect(wrapper.find('[data-role="load-more-active-loading"]').exists()).toBe(true)
    expect(wrapper.get('[data-section="active-defects"]').text()).not.toContain('暂无未关闭缺陷')
    expect(wrapper.get('[data-role="active-defects-count"]').text()).toContain('已加载 20 项')
  })
})
