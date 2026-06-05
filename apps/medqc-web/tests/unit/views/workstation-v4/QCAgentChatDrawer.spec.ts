import { defineComponent, h } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { chatMock } = vi.hoisted(() => ({
  chatMock: vi.fn(),
}))

vi.mock('@/api/qcAgent', () => ({
  qcAgentApi: {
    chat: chatMock,
  },
}))

import QCAgentChatDrawer from '@/views/workstation-v4/components/QCAgentChatDrawer.vue'

const DrawerStub = defineComponent({
  name: 'ADrawer',
  props: {
    open: {
      type: Boolean,
      default: false,
    },
  },
  setup(props, { slots }) {
    return () =>
      props.open
        ? h('section', { 'data-testid': 'qc-agent-drawer-root' }, [
            slots.title?.(),
            slots.default?.(),
          ])
        : null
  },
})

const TextareaStub = defineComponent({
  name: 'ATextarea',
  props: {
    value: {
      type: String,
      default: '',
    },
  },
  emits: ['update:value'],
  setup(props, { attrs, emit }) {
    return () =>
      h('textarea', {
        ...attrs,
        value: props.value,
        onInput: (event: Event) =>
          emit('update:value', (event.target as HTMLTextAreaElement).value),
      })
  },
})

const ButtonStub = defineComponent({
  name: 'AButton',
  setup(_props, { attrs, slots }) {
    return () => h('button', attrs, slots.default?.())
  },
})

function mountDrawer(props: Record<string, unknown> = {}) {
  return mount(QCAgentChatDrawer, {
    props: {
      open: true,
      ...props,
    },
    global: {
      stubs: {
        ADrawer: DrawerStub,
        ATextarea: TextareaStub,
        AButton: ButtonStub,
        ClearOutlined: true,
        RobotOutlined: true,
        SafetyCertificateOutlined: true,
        SendOutlined: true,
      },
    },
  })
}

