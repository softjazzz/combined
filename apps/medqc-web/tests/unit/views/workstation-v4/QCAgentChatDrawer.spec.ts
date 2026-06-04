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

  it('sends message with safe user_context', async () => {
    chatMock.mockResolvedValueOnce({
      status: 'completed',
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
        skipped_rules: [
          { rule_id: 'SC-050', reason: 'unsupported_execution_mode' },
          { rule_id: 'SC-051', reason: 'requires_llm' },
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
    expect(wrapper.findAll('.qc-agent-warnings li')).toHaveLength(1)
    expect(wrapper.text()).toContain(
      '这些规则已被选中，但当前即时质控模式未执行；需要正式规则引擎或 LLM 能力后才能判断。',
    )
    expect(wrapper.text()).toContain('查看脱敏响应摘要')
    expect(wrapper.text()).not.toContain('不应进入请求')
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
        issues: [{ rule_id: 'WR-002', severity: 'medium', message: '缺少上级医师意见' }],
        documents: [{ record_content: '完整病历正文不允许展示' }],
        internal_data: { medical_text: '完整病历正文不允许展示' },
      },
      prompt: '规则 prompt 不允许展示',
    })
    const wrapper = mountDrawer()

    await wrapper.find('[data-testid="qc-agent-message-input"]').setValue('对查房记录做质控')
    await wrapper.find('[data-testid="qc-agent-send-button"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('WR-002')
    expect(wrapper.text()).toContain('缺少上级医师意见')
    expect(wrapper.text()).not.toContain('完整病历正文不允许展示')
    expect(wrapper.text()).not.toContain('medical_text')
    expect(wrapper.text()).not.toContain('record_content')
    expect(wrapper.text()).not.toContain('规则 prompt 不允许展示')
  })
})
