/* eslint-disable vue/one-component-per-file */
import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import SemanticRulesBatchResultDrawer from '@/views/workstation-v4/semantic-rules/components/SemanticRulesBatchResultDrawer.vue'
import type {
  SichuanBatchJob,
  SichuanBatchJobDebugSnapshot,
} from '@/views/workstation-v4/semantic-rules/types'

const ADrawerStub = defineComponent({
  name: 'ADrawerStub',
  props: {
    open: Boolean,
  },
  emits: ['close'],
  setup(props, { slots }) {
    return () => (props.open ? h('div', { class: 'a-drawer-stub' }, slots.default?.()) : null)
  },
})

const ATableStub = defineComponent({
  name: 'ATableStub',
  props: {
    columns: {
      type: Array,
      default: () => [],
    },
    dataSource: {
      type: Array,
      default: () => [],
    },
  },
  setup(props) {
    return () =>
      h(
        'div',
        {
          class: 'a-table-stub',
          'data-size': String((props.dataSource || []).length),
        },
        JSON.stringify(props.dataSource || []),
      )
  },
})

const ASelectStub = defineComponent({
  name: 'ASelectStub',
  props: {
    value: {
      type: String,
      default: undefined,
    },
    options: {
      type: Array,
      default: () => [],
    },
  },
  emits: ['change'],
  setup(props, { emit, attrs }) {
    return () =>
      h(
        'select',
        {
          ...attrs,
          class: ['a-select-stub', attrs.class],
          value: props.value,
          onChange: (event: Event) => {
            const target = event.target as HTMLSelectElement
            emit('change', target.value || undefined)
          },
        },
        [
          h('option', { value: '' }, '全部规则'),
          ...(props.options as Array<{ label: string; value: string }>).map((option) =>
            h('option', { value: option.value }, option.label),
          ),
        ],
      )
  },
})

const AButtonStub = defineComponent({
  name: 'AButtonStub',
  emits: ['click'],
  setup(_, { slots, emit }) {
    return () =>
      h(
        'button',
        {
          onClick: () => emit('click'),
        },
        slots.default?.(),
      )
  },
})

const ADropdownStub = defineComponent({
  name: 'ADropdownStub',
  setup(_, { slots }) {
    return () => h('div', { class: 'a-dropdown-stub' }, [slots.default?.(), slots.overlay?.()])
  },
})

const AMenuStub = defineComponent({
  name: 'AMenuStub',
  emits: ['click'],
  setup(_, { slots }) {
    return () => h('div', { class: 'a-menu-stub' }, slots.default?.())
  },
})

const AMenuItemStub = defineComponent({
  name: 'AMenuItemStub',
  setup(_, { slots }) {
    return () => h('button', { class: 'a-menu-item-stub' }, slots.default?.())
  },
})

const ATagStub = defineComponent({
  name: 'ATagStub',
  setup(_, { slots }) {
    return () => h('span', { class: 'a-tag-stub' }, slots.default?.())
  },
})

const AProgressStub = defineComponent({
  name: 'AProgressStub',
  setup() {
    return () => h('div', { class: 'a-progress-stub' })
  },
})

const ARadioGroupStub = defineComponent({
  name: 'ARadioGroupStub',
  props: {
    value: {
      type: String,
      default: '',
    },
  },
  emits: ['update:value'],
  setup(_, { slots, emit }) {
    return () =>
      h('div', { class: 'a-radio-group-stub' }, [
        h(
          'button',
          {
            class: 'a-radio-business-stub',
            onClick: () => emit('update:value', 'business'),
          },
          '业务视图',
        ),
        h(
          'button',
          {
            class: 'a-radio-advanced-stub',
            onClick: () => emit('update:value', 'advanced'),
          },
          '高级视图',
        ),
        slots.default?.(),
      ])
  },
})

const ARadioButtonStub = defineComponent({
  name: 'ARadioButtonStub',
  setup(_, { slots }) {
    return () => h('button', { class: 'a-radio-button-stub' }, slots.default?.())
  },
})

const ASwitchStub = defineComponent({
  name: 'ASwitchStub',
  props: {
    checked: Boolean,
  },
  emits: ['update:checked'],
  setup() {
    return () => h('button', { class: 'a-switch-stub' })
  },
})

const AInputStub = defineComponent({
  name: 'AInputStub',
  props: {
    value: {
      type: String,
      default: '',
    },
  },
  emits: ['update:value', 'change'],
  setup(props, { emit }) {
    return () =>
      h('input', {
        class: 'a-input-stub',
        value: props.value,
        onInput: (event: Event) => {
          const target = event.target as HTMLInputElement
          emit('update:value', target.value)
          emit('change', event)
        },
      })
  },
})

const drawerStubs = {
  'a-drawer': ADrawerStub,
  'a-table': ATableStub,
  'a-select': ASelectStub,
  'a-button': AButtonStub,
  'a-dropdown': ADropdownStub,
  'a-menu': AMenuStub,
  'a-menu-item': AMenuItemStub,
  'a-tag': ATagStub,
  'a-progress': AProgressStub,
  'a-radio-group': ARadioGroupStub,
  'a-radio-button': ARadioButtonStub,
  'a-switch': ASwitchStub,
  'a-input': AInputStub,
}

type DrawerTestProps = {
  open: boolean
  batchJobDetail: SichuanBatchJob
  batchJobDebugSnapshot: SichuanBatchJobDebugSnapshot
  batchJobDebugLoading: boolean
  batchJobDetailLoading: boolean
  fetchBatchJobDebugSnapshot: ReturnType<typeof vi.fn>
  close: ReturnType<typeof vi.fn>
  exportBatchJobReport: ReturnType<typeof vi.fn>
  reviewBatchJobResult?: ReturnType<typeof vi.fn>
  reviewBatchJobLoading?: boolean
  getBatchJobStatusTagClass: ReturnType<typeof vi.fn>
  getBatchJobStatusText: ReturnType<typeof vi.fn>
  formatDateTime: ReturnType<typeof vi.fn>
}

