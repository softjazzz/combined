import { Select } from 'ant-design-vue'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import QcDiagnosticExport from '@/components/qc/QcDiagnosticExport.vue'
import CaseCommunicationPanel from '@/components/qc/CaseCommunicationPanel.vue'
import QcRecordReviewPreview from '@/views/workstation-v4/components/qc/QcRecordReviewPreview.vue'
import type { QcRecordResultRow } from '@/views/workstation-v4/components/qc/QcRecordResultTable.vue'
import type { SingleRecordQcResultPayload } from '@/views/workstation-v4/customer-sample-validation/single-record-result-model'

const { getLatestResult } = vi.hoisted(() => ({ getLatestResult: vi.fn() }))
vi.mock('@/services/sichuan-rule-workspace-service', () => ({
  getLatestLuxian0609RecordResult: getLatestResult,
}))
vi.mock('@/components/qc/CaseCommunicationPanel.vue', () => ({
  default: {
    props: ['instituteId', 'patientId', 'visitId', 'scene', 'jobId'],
    template: '<div data-testid="case-communication-entry" />',
  },
}))

const row: QcRecordResultRow = {
  recordKey: '["H-1","P-1","V-1"]',
  instituteId: 'H-1',
  patientId: 'P-1',
  visitId: 'V-1',
  patientName: '患者甲',
  department: '内科',
  resultStatus: 'priority',
  resultLabel: '需复核',
  issueSummary: '确定问题 1',
}
function payload(
  overrides: Partial<SingleRecordQcResultPayload> = {},
): SingleRecordQcResultPayload {
  return {
    schema_version: 'lx0609-single-record-result-v1',
    state: 'ready',
    reason_code: '',
    record_ref: 'authorized-record',
    job_id: 'job-1',
    expected_rule_count: 1,
    result_rule_count: 1,
    is_complete: true,
    items: [
      {
        rule_id: 'LX0609-01-01-01',
        rule_name: '测试质控项',
        status: 'non_compliant',
        conclusion: '后端已保存的结论',
        source_document: '入院记录',
      },
    ],
    ...overrides,
  }
}
function deferred() {
  let resolve!: (value: { success: boolean; data: SingleRecordQcResultPayload }) => void
  const promise = new Promise<{ success: boolean; data: SingleRecordQcResultPayload }>((done) => {
    resolve = done
  })
  return { promise, resolve }
}

