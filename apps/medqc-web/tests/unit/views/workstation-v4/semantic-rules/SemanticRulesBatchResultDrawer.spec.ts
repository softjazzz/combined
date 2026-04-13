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
  setup(props, { emit }) {
    return () =>
      h(
        'select',
        {
          class: 'a-select-stub',
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
            status: 'issue',
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
            status: 'issue',
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
  it('应展示失败病历与失败次数两个不同统计口径', () => {
    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props: buildProps(),
      global: {
        stubs: {
          'a-drawer': ADrawerStub,
          'a-table': ATableStub,
          'a-select': ASelectStub,
          'a-button': AButtonStub,
          'a-tag': ATagStub,
        },
      },
    })

    expect(wrapper.text()).toContain('失败病历')
    expect(wrapper.text()).toContain('去重后的病历数')
    expect(wrapper.text()).toContain('失败次数')
    expect(wrapper.text()).toContain('规则执行失败总次数')
  })

  it('按单规则筛选时应联动规则结果概览、命中明细并拉取调试快照', async () => {
    const props = buildProps()
    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props,
      global: {
        stubs: {
          'a-drawer': ADrawerStub,
          'a-table': ATableStub,
          'a-select': ASelectStub,
          'a-button': AButtonStub,
          'a-tag': ATagStub,
        },
      },
    })

    await wrapper.find('.a-select-stub').setValue('rule-job-2')
    await flushPromises()
    await wrapper.vm.$nextTick()

    expect(props.fetchBatchJobDebugSnapshot).toHaveBeenCalledWith('job-1', {
      ruleJobId: 'rule-job-2',
    })

    const tables = wrapper.findAllComponents(ATableStub)
    const ruleOverviewData = tables[0]?.props('dataSource') as Array<{ id?: string }>
    const issueData = tables[1]?.props('dataSource') as Array<{ rule_job_id?: string }>

    expect(ruleOverviewData).toHaveLength(1)
    expect(ruleOverviewData[0]?.id).toBe('rule-job-2')
    expect(issueData).toHaveLength(1)
    expect(issueData[0]?.rule_job_id).toBe('rule-job-2')
    expect(wrapper.text()).toContain('已按规则过滤：SC-002 · 规则二')
  })
})
