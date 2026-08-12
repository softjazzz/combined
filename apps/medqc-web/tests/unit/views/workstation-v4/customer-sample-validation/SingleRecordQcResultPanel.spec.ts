import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import SingleRecordQcResultPanel from '@/views/workstation-v4/customer-sample-validation/SingleRecordQcResultPanel.vue'

const items = [
  {
    rule_id: 'LX0609-018',
    rule_name: '主诉能导出第一诊断',
    status: 'non_compliant',
    conclusion: '主诉共14字，未达到不超过20字的要求；诊断指向性未通过。',
    detail: '主诉仅描述症状，未提供支持第一诊断的特异性表现或病程线索。',
    actual: '主诉14字；第一诊断已找到。',
    standard: '主诉应不超过20字，且应能导出第一诊断。',
    suggestion: '补充诊断指向信息，并保留与第一诊断一致的主诉。',
    model_analysis: '医学分析：当前主诉缺少可区分第一诊断的特异性线索。',
    criterion_results: [
      {
        criterion_id: 'chief_complaint_length',
        kind: 'text_length',
        status: 'passed',
        reason_code: 'requirement_satisfied',
        actual_value: 14,
        expected_value: 20,
        operator: 'lte',
        unit: 'character',
      },
      {
        criterion_id: 'diagnostic_direction',
        kind: 'semantic_relation',
        status: 'failed',
        reason_code: 'complaint_primary_diagnosis_mismatch',
        medical_analysis: '主诉缺少区分第一诊断的特异性表现与病程线索。',
      },
    ],
    evidence: [
      {
        source_ref: 'src_admission_chief_complaint',
        source_type: 'admission_record',
        source_label: '入院记录—主诉',
        field_path: 'chief_complaint',
      },
    ],
  },
  {
    rule_id: 'LX0609-003',
    rule_name: '手术记录：手术后24小时内是否完成',
    status: 'not_applicable',
    conclusion: '本次住院未识别到已实施手术。',
  },
  {
    rule_id: 'LX0609-025',
    rule_name: '手术记录植入物信息完整性',
    status: 'non_compliant',
    conclusion: '发现该质控点对应的明确问题。',
    customer_display_facts: {
      failure_kind: 'implant_information_incomplete',
      source_label: '手术记录',
      missing_fields: ['implant_barcode', 'implant_quantity'],
    },
    evidence: [
      {
        source_ref: 'src_surgery_record',
        source_type: 'surgery_record',
      },
    ],
  },
]

const incompleteNonCompliantItem = {
  rule_id: 'LX0609-025',
  rule_name: '手术记录植入物信息完整性',
  status: 'non_compliant',
  conclusion: '发现该质控点对应的明确问题。',
}

const surgeryConsentMissingItem = {
  rule_id: 'LX0609-033',
  rule_name: '手术知情同意书：无手术知情同意书（有手术记录）',
  status: 'non_compliant',
  conclusion: '已确认实施手术，未检索到手术知情同意书。',
  customer_display_facts: {
    failure_kind: 'surgery_consent_document_missing',
    consent_state: 'missing',
    performed_surgery_confirmed: true,
  },
  evidence: [
    {
      source_ref: 'src_surgery_record_033',
      source_type: 'surgery_record',
      source_label: '手术记录',
    },
  ],
}

const surgeryConsentSignatureMissingItem = {
  ...surgeryConsentMissingItem,
  conclusion: '已确认实施手术，但手术知情同意书缺少术者签名。',
  customer_display_facts: {
    failure_kind: 'surgery_consent_signature_missing',
    consent_state: 'signature_missing',
    performed_surgery_confirmed: true,
    missing_signature_roles: ['surgeon'],
  },
}

const explainedCompliantItem = {
  rule_id: 'LX0609-008',
  rule_name: '病重患者查房记录',
  status: 'compliant',
  conclusion: '病重医嘱期间的查房记录频次符合要求。',
  actual: '已核对病重医嘱起始日与后续查房记录日期，最长间隔为2个自然日。',
  standard: '病重患者每2个自然日内应有至少一份日常病程或上级医师查房记录。',
  criterion_results: [
    {
      criterion_id: 'rounding_interval',
      kind: 'date_interval',
      status: 'passed',
      reason_code: 'requirement_satisfied',
      actual_value: '2个自然日',
      expected_value: '不超过2个自然日',
    },
  ],
  model_analysis: '已按病重医嘱后的时间轴逐段核对，未发现超过规则阈值的查房间隔。',
  suggestion: '无需处理。',
  evidence: [
    {
      source_ref: 'src_senior_round_008',
      source_type: 'senior_course_record',
      source_label: '上级医师查房记录',
      field_path: '记录时间',
    },
  ],
}

const historicalCompliantItem = {
  rule_id: 'LX0609-029',
  rule_name: '术前小结',
  status: 'compliant',
  conclusion: '未发现问题。',
}

