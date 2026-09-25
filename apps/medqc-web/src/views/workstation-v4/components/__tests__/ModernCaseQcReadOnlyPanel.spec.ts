import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ModernCaseQcReadOnlyPanel from '../ModernCaseQcReadOnlyPanel.vue'
import type { ModernCaseQcSnapshot, ModernCaseQcSourceKey } from '@/api/modernCaseQcResult'

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
