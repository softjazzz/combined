import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import QcRemediationSuggestion, {
  canRequestQcRemediationDraft,
  parseQcRemediationSuggestion,
  resolveQcRemediationTitle,
} from '../QcRemediationSuggestion.vue'
import { requestLuxian0609RemediationDraft } from '@/services/sichuan-rule-workspace-service'

vi.mock('@/services/sichuan-rule-workspace-service', () => ({
  requestLuxian0609RemediationDraft: vi.fn(),
}))

const STRUCTURED_SUGGESTION = [
  '修改对象：入院记录',
  '需要补充：入院记录及完成时间',
  '推荐写法：请补充入院记录，并确保在入院后24小时内完成。',
  '注意事项：请依据本次实际诊疗事实补充，保留原始记录；不要编造未核实事实，不要倒签。',
].join('\n')

function mountSuggestion(suggestion: string, status = 'non_compliant') {
  return mount(QcRemediationSuggestion, { props: { suggestion, status } })
}

describe('QcRemediationSuggestion', () => {
  it('按四段式标签切段并逐段展示', () => {
    const wrapper = mountSuggestion(STRUCTURED_SUGGESTION)
    const rows = wrapper.findAll('.qc-remediation-section')

    expect(rows).toHaveLength(4)
    expect(rows.map((row) => row.find('.qc-remediation-label').text())).toEqual([
      '修改对象',
      '需要补充',
      '推荐写法',
      '注意事项',
    ])
    expect(rows[2].find('.qc-remediation-body').text()).toBe(
      '请补充入院记录，并确保在入院后24小时内完成。',
    )
  })

  it('单行压缩后的建议同样按标签切段', () => {
    const singleLine =
      '修改对象：入院记录 需要补充：入院记录及完成时间 推荐写法：请补充入院记录。 注意事项：不要倒签。'
    const parsed = parseQcRemediationSuggestion(singleLine)

    expect(parsed.structured).toBe(true)
    expect(parsed.sections.map((section) => section.label)).toEqual([
      '修改对象',
      '需要补充',
      '推荐写法',
      '注意事项',
    ])
    expect(parsed.sections[3].body).toBe('不要倒签。')
  })

  it('完整保留建议原文，不增删改写任何内容', () => {
    const wrapper = mountSuggestion(STRUCTURED_SUGGESTION)
    const rebuilt = wrapper
      .findAll('.qc-remediation-section')
      .map(
        (row) =>
          `${row.find('.qc-remediation-label').text()}：${row.find('.qc-remediation-body').text()}`,
      )
      .join('\n')

    expect(rebuilt).toBe(STRUCTURED_SUGGESTION)
  })

  it('非结构化旧建议整体原样展示', () => {
    const legacy = '请结合病历原文确认。\n如需补充请保留原始记录。'
    const wrapper = mountSuggestion(legacy, 'data_gap')

    expect(wrapper.findAll('.qc-remediation-section')).toHaveLength(0)
    expect(wrapper.find('.qc-remediation-plain').text()).toBe(legacy)
  })

  it('标题按服务端状态映射', () => {
    expect(resolveQcRemediationTitle('non_compliant')).toBe('修改建议')
    expect(resolveQcRemediationTitle('confirmed_issue')).toBe('修改建议')
    expect(resolveQcRemediationTitle('data_gap')).toBe('核对建议')
    expect(resolveQcRemediationTitle('uncertain')).toBe('核对建议')
    expect(resolveQcRemediationTitle('evaluation_unknown')).toBe('复核建议')
    expect(resolveQcRemediationTitle('technical_error')).toBe('排查建议')
    expect(resolveQcRemediationTitle('compliant')).toBe('处理建议')
    expect(resolveQcRemediationTitle()).toBe('处理建议')

    expect(mountSuggestion(STRUCTURED_SUGGESTION, 'technical_error').text()).toContain('排查建议')
    expect(mountSuggestion(STRUCTURED_SUGGESTION, 'non_compliant').text()).toContain('修改建议')
  })

  it('空建议不渲染任何内容', () => {
    const wrapper = mountSuggestion('', 'non_compliant')

    expect(wrapper.find('.qc-remediation').exists()).toBe(false)
    expect(wrapper.text()).toBe('')
  })

  it('支持紧凑排版', () => {
    const wrapper = mount(QcRemediationSuggestion, {
      props: { suggestion: STRUCTURED_SUGGESTION, status: 'data_gap', dense: true },
    })

    expect(wrapper.find('.qc-remediation--dense').exists()).toBe(true)
    expect(wrapper.find('.qc-remediation-title').text()).toBe('核对建议')
  })
})

