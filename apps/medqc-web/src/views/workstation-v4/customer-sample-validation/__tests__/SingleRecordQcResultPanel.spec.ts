import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const confirmedResultsOnlyRef = ref(true)

vi.mock('@/composables/useQcResultVisibility', () => ({
  useQcResultVisibility: () => ({
    confirmedResultsOnly: confirmedResultsOnlyRef,
  }),
}))

import SingleRecordQcResultPanel from '../SingleRecordQcResultPanel.vue'
import ConsultationRecommendationSummary from '../ConsultationRecommendationSummary.vue'
import type { SingleRecordQcResultItem } from '../single-record-result-model'

function makeConfirmedItems(): SingleRecordQcResultItem[] {
  return [
    {
      rule_id: 'LX0609-02-01-05',
      rule_name: '查房记录：病危（下了病危医嘱）患者未每天记录查房病程，或病情变化时未记录病程',
      status: 'non_compliant',
      conclusion: '病危观察期 2026-05-31 至 2026-06-21，共 22 天；每日病程已记录 15/22 天，缺少 2026-06-08、2026-06-10。',
      evidence: [
        {
          source_ref: 'daily_course_record:doc-1',
          source_type: 'daily_course_record',
          source_label: '日常病程记录',
          evidence_excerpt: '患者病情危重',
        },
      ],
    },
    {
      rule_id: 'LX0609-12-01-02',
      rule_name: '不合理复制病历：2次以上病程记录完全相同（相似度大于70%）',
      status: 'non_compliant',
      conclusion: '检测到 4 组高相似度病程记录。',
      customer_display_facts: {
        copy_similarity_threshold: 0.7,
        copy_match_pairs: [
          {
            source_types: ['senior_course_record', 'senior_course_record'],
            record_times: ['2026-06-06 09:37:00', '2026-06-07 09:47:00'],
            similarity: 0.844,
          },
          {
            source_types: ['senior_course_record', 'senior_course_record'],
            record_times: ['2026-06-08 09:37:00', '2026-06-09 09:47:00'],
            similarity: 0.81,
          },
        ],
      },
      evidence: [],
    },
  ]
}