const explainedDataGapItem = {
  rule_id: 'LX0609-011',
  rule_name: 'CT/MRI 报告后病程记录',
  status: 'data_gap',
  conclusion: '检查报告时间已返回，但缺少可用于时序核对的病程记录时间。',
  detail: '未返回检查报告出具后24小时内可核对的病程记录时间，无法完成时序判断。',
  actual: '已获取CT报告出具时间；后续病程文书的权威记录时间未返回。',
  standard: '需同时具备检查报告时间和后续病程记录时间，方可核对24小时内是否记录。',
  customer_display_facts: {
    checked_sources: ['exam_master', 'daily_course_record'],
    target_document: 'CT/MRI 检查报告',
  },
  data_gap_details: {
    reason_code: 'required_time_unavailable',
    missing_sources: ['daily_course_record'],
    missing_fields: ['daily_course_record.record_time'],
    required_sources: ['exam_master', 'daily_course_record'],
    unavailable_sources: ['daily_course_record'],
    availability: { exam_master: true, daily_course_record: false },
  },
  evidence: [
    {
      source_ref: 'src_ct_report_011',
      source_type: 'exam_master',
      source_label: 'CT/MRI 检查报告',
      field_path: 'report_time',
    },
  ],
}

describe('SingleRecordQcResultPanel', () => {
  it('默认以紧凑摘要展示，客户可明确展开和收起完整详情', async () => {
    const wrapper = mount(SingleRecordQcResultPanel, { props: { items: [items[0]!] } })
    const trigger = wrapper.get('[data-testid="single-record-result-toggle"]')
    const ruleName = wrapper.get('.rule-name')

    expect(trigger.attributes('aria-expanded')).toBe('false')
    expect(trigger.text()).not.toContain('查看详情')
    expect(trigger.text()).not.toContain('收起详情')
    expect(wrapper.text()).toContain(items[0]!.conclusion)
    expect(wrapper.find('.result-detail').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('完整判定说明')
    expect(wrapper.text()).not.toContain('关键证据')
    expect(wrapper.text()).not.toContain('处理建议')

    await ruleName.trigger('click')

    expect(trigger.attributes('aria-expanded')).toBe('true')
    expect(trigger.text()).not.toContain('收起详情')
    expect(wrapper.find('.result-detail').exists()).toBe(true)
    expect(wrapper.text()).toContain('完整判定说明')
    expect(wrapper.text()).toContain('关键证据')
    expect(wrapper.text()).toContain('处理建议')

    await ruleName.trigger('click')

    expect(trigger.attributes('aria-expanded')).toBe('false')
    expect(trigger.text()).not.toContain('查看详情')
    expect(wrapper.find('.result-detail').exists()).toBe(false)
  })

  it('直接展示 016 Canonical facts 中的实际相似度、阈值和比对范围', async () => {
    const wrapper = mount(SingleRecordQcResultPanel, {
      props: {
        items: [
          {
            rule_id: 'LX0609-016',
            rule_name: '不合理复制病历',
            status: 'non_compliant',
            conclusion: '入院记录与首次病程记录存在高度重复',
            customer_display_facts: {
              failure_kind: 'admission_first_course_copy_detected',
              copy_similarity: 1,
              copy_similarity_threshold: 0.7,
              compared_sections: ['入院记录现病史', '首次病程记录病例特点'],
            },
          },
        ],
      },
    })

    await wrapper.get('[data-testid="single-record-result-toggle"]').trigger('click')

    expect(wrapper.get('[data-testid="single-record-detail-grid"]').text()).toContain(
      '实际相似度100%',
    )
    expect(wrapper.get('[data-testid="single-record-detail-grid"]').text()).toContain('判定阈值70%')
    expect(wrapper.get('[data-testid="single-record-detail-grid"]').text()).toContain(
      '比对范围入院记录现病史、首次病程记录病例特点',
    )
    expect(wrapper.get('[data-testid="single-record-detail-grid"]').text()).not.toContain(
      '判定类型',
    )
    expect(wrapper.get('[data-testid="single-record-detail-grid"]').text()).toContain(
      '问题说明入院记录现病史与首次病程记录病例特点高度重复',
    )
  })

  it('将 017 的内部复制相似度原因码转换为客户可读结论', async () => {
    const wrapper = mount(SingleRecordQcResultPanel, {
      props: {
        items: [
          {
            rule_id: 'LX0609-017',
            rule_name: '不合理复制病历：2次以上病程记录完全相同（相似度大于70%）',
            status: 'non_compliant',
            conclusion: '两份日常病程记录全文相似度 100%，达到判定阈值 70%。',
            customer_display_facts: {
              failure_kind: 'copy_similarity_threshold_exceeded',
              copy_similarity: 1,
              copy_similarity_threshold: 0.7,
            },
          },
        ],
      },
    })

    await wrapper.get('[data-testid="single-record-result-toggle"]').trigger('click')

    const detail = wrapper.get('[data-testid="single-record-detail-grid"]').text()
    expect(detail).toContain('问题说明病程记录相似度达到判定阈值')
    expect(detail).toContain('实际相似度100%')
    expect(detail).toContain('判定阈值70%')
    expect(detail).not.toContain('copy_similarity_threshold_exceeded')
  })

  it('将 017 命中的多组病程配对按时间和相似度逐组展示', async () => {
    const wrapper = mount(SingleRecordQcResultPanel, {
      props: {
        items: [
          {
            rule_id: 'LX0609-017',
            rule_name: '不合理复制病历：2次以上病程记录完全相同（相似度大于70%）',
            status: 'non_compliant',
            conclusion: '最高相似度100%，另有3组病程记录达到判定阈值。',
            customer_display_facts: {
              failure_kind: 'copy_similarity_threshold_exceeded',
              copy_similarity: 1,
              copy_similarity_threshold: 0.7,
              copy_match_pairs: [
                {
                  source_types: ['daily_course_record', 'daily_course_record'],
                  record_times: ['2026-07-08 08:35:49', '2026-07-11 09:13:25'],
                  similarity: 1,
                },
                {
                  source_types: ['daily_course_record', 'senior_course_record'],
                  record_times: ['2026-07-08 08:35:49', '2026-07-12 09:05:00'],
                  similarity: 0.936,
                },
                {
                  source_types: ['daily_course_record', 'daily_course_record'],
                  record_times: ['2026-07-09 08:20:00', '2026-07-11 09:13:25'],
                  similarity: 0.812,
                },
                {
                  source_types: ['daily_course_record', 'daily_course_record'],
                  record_times: ['2026-07-10 08:10:00', '2026-07-13 09:00:00'],
                  similarity: 0.701,
                },
              ],
            },
          },
        ],
      },
    })

    await wrapper.get('[data-testid="single-record-result-toggle"]').trigger('click')

    const groups = wrapper.findAll('[data-testid="copy-match-pair"]')
    expect(groups).toHaveLength(4)
    expect(groups[0]?.text()).toContain('组合 1')
    expect(groups[0]?.text()).toContain('相似度 100%')
    expect(groups[0]?.text()).toContain('日常病程记录 · 2026-07-08 08:35:49')
    expect(groups[0]?.text()).toContain('日常病程记录 · 2026-07-11 09:13:25')
    expect(groups[1]?.text()).toContain('上级医师查房记录 · 2026-07-12 09:05:00')
    expect(groups[1]?.text()).toContain('相似度 93.6%')
    expect(wrapper.text()).not.toContain('[object Object]')
  })

  it('未知内部原因码没有客户文案时不在结果卡片中直接显示', async () => {
    const wrapper = mount(SingleRecordQcResultPanel, {
      props: {
        items: [
          {
            rule_id: 'LX0609-017',
            rule_name: '不合理复制病历',
            status: 'non_compliant',
            conclusion: '发现需要复核的病程记录相似内容。',
            customer_display_facts: {
              failure_kind: 'future_internal_failure_kind',
              copy_similarity: 0.8,
              copy_similarity_threshold: 0.7,
            },
          },
        ],
      },
    })

    await wrapper.get('[data-testid="single-record-result-toggle"]').trigger('click')

    const detail = wrapper.get('[data-testid="single-record-detail-grid"]').text()
    expect(detail).not.toContain('future_internal_failure_kind')
    expect(detail).not.toContain('问题说明')
    expect(detail).toContain('实际相似度80%')
    expect(detail).toContain('判定阈值70%')
  })

  it('按引擎返回顺序展示每条规则的状态、编号、标题和结论', () => {
    const wrapper = mount(SingleRecordQcResultPanel, { props: { items } })

    expect(wrapper.find('[data-testid="single-record-result-toolbar"]').exists()).toBe(true)
    expect(wrapper.find('.result-column-header').exists()).toBe(false)
    expect(wrapper.get('[data-testid="single-record-result-summary"]').text()).toContain(
      '3 个质控点 · 已执行 3',
    )
    const rows = wrapper.findAll('[data-testid="single-record-result-row"]')
    expect(rows).toHaveLength(3)
    expect(rows[0]!.get('[data-testid="single-record-result-row-header"]').text()).toContain(
      'LX0609-018',
    )
    expect(rows[0]!.get('.status-cell').text()).toContain('确定问题')
    expect(rows[0]!.get('.result-row-meta').text()).toContain('LX0609-018')
    expect(rows[0]!.get('[data-testid="single-record-result-conclusion"]').text()).toContain(
      '主诉共14字，未达到不超过20字的要求；诊断指向性未通过。',
    )
    expect(rows[1]!.text()).toContain('LX0609-003')
    expect(rows[2]!.text()).toContain('LX0609-025')
    expect(wrapper.text()).toContain('全部')
    expect(wrapper.text()).toContain('确定问题')
    expect(wrapper.text()).toContain('待处理')
    expect(wrapper.text()).toContain('不适用')
    expect(wrapper.text()).toContain('合规')
    expect(wrapper.find('[data-testid="single-record-document-group"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid^="single-record-report-tab-"]').exists()).toBe(false)
  })

  it('分组模式按客户文书主题展示四类报告页签，技术异常只进入系统状态和全部规则', async () => {
    const groupedItems = [
      {
        rule_id: 'LX0609-025',
        rule_name: '植入物相关记录',
        source_document: '手术记录',
        qc_point: '未记录植入物种类及数量',
        status: 'non_compliant',
        conclusion: '植入物种类及数量未记录。',
        evidence: [{ source_ref: 'src_surgery_025', source_type: 'surgery_record' }],
      },
      {
        rule_id: 'LX0609-020',
        rule_name: '会诊意见执行情况',
        source_document: '会诊记录',
        status: 'data_gap',
        conclusion: '缺少可核对的后续病程记录。',
      },
      {
        rule_id: 'LX0609-023',
        rule_name: '会诊意见落实内容',
        source_document: '会诊记录',
        status: 'uncertain',
        conclusion: '执行内容仍需人工判断。',
      },
      {
        rule_id: 'LX0609-002',
        rule_name: '首次病程记录',
        source_document: '首次病程记录',
        status: 'technical_error',
        conclusion: '本次结果生成异常。',
      },
      {
        rule_id: 'LX0609-001',
        rule_name: '入院记录及时性',
        source_document: '入院记录',
        status: 'compliant',
        conclusion: '符合要求。',
      },
    ]
    const wrapper = mount(SingleRecordQcResultPanel, {
      props: { items: groupedItems, presentationMode: 'grouped' },
    })

    expect(
      wrapper.findAll('[data-testid^="single-record-report-tab-"]').map((tab) => tab.text()),
    ).toEqual(['确定问题1', '资料待核实1', '待判断1', '全部规则5'])
    expect(
      wrapper
        .get('[data-testid="single-record-report-tab-non_compliant"]')
        .attributes('aria-selected'),
    ).toBe('true')
    expect(wrapper.get('[data-testid="single-record-system-status"]').text()).toContain(
      '1 条结果校验异常',
    )
    expect(wrapper.findAll('[data-testid="single-record-document-group"]')).toHaveLength(1)
    expect(wrapper.get('[data-testid="single-record-document-group"]').text()).toContain('手术记录')
    expect(wrapper.text()).toContain('1处证据')
    expect(wrapper.findAll('[data-testid="single-record-result-row"]')).toHaveLength(1)
    expect(wrapper.text()).not.toContain('LX0609-002')

    await wrapper.get('[data-testid="single-record-report-tab-all"]').trigger('click')
    expect(wrapper.findAll('[data-testid="single-record-document-group"]')).toHaveLength(4)
    expect(wrapper.findAll('[data-testid="single-record-result-row"]')).toHaveLength(5)
    expect(wrapper.text()).toContain('LX0609-002')
    expect(wrapper.text()).toContain('LX0609-001')

    const surgeryGroupToggle = wrapper.findAll(
      '[data-testid="single-record-document-group-toggle"]',
    )[0]!
    await surgeryGroupToggle.trigger('click')
    expect(
      wrapper
        .findAll('[data-testid="single-record-document-group-toggle"]')[0]!
        .attributes('aria-expanded'),
    ).toBe('false')
    expect(wrapper.findAll('[data-testid="single-record-result-row"]')).toHaveLength(4)
    await wrapper
      .findAll('[data-testid="single-record-document-group-toggle"]')[0]!
      .trigger('click')
    await wrapper
      .findAll('[data-testid="single-record-result-row"]')[0]!
      .get('[data-testid="single-record-result-toggle"]')
      .trigger('click')
    await wrapper.get('[data-testid="single-record-evidence"]').trigger('click')
    expect(wrapper.emitted('locate-evidence')).toBeTruthy()
  })

  it('分组模式按确定问题、资料待核实、待判断、全部规则选择首个非空页签', async () => {
    const wrapper = mount(SingleRecordQcResultPanel, {
      props: {
        presentationMode: 'grouped',
        items: [
          {
            rule_id: 'LX0609-020',
            rule_name: '会诊意见执行情况',
            source_document: '会诊记录',
            status: 'data_gap',
          },
          {
            rule_id: 'LX0609-023',
            rule_name: '会诊意见落实内容',
            source_document: '会诊记录',
            status: 'uncertain',
          },
        ],
      },
    })

    expect(
      wrapper.get('[data-testid="single-record-report-tab-data_gap"]').attributes('aria-selected'),
    ).toBe('true')

    await wrapper.setProps({
      items: [
        {
          rule_id: 'LX0609-023',
          rule_name: '会诊意见落实内容',
          source_document: '会诊记录',
          status: 'uncertain',
        },
      ],
    })
    expect(
      wrapper.get('[data-testid="single-record-report-tab-uncertain"]').attributes('aria-selected'),
    ).toBe('true')

    await wrapper.setProps({
      items: [
        {
          rule_id: 'LX0609-001',
          rule_name: '入院记录及时性',
          source_document: '入院记录',
          status: 'compliant',
        },
      ],
    })
    expect(
      wrapper.get('[data-testid="single-record-report-tab-all"]').attributes('aria-selected'),
    ).toBe('true')
  })

  it('合规项有现有核对说明或证据时，也可展开查看详细依据', async () => {
    const wrapper = mount(SingleRecordQcResultPanel, {
      props: {
        items: [
          {
            rule_id: 'LX0609-045',
            rule_name: '输血记录：无输血病程记录',
            status: 'compliant',
            conclusion: '已找到可核对的输血病程记录（3份）。',
            detail: '已按输血发生时间核对后续病程记录，均可定位复核。',
            actual: '共核对3份输血病程记录，记录时间均在本次住院期间。',
            standard: '存在输血事件时，应有可定位的输血病程记录。',
            evidence: [
              {
                source_ref: 'src_bloodtrans_record_045',
                source_type: 'bloodtrans_record',
                source_label: '输血病程记录',
                field_path: '记录时间',
              },
            ],
          },
        ],
      },
    })

    await wrapper.get('[data-testid="single-record-result-toggle"]').trigger('click')

    expect(wrapper.get('[data-testid="single-record-compliant-detail"]').text()).toContain(
      '核对说明已按输血发生时间核对后续病程记录，均可定位复核。',
    )
    expect(wrapper.get('[data-testid="single-record-compliant-detail"]').text()).toContain(
      '核对情况共核对3份输血病程记录，记录时间均在本次住院期间。',
    )
    expect(wrapper.get('[data-testid="single-record-detail-grid"]').text()).toContain(
      '关键证据输血病程记录',
    )
  })

  it('占位结果单独计为未执行，不把质控点总数冒充执行完成数', () => {
    const wrapper = mount(SingleRecordQcResultPanel, {
      props: {
        items: [
          ...items,
          {
            rule_id: 'LX0609-051',
            rule_name: '死亡病历讨论记录',
            status: 'not_executed',
            conclusion: '本次未执行',
          },
        ],
      },
    })

    expect(wrapper.get('[data-testid="single-record-result-summary"]').text()).toBe(
      '4 个质控点 · 已执行 3 · 未执行 1',
    )
  })

  it('按唯一状态分组筛选，所有Tab数量之和等于全部且不影响展开与定位', async () => {
    const tabItems = [
      ...items,
      {
        rule_id: 'LX0609-001',
        rule_name: '入院记录',
        status: 'data_gap',
        conclusion: '资料不足。',
      },
      {
        rule_id: 'LX0609-002',
        rule_name: '首次病程',
        status: 'technical_error',
        conclusion: '来源异常。',
      },
      {
        rule_id: 'LX0609-004',
        rule_name: '入院病程',
        status: 'compliant',
        conclusion: '符合要求。',
      },
    ]
    const wrapper = mount(SingleRecordQcResultPanel, { props: { items: tabItems } })

    const tabs = wrapper.findAll('[role="tab"]')
    expect(tabs.map((tab) => tab.text())).toEqual([
      '全部6',
      '确定问题2',
      '待处理2',
      '不适用1',
      '合规1',
    ])
    expect(wrapper.findAll('[data-testid="single-record-result-row"]')).toHaveLength(6)

    await wrapper.get('[data-testid="single-record-result-tab-pending"]').trigger('click')
    expect(wrapper.findAll('[data-testid="single-record-result-row"]')).toHaveLength(2)
    expect(wrapper.text()).toContain('LX0609-001')
    expect(wrapper.text()).toContain('LX0609-002')
    expect(wrapper.text()).not.toContain('LX0609-025')

    await wrapper.get('[data-testid="single-record-result-tab-non_compliant"]').trigger('click')
    await wrapper
      .findAll('[data-testid="single-record-result-row"]')[0]!
      .get('button')
      .trigger('click')
    await wrapper.get('[data-testid="single-record-evidence"]').trigger('click')
    expect(wrapper.emitted('locate-evidence')).toBeTruthy()
  })

  it('展开后展示完整判定、逐项判定、证据、医学分析与建议', async () => {
    const wrapper = mount(SingleRecordQcResultPanel, { props: { items } })

    await wrapper
      .findAll('[data-testid="single-record-result-row"]')[0]!
      .get('button')
      .trigger('click')

    expect(wrapper.text()).toContain('完整判定说明')
    expect(wrapper.text()).toContain('逐项判定')
    expect(wrapper.text()).toContain('主诉书写规范性')
    expect(wrapper.text()).toContain('主诉共 14 字；标准为不超过 20 字。')
    expect(wrapper.text()).toContain('诊断指向性')
    expect(wrapper.text()).toContain('实际情况')
    expect(wrapper.text()).toContain('核对标准')
    expect(wrapper.text()).toContain('关键证据')
    expect(wrapper.text()).toContain('医学分析')
    expect(wrapper.text()).toContain('模型分析 / 医学判断')
    expect(wrapper.text()).toContain('当前主诉缺少可区分第一诊断的特异性线索')
    expect(wrapper.text()).toContain('处理建议')
    expect(wrapper.find('[data-testid="single-record-detail-grid"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="single-record-evidence"]').classes()).toContain(
      'evidence-row',
    )
  })

  it('证据点击只发出 locate-evidence，不在组件内定位文书', async () => {
    const wrapper = mount(SingleRecordQcResultPanel, { props: { items } })
    await wrapper
      .findAll('[data-testid="single-record-result-row"]')[0]!
      .get('button')
      .trigger('click')
    await wrapper.get('[data-testid="single-record-evidence"]')!.trigger('click')

    expect(wrapper.emitted('locate-evidence')).toEqual([[items[0]!.evidence![0]]])
  })

  it('确定问题缺少具体解释时仍原样展示引擎结论', () => {
    const wrapper = mount(SingleRecordQcResultPanel, {
      props: { items: [incompleteNonCompliantItem] },
    })

    expect(wrapper.text()).toContain('确定问题')
    expect(wrapper.text()).toContain('发现该质控点对应的明确问题。')
    expect(wrapper.text()).not.toContain('本次保存结果缺少具体判定说明')
  })

  it('033 原样展示服务端结论，并将手术同意书事实翻译为客户语言', async () => {
    const wrapper = mount(SingleRecordQcResultPanel, {
      props: { items: [surgeryConsentMissingItem] },
    })

    expect(wrapper.get('[data-testid="single-record-result-conclusion"]').text()).toBe(
      '已确认实施手术，未检索到手术知情同意书。',
    )

    await wrapper.get('[data-testid="single-record-result-row"] button').trigger('click')

    expect(wrapper.text()).toContain('未检索到手术知情同意书')
    expect(wrapper.text()).toContain('手术知情同意书')
    expect(wrapper.text()).toContain('已实施手术')
    expect(wrapper.text()).toContain('是')
    expect(wrapper.text()).not.toContain('surgery_consent_document_missing')
    expect(wrapper.text()).not.toContain('consent_state')
  })

  it('033 签名缺失不误写为整份同意书缺失，也不展示原始枚举', async () => {
    const wrapper = mount(SingleRecordQcResultPanel, {
      props: { items: [surgeryConsentSignatureMissingItem] },
    })

    expect(wrapper.get('[data-testid="single-record-result-conclusion"]').text()).toBe(
      '已确认实施手术，但手术知情同意书缺少术者签名。',
    )
    expect(wrapper.text()).not.toContain('未检索到手术知情同意书')

    await wrapper.get('[data-testid="single-record-result-row"] button').trigger('click')

    expect(wrapper.text()).toContain('缺少签名')
    expect(wrapper.text()).toContain('术者')
    expect(wrapper.text()).not.toContain('surgery_consent_signature_missing')
    expect(wrapper.text()).not.toContain('signature_missing')
    expect(wrapper.text()).not.toContain('surgeon')
  })

  it('仅保存模型分析的LLM不合规结果仍可展开查看原始判断', async () => {
    const wrapper = mount(SingleRecordQcResultPanel, {
      props: {
        items: [
          {
            rule_id: 'LX0609-018',
            rule_name: '主诉能导出第一诊断',
            status: 'non_compliant',
            conclusion: '发现该质控点对应的明确问题。',
            model_analysis: '主诉仅描述咳嗽、咳痰和气促，缺少提示急性下呼吸道感染的特异性线索。',
          },
        ],
      },
    })

    await wrapper.get('[data-testid="single-record-result-row"] button').trigger('click')

    expect(wrapper.text()).toContain('模型分析 / 医学判断')
    expect(wrapper.text()).toContain('缺少提示急性下呼吸道感染的特异性线索')
    expect(wrapper.text()).not.toContain('本次保存结果缺少具体判定说明')
  })

  it('不向客户展示缺失字段和判定类型，并保留安全证据定位入口', async () => {
    const wrapper = mount(SingleRecordQcResultPanel, { props: { items: [items[2]!] } })

    await wrapper.get('[data-testid="single-record-result-row"] button').trigger('click')

    expect(wrapper.text()).toContain('判定事实')
    expect(wrapper.text()).toContain('植入物信息填写不完整')
    expect(wrapper.text()).not.toContain('缺失字段')
    expect(wrapper.text()).not.toContain('条码/批号、数量')
    expect(wrapper.get('[data-testid="single-record-evidence"]').text()).toContain('手术记录')
  })

  it('012只把触发报告作为关键证据，并以中文说明已核对的病程范围', async () => {
    const wrapper = mount(SingleRecordQcResultPanel, {
      props: {
        items: [
          {
            rule_id: 'LX0609-012',
            rule_name: 'CT/MRI 阳性结果无分析',
            status: 'non_compliant',
            conclusion:
              'CT/MRI 报告于 2026-07-08 17:55:17 出具。已核对首次病程记录及后续病程记录，未找到报告后 24 小时内的阳性结果分析记录。',
            customer_display_facts: {
              failure_kind: 'exam_lab_requirement_not_documented',
              checked_sources: ['exam_lab_report', 'course_record'],
              reviewed_record_scope: '首次病程记录及后续病程记录',
              threshold_hours: 24,
            },
            evidence: [
              {
                source_ref: 'src_ct_report_012',
                source_type: 'exam_master',
              },
              {
                source_ref: 'src_daily_course_012',
                source_type: 'daily_course_record',
                source_label: '日常病程记录',
              },
            ],
          },
        ],
      },
    })

    await wrapper.get('[data-testid="single-record-result-row"] button').trigger('click')

    const detail = wrapper.get('[data-testid="single-record-detail-grid"]').text()
    expect(detail).toContain('已核对病程首次病程记录及后续病程记录')
    expect(detail).not.toContain('exam_lab_requirement_not_documented')
    expect(detail).not.toContain('已核对来源')
    expect(wrapper.get('[data-testid="single-record-evidence"]').text()).toContain(
      'CT/MRI 检查报告',
    )
    expect(wrapper.get('[data-testid="single-record-evidence"]').text()).not.toContain(
      '日常病程记录',
    )
  })

  it('四级手术MDT问题展示手术等级、等级来源和讨论事实', async () => {
    const wrapper = mount(SingleRecordQcResultPanel, {
      props: {
        items: [
          {
            rule_id: 'LX0609-040',
            rule_name: '四级手术术前多学科讨论',
            status: 'non_compliant',
            conclusion: '四级手术术前未完成多学科讨论。',
            customer_display_facts: {
              performed_surgery_confirmed: true,
              procedure_kind: 'surgery',
              effective_surgery_level: '四级',
              surgery_level_source: 'hospital_performance',
              mdt_discussion_state: 'missing',
            },
          },
        ],
      },
    })

    await wrapper.get('[data-testid="single-record-result-row"] button').trigger('click')

    expect(wrapper.text()).toContain('手术等级')
    expect(wrapper.text()).toContain('四级')
    expect(wrapper.text()).toContain('等级来源')
    expect(wrapper.text()).toContain('院内绩效目录')
    expect(wrapper.text()).toContain('多学科讨论')
    expect(wrapper.text()).toContain('未完成')
  })

  it('时限问题直接展示后端返回的入院时间、记录时间、实际间隔和超出时长', async () => {
    const wrapper = mount(SingleRecordQcResultPanel, {
      props: {
        items: [
          {
            rule_id: 'LX0609-002',
            rule_name: '首次病程记录',
            status: 'non_compliant',
            conclusion: '首次病程记录距入院时间共 448.6 小时，超过 8 小时要求 440.6 小时。',
            customer_display_facts: {
              failure_kind: 'timeliness_requirement_not_met',
              target_document: 'first_course_record',
              source_label: '首次病程记录',
              anchor_time: '2026-06-20 17:19:08',
              observed_time: '2026-07-09 09:54:57',
              threshold_hours: 8,
              elapsed_hours: 448.6,
              overdue_hours: 440.6,
            },
          },
        ],
      },
    })

    await wrapper.get('[data-testid="single-record-result-row"] button').trigger('click')

    expect(wrapper.get('[data-testid="timeliness-metrics"]').text()).toContain('规定时限8 小时')
    expect(wrapper.get('[data-testid="timeliness-metrics"]').text()).toContain('实际间隔448.6 小时')
    expect(wrapper.get('[data-testid="timeliness-metrics"]').text()).toContain('超出时限440.6 小时')
    expect(wrapper.get('[data-testid="timeliness-timeline"]').text()).toContain(
      '2026-06-20 17:19:08',
    )
    expect(wrapper.get('[data-testid="timeliness-timeline"]').text()).toContain(
      '2026-07-09 09:54:57',
    )
    expect(wrapper.text()).toContain('入院时间')
    expect(wrapper.text()).toContain('2026-06-20 17:19:08')
    expect(wrapper.text()).toContain('首次病程记录时间')
    expect(wrapper.text()).toContain('2026-07-09 09:54:57')
    expect(wrapper.text()).toContain('实际间隔')
    expect(wrapper.text()).toContain('448.6 小时')
    expect(wrapper.text()).toContain('超出时限')
    expect(wrapper.text()).toContain('440.6 小时')
  })

  it('时限指标不完整时仍展示后端已返回的时间点', async () => {
    const wrapper = mount(SingleRecordQcResultPanel, {
      props: {
        items: [
          {
            rule_id: 'LX0609-002',
            rule_name: '首次病程记录',
            status: 'data_gap',
            conclusion: '已返回核对时间，但缺少完整时限指标。',
            customer_display_facts: {
              anchor_time: '2026-06-20 17:19:08',
              observed_time: '2026-07-09 09:54:57',
            },
          },
        ],
      },
    })

    await wrapper.get('[data-testid="single-record-result-row"] button').trigger('click')

    expect(wrapper.find('[data-testid="timeliness-metrics"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="timeliness-timeline"]').text()).toContain(
      '2026-06-20 17:19:08',
    )
    expect(wrapper.get('[data-testid="timeliness-timeline"]').text()).toContain(
      '2026-07-09 09:54:57',
    )
  })

  it('合规时限结果沿用指标带和时间轴，并翻译受控事实枚举', async () => {
    const wrapper = mount(SingleRecordQcResultPanel, {
      props: {
        items: [
          {
            rule_id: 'LX0609-001',
            rule_name: '入院记录：入院后24小时内是否完成',
            status: 'compliant',
            conclusion: '符合质控要求',
            suggestion: '继续保持。',
            customer_display_facts: {
              failure_kind: 'timeliness_requirement_satisfied',
              target_document: 'admission_record',
              source_label: '入院记录',
              anchor_time: '2026-06-20 17:19:08',
              observed_time: '2026-06-20 19:23:45',
              threshold_hours: 24,
              elapsed_hours: 2.08,
            },
            evidence: [
              {
                source_ref: 'src_admission_record',
                source_type: 'admission_record',
                source_label: '入院记录',
              },
            ],
          },
        ],
      },
    })

    await wrapper.get('[data-testid="single-record-result-row"] button').trigger('click')

    const metrics = wrapper.get('[data-testid="timeliness-metrics"]')
    expect(metrics.classes()).toContain('has-2-metrics')
    expect(metrics.text()).toContain('规定时限24 小时')
    expect(metrics.text()).toContain('实际间隔2.08 小时')
    expect(metrics.text()).not.toContain('超出时限')
    expect(wrapper.get('[data-testid="timeliness-timeline"]').text()).toContain(
      '2026-06-20 19:23:45',
    )
    expect(wrapper.text()).toContain('核对依据')
    expect(wrapper.get('[data-testid="single-record-evidence"]').text()).toContain('入院记录')
    expect(wrapper.text()).not.toContain('处理建议')
    expect(wrapper.text()).not.toContain('继续保持')
    expect(wrapper.text()).not.toContain('timeliness_requirement_satisfied')
    expect(wrapper.text()).not.toContain('admission_record')
  })

  it('合规结果存在逐项判定时可展开查看合规依据', async () => {
    const wrapper = mount(SingleRecordQcResultPanel, { props: { items: [explainedCompliantItem] } })

    expect(wrapper.text()).toContain('合规')
    await wrapper.get('[data-testid="single-record-result-row"] button').trigger('click')
    expect(wrapper.find('.result-detail').exists()).toBe(true)
    expect(wrapper.get('[data-testid="single-record-compliant-criteria"]').text()).toContain(
      '合规依据',
    )
    expect(wrapper.get('[data-testid="single-record-compliant-criteria"]').text()).toContain(
      '子项核对通过',
    )
    expect(wrapper.text()).toContain('核对情况')
    expect(wrapper.text()).toContain(explainedCompliantItem.actual)
    expect(wrapper.text()).toContain('合规标准')
    expect(wrapper.text()).toContain(explainedCompliantItem.standard)
    expect(wrapper.text()).toContain('模型分析 / 医学判断')
    expect(wrapper.text()).not.toContain('无需处理。')
  })

  it('合规结果不补造通过依据或重跑提示', async () => {
    const wrapper = mount(SingleRecordQcResultPanel, {
      props: { items: [historicalCompliantItem] },
    })

    expect(wrapper.text()).toContain('未发现问题。')
    expect(wrapper.text()).not.toContain('历史结果缺少可核查通过依据')
    expect(wrapper.find('.toggle-mark').exists()).toBe(false)
    expect(wrapper.find('.result-detail').exists()).toBe(false)
  })

  it('数据不足展示具体缺口、当前已知事实和可定位证据，不泛化为资料不足', async () => {
    const wrapper = mount(SingleRecordQcResultPanel, { props: { items: [explainedDataGapItem] } })

    await wrapper.get('[data-testid="single-record-result-row"] button').trigger('click')

    expect(wrapper.text()).toContain('数据不足')
    expect(wrapper.text()).toContain('缺口说明')
    expect(wrapper.text()).toContain('后续病程文书的权威记录时间未返回')
    expect(wrapper.text()).toContain('当前已知情况')
    expect(wrapper.text()).toContain('所需核对条件')
    expect(wrapper.text()).toContain('已核对来源')
    expect(wrapper.text()).toContain('待补资料')
    expect(wrapper.text()).toContain('缺少来源')
    expect(wrapper.text()).toContain('daily_course_record')
    expect(wrapper.text()).not.toContain('缺少字段')
    expect(wrapper.text()).not.toContain('daily_course_record.record_time')
    expect(wrapper.get('[data-testid="single-record-evidence"]').text()).toContain(
      'CT/MRI 检查报告',
    )
  })

  it('数据不足结果未保存具体缺口时不由前端补造说明', async () => {
    const wrapper = mount(SingleRecordQcResultPanel, {
      props: {
        items: [{ rule_id: 'LX0609-014', rule_name: '细菌培养记录', status: 'data_gap' }],
      },
    })

    await wrapper.get('[data-testid="single-record-result-row"] button').trigger('click')

    expect(wrapper.text()).not.toContain('历史数据不足结果未保存缺少的受控来源、字段或核对条件')
  })

  it('已授权原文短摘录显示在对应证据下，并仍可点击定位', async () => {
    const item = {
      ...items[2]!,
      evidence: [
        {
          source_ref: 'src_1234567890abcdef12345678',
          source_type: 'surgery_record',
          evidence_excerpt: '手术经过：置入人工关节假体，术中情况平稳。',
          excerpt_kind: '文书级依据',
        },
      ],
    }
    const wrapper = mount(SingleRecordQcResultPanel, { props: { items: [item] } })

    await wrapper.get('[data-testid="single-record-result-row"] button').trigger('click')

    const evidence = wrapper.get('[data-testid="single-record-evidence"]')
    expect(evidence.text()).toContain('文书级依据')
    expect(evidence.text()).toContain('置入人工关节假体')
    await evidence.trigger('click')
    expect(wrapper.emitted('locate-evidence')).toEqual([[item.evidence[0]]])
  })

  it('会诊执行问题将会诊证据显示为会诊记录而不是泛化来源文书', async () => {
    const wrapper = mount(SingleRecordQcResultPanel, {
      props: {
        items: [
          {
            rule_id: 'LX0609-020',
            rule_name: '会诊记录：有会诊记录单无请会诊执行记录',
            status: 'non_compliant',
            conclusion:
              '共核对2次已完成会诊的2条建议：1条已找到明确执行记录，1条未找到对应执行记录。未闭环：第2次会诊的检查类建议。',
            evidence: [
              {
                source_ref: 'src_consult_missing',
                source_type: 'consultation_record',
              },
            ],
          },
        ],
      },
    })

    await wrapper.get('[data-testid="single-record-result-row"] button').trigger('click')

    const evidence = wrapper.get('[data-testid="single-record-evidence"]')
    expect(evidence.text()).toContain('会诊记录')
    expect(evidence.text()).not.toContain('来源文书')
  })
})