function buildProps(): DrawerTestProps {
  const batchJobDetail: SichuanBatchJob = {
    id: 'job-1',
    rule_code: 'SC-BATCH',
    rule_name: '全病历批量任务',
    scope: 'final',
    status: 'running',
    created_at: '2026-04-13T12:00:00Z',
    total_records: 10,
    success_count: 7,
    failed_count: 3,
    issue_records: 2,
    summary: {
      total_records: 10,
      success_count: 7,
      failed_count: 3,
      failed_record_count: 2,
      issue_records: 2,
      compliant_records: 8,
      total_tokens: 120,
      total_processing_time: 12,
      executor_breakdown: { program: 1, llm: 1 },
      cache_breakdown: { hit: 1, miss: 1 },
      result_aggregation: {
        cluster_count: 1,
        duplicate_hits: 0,
        clusters: [],
        rule_breakdown: [
          { rule_id: 'SC-001', rule_name: '规则一', hits: 1 },
          { rule_id: 'SC-002', rule_name: '规则二', hits: 1 },
        ],
        executor_breakdown: [{ key: 'program', count: 1 }],
        document_breakdown: [{ key: 'admission_record', count: 1 }],
        defect_level_breakdown: [{ key: 'critical', count: 1 }],
      },
    },
    rule_results: [
      {
        id: 'rule-job-1',
        rule_code: 'SC-001',
        rule_name: '规则一',
        status: 'completed',
        issue_records: 1,
        success_count: 4,
        failed_count: 0,
        items: [
          {
            rule_job_id: 'rule-job-1',
            rule_id: 'SC-001',
            rule_code: 'SC-001',
            record_id: 'record-1',
            visit_id: 'visit-1',
            patient_name: '张某某',
            department: '神经内科',
            status: 'non_compliant',
            is_compliant: false,
            findings: '规则一命中',
          },
        ],
      },
      {
        id: 'rule-job-2',
        rule_code: 'SC-002',
        rule_name: '规则二',
        status: 'completed',
        issue_records: 1,
        success_count: 3,
        failed_count: 1,
        items: [
          {
            rule_job_id: 'rule-job-2',
            rule_id: 'SC-002',
            rule_code: 'SC-002',
            record_id: 'record-2',
            visit_id: 'visit-2',
            patient_name: '李某某',
            department: '普外科',
            status: 'non_compliant',
            is_compliant: false,
            findings: '规则二命中',
          },
        ],
      },
    ],
  }

  const batchJobDebugSnapshot: SichuanBatchJobDebugSnapshot = {
    job_id: 'job-1',
    status: 'running',
    scope: 'final',
    execution_mode: 'batch',
    rule_count: 2,
    filtered_rule_count: 2,
    current_rule: {
      rule_job_id: 'rule-job-1',
      rule_code: 'SC-001',
      rule_name: '规则一',
      progress: {
        completed: 4,
      },
    },
    rules: [
      {
        rule_job_id: 'rule-job-1',
        rule_code: 'SC-001',
        rule_name: '规则一',
        status: 'running',
        progress: {
          completed: 4,
        },
        debug: {
          trace_id: 'trace-1',
        },
      },
      {
        rule_job_id: 'rule-job-2',
        rule_code: 'SC-002',
        rule_name: '规则二',
        status: 'completed',
        progress: {
          completed: 3,
        },
        debug: {
          trace_id: 'trace-2',
        },
      },
    ],
    recent_items: [],
    recent_failed_records: [],
    updated_at: '2026-04-13T12:05:00Z',
  }

  return {
    open: true,
    batchJobDetail,
    batchJobDebugSnapshot,
    batchJobDebugLoading: false,
    batchJobDetailLoading: false,
    fetchBatchJobDebugSnapshot: vi.fn().mockResolvedValue(batchJobDebugSnapshot),
    close: vi.fn(),
    exportBatchJobReport: vi.fn(),
    getBatchJobStatusTagClass: vi.fn().mockReturnValue('status-tag'),
    getBatchJobStatusText: vi.fn().mockReturnValue('执行中'),
    formatDateTime: vi
      .fn()
      .mockImplementation((value?: string | Date | null) => String(value || '-')),
  }
}

