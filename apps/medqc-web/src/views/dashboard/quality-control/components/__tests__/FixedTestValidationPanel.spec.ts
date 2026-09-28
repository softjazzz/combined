import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  list: vi.fn(), getProof: vi.fn(), run: vi.fn(), publish: vi.fn(),
}))

vi.mock('@/services/test-medical-records', () => ({ listTestRecords: mocks.list }))
vi.mock('@/services/custom-rule-workspace-service', () => ({
  getFixedTestValidation: mocks.getProof,
  runFixedTestValidation: mocks.run,
  publishValidatedWorkspaceDraft: mocks.publish,
}))

import FixedTestValidationPanel from '../FixedTestValidationPanel.vue'

const record = {
  id: 'item-1', institute_id: 'HOSP-A', patient_id: 'PAT-A', visit_id: 'VISIT-A',
  case_title: '测试病例A', patient_name: '患者A', department: '内科', mr_no: 'MR-1',
  document_count: 2, rule_ids: [], rule_count: 0, latest_job_id: '', bundle_status: 'ready',
  origin: 'created', sex: null, age: null, admission_time: null, source_item_id: '', state: 'active',
  removed: false, superseded_by: null, created_at: '2026-09-28T10:00:00Z', updated_at: '2026-09-28T11:00:00Z',
}
const proof = {
  schema_version: 'fixed_test_records_v1', validation_id: 'validation-1', draft_id: 'draft-1',
  validated_revision: '2026-09-28T12:00:00Z', proof_revision: 'proof-1', created_at: '2026-09-28T12:01:00Z',
  item_count: 1, success_count: 1, failed_count: 0, issue_records: 1, compliant_records: 0,
  unknown_count: 0, technical_error_count: 0,
  selected_items: [{ item_id: 'item-1', item_updated_at: record.updated_at, record_ref: {
    institute_id: 'HOSP-A', patient_id: 'PAT-A', visit_id: 'VISIT-A',
  } }],
  results: [{ item_id: 'item-1', item_updated_at: record.updated_at, record_ref: {
    institute_id: 'HOSP-A', patient_id: 'PAT-A', visit_id: 'VISIT-A',
  }, status: 'non_compliant', issue_count: 1,
  finding: { description: '首次病程记录存在', evidence: '可信文书目录命中' },
  condition_trace: ['condition-1=true'],
  }], failures: [],
}
const emptyState = {
  draft_id: 'draft-1', draft_updated_at: '2026-09-28T12:00:00Z', validation: null,
  draft_status: 'draft', published_rule_id: null,
  publish_ready: false, unavailable_reason: 'not_tested',
}

function render() {
  return mount(FixedTestValidationPanel, {
    props: { draftId: 'draft-1', draftUpdatedAt: '2026-09-28T12:00:00Z', actorKey: 'manager|qc_manager', enabled: true },
  })
}

