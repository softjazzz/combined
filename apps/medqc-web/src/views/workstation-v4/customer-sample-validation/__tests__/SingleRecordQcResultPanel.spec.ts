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
})