describe('QcRecordReviewPreview', () => {
  it.each(['failed', 'partial_failed'] as const)(
    '读取成功但执行 %s 时保留有效项并隐藏失败横幅', async (executionStatus) => {
      const data = payload({
        execution_status: executionStatus, failed_rule_count: 2,
        failed_rule_ids: ['LX0609-07-03-01', 'LX0609-03-01-04'], is_complete: false,
        items: executionStatus === 'failed' ? [] : payload().items,
        result_rule_count: executionStatus === 'failed' ? 0 : 1,
      })
      getLatestResult.mockResolvedValue({ success: true, data })
      const wrapper = mount(QcRecordReviewPreview, { props: { row } })
      await flushPromises()
      expect(wrapper.text()).not.toContain('本次质控未全部完成')
      expect(wrapper.findAll('[data-testid="preview-item"]')).toHaveLength(data.items.length)
      expect(wrapper.find('.full-result-button').exists()).toBe(true)
      if (executionStatus === 'failed') expect(wrapper.text()).toContain('该状态暂无质控项')
      else expect(wrapper.text()).toContain('后端已保存的结论')
      // 刷新为正常成功轮后不残留旧失败提示。
      getLatestResult.mockResolvedValue({ success: true, data: payload() })
      await wrapper.setProps({ refreshKey: 1 })
      await flushPromises()
      expect(wrapper.find('[role="alert"]').exists()).toBe(false)
      expect(wrapper.text()).toContain('后端已保存的结论')
      wrapper.unmount()
    },
  )
  it('病历沟通只传递当前已保存结果及精确三坐标，不改变原预览', async () => {
    const wrapper = mount(QcRecordReviewPreview, { props: { row, carePhase: 'discharged' } })
    await flushPromises()
    expect(wrapper.getComponent(CaseCommunicationPanel).props()).toEqual({
      instituteId: 'H-1',
      patientId: 'P-1',
      visitId: 'V-1',
      scene: 'final',
      jobId: 'job-1',
    })
    await wrapper.setProps({ row: { ...row, resultStatus: 'not-run' } })
    expect(wrapper.findComponent(CaseCommunicationPanel).exists()).toBe(false)
    wrapper.unmount()
  })
  it('接口展示字段返回英文枚举时使用中文状态，不改变状态筛选', async () => {
    const data = payload()
    data.items[0].display_status = 'non_compliant'
    getLatestResult.mockResolvedValue({ success: true, data })
    const wrapper = mount(QcRecordReviewPreview, { props: { row } })
    await flushPromises()
    expect(wrapper.get('.status-label').text()).toBe('确定问题')
    expect(wrapper.text()).not.toContain('non_compliant')
    expect(wrapper.getComponent(Select).props('value')).toBe('non_compliant')
    wrapper.unmount()
  })

  beforeEach(() => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    )
    getLatestResult.mockReset()
    getLatestResult.mockResolvedValue({ success: true, data: payload() })
  })
  afterEach(() => vi.unstubAllGlobals())

  it('未选择和未运行不请求，患者字段缺失保留占位', async () => {
    const wrapper = mount(QcRecordReviewPreview, { props: { row: null } })
    expect(wrapper.text()).toContain('请选择左侧病历')
    await wrapper.setProps({ row: { ...row, resultStatus: 'not-run' } })
    expect(wrapper.text()).toContain('暂无已保存质控结果')
    expect(wrapper.text()).toContain('入院时间—最近质控—')
    expect(getLatestResult).not.toHaveBeenCalled()
  })

  it('授权的捕获失败从终末预览明确打开上次结果，预览不自行查旧任务', async () => {
    getLatestResult.mockResolvedValue({ success: true, data: payload({
      state: 'technical_error', reason_code: 'material_capture_failed', items: [], result_rule_count: 0,
    }) })
    const wrapper = mount(QcRecordReviewPreview, { props: { row, carePhase: 'discharged' } })
    await flushPromises()
    const action = wrapper.get('[role="alert"] button')
    expect(action.text()).toBe('查看上一次有效结果')
    await action.trigger('click')
    expect(wrapper.emitted('open-full')).toEqual([[row.recordKey, { resultView: 'previous_valid', anchorJobId: 'job-1' }]])
    expect(getLatestResult).toHaveBeenCalledTimes(1)
  })

  it('显示加载状态并按服务端三坐标读取，默认确定问题，可打开完整结果', async () => {
    const request = deferred()
    getLatestResult.mockReturnValue(request.promise)
    const wrapper = mount(QcRecordReviewPreview, { props: { row } })
    expect(wrapper.get('[role="status"]').text()).toContain('正在读取')
    request.resolve({ success: true, data: payload() })
    await flushPromises()
    expect(getLatestResult).toHaveBeenCalledWith({
      instituteId: 'H-1',
      patientId: 'P-1',
      visitId: 'V-1',
    })
    expect(wrapper.getComponent(Select).props('value')).toBe('non_compliant')
    expect(wrapper.text()).toContain('后端已保存的结论')
    expect(wrapper.text()).toContain('入院记录')
    const diagnosticExport = wrapper.getComponent(QcDiagnosticExport)
    expect(diagnosticExport.text()).toContain('质控诊断包')
    expect(diagnosticExport.props('context')).toMatchObject({
      instituteId: 'H-1',
      patientId: 'P-1',
      visitId: 'V-1',
      recordRef: 'authorized-record',
      jobId: 'job-1',
      resultSchemaVersion: 'lx0609-single-record-result-v1',
    })
    await wrapper.get('.preview-item .text-button').trigger('click')
    await wrapper.get('.full-result-button').trigger('click')
    expect(wrapper.emitted('open-full')).toEqual([[row.recordKey], [row.recordKey]])
    expect(wrapper.text()).not.toContain('定位成功')
  })

  it('全文展开复用同一说明节点，已保存建议默认展示且完整分段', async () => {
    const data = payload()
    data.items[0].suggestion =
      '修改对象：会诊记录 需要补充：执行结果 推荐写法：依据事实记录 注意事项：不要倒签'
    getLatestResult.mockResolvedValue({ success: true, data })
    const wrapper = mount(QcRecordReviewPreview, { props: { row } })
    await flushPromises()
    const summary = wrapper.get('.item-summary').element
    const suggestion = wrapper.get('[data-testid="qc-remediation-suggestion"]')
    expect(suggestion.text()).toContain('修改建议')
    expect(suggestion.findAll('.qc-remediation-section')).toHaveLength(4)
    expect(suggestion.text()).toContain('不要倒签')
    await wrapper.get('.expand-button').trigger('click')
    expect(wrapper.get('.item-summary').element).toBe(summary)
    expect(wrapper.get('.item-summary').classes()).toContain('is-expanded')
    expect(wrapper.text().split('后端已保存的结论')).toHaveLength(2)
    expect(wrapper.get('[data-testid="qc-remediation-suggestion"]').text()).toContain('不要倒签')
    await wrapper.get('.expand-button').trigger('click')
    expect(wrapper.get('.item-summary').classes()).not.toContain('is-expanded')
    wrapper.unmount()
  })

  it.each([
    ['入院记录：缺少签名', '缺少签名'],
    ['入院记录:缺少签名', '缺少签名'],
    ['其他文书：缺少签名', '其他文书：缺少签名'],
    ['入院记录：', '入院记录：'],
  ])('标题只移除确切文书前缀：%s', async (name, expected) => {
    const data = payload()
    data.items[0].rule_name = name
    getLatestResult.mockResolvedValue({ success: true, data })
    const wrapper = mount(QcRecordReviewPreview, { props: { row } })
    await flushPromises()
    expect(wrapper.get('.item-heading h3').text()).toBe(expected)
    expect(wrapper.get('.item-heading h3').attributes('title')).toBe(name)
    expect(wrapper.get('.item-meta').text()).toContain('入院记录')
    expect(data.items[0].rule_name).toBe(name)
    wrapper.unmount()
  })

  it.each([
    ['technical_error', 'authorized-record', '质控结果读取异常'],
    ['ready', '', '缺少当前病历的服务端授权引用'],
    ['not_found', 'authorized-record', '暂无已保存质控结果'],
  ] as const)('阻止不安全结果展示：%s / %s', async (state, record_ref, message) => {
    getLatestResult.mockResolvedValue({ success: true, data: payload({ state, record_ref }) })
    const wrapper = mount(QcRecordReviewPreview, { props: { row } })
    await flushPromises()
    expect(wrapper.text()).toContain(message)
    expect(wrapper.text()).not.toContain('后端已保存的结论')
    expect(wrapper.find('.full-result-button').exists()).toBe(false)
    expect(wrapper.findComponent(QcDiagnosticExport).exists()).toBe(false)
  })

  it('读取失败支持重试，refreshKey重读同一病历', async () => {
    getLatestResult.mockRejectedValueOnce(new Error('network'))
    const wrapper = mount(QcRecordReviewPreview, { props: { row } })
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('读取失败')
    await wrapper.get('[role="alert"] button').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="preview-item"]').exists()).toBe(true)
    await wrapper.setProps({ refreshKey: 1 })
    await flushPromises()
    expect(getLatestResult).toHaveBeenCalledTimes(3)
  })

  it('快速切换患者时旧响应不能覆盖新结果', async () => {
    const first = deferred()
    const second = deferred()
    getLatestResult.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    const wrapper = mount(QcRecordReviewPreview, { props: { row } })
    const nextRow = {
      ...row,
      patientId: 'P-2',
      patientName: '患者乙',
      recordKey: '["H-1","P-2","V-1"]',
    }
    await wrapper.setProps({ row: nextRow })
    second.resolve({
      success: true,
      data: payload({ items: [{ rule_id: 'NEW', rule_name: '新患者结果', status: 'compliant' }] }),
    })
    await flushPromises()
    first.resolve({ success: true, data: payload() })
    await flushPromises()
    expect(wrapper.text()).toContain('新患者结果')
    expect(wrapper.text()).not.toContain('后端已保存的结论')
    await wrapper.get('.full-result-button').trigger('click')
    expect(wrapper.emitted('open-full')).toEqual([[nextRow.recordKey]])
  })

  it('技术异常和未知状态保持待处理入口，全部入口可查看所有分组，最多预览三项', async () => {
    const statuses = [
      'technical_error',
      'not_executed',
      'new_status',
      'ai_suggested_compliant',
      'data_gap',
      'compliant',
      'not_applicable',
    ]
    getLatestResult.mockResolvedValue({
      success: true,
      data: payload({
        items: statuses.map((status, index) => ({
          rule_id: `RULE-${index}`,
          rule_name: status === 'technical_error' ? '技术异常规则' : `规则${index}`,
          status,
          conclusion: '原始说明',
        })),
      }),
    })
    const wrapper = mount(QcRecordReviewPreview, { props: { row } })
    await flushPromises()
    expect(wrapper.getComponent(Select).props('value')).toBe('pending')
    expect(
      wrapper
        .getComponent(Select)
        .props('options')
        .find((option) => option.value === 'pending')!.label,
    ).toContain('5')
    expect(wrapper.text()).toContain('技术异常')
    expect(wrapper.findAll('[data-testid="preview-item"]')).toHaveLength(3)
    expect(wrapper.getComponent(Select).props('options')).toHaveLength(5)
    expect(wrapper.find('.ant-pagination').exists()).toBe(false)
    wrapper.getComponent(Select).vm.$emit('update:value', 'compliant')
    await flushPromises()
    expect(wrapper.findAll('[data-testid="preview-item"]')).toHaveLength(1)
    wrapper.getComponent(Select).vm.$emit('update:value', 'all')
    await flushPromises()
    expect(wrapper.text()).toContain('共 7 项')
  })

  it('身份缺失不请求，卸载后在途请求不恢复结果', async () => {
    const missing = mount(QcRecordReviewPreview, { props: { row: { ...row, visitId: undefined } } })
    expect(missing.text()).toContain('身份信息不完整')
    expect(getLatestResult).not.toHaveBeenCalled()
    missing.unmount()
    const request = deferred()
    getLatestResult.mockReturnValueOnce(request.promise)
    const wrapper = mount(QcRecordReviewPreview, { props: { row } })
    wrapper.unmount()
    request.resolve({ success: true, data: payload() })
    await flushPromises()
    expect(wrapper.emitted('open-full')).toBeUndefined()
  })
})