describe('SemanticRulesBatchResultDrawer', () => {
  it('应提供明确返回样本验证入口并复用关闭逻辑', async () => {
    const props = buildProps()
    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props,
      global: {
        stubs: drawerStubs,
      },
    })

    const backButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('返回样本验证'))
    expect(backButton).toBeTruthy()

    await backButton?.trigger('click')
    expect(props.close).toHaveBeenCalledTimes(1)
  })

  it('已完成任务应提供 HTML 明细、Excel 和 CSV 导出入口', async () => {
    const props = buildProps()
    props.batchJobDetail.status = 'completed'
    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props,
      global: {
        stubs: drawerStubs,
      },
    })

    expect(wrapper.text()).toContain('导出 HTML 明细')
    expect(wrapper.text()).toContain('导出 Excel')
    expect(wrapper.text()).toContain('导出 CSV')
    ;(
      wrapper.vm as unknown as { handleExportMenuClick: (event: { key: string }) => void }
    ).handleExportMenuClick({
      key: 'html',
    })

    expect(props.exportBatchJobReport).toHaveBeenCalledWith('html')
  })

  it('部分失败任务应保留有效结果并单独展示失败规则', () => {
    const props = buildProps()
    props.batchJobDetail.status = 'failed'
    props.batchJobDetail.rule_set_key = 'luxian_0609_qc_v1'
    props.batchJobDetail.items = [
      {
        rule_id: 'LX0609-011',
        rule_code: 'LX0609-011',
        record_id: 'record-safe-1',
        visit_id: 'visit-safe-1',
        status: 'compliant',
        is_compliant: true,
      },
    ]
    props.batchJobDetail.failed_records = [
      {
        rule_id: 'LX0609-012',
        record_ref: '病例-失败-1',
        status: 'technical_error',
        reason_code: 'record_execution_failed',
      },
    ]
    if (props.batchJobDetail.summary) {
      props.batchJobDetail.summary.execution_status = 'partial_failed'
      props.batchJobDetail.summary.completed_rule_count = 1297
      props.batchJobDetail.summary.failed_rule_count = 3
    }

    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props,
      global: { stubs: drawerStubs },
    })

    expect(wrapper.text()).toContain('部分执行失败')
    expect(wrapper.text()).toContain('已保留并可查看 1297 项有效结果')
    expect(wrapper.text()).toContain('LX0609-012')
    expect(wrapper.text()).toContain('病例-失败-1')
    expect(wrapper.text()).toContain('模型输出失败，未形成质控结论')
  })

  it('泸县0609任务应展示复核建议并允许手动触发复核', async () => {
    const props = buildProps()
    props.batchJobDetail.status = 'completed'
    props.batchJobDetail.rule_set_key = 'luxian_0609_qc_v1'
    props.reviewBatchJobResult = vi.fn()
    if (props.batchJobDetail.summary) {
      props.batchJobDetail.summary.review_report = {
        review_status: 'completed',
        summary: {
          total_findings: 1,
          p0: 0,
          p1: 1,
          p2: 0,
        },
        findings: [
          {
            id: 'review-1',
            rule_id: 'LX0609-020',
            record_id: 'visit-001',
            severity: 'P1',
            suggested_status: 'not_applicable',
            customer_message: '当前病历未见会诊文书证据，本项不宜作为会诊执行问题展示。',
          },
        ],
      }
    }
    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props,
      global: {
        stubs: drawerStubs,
      },
    })

    expect(wrapper.text()).toContain('结果复核建议')
    expect(wrapper.text()).toContain('共 1 条建议')
    expect(wrapper.text()).toContain('当前病历未见会诊文书证据')

    const reviewButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('复核本次结果'))
    expect(reviewButton).toBeTruthy()
    await reviewButton?.trigger('click')
    expect(props.reviewBatchJobResult).toHaveBeenCalledTimes(1)
  })

  it('泸县0609原生任务不应展示模型、Prompt和Token诊断字段', async () => {
    const props = buildProps()
    props.batchJobDetail.status = 'completed'
    props.batchJobDetail.rule_set_key = 'luxian_0609_qc_v1'
    props.batchJobDetail.draft_ids = ['LX0609-029', 'LX0609-030', 'LX0609-032']
    props.batchJobDetail.filters = {
      rule_set_key: 'luxian_0609_qc_v1',
      rule_ids: ['LX0609-029', 'LX0609-030', 'LX0609-032'],
    }
    Object.assign(props.batchJobDetail.rule_results?.[0]?.items?.[0] || {}, {
      audit: { model_name: 'INTERNAL_NATIVE_MODEL_MARKER' },
    })
    if (props.batchJobDetail.summary) {
      props.batchJobDetail.summary.performance_profile = {
        tokens_total: 0,
        prompt_tokens: 0,
        completion_tokens: 0,
        unattributed_tokens: 0,
      }
    }

    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props,
      global: {
        stubs: drawerStubs,
      },
    })

    const deepReviewButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('深度复核'))
    expect(deepReviewButton).toBeTruthy()
    await deepReviewButton?.trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).not.toContain('INTERNAL_NATIVE_MODEL_MARKER')

    await wrapper.find('.a-radio-advanced-stub').trigger('click')
    await wrapper.vm.$nextTick()

    const issueTable = wrapper
      .findAllComponents(ATableStub)
      .find((table) =>
        (table.props('columns') as Array<{ key?: string }>).some(
          (column) => column.key === 'findings',
        ),
      )
    const issueColumnKeys = (issueTable?.props('columns') as Array<{ key?: string }>).map(
      (column) => column.key,
    )
    expect(issueColumnKeys).not.toContain('prompt_version')
    expect(issueColumnKeys).not.toContain('model_version')
    expect(wrapper.text()).not.toContain('总 Token')
    expect(wrapper.text()).not.toContain('输入 Token')
    expect(wrapper.text()).not.toContain('语义规则')
    expect(wrapper.text()).not.toContain('累计模型处理耗时')
    expect(wrapper.text()).not.toContain('底层执行规则')
    expect(wrapper.text()).not.toContain('映射到')
    expect(wrapper.text()).toContain('客户质控点')
  })

  it('应展示当前任务摘要中的病历级与规则级统计口径', () => {
    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props: buildProps(),
      global: {
        stubs: drawerStubs,
      },
    })

    expect(wrapper.text()).toContain('总病历10')
    expect(wrapper.text()).toContain('不合规规则2')
    expect(wrapper.text()).toContain('AI判断规则0')
    expect(wrapper.text()).toContain('已完成 0 / 10 份病历')
  })

  it('按单规则筛选时应联动规则结果概览、命中明细并拉取调试快照', async () => {
    const props = buildProps()
    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props,
      global: {
        stubs: drawerStubs,
      },
    })

    await wrapper.find('.a-radio-advanced-stub').trigger('click')
    await wrapper.vm.$nextTick()

    const genericIssueTable = wrapper
      .findAllComponents(ATableStub)
      .find((table) =>
        (table.props('columns') as Array<{ key?: string }>).some(
          (column) => column.key === 'findings',
        ),
      )
    const genericIssueColumnKeys = (
      genericIssueTable?.props('columns') as Array<{ key?: string }>
    ).map((column) => column.key)
    expect(genericIssueColumnKeys).toContain('prompt_version')
    expect(genericIssueColumnKeys).toContain('model_version')

    await wrapper.find('.debug-rule-select.a-select-stub').setValue('rule-job-2')
    await flushPromises()
    await wrapper.vm.$nextTick()

    expect(props.fetchBatchJobDebugSnapshot).toHaveBeenCalledWith('job-1', {
      ruleJobId: 'rule-job-2',
    })

    const tables = wrapper.findAllComponents(ATableStub)
    const ruleOverviewData = tables
      .map((table) => table.props('dataSource') as Array<{ id?: string }>)
      .find((data) => data.some((item) => item.id === 'rule-job-2')) as Array<{ id?: string }>
    expect(ruleOverviewData).toHaveLength(1)
    expect(ruleOverviewData[0]?.id).toBe('rule-job-2')

    await wrapper.find('.a-radio-business-stub').trigger('click')
    await wrapper.vm.$nextTick()

    const issueCards = wrapper.findAll('.issue-conclusion-card')
    expect(issueCards).toHaveLength(1)
    expect(issueCards[0]?.text()).toContain('SC-002')
    expect(issueCards[0]?.text()).toContain('规则二')
    expect(issueCards[0]?.text()).toContain('规则二命中')
    expect(wrapper.text()).toContain('规则：SC-002 · 规则二')
  })

  it('应保持任务统计摘要与问题明细数量一致', async () => {
    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props: buildProps(),
      global: {
        stubs: drawerStubs,
      },
    })

    const allRecordButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('全部病历'))
    expect(allRecordButton).toBeTruthy()
    await allRecordButton?.trigger('click')
    await wrapper.vm.$nextTick()

    const issueCards = wrapper.findAll('.issue-conclusion-card')

    expect(issueCards).toHaveLength(2)
    expect(wrapper.text()).toContain('当前共 2 条重点结果，其中不合规 2 条，AI判断 0 条')
    expect(wrapper.text()).toContain('重点结果')
    expect(wrapper.text()).toContain('总病历10')
    expect(wrapper.text()).toContain('规则一命中')
    expect(wrapper.text()).toContain('规则二命中')
  })

  it('多份病历同时质控时应按病历分组并支持筛选单份病历', async () => {
    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props: buildProps(),
      global: {
        stubs: drawerStubs,
      },
    })

    expect(wrapper.text()).toContain('先选病历，再看质控点')
    expect(wrapper.text()).toContain('本次涉及 2 份病历')
    expect(wrapper.text()).toContain('张某某 · record-1')
    expect(wrapper.text()).toContain('李某某 · record-2')

    const recordButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('张某某 · record-1'))
    expect(recordButton).toBeTruthy()
    await recordButton?.trigger('click')
    await wrapper.vm.$nextTick()

    const issueCards = wrapper.findAll('.issue-conclusion-card')
    expect(issueCards).toHaveLength(1)
    expect(issueCards[0]?.text()).toContain('规则一命中')
    expect(issueCards[0]?.text()).not.toContain('规则二命中')
    expect(wrapper.text()).toContain('张某某 · record-1：当前共 1 条重点结果')

    const secondRecordButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('李某某 · record-2'))
    expect(secondRecordButton).toBeTruthy()
    await secondRecordButton?.trigger('click')
    await wrapper.vm.$nextTick()
    const secondRecordCards = wrapper.findAll('.issue-conclusion-card')
    expect(secondRecordCards).toHaveLength(1)
    expect(secondRecordCards[0]?.text()).toContain('规则二命中')
    expect(secondRecordCards[0]?.text()).not.toContain('规则一命中')
  })

  it('泸县0609任务即使带正式后处理字段，也应按客户质控点状态展示不合规', async () => {
    const props = buildProps()
    props.batchJobDetail.status = 'completed'
    props.batchJobDetail.rule_set_key = 'luxian_0609_qc_v1'
    props.batchJobDetail.filters = {
      rule_set_key: 'luxian_0609_qc_v1',
      selected_rule_ids: ['LX0609-020', 'LX0609-021'],
      scoped_customer_rule_ids: ['LX0609-020', 'LX0609-021'],
      record_rule_map: { record_1: ['LX-017', 'SC-068'] },
    }
    Object.assign(props.batchJobDetail.summary || {}, {
      rule_set_key: 'luxian_0609_qc_v1',
      display_status_counts: {
        confirmed_defect: 0,
        data_quality_gap: 0,
        technical_error_internal: 0,
      },
    })

    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props,
      global: {
        stubs: drawerStubs,
      },
    })

    const allRecordButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('全部病历'))
    expect(allRecordButton).toBeTruthy()
    await allRecordButton?.trigger('click')
    await wrapper.vm.$nextTick()

    const text = wrapper.text()
    expect(text).toContain('任务已完成，已发现泸县0609质控点问题')
    expect(text).toContain('不合规 2 条')
    expect(text).toContain('当前展示泸县0609选定质控点验证结果，共 2 条客户质控点结果')
    expect(text).toContain('LX0609 客户质控点结果')
    expect(text).not.toContain('本次未发现泸县0609质控点问题')
  })

  it('泸县0609全量任务不应显示为 scoped run', () => {
    const props = buildProps()
    props.batchJobDetail.status = 'completed'
    props.batchJobDetail.rule_set_key = 'luxian_0609_qc_v1'
    props.batchJobDetail.customer_rule_count = 49
    props.batchJobDetail.execution_rule_count = 59
    props.batchJobDetail.rule_count = 49
    props.batchJobDetail.filters = {
      rule_set_key: 'luxian_0609_qc_v1',
      rule_ids: ['SC-002', 'CL-081'],
      customer_rule_count: 49,
      execution_rule_count: 59,
      rule_count: 59,
    }
    Object.assign(props.batchJobDetail.summary || {}, {
      rule_set_key: 'luxian_0609_qc_v1',
      rule_count: 49,
      execution_rule_count: 59,
    })

    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props,
      global: {
        stubs: drawerStubs,
      },
    })

    const text = wrapper.text()
    expect(text).toContain('全量 0609 规则集')
    expect(text).toContain('未限定，执行全量 0609 质控点')
    expect(text).toContain('全量运行，不按单病历限定执行规则')
    expect(text).toContain('当前展示泸县0609全量 0609 规则集结果')
    expect(text).not.toContain('scoped run')
  })

  it('无问题默认视图应展示合规和不适用结果的判定依据', () => {
    const props = buildProps()
    props.batchJobDetail.status = 'completed'
    props.batchJobDetail.rule_set_key = 'luxian_0609_qc_v1'
    if (props.batchJobDetail.summary) {
      props.batchJobDetail.summary.rule_set_key = 'luxian_0609_qc_v1'
    }

    const firstItem = props.batchJobDetail.rule_results?.[0]?.items?.[0]
    Object.assign(firstItem || {}, {
      rule_code: 'LX0609-002',
      rule_name: '首次病程：入院后 8 小时内无首次病程记录',
      status: 'compliant',
      result_status: 'compliant',
      is_compliant: true,
      findings: '首次病程记录已在入院后8小时内完成。',
      evidence:
        '执行证据：入院时间：2026-06-01 08:00:00；首次病程记录记录时间：2026-06-01 10:30:00；间隔：2.5小时',
    })
    const secondItem = props.batchJobDetail.rule_results?.[1]?.items?.[0]
    Object.assign(secondItem || {}, {
      rule_code: 'LX0609-041',
      rule_name: '输血知情同意书：无输血知情同意书',
      status: 'not_applicable',
      result_status: 'not_applicable',
      is_compliant: true,
      findings: '未发现本次住院发生输血相关事件。',
      evidence: '判定依据：未发现本次住院存在输血医嘱、输血申请、输血记录或血制品收费。',
    })

    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props,
      global: {
        stubs: drawerStubs,
      },
    })

    const text = wrapper.text()
    expect(text).toContain('当前没有需要复核或整改的问题项')
    expect(text).toContain('未提示问题的依据')
    expect(text).toContain('未发现问题依据')
    expect(text).toContain('首次病程记录记录时间：2026-06-01 10:30:00')
    expect(text).toContain('不适用依据')
    expect(text).toContain('未发现本次住院存在输血医嘱')
  })

  it('客户结果卡不应暴露内部触发状态，应优先展示执行证据', async () => {
    const props = buildProps()
    const firstItem = props.batchJobDetail.rule_results?.[0]?.items?.[0]
    Object.assign(firstItem || {}, {
      rule_code: 'LX0609-002',
      rule_name: '首次病程：入院后 8 小时内无首次病程记录',
      status: 'non_compliant',
      result_status: 'non_compliant',
      findings: 'LLM 返回非结构化结果，请查看原始输出。首次病程记录未在入院后8小时内完成。',
      suggestion: '请查看原始输出后人工复核。',
      evidence:
        '来源未标注 · evidence：' +
        '证据模板：时限类 质控点：LX0609-002 首次病程：入院后 8 小时内无首次病程记录 ' +
        'trigger_status: unknown ' +
        '触发状态：unknown 触发说明：未识别到可安全门控的触发族，进入常规执行 ' +
        '映射执行规则：CL-081、SC-021 应包含证据要素：触发时间、截止时间、实际记录时间、超时或缺失结论、来源文书/表字段 ' +
        '执行证据：入院时间：2026-06-01 08:00:00；2026-06-01 首次病程记录记录时间：2026-06-01 19:00:00；间隔：11.0小时',
    })

    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props,
      global: {
        stubs: drawerStubs,
      },
    })

    const issueCard = wrapper.findAll('.issue-conclusion-card')[0]
    expect(issueCard?.text()).toContain('入院时间：2026-06-01 08:00:00')
    expect(issueCard?.text()).toContain('间隔：11.0小时')
    expect(issueCard?.text()).toContain('结合原文确认')
    expect(issueCard?.text()).not.toContain('人工复核')
    expect(issueCard?.text()).not.toContain('人工核对')
    expect(issueCard?.text()).not.toContain('触发状态')
    expect(issueCard?.text()).not.toContain('触发说明')
    expect(issueCard?.text()).not.toContain('unknown')
    expect(issueCard?.text()).not.toContain('来源未标注')
    expect(issueCard?.text()).not.toContain('evidence')
    expect(issueCard?.text()).not.toContain('LLM')
    expect(issueCard?.text()).not.toContain('原始输出')

    const expandButton = issueCard
      ?.findAll('button')
      .find((button) => button.text().includes('展开完整说明'))
    expect(expandButton).toBeTruthy()
    await expandButton?.trigger('click')
    await wrapper.vm.$nextTick()

    expect(issueCard?.text()).toContain('首次病程记录记录时间：2026-06-01 19:00:00')
    expect(issueCard?.text()).not.toContain('映射执行规则')
    expect(issueCard?.text()).not.toContain('应包含证据要素')
    expect(issueCard?.text()).not.toContain('证据模板')
    expect(issueCard?.text()).not.toContain('trigger_status')
    expect(issueCard?.text()).not.toContain('来源未标注')
    expect(issueCard?.text()).not.toContain('evidence')
    expect(issueCard?.text()).not.toContain('LLM')
    expect(issueCard?.text()).not.toContain('原始输出')
  })

  it('稳定查房结果不应把病危病重门控线索展示为关键证据', () => {
    const props = buildProps()
    const firstItem = props.batchJobDetail.rule_results?.[0]?.items?.[0]
    Object.assign(firstItem || {}, {
      rule_code: 'LX0609-007',
      rule_name: '查房记录：病情稳定患者3天内无查房病程记录',
      status: 'non_compliant',
      result_status: 'non_compliant',
      evidence:
        '证据模板：通用质控 质控点：LX0609-007 查房记录：病情稳定患者3天内无查房病程记录 ' +
        '判定依据：已发现相关事件，进入规则复核。 来源线索：病危、危重 ' +
        '执行证据：【日常病程记录】今日查房,患者一般情况可,咳嗽、呼吸困难好转,无咯血、发热',
    })

    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props,
      global: {
        stubs: drawerStubs,
      },
    })

    const issueCard = wrapper.findAll('.issue-conclusion-card')[0]
    expect(issueCard?.text()).toContain('【日常病程记录】今日查房')
    expect(issueCard?.text()).not.toContain('来源线索')
    expect(issueCard?.text()).not.toContain('病危、危重')
    expect(issueCard?.text()).not.toContain('已发现相关事件，进入规则复核')
  })

  it('客户结果卡应优先展示清洗后的完整执行证据，而不是过短的结构化片段', () => {
    const props = buildProps()
    const firstItem = props.batchJobDetail.rule_results?.[0]?.items?.[0]
    Object.assign(firstItem || {}, {
      rule_code: 'LX0609-002',
      rule_name: '首次病程：入院后 8 小时内无首次病程记录',
      status: 'non_compliant',
      result_status: 'non_compliant',
      findings: '首次病程记录未在入院后8小时内完成。',
      evidence:
        '证据模板：时限类\n' +
        '映射执行规则：CL-081、SC-021\n' +
        '执行证据：入院时间：2026-02-02 10:07:26；首次病程记录记录时间：2026-02-09 09:34:44；间隔：167.5小时',
      evidence_items: [
        {
          evidence_id: 'E-001',
          source_document_type: '首次病程记录',
          field_path: 'authored_at',
          quote: '首次病程记录记录时间：2026-02-09 09:34:44',
        },
      ],
    })

    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props,
      global: {
        stubs: drawerStubs,
      },
    })

    const issueCard = wrapper.findAll('.issue-conclusion-card')[0]
    const evidenceFacts = issueCard?.findAll('.issue-evidence-fact') || []
    expect(evidenceFacts.length).toBeGreaterThanOrEqual(3)
    expect(evidenceFacts[0]?.text()).toContain('入院时间')
    expect(evidenceFacts[1]?.text()).toContain('首次病程记录记录时间')
    expect(evidenceFacts[2]?.text()).toContain('间隔')
    expect(issueCard?.text()).toContain('2026-02-02 10:07:26')
    expect(issueCard?.text()).toContain('间隔：167.5小时')
    expect(issueCard?.text()).not.toContain('证据模板')
    expect(issueCard?.text()).not.toContain('映射执行规则')
  })

  it('data_gap 结果摘要应展示数据缺口，不应展示门控关键词', () => {
    const props = buildProps()
    props.batchJobDetail.rule_set_key = 'luxian_0609_qc_v1'
    const firstItem = props.batchJobDetail.rule_results?.[0]?.items?.[0]
    Object.assign(firstItem || {}, {
      rule_code: 'LX0609-013',
      rule_id: 'LX0609-013',
      qc_point_id: 'LX0609-013',
      customer_rule_id: 'LX0609-013',
      rule_set_key: 'luxian_0609_qc_v1',
      rule_name: '病理检查：病理检查结果在手术记录、病程中未记录',
      status: 'data_gap',
      result_status: 'data_gap',
      display_status: 'data_quality_gap',
      is_compliant: false,
      defect_level: '轻微缺陷',
      findings: '已发现触发事件，但缺少病理报告时间，无法完成自动判定。',
      evidence:
        '触发门控：已发现触发事实，但缺少完成判定所需的结构化字段 ' +
        '匹配关键词：手术记录、术前讨论、麻醉记录、安全核查、切口、术后 ' +
        '数据缺口：病理报告时间',
    })

    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props,
      global: {
        stubs: drawerStubs,
      },
    })

    const issueCard = wrapper
      .findAll('.issue-conclusion-card')
      .find((card) => card.text().includes('缺少病理报告时间'))
    expect(issueCard).toBeTruthy()
    expect(issueCard?.text()).toContain('缺少病理报告时间')
    expect(issueCard?.text()).toContain('数据不足，需补充资料')
    expect(issueCard?.text()).not.toContain('轻微缺陷')
    expect(issueCard?.text()).not.toContain('触发门控')
    expect(issueCard?.text()).not.toContain('匹配关键词')
    expect(issueCard?.text()).not.toContain('安全核查')
  })

  it('客户质控点结果应优先展示确定不合规，数据不足和 AI 判断排在后面', async () => {
    const props = buildProps()
    props.batchJobDetail.status = 'completed'
    props.batchJobDetail.rule_set_key = 'luxian_0609_qc_v1'
    props.batchJobDetail.rule_results = [
      {
        id: 'rule-job-lx',
        rule_code: 'LX0609',
        rule_name: '泸县0609质控点验证',
        status: 'completed',
        items: [
          {
            rule_job_id: 'rule-job-lx',
            rule_id: 'LX0609-016',
            rule_code: 'LX0609-016',
            rule_name: '不合理复制病历：首次病程记录与入院记录完全相同',
            record_id: '2265389',
            status: 'data_gap',
            result_status: 'data_gap',
            is_compliant: false,
            findings: '首次病程记录缺失或正文为空，无法判断是否存在复制病历内容。',
          },
          {
            rule_job_id: 'rule-job-lx',
            rule_id: 'LX0609-017',
            rule_code: 'LX0609-017',
            rule_name: '不合理复制病历：2次以上病程记录完全相同',
            record_id: '2265389',
            status: 'uncertain',
            result_status: 'uncertain',
            is_compliant: false,
            findings: '病程记录重复度未形成可靠自动结论，需人工复核。',
          },
          {
            rule_job_id: 'rule-job-lx',
            rule_id: 'LX0609-007',
            rule_code: 'LX0609-007',
            rule_name: '查房记录：病情稳定患者3天内无查房病程记录',
            record_id: '2265389',
            status: 'non_compliant',
            result_status: 'non_compliant',
            is_compliant: false,
            findings: '病情稳定患者相邻病程或查房记录间隔超过3天。',
          },
        ],
      },
    ]

    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props,
      global: {
        stubs: drawerStubs,
      },
    })

    const navItems = wrapper.findAll('.issue-review-nav-item')
    expect(navItems).toHaveLength(3)
    expect(navItems[0]?.text()).toContain('LX0609-007')
    expect(navItems[0]?.text()).toContain('确定问题')
    expect(navItems[1]?.text()).toContain('LX0609-016')
    expect(navItems[1]?.text()).toContain('数据不足')
    expect(navItems[2]?.text()).toContain('LX0609-017')
    expect(navItems[2]?.text()).toContain('AI判断')

    let cards = wrapper.findAll('.issue-conclusion-card')
    expect(cards).toHaveLength(1)
    expect(cards[0]?.text()).toContain('LX0609-007')
    expect(cards[0]?.classes()).toContain('issue-conclusion-card--danger')

    await navItems[1]?.trigger('click')
    await wrapper.vm.$nextTick()
    cards = wrapper.findAll('.issue-conclusion-card')
    expect(cards).toHaveLength(1)
    expect(cards[0]?.text()).toContain('LX0609-016')
    expect(cards[0]?.text()).toContain('数据不足')
    expect(cards[0]?.classes()).toContain('issue-conclusion-card--warning')

    await navItems[2]?.trigger('click')
    await wrapper.vm.$nextTick()
    cards = wrapper.findAll('.issue-conclusion-card')
    expect(cards).toHaveLength(1)
    expect(cards[0]?.text()).toContain('LX0609-017')
    expect(cards[0]?.text()).toContain('AI判断')
    expect(cards[0]?.text()).not.toContain('人工复核')
    expect(cards[0]?.classes()).toContain('issue-conclusion-card--warning')
  })

  it('LX0609 客户结果只展示安全病历引用并按规范状态分桶', async () => {
    const props = buildProps()
    props.batchJobDetail.status = 'completed'
    props.batchJobDetail.rule_set_key = 'luxian_0609_qc_v1'
    const unsafeRecordId = 'RAW-RECORD-LEAK-0609'
    const unsafeVisitId = 'RAW-VISIT-LEAK-0609'
    const unsafePatientName = '原始患者姓名泄漏'
    const unsafeDepartment = '原始科室泄漏'
    const safeRecordRef = 'case-7d36f8a1'
    props.batchJobDetail.rule_results = [
      {
        id: 'rule-job-lx-safe',
        rule_code: 'LX0609',
        rule_name: '泸县0609质控点验证',
        status: 'completed',
        items: [
          Object.assign(
            {
              rule_job_id: 'rule-job-lx-safe',
              rule_id: 'LX0609-021',
              rule_code: 'LX0609-021',
              rule_name: '会诊申请目的完整性',
              record_id: unsafeRecordId,
              visit_id: unsafeVisitId,
              patient_name: unsafePatientName,
              department: unsafeDepartment,
              status: 'non_compliant',
              result_status: 'non_compliant',
              is_compliant: false,
              findings: '会诊申请目的缺失。',
            },
            {
              record_ref: safeRecordRef,
              canonical_status: 'ai_suggested_non_compliant',
              reason_code: 'consultation_application_needs_review',
            },
          ),
          Object.assign(
            {
              rule_job_id: 'rule-job-lx-safe',
              rule_id: 'LX0609-029',
              rule_code: 'LX0609-029',
              rule_name: '术前小结完整性',
              record_id: unsafeRecordId,
              visit_id: unsafeVisitId,
              patient_name: unsafePatientName,
              department: unsafeDepartment,
              status: 'non_compliant',
              result_status: 'non_compliant',
              is_compliant: false,
              findings: '术前小结来源未同步。',
            },
            {
              record_ref: safeRecordRef,
              canonical_status: 'data_gap',
              reason_code: 'source_unavailable',
            },
          ),
          Object.assign(
            {
              rule_job_id: 'rule-job-lx-safe',
              rule_id: 'LX0609-033',
              rule_code: 'LX0609-033',
              rule_name: '手术知情同意书完整性',
              record_id: unsafeRecordId,
              visit_id: unsafeVisitId,
              patient_name: unsafePatientName,
              department: unsafeDepartment,
              status: 'non_compliant',
              result_status: 'non_compliant',
              is_compliant: false,
              findings: '来源读取异常。',
            },
            {
              record_ref: safeRecordRef,
              canonical_status: 'technical_error',
              reason_code: 'source_query_failed',
            },
          ),
        ],
      },
    ]
    props.batchJobDetail.items = [
      Object.assign(
        {
          rule_job_id: 'rule-job-lx-safe',
          rule_id: 'LX0609-021',
          rule_code: 'LX0609-021',
          rule_name: '会诊申请目的完整性',
          status: 'ai_suggested_non_compliant',
          is_compliant: false,
          conclusion: '会诊申请目的需质控员确认。',
          findings: 'RAW-INTERNAL-FINDINGS-021',
          evidence: [
            {
              source_type: 'consultation_record',
              source_ref: 'doc-3fa891',
            },
            {
              source_type: 'death_record',
              source_ref: 'doc-death-051',
            },
            {
              source_type: 'death_discussion',
              source_ref: 'doc-discussion-051',
            },
            {
              source_type: 'senior_course_record',
              source_ref: 'doc-senior-067',
            },
            {
              source_type: 'handoff_record',
              source_ref: 'doc-handoff-071',
            },
            {
              source_type: 'handover_record',
              source_ref: 'doc-handover-071',
            },
          ],
        },
        {
          record_ref: safeRecordRef,
          reason_code: 'consultation_application_needs_review',
        },
      ),
      Object.assign(
        {
          rule_job_id: 'rule-job-lx-safe',
          rule_id: 'LX0609-029',
          rule_code: 'LX0609-029',
          rule_name: '术前小结完整性',
          status: 'data_gap',
          is_compliant: false,
          conclusion: '术前小结来源尚未同步。',
          evidence: [
            {
              source_type: 'presurg_summary',
              source_ref: 'doc-7a102b',
            },
          ],
        },
        {
          record_ref: safeRecordRef,
          reason_code: 'source_unavailable',
        },
      ),
      Object.assign(
        {
          rule_job_id: 'rule-job-lx-safe',
          rule_id: 'LX0609-033',
          rule_code: 'LX0609-033',
          rule_name: '手术知情同意书完整性',
          status: 'technical_error',
          is_compliant: false,
          conclusion: '手术知情同意书来源读取异常。',
          evidence: [
            {
              source_type: 'surgery_inform_consent',
              source_ref: 'doc-88bc20',
            },
          ],
        },
        {
          record_ref: safeRecordRef,
          reason_code: 'source_query_failed',
        },
      ),
    ]
    Object.assign(props.batchJobDetail.summary!, {
      review_report: {
        review_status: 'completed',
        summary: { total_findings: 1, p0: 0, p1: 1, p2: 0 },
        findings: [
          Object.assign(
            {
              id: 'review-safe-1',
              rule_id: 'LX0609-021',
              record_id: unsafeRecordId,
              patient_name: unsafePatientName,
              department: unsafeDepartment,
              severity: 'P1',
              customer_message: '建议复核会诊申请目的。',
            },
            {
              record_ref: safeRecordRef,
              reason_code: 'consultation_application_needs_review',
            },
          ),
        ],
      },
    })

    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props: {
        ...props,
        focusRecordId: unsafeRecordId,
        focusVisitId: unsafeVisitId,
        focusRecordLabel: unsafePatientName,
      },
      global: {
        stubs: drawerStubs,
      },
    })

    expect(wrapper.text()).toContain(safeRecordRef)
    expect(wrapper.text()).not.toContain(unsafeRecordId)
    expect(wrapper.text()).not.toContain(unsafeVisitId)
    expect(wrapper.text()).not.toContain(unsafePatientName)
    expect(wrapper.text()).not.toContain(unsafeDepartment)
    const navItems = wrapper.findAll('.issue-review-nav-item')
    expect(navItems).toHaveLength(3)
    expect(navItems.some((item) => item.text().includes('AI判断'))).toBe(true)
    expect(navItems.some((item) => item.text().includes('数据不足'))).toBe(true)
    expect(navItems.some((item) => item.text().includes('技术异常'))).toBe(true)
    expect(wrapper.text()).not.toContain('确定问题')
    const lx021Nav = navItems.find((item) => item.text().includes('LX0609-021'))
    expect(lx021Nav).toBeTruthy()
    await lx021Nav!.trigger('click')
    expect(wrapper.text()).toContain('会诊申请目的需质控员确认。')
    expect(wrapper.text()).toContain('判定依据：会诊申请目的需复核')
    expect(wrapper.text()).toContain('会诊记录 · doc-3fa891')
    expect(wrapper.text()).toContain('死亡记录 · doc-death-051')
    expect(wrapper.text()).toContain('死亡病历讨论记录 · doc-discussion-051')
    expect(wrapper.text()).toContain('上级医师查房记录 · doc-senior-067')
    expect(wrapper.text()).toContain('交班记录 · doc-handoff-071')
    expect(wrapper.text()).toContain('接班记录 · doc-handover-071')
    expect(wrapper.text()).not.toContain('未返回结论')
    expect(wrapper.text()).not.toContain('RAW-INTERNAL-FINDINGS-021')
  })

  it('单病历聚焦时应按 record_ref 过滤顶层结果，不能串用其他病历结果', () => {
    const props = buildProps()
    props.batchJobDetail.status = 'completed'
    props.batchJobDetail.rule_set_key = 'luxian_0609_qc_v1'
    props.batchJobDetail.items = [
      {
        rule_job_id: 'rule-job-a',
        rule_id: 'LX0609-025',
        rule_code: 'LX0609-025',
        rule_name: '植入物信息完整性',
        record_ref: 'case-A',
        status: 'non_compliant',
        canonical_status: 'non_compliant',
        is_compliant: false,
        conclusion: 'case-A 的植入物信息缺失。',
        findings: 'case-A 不应显示',
      },
      {
        rule_job_id: 'rule-job-b',
        rule_id: 'LX0609-018',
        rule_code: 'LX0609-018',
        rule_name: '主诉能导出第一诊断',
        record_ref: 'case-B',
        status: 'non_compliant',
        canonical_status: 'non_compliant',
        is_compliant: false,
        conclusion: 'case-B 的主诉长度不足。',
        findings: 'case-B 应显示',
      },
    ]

    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props: {
        ...props,
        focusRecordRef: 'case-B',
        focusRecordLabel: '病历 case-B',
      },
      global: {
        stubs: drawerStubs,
      },
    })

    const text = wrapper.text()
    expect(text).toContain('case-B')
    expect(text).toContain('LX0609-018')
    expect(text).toContain('case-B 的主诉长度不足')
    expect(text).not.toContain('LX0609-025')
    expect(text).not.toContain('case-A 的植入物信息缺失')
    expect(text).not.toContain('case-A 不应显示')
  })

  it('LX0609-018 已提供受控展示事实时，应展示可读判定明细而非通用话术', () => {
    const props = buildProps()
    props.batchJobDetail.status = 'completed'
    props.batchJobDetail.rule_set_key = 'luxian_0609_qc_v1'
    props.batchJobDetail.rule_results = [
      {
        id: 'rule-job-lx-018',
        rule_code: 'LX0609-018',
        rule_name: '主诉能导出第一诊断',
        status: 'completed',
        items: [
          {
            rule_job_id: 'rule-job-lx-018',
            rule_id: 'LX0609-018',
            rule_code: 'LX0609-018',
            rule_name: '主诉能导出第一诊断',
            record_id: 'record-018',
            status: 'non_compliant',
            result_status: 'non_compliant',
            is_compliant: false,
            findings: '规则要求未满足。',
            reason_code: 'threshold_exceeded',
            customer_display_facts: {
              complaint_length: 21,
              length_state: 'violated',
              primary_diagnosis_available: true,
              diagnostic_relation_state: 'supported',
              diagnostic_reason_dimensions: ['anatomic_site', 'symptom_pattern'],
              source_label: '入院记录—主诉',
            },
          },
        ],
      },
    ]

    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props: {
        ...props,
        focusRecordId: 'record-018',
      },
      global: { stubs: drawerStubs },
    })

    expect(wrapper.text()).toContain('主诉超过20字上限；诊断指向子项通过。')
    expect(wrapper.text()).toContain('主诉共21字，超过20字上限。')
    expect(wrapper.text()).toContain('诊断指向子项通过')
    expect(wrapper.text()).toContain('实际值：21字')
    expect(wrapper.text()).toContain('入院记录—主诉')
    expect(wrapper.text()).not.toContain('规则要求未满足。')
  })

  it('复制病历结果应展示左右对比证据', () => {
    const props = buildProps()
    const firstItem = props.batchJobDetail.rule_results?.[0]?.items?.[0]
    Object.assign(firstItem || {}, {
      rule_code: 'LX0609-016',
      rule_name: '不合理复制病历：首次病程记录病例特点与入院记录、现病史完全相同',
      status: 'non_compliant',
      result_status: 'non_compliant',
      findings: '首次病程记录与入院记录存在高度重复。',
      evidence_items: [
        {
          evidence_id: 'COPY-PAIR-1-PREVIOUS',
          source_document_type: '入院记录',
          field_path: '现病史',
          quote: '患者腰背部疼痛伴活动受限3天，夜间疼痛明显。',
          evidence_role: 'copy_compare_previous_pair',
          actual_value: '片段相似度 0.96',
        },
        {
          evidence_id: 'COPY-PAIR-1-CURRENT',
          source_document_type: '首次病程记录',
          field_path: '病例特点',
          quote: '患者腰背部疼痛伴活动受限3天，夜间疼痛明显。',
          evidence_role: 'copy_compare_current_pair',
          actual_value: '片段相似度 0.96',
        },
        {
          evidence_id: 'COPY-PAIR-2-PREVIOUS',
          source_document_type: '入院记录',
          field_path: '现病史',
          quote: '入院后继续完善检查，暂予止痛及营养神经治疗。',
          evidence_role: 'copy_compare_previous_pair',
        },
        {
          evidence_id: 'COPY-PAIR-2-CURRENT',
          source_document_type: '首次病程记录',
          field_path: '病例特点',
          quote: '入院后继续完善检查，暂予止痛及营养神经治疗。',
          evidence_role: 'copy_compare_current_pair',
        },
        {
          evidence_id: 'COPY-METRIC',
          source_document_type: '复制病历比对指标',
          field_path: '重复度判定',
          quote: '全文相似度 0.94；句子覆盖率 0.91。',
          evidence_role: 'copy_similarity_metric',
        },
        {
          evidence_id: 'COPY-MISSING-DIFFERENCE',
          source_document_type: '差异不足说明',
          field_path: '缺少差异说明',
          quote: '未见本次记录相较前次记录补充明确病情变化、诊疗分析或后续计划调整。',
          evidence_role: 'copy_missing_difference',
        },
      ],
    })

    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props,
      global: {
        stubs: drawerStubs,
      },
    })

    const compare = wrapper.find('.copy-evidence-compare')
    expect(compare.exists()).toBe(true)
    expect(compare.text()).toContain('入院记录')
    expect(compare.text()).toContain('首次病程记录')
    expect(compare.text()).toContain('患者腰背部疼痛伴活动受限3天')
    expect(compare.text()).toContain('重复片段 1')
    expect(compare.text()).toContain('重复片段 2')
    expect(compare.text()).toContain('全文相似度 0.94')
    expect(compare.text()).toContain('缺少差异说明')
  })

  it('旧复制病历结果只有单组片段时应提示重新质控，不再渲染成完整对照', () => {
    const props = buildProps()
    const firstItem = props.batchJobDetail.rule_results?.[0]?.items?.[0]
    Object.assign(firstItem || {}, {
      rule_code: 'LX0609-017',
      rule_name: '不合理复制病历：2次以上病程记录完全相同',
      status: 'non_compliant',
      result_status: 'non_compliant',
      findings: '两份病程记录高度相似。',
      evidence_items: [
        {
          evidence_id: 'COPY-PREVIOUS',
          source_document_type: '上级医师查房记录',
          field_path: '前次病程/查房片段',
          quote: '今日郑瑞清副主任医师代主治医师查房：患者为37岁男性，起病急，病程短',
          evidence_role: 'source_previous_snippet',
        },
        {
          evidence_id: 'COPY-CURRENT',
          source_document_type: '上级医师查房记录',
          field_path: '本次病程/查房片段',
          quote: '今日郑瑞清副主任医师代主治医师查房：患者为37岁男性，起病急，病程短',
          evidence_role: 'target_current_snippet',
        },
        {
          evidence_id: 'COPY-METRIC',
          source_document_type: '复制病历比对指标',
          field_path: '重复度判定',
          quote: '两份病程记录全文相似度 0.64，本次记录被前次记录覆盖率 0.94。',
          evidence_role: 'copy_similarity_metric',
        },
      ],
    })

    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props,
      global: {
        stubs: drawerStubs,
      },
    })

    const compare = wrapper.find('.copy-evidence-compare')
    expect(compare.exists()).toBe(true)
    expect(compare.text()).toContain('当前任务结果只保存了单组对照片段')
    expect(compare.findAll('.copy-evidence-pair')).toHaveLength(0)
    expect(
      compare.findAll(
        '.copy-evidence-column:not(.copy-evidence-column--metric):not(.copy-evidence-column--gap)',
      ),
    ).toHaveLength(0)
    expect(compare.text()).toContain('全文相似度 0.64')
  })

  it('运行中暂无返回结果时应展示等待首份病历的动态提示', () => {
    const props = buildProps()
    if (props.batchJobDetail.summary) {
      props.batchJobDetail.summary.stream_state = {
        enabled: true,
        processed_records: 0,
        total_records: 3,
        latest_result_count: 0,
        partial_item_count: 0,
        updated_at: '2026-04-13T12:01:00Z',
      }
    }
    props.batchJobDetail.total_records = 3
    props.batchJobDetail.success_count = 0
    props.batchJobDetail.issue_records = 0
    props.batchJobDetail.items = []
    props.batchJobDetail.rule_results = (props.batchJobDetail.rule_results || []).map((rule) => ({
      ...rule,
      items: [],
      issue_records: 0,
      success_count: 0,
    }))

    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props,
      global: {
        stubs: drawerStubs,
      },
    })

    expect(wrapper.text()).toContain('正在等待首份病历结果')
    expect(wrapper.text()).toContain('模型仍在处理首份病历，结果会自动出现在这里')
    expect(wrapper.find('.stream-waiting-card').exists()).toBe(true)
  })

  it('运行中已有部分结果时应立即展示结果卡并提示后续会追加', async () => {
    const props = buildProps()
    if (props.batchJobDetail.summary) {
      props.batchJobDetail.summary.stream_state = {
        enabled: true,
        processed_records: 1,
        total_records: 3,
        latest_record_id: 'record-1',
        latest_visit_id: 'V001',
        latest_result_count: 2,
        partial_item_count: 2,
        updated_at: '2026-04-13T12:02:00Z',
      }
    }
    props.batchJobDetail.total_records = 3

    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props,
      global: {
        stubs: drawerStubs,
      },
    })

    expect(wrapper.text()).toContain('已返回 2 条结果，任务仍在继续')
    expect(wrapper.text()).toContain('正在分析：V001')
    expect(wrapper.findAll('.issue-conclusion-card')).toHaveLength(1)

    const allRecordButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('全部病历'))
    expect(allRecordButton).toBeTruthy()
    await allRecordButton?.trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.findAll('.issue-conclusion-card')).toHaveLength(2)
  })

  it('应按证据链展示泸县0609结果的触发事实、依赖数据和关键证据', async () => {
    const props = buildProps()
    const firstItem = props.batchJobDetail.rule_results?.[0]?.items?.[0]
    Object.assign(firstItem || {}, {
      qc_point_id: 'LX0609-014',
      rule_set_key: 'luxian_0609_qc_v1',
      schema_version: 'luxian_0609_evidence_chain_v1',
      result_status: 'non_compliant',
      executor_type: 'llm',
      trigger: {
        applicable: true,
        trigger_facts: [
          {
            fact_label: '阳性培养报告',
            fact_value: '尿培养报告阳性',
            source_document_type: '检验报告',
            record_time: '2026-06-03 14:20',
          },
        ],
      },
      dependencies: {
        required_sources: [{ source_name: '检验报告' }, { source_name: '病程记录' }],
        missing_sources: [{ source_name: '24小时内病程分析' }],
        source_coverage_level: 'partial',
      },
      evidence_items: [
        {
          evidence_id: 'E-001',
          source_document_type: '日常病程记录',
          record_time: '2026-06-04 09:10',
          field_path: 'daily_course_record.record_content',
          quote: '病程记录未分析尿培养阳性结果与抗感染方案关系。',
        },
      ],
      decision: {
        decision_summary: '细菌培养阳性结果未在病程中及时分析。',
        threshold: '报告后24小时内完成分析',
        actual_value: '未见分析记录',
        suggestion: '补充阳性培养结果与诊疗方案关系分析。',
      },
    })

    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props,
      global: {
        stubs: drawerStubs,
      },
    })

    expect(wrapper.text()).toContain('状态口径：不合规')
    expect(wrapper.text()).toContain('触发事实 1 条')
    expect(wrapper.text()).toContain('缺少数据 1 项')

    const expandButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('展开完整说明'))
    expect(expandButton).toBeTruthy()
    await expandButton?.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('证据链')
    expect(wrapper.text()).toContain('阳性培养报告')
    expect(wrapper.text()).toContain('尿培养报告阳性')
    expect(wrapper.text()).toContain('缺失数据')
    expect(wrapper.text()).toContain('24小时内病程分析')
    expect(wrapper.text()).toContain('日常病程记录')
    expect(wrapper.text()).toContain('病程记录未分析尿培养阳性结果与抗感染方案关系')
    expect(wrapper.text()).toContain('报告后24小时内完成分析')
  })

  it('应在结果卡片摘要中展示多条关键原文证据', () => {
    const props = buildProps()
    const firstItem = props.batchJobDetail.rule_results?.[0]?.items?.[0]
    Object.assign(firstItem || {}, {
      rule_code: 'LX0609-026',
      rule_name: '化疗记录：病程中化学治疗记录情况与医嘱不一致',
      qc_point_id: 'LX0609-026',
      rule_set_key: 'luxian_0609_qc_v1',
      schema_version: 'luxian_0609_evidence_chain_v1',
      result_status: 'non_compliant',
      status: 'non_compliant',
      findings: '化疗医嘱已开具具体药物、剂量、用法和时间，但病程记录仅泛化描述辅助化疗。',
      evidence_items: [
        {
          evidence_id: 'E-001',
          source_document_type: '化疗医嘱',
          field_path: '化疗医嘱',
          quote: '长期医嘱：奥沙利铂 130mg d1 静脉滴注；卡培他滨 1.5g bid po d1-d14。',
        },
        {
          evidence_id: 'E-002',
          source_document_type: '化疗前病程记录',
          field_path: '病程记录',
          quote: '今日准备开始辅助化疗，已交代可能出现恶心、呕吐等不良反应。',
        },
      ],
      decision: {
        decision_summary: '化疗医嘱与病程记录不一致。',
        suggestion: '在病程记录中补充化疗方案名称、药物名称、剂量、给药方式和时间。',
      },
    })

    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props,
      global: {
        stubs: drawerStubs,
      },
    })

    expect(wrapper.text()).toContain('奥沙利铂 130mg')
    expect(wrapper.text()).toContain('今日准备开始辅助化疗')
    expect(wrapper.text()).not.toContain('触发状态：unknown')
  })

  it('LX0609 单病历焦点下应汇总输血前评估、输血病程和输血后评价均已齐备', () => {
    const props = buildProps()
    props.batchJobDetail.status = 'completed'
    props.batchJobDetail.rule_set_key = 'luxian_0609_qc_v1'
    props.batchJobDetail.items = [
      {
        rule_id: 'LX0609-044',
        rule_code: 'LX0609-044',
        rule_name: '输血前评估记录',
        record_ref: 'case-A',
        status: 'compliant',
        canonical_status: 'compliant',
        is_compliant: true,
      },
      {
        rule_id: 'LX0609-045',
        rule_code: 'LX0609-045',
        rule_name: '输血病程记录',
        record_ref: 'case-A',
        status: 'compliant',
        canonical_status: 'compliant',
        is_compliant: true,
      },
      {
        rule_id: 'LX0609-047',
        rule_code: 'LX0609-047',
        rule_name: '输血后评价',
        record_ref: 'case-A',
        status: 'compliant',
        canonical_status: 'compliant',
        is_compliant: true,
      },
      {
        rule_id: 'LX0609-044',
        rule_code: 'LX0609-044',
        rule_name: '输血前评估记录',
        record_ref: 'case-B',
        status: 'data_gap',
        canonical_status: 'data_gap',
        is_compliant: false,
      },
    ]

    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props: { ...props, focusRecordRef: 'case-A' },
      global: { stubs: drawerStubs },
    })

    const summary = wrapper.find('[data-testid="transfusion-documentation-summary"]')
    expect(summary.exists()).toBe(true)
    expect(summary.text()).toContain('输血前评估、输血病程、输血后评价已齐备')
    expect(summary.text()).not.toContain('数据不足')
  })

  it('LX0609 输血三项汇总应仅使用当前焦点病例，并说明缺少的具体项目及状态', () => {
    const props = buildProps()
    props.batchJobDetail.status = 'completed'
    props.batchJobDetail.rule_set_key = 'luxian_0609_qc_v1'
    props.batchJobDetail.items = [
      {
        rule_id: 'LX0609-044',
        rule_code: 'LX0609-044',
        rule_name: '输血前评估记录',
        record_ref: 'case-B',
        status: 'non_compliant',
        canonical_status: 'non_compliant',
        is_compliant: false,
      },
      {
        rule_id: 'LX0609-045',
        rule_code: 'LX0609-045',
        rule_name: '输血病程记录',
        record_ref: 'case-B',
        status: 'data_gap',
        canonical_status: 'data_gap',
        is_compliant: false,
      },
      {
        rule_id: 'LX0609-047',
        rule_code: 'LX0609-047',
        rule_name: '输血后评价',
        record_ref: 'case-B',
        status: 'uncertain',
        canonical_status: 'uncertain',
        is_compliant: false,
      },
      {
        rule_id: 'LX0609-046',
        rule_code: 'LX0609-046',
        rule_name: '输血病程记录完整性',
        record_ref: 'case-B',
        status: 'non_compliant',
        canonical_status: 'non_compliant',
        is_compliant: false,
      },
    ]

    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props: { ...props, focusRecordRef: 'case-B' },
      global: { stubs: drawerStubs },
    })

    const summary = wrapper.find('[data-testid="transfusion-documentation-summary"]')
    expect(summary.exists()).toBe(true)
    expect(summary.text()).toContain('输血前评估：不合规')
    expect(summary.text()).toContain('输血病程：数据不足')
    expect(summary.text()).toContain('输血后评价：AI判断')
    expect(summary.text()).not.toContain('LX0609-046')
  })

  it('非LX0609任务不展示输血三项汇总', () => {
    const props = buildProps()
    props.batchJobDetail.items = [
      {
        rule_id: 'LX0609-044',
        rule_code: 'LX0609-044',
        record_ref: 'case-A',
        status: 'compliant',
        canonical_status: 'compliant',
        is_compliant: true,
      },
    ]

    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props: { ...props, focusRecordRef: 'case-A' },
      global: { stubs: drawerStubs },
    })

    expect(wrapper.find('[data-testid="transfusion-documentation-summary"]').exists()).toBe(false)
  })
})