describe('QCAgentChatDrawer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders medical intelligence workspace empty state and capability shortcuts', async () => {
    const wrapper = mountDrawer({
      userContext: {
        visit_id: '2298532',
      },
    })

    expect(wrapper.text()).toContain('单病历只读分析，支持质控、编码、入组模拟')
    expect(wrapper.text()).toContain('定位病历、匹配文书、执行规则、输出建议')
    expect(wrapper.text()).toContain('输入诊断/手术名称，查询 ICD 候选并给出病历编码建议')
    expect(wrapper.text()).toContain('输入主诊断、手术、年龄和费用，执行 DRG/DIP 模拟')

    const buttons = wrapper.findAll('button')
    await buttons.find((button) => button.text().includes('ICD 诊断编码查询'))?.trigger('click')
    expect(
      (wrapper.find('[data-testid="qc-agent-message-input"]').element as HTMLTextAreaElement).value,
    ).toContain('2型糖尿病')

    await buttons.find((button) => button.text().includes('DIP 入组预测'))?.trigger('click')
    expect(
      (wrapper.find('[data-testid="qc-agent-message-input"]').element as HTMLTextAreaElement).value,
    ).toContain('DIP 入组')
  })

  it('sends message with safe user_context', async () => {
    chatMock.mockResolvedValueOnce({
      status: 'completed',
      parsed_intent: {
        result_type: 'document_qc',
      },
      plan: [
        { tool_name: 'get_record_context', status: 'success' },
        { tool_name: 'run_document_qc', status: 'success' },
      ],
      result: {
        qc_summary: {
          issue_count: 0,
          passed_count: 4,
          skipped_count: 16,
          rule_count: 20,
          total_rules: 4,
        },
        executed_rules: [
          {
            rule_id: 'WR-001',
            rule_name: '查房记录是否存在',
            status: 'passed',
            passed: true,
            explanation: '检查是否命中查房相关文书。',
            evidence_summary: '命中 10 份病程/查房文书，最长 842 字',
            matched_documents: [
              {
                document_type: '上级查房记录',
                record_time: '2026-05-03 08:30:00',
                text_length: 842,
                source_table: 'senior_course_record',
              },
            ],
          },
        ],
        skipped_rules: [
          {
            rule_id: 'SC-050',
            rule_name: '上级医师查房病情分析或诊疗意见',
            reason: 'unsupported_execution_mode',
            reason_label: '暂未接入只读程序化执行器',
            next_step: '需补充安全程序化 evaluator 或接入正式只读规则引擎。',
          },
          {
            rule_id: 'SC-051',
            rule_name: '查房记录诊断依据充分性',
            reason: 'requires_llm',
            reason_label: '需要受控 LLM 判断',
            next_step: '需接入受控 LLM 规则执行器后判断。',
          },
        ],
        warnings: ['16 条规则因执行边界限制被跳过'],
      },
      warnings: ['16 条规则因执行边界限制被跳过'],
    })
    const wrapper = mountDrawer({
      userContext: {
        visit_id: '2298532',
        patient_id: 'P001',
        name: '张三',
        department: '神经内科',
        medical_text: '不应进入请求',
      },
    })

    await wrapper.find('[data-testid="qc-agent-message-input"]').setValue('对查房记录做质控')
    await wrapper.find('[data-testid="qc-agent-send-button"]').trigger('click')
    await flushPromises()

    expect(chatMock).toHaveBeenCalledWith({
      message: '对查房记录做质控',
      user_context: {
        visit_id: '2298532',
        patient_id: 'P001',
        name: '张三',
        department: '神经内科',
      },
    })
    expect(wrapper.text()).toContain(
      '已执行 4 条规则，暂未发现问题；另有 16 条规则因当前只读执行边界未执行。',
    )
    expect(wrapper.text()).toContain('已发现问题')
    expect(wrapper.text()).toContain('已执行通过')
    expect(wrapper.text()).toContain('未执行规则')
    expect(wrapper.text()).toContain('选中规则')
    expect(wrapper.text()).toContain('部分执行')
    expect(wrapper.text()).toContain('get_record_context')
    expect(wrapper.text()).toContain('已执行规则')
    expect(wrapper.text()).toContain('查房记录是否存在')
    expect(wrapper.text()).toContain('检查是否命中查房相关文书。')
    expect(wrapper.text()).toContain('命中 1 份文书，上级查房记录，合计 842 字')
    expect(wrapper.findAll('.qc-agent-warnings li')).toHaveLength(1)
    expect(wrapper.text()).toContain(
      '这些规则已被选中，但当前即时质控模式未执行；需要正式规则引擎或 LLM 能力后才能判断。',
    )
    expect(wrapper.text()).toContain('暂未接入只读程序化执行器')
    expect(wrapper.text()).toContain('需接入受控 LLM 规则执行器后判断。')
    expect(wrapper.text()).toContain('查看脱敏响应摘要')
    expect(wrapper.text()).not.toContain('不应进入请求')
  })

  it('renders ICD search result card with candidates and actions', async () => {
    chatMock.mockResolvedValueOnce({
      status: 'completed',
      parsed_intent: {
        result_type: 'icd_candidates',
      },
      plan: [{ tool_name: 'search_icd_codes', status: 'success' }],
      result: {
        query: '2型糖尿病',
        code_type: 'diagnosis',
        version: 'insurance',
        returned: 1,
        candidates: [
          {
            code: 'E11.900',
            name: '2型糖尿病',
            type: 'diagnosis',
            version: 'insurance',
            confidence: 0.96,
            match_type: 'name',
            mapped_code: 'E11.900x001',
            mapped_name: '2型糖尿病医保版',
          },
        ],
      },
    })
    const wrapper = mountDrawer()

    await wrapper.find('[data-testid="qc-agent-message-input"]').setValue('查询 2型糖尿病 ICD 编码')
    await wrapper.find('[data-testid="qc-agent-send-button"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('ICD 查询')
    expect(wrapper.text()).toContain('查询词')
    expect(wrapper.text()).toContain('2型糖尿病')
    expect(wrapper.text()).toContain('E11.900')
    expect(wrapper.text()).toContain('置信度：96%')
    expect(wrapper.text()).toContain('映射：E11.900x001 2型糖尿病医保版')
    expect(wrapper.text()).toContain('复制编码')
    expect(wrapper.text()).toContain('用该编码做 DRG/DIP 入组')
  })

  it('renders coding suggestion result with diagnosis and procedure candidates', async () => {
    chatMock.mockResolvedValueOnce({
      status: 'completed',
      parsed_intent: {
        result_type: 'record_icd_suggestions',
      },
      plan: [{ tool_name: 'suggest_record_icd_codes', status: 'success' }],
      result: {
        record_summary: {
          visit_id: '2298532',
          patient_name: '张三',
          department: '神经内科',
        },
        diagnosis_candidates: [
          {
            name: '高血压',
            existing_code: 'I10.x01',
            source: 'structured_context',
            confidence: 0.9,
            candidates: [{ code: 'I10.x01', name: '高血压', confidence: 0.93 }],
          },
        ],
        procedure_candidates: [
          {
            name: '腰椎穿刺术',
            source: 'explicit_record_field',
            confidence: 0.65,
            low_confidence: true,
            candidates: [{ code: '03.3101', name: '腰椎穿刺术', confidence: 0.88 }],
          },
        ],
        warnings: ['仅为编码建议，不写入正式首页或结算表'],
      },
    })
    const wrapper = mountDrawer()

    await wrapper
      .find('[data-testid="qc-agent-message-input"]')
      .setValue('给 visit_id=2298532 推荐编码')
    await wrapper.find('[data-testid="qc-agent-send-button"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('编码建议')
    expect(wrapper.text()).toContain('张三 / 神经内科 / visit_id=2298532')
    expect(wrapper.text()).toContain('主要诊断候选')
    expect(wrapper.text()).toContain('高血压')
    expect(wrapper.text()).toContain('来源：病案首页/结构化上下文')
    expect(wrapper.text()).toContain('手术/操作候选')
    expect(wrapper.text()).toContain('腰椎穿刺术')
    expect(wrapper.text()).toContain('低置信度')
    expect(wrapper.text()).toContain('仅为编码建议，不写入正式首页或结算表')
  })

  it('renders DRG and DIP grouping result cards', async () => {
    chatMock
      .mockResolvedValueOnce({
        status: 'completed',
        parsed_intent: {
          result_type: 'drg_group',
        },
        result: {
          success: false,
          fallback: true,
          external_call: true,
          input_summary: {
            primary_diagnosis_code: 'K80.101',
            secondary_diagnosis_count: 2,
            procedure_count: 1,
            total_cost: 12000,
          },
          adrg_code: 'HD1',
          adrg_name: '胆道疾病',
          drg_code: 'HD19',
          drg_name: '胆囊切除',
          weight: 1.21,
          baseline_payment: 9800,
          profit_margin: -2200,
          mapped_code: 'K80.101',
          mapped_code_name: '胆囊结石伴胆囊炎',
          grouping_logic: '按主诊断和手术进入胆道疾病组',
          error_summary: '外部分组服务调用失败',
          warnings: ['模拟入组；外部失败时显示降级模式'],
        },
      })
      .mockResolvedValueOnce({
        status: 'completed',
        parsed_intent: {
          result_type: 'dip_group',
        },
        result: {
          success: true,
          input_summary: {
            city_name: '泸州市',
            pdx_code: 'I10.x01',
            proc_count: 0,
            total_fee: 8000,
            los: 7,
          },
          dip_code: 'DIP001',
          dip_name: '高血压病种',
          dip_type: '核心病种',
          grouping_path: '主诊断入组',
        },
      })

    const wrapper = mountDrawer()
    await wrapper
      .find('[data-testid="qc-agent-message-input"]')
      .setValue('用 K80.101 和 51.2101 做 DRG 入组')
    await wrapper.find('[data-testid="qc-agent-send-button"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('DRG 模拟')
    expect(wrapper.text()).toContain('降级模式')
    expect(wrapper.text()).toContain('主诊断编码')
    expect(wrapper.text()).toContain('K80.101')
    expect(wrapper.text()).toContain('HD19 胆囊切除')
    expect(wrapper.text()).toContain('外部分组服务调用失败')

    await wrapper.find('[data-testid="qc-agent-message-input"]').setValue('用 I10.x01 做 DIP 入组')
    await wrapper.find('[data-testid="qc-agent-send-button"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('DIP 预测')
    expect(wrapper.text()).toContain('泸州市')
    expect(wrapper.text()).toContain('DIP001')
    expect(wrapper.text()).toContain('高血压病种')
    expect(wrapper.text()).toContain('主诊断入组')
    expect(wrapper.text()).toContain('8000.00 元 / 7 天')
  })

  it('renders needs_confirmation candidates and continues with confirm_selection', async () => {
    chatMock
      .mockResolvedValueOnce({
        status: 'needs_confirmation',
        candidates: [
          {
            visit_id: 'V001',
            patient_id: 'P001',
            patient_name: '张三',
            department: '神经内科',
            discharge_date: '2026-06-01',
          },
        ],
        warnings: ['命中多份病历'],
      })
      .mockResolvedValueOnce({
        status: 'completed',
        plan: [{ tool_name: 'run_document_qc', status: 'success' }],
        result: {
          qc_summary: { issue_count: 0, passed_count: 1, skipped_count: 0, rule_count: 1 },
        },
      })
    const wrapper = mountDrawer()

    await wrapper.find('[data-testid="qc-agent-message-input"]').setValue('对张三的查房记录做质控')
    await wrapper.find('[data-testid="qc-agent-send-button"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('候选病历')
    await wrapper.find('.qc-agent-candidate__button').trigger('click')
    await flushPromises()

    expect(chatMock).toHaveBeenNthCalledWith(2, {
      message: '对张三的查房记录做质控',
      confirm_selection: {
        visit_id: 'V001',
        patient_id: 'P001',
      },
      user_context: {},
    })
    expect(wrapper.text()).toContain('run_document_qc')
    expect(wrapper.text()).toContain('完整执行')
  })

  it('renders needs_clarification and unsupported without confirmation action', async () => {
    chatMock.mockResolvedValueOnce({
      status: 'needs_clarification',
      warnings: ['未识别到明确文书类型'],
    })
    const clarification = mountDrawer()
    await clarification.find('[data-testid="qc-agent-message-input"]').setValue('帮我看看')
    await clarification.find('[data-testid="qc-agent-send-button"]').trigger('click')
    await flushPromises()

    expect(clarification.text()).toContain('需澄清')
    expect(clarification.text()).toContain('建议问法')
    expect(clarification.find('.qc-agent-candidate__button').exists()).toBe(false)

    chatMock.mockResolvedValueOnce({
      status: 'unsupported',
      warnings: ['当前受控 Agent 不支持写入'],
    })
    const unsupported = mountDrawer()
    await unsupported.find('[data-testid="qc-agent-message-input"]').setValue('删除质控结果')
    await unsupported.find('[data-testid="qc-agent-send-button"]').trigger('click')
    await flushPromises()

    expect(unsupported.text()).toContain('不支持')
    expect(unsupported.text()).toContain('当前受控 Agent 不支持写入')
    expect(unsupported.find('.qc-agent-candidate__button').exists()).toBe(false)
  })

  it('does not render sensitive keys or raw document text from response', async () => {
    chatMock.mockResolvedValueOnce({
      status: 'completed',
      result: {
        qc_summary: { issue_count: 1, passed_count: 0, skipped_count: 0, rule_count: 1 },
        issues: [
          {
            rule_id: 'WR-002',
            severity: 'medium',
            message: '缺少上级医师意见',
            evidence_summary: '未见上级医师查房意见线索',
            suggestion: '请补充上级医师查房意见。',
          },
        ],
        documents: [{ record_content: '完整病历正文不允许展示' }],
        internal_data: { medical_text: '完整病历正文不允许展示' },
        raw_response: { token: 'secret-token' },
        vector: 'embedding-vector',
      },
      prompt: '规则 prompt 不允许展示',
      api_key: 'secret-api-key',
    })
    const wrapper = mountDrawer()

    await wrapper.find('[data-testid="qc-agent-message-input"]').setValue('对查房记录做质控')
    await wrapper.find('[data-testid="qc-agent-send-button"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('WR-002')
    expect(wrapper.text()).toContain('缺少上级医师意见')
    expect(wrapper.text()).toContain('未见上级医师查房意见线索')
    expect(wrapper.text()).toContain('请补充上级医师查房意见。')
    expect(wrapper.text()).not.toContain('完整病历正文不允许展示')
    expect(wrapper.text()).not.toContain('medical_text')
    expect(wrapper.text()).not.toContain('record_content')
    expect(wrapper.text()).not.toContain('规则 prompt 不允许展示')
    expect(wrapper.text()).not.toContain('secret-token')
    expect(wrapper.text()).not.toContain('embedding-vector')
    expect(wrapper.text()).not.toContain('secret-api-key')
  })
})