describe('FixedTestValidationPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.list.mockResolvedValue({ success: true, data: { items: [record], total: 1, page: 1, page_size: 100 } })
    mocks.getProof.mockResolvedValue({ success: true, data: emptyState })
    mocks.run.mockResolvedValue({ success: true, data: { ...emptyState, validation: proof, publish_ready: true, unavailable_reason: null }, resultUnknown: false, conflict: false })
    mocks.publish.mockResolvedValue({ success: true, data: { draft_id: 'draft-1', rule_code: 'CUSTOM-001', published_rule_id: 'rule-1', status: 'published' }, resultUnknown: false, conflict: false })
  })

  it('冻结所选固定池版本并把发现缺陷作为有效测试结果展示', async () => {
    mocks.run.mockResolvedValueOnce({
      success: true,
      data: { ...emptyState, draft_updated_at: '2026-09-28T13:00:00Z', validation: proof, publish_ready: true, unavailable_reason: null },
      resultUnknown: false, conflict: false,
    })
    const wrapper = render()
    await flushPromises()
    await wrapper.get('input[type="checkbox"]').setValue(true)
    await wrapper.get('[data-testid="run-fixed-validation"]').trigger('click')
    await flushPromises()

    expect(mocks.run).toHaveBeenCalledWith('draft-1', {
      expected_updated_at: '2026-09-28T12:00:00Z',
      items: [{ item_id: 'item-1', expected_updated_at: '2026-09-28T11:00:00Z' }],
    })
    expect(wrapper.text()).toContain('发现缺陷')
    expect(wrapper.text()).toContain('可信文书目录命中')
    expect(wrapper.text()).toContain('固定测试已完成，可以发布')
    expect(wrapper.emitted('draft-updated')?.[0]).toEqual(['2026-09-28T13:00:00Z'])
  })

  it('只用当前证明与草稿版本发布并呈现真实成功状态', async () => {
    mocks.getProof.mockResolvedValue({ success: true, data: { ...emptyState, validation: proof, publish_ready: true, unavailable_reason: null } })
    const wrapper = render()
    await flushPromises()
    await wrapper.get('[data-testid="publish-validated-draft"]').trigger('click')
    await flushPromises()

    expect(mocks.publish).toHaveBeenCalledWith('draft-1', {
      expected_updated_at: '2026-09-28T12:00:00Z', validation_id: 'validation-1',
    })
    expect(wrapper.text()).toContain('质控点 CUSTOM-001 已发布')
    expect(wrapper.emitted('published')).toHaveLength(1)
  })

  it('测试写回执未知时先回读新证明而不盲目重试', async () => {
    mocks.run.mockResolvedValue({ success: false, message: '结果未知', resultUnknown: true, conflict: false })
    mocks.getProof
      .mockResolvedValueOnce({ success: true, data: emptyState })
      .mockResolvedValueOnce({ success: true, data: { ...emptyState, validation: proof, publish_ready: true, unavailable_reason: null } })
    const wrapper = render()
    await flushPromises()
    await wrapper.get('input[type="checkbox"]').setValue(true)
    await wrapper.get('[data-testid="run-fixed-validation"]').trigger('click')
    await flushPromises()

    expect(mocks.run).toHaveBeenCalledTimes(1)
    expect(mocks.getProof).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('已重新读取并确认测试证明')
    expect(wrapper.get('[data-testid="run-fixed-validation"]').attributes('disabled')).toBeUndefined()
  })

  it('测试结果未知且回读没有新证明时保持锁定', async () => {
    mocks.run.mockResolvedValue({ success: false, message: '结果未知', resultUnknown: true, conflict: false })
    const wrapper = render()
    await flushPromises()
    await wrapper.get('input[type="checkbox"]').setValue(true)
    await wrapper.get('[data-testid="run-fixed-validation"]').trigger('click')
    await flushPromises()
    expect(mocks.run).toHaveBeenCalledTimes(1)
    expect(wrapper.get('[data-testid="run-fixed-validation"]').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('操作结果仍无法确认')

    await wrapper.get('.panel-heading .secondary-button').trigger('click')
    await flushPromises()
    await wrapper.get('input[type="checkbox"]').setValue(true)
    expect(wrapper.get('[data-testid="run-fixed-validation"]').attributes('disabled')).toBeDefined()
    expect(mocks.run).toHaveBeenCalledTimes(1)
  })

  it('测试结果未知后dirty关闭再开启仍不能绕过锁', async () => {
    mocks.run.mockResolvedValue({ success: false, message: '结果未知', resultUnknown: true, conflict: false })
    const wrapper = render()
    await flushPromises()
    await wrapper.get('input[type="checkbox"]').setValue(true)
    await wrapper.get('[data-testid="run-fixed-validation"]').trigger('click')
    await flushPromises()

    await wrapper.setProps({ enabled: false })
    await flushPromises()
    await wrapper.setProps({ enabled: true })
    await flushPromises()
    await wrapper.get('input[type="checkbox"]').setValue(true)
    expect(wrapper.get('[data-testid="run-fixed-validation"]').attributes('disabled')).toBeDefined()
    expect(mocks.run).toHaveBeenCalledTimes(1)
  })

  it('测试请求进行中dirty关开会转未知锁且不能重复POST', async () => {
    let resolveRun!: (value: unknown) => void
    const pendingRun = new Promise((resolve) => { resolveRun = resolve })
    mocks.run.mockReturnValueOnce(pendingRun)
    const wrapper = render()
    await flushPromises()
    await wrapper.get('input[type="checkbox"]').setValue(true)
    await wrapper.get('[data-testid="run-fixed-validation"]').trigger('click')
    await Promise.resolve()

    await wrapper.setProps({ enabled: false })
    await wrapper.setProps({ enabled: true })
    await flushPromises()
    await wrapper.get('input[type="checkbox"]').setValue(true)
    expect(wrapper.get('[data-testid="run-fixed-validation"]').attributes('disabled')).toBeDefined()
    await wrapper.get('[data-testid="run-fixed-validation"]').trigger('click')
    expect(mocks.run).toHaveBeenCalledTimes(1)

    resolveRun({
      success: true,
      data: { ...emptyState, validation: proof, publish_ready: true, unavailable_reason: null },
      resultUnknown: false,
      conflict: false,
    })
    await flushPromises()
    expect(mocks.run).toHaveBeenCalledTimes(1)
  })

  it('发布结果未知时只以已发布GET状态确认成功', async () => {
    mocks.getProof
      .mockResolvedValueOnce({ success: true, data: { ...emptyState, validation: proof, publish_ready: true, unavailable_reason: null } })
      .mockResolvedValueOnce({ success: true, data: {
        ...emptyState, draft_status: 'published', published_rule_id: 'rule-1', validation: proof,
        publish_ready: false, unavailable_reason: 'draft_changed',
      } })
    mocks.publish.mockResolvedValue({ success: false, message: '发布结果未知', resultUnknown: true, conflict: false })
    const wrapper = render()
    await flushPromises()
    await wrapper.get('[data-testid="publish-validated-draft"]').trigger('click')
    await flushPromises()
    expect(mocks.publish).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('已重新读取并确认质控点发布成功')
    expect(wrapper.emitted('published')).toHaveLength(1)
  })

  it('非active固定池回执失败关闭且不允许选择测试', async () => {
    mocks.list.mockResolvedValue({ success: true, data: { items: [{ ...record, state: 'superseded' }], total: 1, page: 1, page_size: 100 } })
    const wrapper = render()
    await flushPromises()
    expect(wrapper.text()).toContain('固定测试病例回执格式异常')
    expect(wrapper.find('input[type="checkbox"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="run-fixed-validation"]').attributes('disabled')).toBeDefined()
  })

  it.each([
    { institute_id: '' },
    { patient_id: '' },
    { visit_id: '' },
    { updated_at: 'not-a-date' },
  ])('active病例缺可信身份或版本时失败关闭: %o', async (invalid) => {
    mocks.list.mockResolvedValue({
      success: true,
      data: { items: [{ ...record, ...invalid }], total: 1, page: 1, page_size: 100 },
    })
    const wrapper = render()
    await flushPromises()
    expect(wrapper.text()).toContain('固定测试病例回执格式异常')
    expect(wrapper.find('input[type="checkbox"]').exists()).toBe(false)
  })

  it('账号变化后丢弃旧列表与证明迟到响应', async () => {
    let resolveList!: (value: unknown) => void
    const pendingList = new Promise((resolve) => { resolveList = resolve })
    mocks.list.mockReturnValueOnce(pendingList).mockResolvedValueOnce({ success: true, data: { items: [], total: 0, page: 1, page_size: 100 } })
    const wrapper = render()
    await Promise.resolve()
    await wrapper.setProps({ actorKey: 'manager-2|qc_manager' })
    await flushPromises()
    resolveList({ success: true, data: { items: [record], total: 1, page: 1, page_size: 100 } })
    await flushPromises()
    expect(wrapper.text()).not.toContain('测试病例A')
  })
})
