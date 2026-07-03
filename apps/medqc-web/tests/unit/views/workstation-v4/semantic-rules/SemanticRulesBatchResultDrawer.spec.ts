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

  it('应展示当前任务摘要中的病历级与规则级统计口径', () => {
    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props: buildProps(),
      global: {
        stubs: drawerStubs,
      },
    })

    expect(wrapper.text()).toContain('总病历10')
    expect(wrapper.text()).toContain('不合规规则2')
    expect(wrapper.text()).toContain('待复核规则0')
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

    expect(wrapper.text()).toContain('按病历查看')
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
  })

  it('泸县0609任务即使带正式后处理字段，也应按客户质控点状态展示不合规', () => {
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
    expect(issueCard?.text()).not.toContain('触发门控')
    expect(issueCard?.text()).not.toContain('匹配关键词')
    expect(issueCard?.text()).not.toContain('安全核查')
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
          evidence_id: 'E-001',
          source_document_type: '入院记录',
          field_path: '现病史',
          quote: '患者腰背部疼痛伴活动受限3天，夜间疼痛明显。',
          evidence_role: 'source_admission_snippet',
        },
        {
          evidence_id: 'E-002',
          source_document_type: '首次病程记录',
          field_path: '病例特点',
          quote: '患者腰背部疼痛伴活动受限3天，夜间疼痛明显。',
          evidence_role: 'target_course_snippet',
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

  it('运行中已有部分结果时应立即展示结果卡并提示后续会追加', () => {
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
})