const DRAFT_CONTEXT = { instituteId: '泸县人民医院', patientId: 'P-1', visitId: 'V-1' }

function mountDraftable(props: Record<string, unknown> = {}) {
  return mount(QcRemediationSuggestion, {
    props: {
      suggestion: STRUCTURED_SUGGESTION,
      status: 'non_compliant',
      ruleId: 'LX0609-020',
      recordContext: DRAFT_CONTEXT,
      ...props,
    },
  })
}

describe('QcRemediationSuggestion 按需整改草稿', () => {
  it('只对三个会诊规则、不合规且三坐标齐全的结果开放入口', () => {
    expect(canRequestQcRemediationDraft('LX0609-020', 'non_compliant', DRAFT_CONTEXT)).toBe(true)
    expect(canRequestQcRemediationDraft('LX0609-022', 'non_compliant', DRAFT_CONTEXT)).toBe(true)
    expect(canRequestQcRemediationDraft('LX0609-023', 'non_compliant', DRAFT_CONTEXT)).toBe(true)

    expect(canRequestQcRemediationDraft('LX0609-018', 'non_compliant', DRAFT_CONTEXT)).toBe(false)
    expect(canRequestQcRemediationDraft('LX0609-020', 'data_gap', DRAFT_CONTEXT)).toBe(false)
    expect(canRequestQcRemediationDraft('LX0609-020', 'non_compliant', { instituteId: 'x' })).toBe(
      false,
    )
  })

  it('缺少三坐标时不渲染草稿入口', () => {
    const wrapper = mountDraftable({ recordContext: undefined })

    expect(wrapper.find('[data-testid="qc-remediation-draft"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="qc-remediation-draft-request"]').exists()).toBe(false)
  })

  it('点击生成后才展示草稿正文，并标注待医师确认', async () => {
    vi.mocked(requestLuxian0609RemediationDraft).mockResolvedValueOnce({
      success: true,
      data: {
        available: true,
        rule_id: 'LX0609-020',
        draft: '拟补充第2次会诊意见的执行情况。',
      },
    })
    const wrapper = mountDraftable()

    expect(wrapper.find('[data-testid="qc-remediation-draft-text"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('待医师确认')

    await wrapper.find('[data-testid="qc-remediation-draft-request"]').trigger('click')
    await flushPromises()

    expect(requestLuxian0609RemediationDraft).toHaveBeenCalledWith(DRAFT_CONTEXT, 'LX0609-020')
    expect(wrapper.find('[data-testid="qc-remediation-draft-text"]').text()).toBe(
      '拟补充第2次会诊意见的执行情况。',
    )
    // 权威建议不被改写。
    expect(wrapper.find('.qc-remediation-sections').exists()).toBe(true)
  })

  it('生成失败时只提示，不展示任何草稿', async () => {
    vi.mocked(requestLuxian0609RemediationDraft).mockResolvedValueOnce({
      success: false,
      message: '生成整改草稿失败',
    })
    const wrapper = mountDraftable()

    await wrapper.find('[data-testid="qc-remediation-draft-request"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="qc-remediation-draft-text"]').exists()).toBe(false)
    expect(wrapper.find('.qc-remediation-draft-error').text()).toBe('生成整改草稿失败')
  })
})
