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
  setup(_, { slots }) {
    return () => h('div', { class: 'a-radio-group-stub' }, slots.default?.())
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
  'a-tag': ATagStub,
  'a-progress': AProgressStub,
  'a-radio-group': ARadioGroupStub,
  'a-radio-button': ARadioButtonStub,
  'a-switch': ASwitchStub,
  'a-input': AInputStub,
}

function buildProps() {
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
  it('应展示当前任务摘要中的病历级与规则级统计口径', () => {
    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props: buildProps(),
      global: {
        stubs: drawerStubs,
      },
    })

    expect(wrapper.text()).toContain('涉及问题病历')
    expect(wrapper.text()).toContain('病历级去重统计')
    expect(wrapper.text()).toContain('失败次数')
    expect(wrapper.text()).toContain('规则执行失败总次数')
  })

  it('按单规则筛选时应联动规则结果概览、命中明细并拉取调试快照', async () => {
    const props = buildProps()
    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props,
      global: {
        stubs: drawerStubs,
      },
    })

    await wrapper.find('.debug-rule-select.a-select-stub').setValue('rule-job-2')
    await flushPromises()
    await wrapper.vm.$nextTick()

    expect(props.fetchBatchJobDebugSnapshot).toHaveBeenCalledWith('job-1', {
      ruleJobId: 'rule-job-2',
    })

    const tables = wrapper.findAllComponents(ATableStub)
    const ruleOverviewData = tables[0]?.props('dataSource') as Array<{ id?: string }>
    const issueCards = wrapper.findAll('.issue-conclusion-card')

    expect(ruleOverviewData).toHaveLength(1)
    expect(ruleOverviewData[0]?.id).toBe('rule-job-2')
    expect(issueCards).toHaveLength(1)
    expect(issueCards[0]?.text()).toContain('SC-002 · 规则二')
    expect(issueCards[0]?.text()).toContain('规则二命中')
    expect(wrapper.text()).toContain('已按规则过滤：SC-002 · 规则二')
  })

  it('应保持任务统计摘要与问题明细数量一致', () => {
    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props: buildProps(),
      global: {
        stubs: drawerStubs,
      },
    })

    const issueCards = wrapper.findAll('.issue-conclusion-card')

    expect(issueCards).toHaveLength(2)
    expect(wrapper.text()).toContain('当前共 2 条重点结果，其中不合规 2 条，待复核 0 条')
    expect(wrapper.text()).toContain('重点结果')
    expect(wrapper.text()).toContain('涉及问题病历')
    expect(wrapper.text()).toContain('规则一命中')
    expect(wrapper.text()).toContain('规则二命中')
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
})