describe('SingleRecordQcResultPanel clinician UX refinements', () => {
  beforeEach(() => {
    confirmedResultsOnlyRef.value = true
  })

  it('hides single-tab bar, removes redundant confirmed pills, and extracts document badges', () => {
    const wrapper = mount(SingleRecordQcResultPanel, {
      props: {
        items: makeConfirmedItems(),
        presentationMode: 'grouped',
      },
      global: {
        stubs: {
          MqIcon: true,
          QcResultFeedbackControl: true,
          QcRemediationSuggestion: true,
          CriterionResultBlock: true,
          ConsultationRecommendationSummary: true,
          ExamLabEventResultBlock: true,
          TimelinessResultBlock: true,
        },
      },
    })

    // Only 1 category -> tab bar is omitted to reclaim vertical space
    expect(wrapper.find('[role="tablist"]').exists()).toBe(false)
    // Redundant confirmed pills removed from each card
    expect(wrapper.findAll('.status-pill')).toHaveLength(0)
    // Document badge extracted from rule prefix
    const docBadges = wrapper.findAll('[data-testid="single-record-doc-badge"]')
    expect(docBadges[0].text()).toContain('查房记录')
    // Title strips redundant document prefix
    const titles = wrapper.findAll('.rule-name')
    expect(titles[0].text()).toBe('病危（下了病危医嘱）患者未每天记录查房病程，或病情变化时未记录病程')
    // Review progress shows 0/2 initially
    expect(wrapper.find('[data-testid="single-record-review-progress"]').text()).toBe('已看 0/2')
    // Dates in conclusion text are highlighted and bolded without altering surrounding prose
    const dateTokens = wrapper.findAll('.rule-conclusion-date').map((node) => node.text())
    expect(dateTokens).toEqual(['2026-05-31', '2026-06-21', '2026-06-08', '2026-06-10'])
    // Structured 2-line copy match renders 篇1 / 篇2
    expect(wrapper.find('[data-testid="copy-match-headline-documents"]').text()).toContain('篇1')
    expect(wrapper.find('[data-testid="copy-match-headline-documents"]').text()).toContain('篇2')
  })

  it('tracks active card, reviewed progress, and emits locate-evidence on quick locate click', async () => {
    const wrapper = mount(SingleRecordQcResultPanel, {
      props: {
        items: makeConfirmedItems(),
        presentationMode: 'grouped',
      },
      global: {
        stubs: {
          MqIcon: true,
          QcResultFeedbackControl: true,
          QcRemediationSuggestion: true,
          CriterionResultBlock: true,
          ConsultationRecommendationSummary: true,
          ExamLabEventResultBlock: true,
          TimelinessResultBlock: true,
        },
      },
    })

    const quickLocate = wrapper.find('[data-testid="single-record-quick-locate"]')
    expect(quickLocate.exists()).toBe(true)
    await quickLocate.trigger('click')

    expect(wrapper.emitted('locate-evidence')).toHaveLength(1)
    const rows = wrapper.findAll('[data-testid="single-record-result-row"]')
    expect(rows[0].classes()).toContain('is-active')
    expect(rows[0].attributes('aria-current')).toBe('true')
    expect(wrapper.find('[data-testid="single-record-review-progress"]').text()).toBe('已看 1/2')
    expect(wrapper.findAll('[data-testid="single-record-reviewed-badge"]')).toHaveLength(1)
  })

  it('keeps multi-tab bar visible when multiple statuses are enabled', () => {
    confirmedResultsOnlyRef.value = false
    const wrapper = mount(SingleRecordQcResultPanel, {
      props: {
        items: makeConfirmedItems(),
        presentationMode: 'grouped',
      },
      global: {
        stubs: {
          MqIcon: true,
          QcResultFeedbackControl: true,
          QcRemediationSuggestion: true,
          CriterionResultBlock: true,
          ConsultationRecommendationSummary: true,
          ExamLabEventResultBlock: true,
          TimelinessResultBlock: true,
        },
      },
    })

    expect(wrapper.find('[role="tablist"]').exists()).toBe(true)
  })

  it('does not emit select when collapsing an already-expanded card', async () => {
    const wrapper = mount(SingleRecordQcResultPanel, {
      props: {
        items: makeConfirmedItems(),
        presentationMode: 'grouped',
      },
      global: {
        stubs: {
          MqIcon: true,
          QcResultFeedbackControl: true,
          QcRemediationSuggestion: true,
          CriterionResultBlock: true,
          ConsultationRecommendationSummary: true,
          ExamLabEventResultBlock: true,
          TimelinessResultBlock: true,
        },
      },
    })

    const firstToggle = wrapper.findAll('[data-testid="single-record-result-toggle"]')[0]
    await firstToggle.trigger('click')
    expect(wrapper.emitted('select')).toEqual([['LX0609-02-01-05-0']])
    expect(firstToggle.attributes('aria-expanded')).toBe('true')

    // Collapsing via the card trigger must NOT emit select again
    await firstToggle.trigger('click')
    expect(firstToggle.attributes('aria-expanded')).toBe('false')
    expect(wrapper.emitted('select')).toHaveLength(1)

    // Re-expand and collapse via the footer details button
    await firstToggle.trigger('click')
    expect(wrapper.emitted('select')).toHaveLength(2)
    const collapseButton = wrapper.findAll('.result-details-hint')[0]
    await collapseButton.trigger('click')
    expect(firstToggle.attributes('aria-expanded')).toBe('false')
    expect(wrapper.emitted('select')).toHaveLength(2)
  })

  it('updates active card and chip state when clicking an evidence chip inside an expanded card', async () => {
    const items = makeConfirmedItems()
    items[0] = {
      ...items[0],
      evidence: [
        ...items[0].evidence!,
        {
          source_ref: 'senior_course_record:doc-2',
          source_type: 'senior_course_record',
          source_label: '上级医师查房记录',
          evidence_excerpt: '上级查房评估',
        },
      ],
    }
    const wrapper = mount(SingleRecordQcResultPanel, {
      props: {
        items,
        presentationMode: 'grouped',
      },
      global: {
        stubs: {
          MqIcon: true,
          QcResultFeedbackControl: true,
          QcRemediationSuggestion: true,
          CriterionResultBlock: true,
          ConsultationRecommendationSummary: true,
          ExamLabEventResultBlock: true,
          TimelinessResultBlock: true,
        },
      },
    })

    // Expand card 0, then switch active focus to card 1 via its trigger
    const toggles = wrapper.findAll('[data-testid="single-record-result-toggle"]')
    await toggles[0].trigger('click')
    // Click second evidence chip inside card 0
    const chips = wrapper.findAll('[data-testid="single-record-evidence"]')
    expect(chips).toHaveLength(2)
    expect(chips[0].classes()).toContain('is-active')

    // Click second chip -> activates card 0, marks second chip active, emits locate-evidence
    await chips[1].trigger('click')
    const rows = wrapper.findAll('[data-testid="single-record-result-row"]')
    expect(rows[0].classes()).toContain('is-active')
    expect(rows[0].attributes('aria-current')).toBe('true')
    expect(chips[1].classes()).toContain('is-active')
    expect(chips[0].classes()).not.toContain('is-active')
    expect(wrapper.emitted('locate-evidence')).toEqual([[items[0].evidence![1]]])
    expect(wrapper.find('[data-testid="single-record-review-progress"]').text()).toBe('已看 1/2')

    // Verify clicking an evidence chip inside still-expanded card 0 reclaims active state from card 1
    const twoEvidenceItems = makeConfirmedItems()
    twoEvidenceItems[1] = {
      ...twoEvidenceItems[1],
      evidence: [
        {
          source_ref: 'senior_course_record:doc-9',
          source_type: 'senior_course_record',
          source_label: '上级医师查房记录',
        },
      ],
    }
    const wrapper2 = mount(SingleRecordQcResultPanel, {
      props: {
        items: twoEvidenceItems,
        presentationMode: 'grouped',
      },
      global: {
        stubs: {
          MqIcon: true,
          QcResultFeedbackControl: true,
          QcRemediationSuggestion: true,
          CriterionResultBlock: true,
          ConsultationRecommendationSummary: true,
          ExamLabEventResultBlock: true,
          TimelinessResultBlock: true,
        },
      },
    })
    await wrapper2.findAll('[data-testid="single-record-result-toggle"]')[0].trigger('click')
    // Move active state to card 1 via quick locate (card 0 stays expanded)
    await wrapper2.findAll('[data-testid="single-record-quick-locate"]')[1].trigger('click')
    let rows2 = wrapper2.findAll('[data-testid="single-record-result-row"]')
    expect(rows2[1].classes()).toContain('is-active')
    expect(rows2[0].classes()).not.toContain('is-active')

    // Now click the evidence chip inside still-expanded card 0 -> card 0 regains active state
    await wrapper2.get('[data-testid="single-record-evidence"]').trigger('click')
    rows2 = wrapper2.findAll('[data-testid="single-record-result-row"]')
    expect(rows2[0].classes()).toContain('is-active')
    expect(rows2[0].attributes('aria-current')).toBe('true')
    expect(rows2[1].classes()).not.toContain('is-active')
    expect(wrapper2.get('[data-testid="single-record-evidence"]').classes()).toContain('is-active')
  })

  it.each(['flat', 'grouped'] as const)(
    'P1-18: %s 模式下切换 items 数据集时重置展开、激活、已看、反馈与规则全文状态',
    async (presentationMode) => {
      const wrapper = mount(SingleRecordQcResultPanel, {
        props: {
          items: makeConfirmedItems(),
          presentationMode,
          feedbackEnabled: true,
        },
        global: {
          stubs: {
            MqIcon: true,
            QcResultFeedbackControl: true,
            QcRemediationSuggestion: true,
            CriterionResultBlock: true,
            ConsultationRecommendationSummary: true,
            ExamLabEventResultBlock: true,
            TimelinessResultBlock: true,
          },
        },
      })

      await wrapper.findAll('[data-testid="single-record-result-toggle"]')[0].trigger('click')
      await wrapper.get('[data-testid="single-record-feedback-entry-hint"]').trigger('click')
      await wrapper.get('[data-testid="single-record-rule-fulltext-toggle"]').trigger('click')
      expect(wrapper.find('[data-testid="single-record-feedback-disclosure"]').exists()).toBe(true)
      expect(wrapper.find('[data-testid="single-record-rule-fulltext"]').exists()).toBe(true)
      expect(wrapper.get('[data-testid="single-record-review-progress"]').text()).toBe('已看 1/2')

      await wrapper.setProps({
        items: [
          {
            rule_id: 'LX0609-01-01-01',
            rule_name: '入院记录：入院记录及时性',
            status: 'non_compliant',
            conclusion: '第二份病历问题。',
            evidence: [],
          },
        ],
      })

      expect(wrapper.get('[data-testid="single-record-result-toggle"]').attributes('aria-expanded')).toBe('false')
      expect(wrapper.find('[data-testid="single-record-feedback-disclosure"]').exists()).toBe(false)
      expect(wrapper.find('[data-testid="single-record-rule-fulltext"]').exists()).toBe(false)
      expect(wrapper.get('[data-testid="single-record-review-progress"]').text()).toBe('已看 0/1')
      expect(wrapper.findAll('[data-testid="single-record-result-row"]')[0].classes()).not.toContain('is-active')
      wrapper.unmount()
    },
  )

  it('P1-18: 相同 source_ref 的多条证据胶囊稳定渲染且按规则隔离反馈错误', async () => {
    const items: SingleRecordQcResultItem[] = [
      {
        rule_id: 'LX0609-03-01-04',
        rule_name: '会诊记录：会诊意见执行核对',
        status: 'non_compliant',
        conclusion: '两条建议来自同一会诊文书。',
        customer_display_facts: {
          recommendation_evidence: [
            {
              episode_index: 1,
              recommendation_index: 1,
              recommendation_text: '建议复查血常规',
              execution_state: 'missing',
              opinion_evidence: [
                {
                  source_type: 'consultation_record',
                  source_ref: 'src_0123456789abcdef01234567',
                },
              ],
            },
            {
              episode_index: 1,
              recommendation_index: 2,
              recommendation_text: '建议完善凝血功能检查',
              execution_state: 'missing',
              opinion_evidence: [
                {
                  source_type: 'consultation_record',
                  source_ref: 'src_0123456789abcdef01234567',
                },
              ],
            },
          ],
        },
        evidence: [],
      },
      {
        rule_id: 'LX0609-02-01-05',
        rule_name: '查房记录：病危查房',
        status: 'non_compliant',
        conclusion: '缺少查房记录。',
        evidence: [],
      },
    ]

    const wrapper = mount(SingleRecordQcResultPanel, {
      props: {
        items,
        presentationMode: 'flat',
        feedbackEnabled: true,
        feedbackErrorByRule: { 'LX0609-03-01-04': '仅规则1保存失败' },
      },
      global: {
        stubs: {
          MqIcon: true,
          QcRemediationSuggestion: true,
          CriterionResultBlock: true,
          ConsultationRecommendationSummary: true,
          ExamLabEventResultBlock: true,
          TimelinessResultBlock: true,
        },
      },
    })

    const toggles = wrapper.findAll('[data-testid="single-record-result-toggle"]')
    await toggles[0].trigger('click')
    const chips = wrapper.findAll('[data-testid="single-record-evidence"]')
    expect(chips).toHaveLength(2)
    expect(chips[0].text()).toContain('第1条建议')
    expect(chips[1].text()).toContain('第2条建议')

    await wrapper.get('[data-testid="single-record-feedback-entry-hint"]').trigger('click')
    expect(wrapper.get('[data-testid="qc-result-feedback-error"]').text()).toContain('仅规则1保存失败')

    // 切换到第二条规则后，不应显示第一条规则的保存错误
    await toggles[1].trigger('click')
    await wrapper.get('[data-testid="single-record-feedback-entry-hint"]').trigger('click')
    expect(wrapper.find('[data-testid="qc-result-feedback-error"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('P1-18: ConsultationRecommendationSummary 为每个实例生成唯一标题 ID', () => {
    const presentation = {
      comparedCount: 1,
      excludedCount: 1,
      checkedSources: ['会诊记录', '医嘱'],
      rows: [
        {
          key: 'r1',
          episodeIndex: 1,
          recommendationIndex: 1,
          state: 'missing' as const,
          statusLabel: '未执行',
          text: '建议复查血常规',
          detail: '未见对应医嘱',
        },
        {
          key: 'r2',
          episodeIndex: 1,
          recommendationIndex: 2,
          state: 'excluded' as const,
          statusLabel: '不纳入',
          text: '必要时随访',
          detail: '按口径不纳入',
        },
      ],
    }

    const first = mount(ConsultationRecommendationSummary, { props: { presentation } })
    const second = mount(ConsultationRecommendationSummary, { props: { presentation } })

    const firstComparedId = first.get('.consultation-compared h5').attributes('id')
    const secondComparedId = second.get('.consultation-compared h5').attributes('id')
    const firstExcludedId = first.get('.consultation-excluded h5').attributes('id')
    const secondExcludedId = second.get('.consultation-excluded h5').attributes('id')

    expect(firstComparedId).toBeTruthy()
    expect(secondComparedId).toBeTruthy()
    expect(firstComparedId).not.toBe(secondComparedId)
    expect(first.get('.consultation-compared').attributes('aria-labelledby')).toBe(firstComparedId)
    expect(second.get('.consultation-compared').attributes('aria-labelledby')).toBe(secondComparedId)

    expect(firstExcludedId).toBeTruthy()
    expect(secondExcludedId).toBeTruthy()
    expect(firstExcludedId).not.toBe(secondExcludedId)
    expect(first.get('.consultation-excluded').attributes('aria-labelledby')).toBe(firstExcludedId)
    expect(second.get('.consultation-excluded').attributes('aria-labelledby')).toBe(secondExcludedId)

    first.unmount()
    second.unmount()
  })

  it('renders .result-index-badge contiguously (01, 02, ...) and renumbers without gaps when a document group is collapsed', async () => {
    const groupedItems: SingleRecordQcResultItem[] = [
      {
        rule_id: 'LX0609-01-01-01',
        rule_name: '入院记录：入院记录及时性',
        source_document: '入院记录',
        status: 'non_compliant',
        conclusion: '入院记录超期。',
      },
      {
        rule_id: 'LX0609-04-02-01',
        rule_name: '手术记录：手术记录完成时限',
        source_document: '手术记录',
        status: 'non_compliant',
        conclusion: '手术记录超期。',
      },
      {
        rule_id: 'LX0609-04-02-02',
        rule_name: '手术记录：术者签名核对',
        source_document: '手术记录',
        status: 'non_compliant',
        conclusion: '手术记录缺少术者签名。',
      },
      {
        rule_id: 'LX0609-04-02-04',
        rule_name: '手术记录：植入物信息完整性',
        source_document: '手术记录',
        status: 'non_compliant',
        conclusion: '缺少植入物材质。',
      },
      {
        rule_id: 'LX0609-02-01-05',
        rule_name: '查房记录：病危查房记录',
        source_document: '查房记录',
        status: 'non_compliant',
        conclusion: '缺少每日查房记录。',
      },
    ]

    const wrapper = mount(SingleRecordQcResultPanel, {
      props: {
        items: groupedItems,
        presentationMode: 'grouped',
      },
      global: {
        stubs: {
          MqIcon: true,
          QcResultFeedbackControl: true,
          QcRemediationSuggestion: true,
          CriterionResultBlock: true,
          ConsultationRecommendationSummary: true,
          ExamLabEventResultBlock: true,
          TimelinessResultBlock: true,
        },
      },
    })

    // Initially all 5 cards are visible -> 01..05
    expect(wrapper.findAll('.result-index-badge').map((node) => node.text())).toEqual([
      '01',
      '02',
      '03',
      '04',
      '05',
    ])

    // Collapse the 3-item 手术记录 group -> remaining visible cards renumber contiguously to 01, 02
    const groupToggle = wrapper.get('[data-testid="single-record-document-group-toggle"]')
    await groupToggle.trigger('click')
    expect(groupToggle.attributes('aria-expanded')).toBe('false')
    expect(wrapper.findAll('.result-index-badge').map((node) => node.text())).toEqual(['01', '02'])

    // Re-expand the group -> returns to 01..05
    await groupToggle.trigger('click')
    expect(wrapper.findAll('.result-index-badge').map((node) => node.text())).toEqual([
      '01',
      '02',
      '03',
      '04',
      '05',
    ])

    wrapper.unmount()
  })
})
