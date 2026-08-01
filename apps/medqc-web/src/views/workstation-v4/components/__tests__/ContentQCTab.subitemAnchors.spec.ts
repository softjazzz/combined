import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import ContentQCTab from '../ContentQCTab.vue'
import { evaluateSichuanBundleQC } from '@/api/qc'
import type { BatchQCEvaluateResponse } from '@/api/qc'

vi.mock('@/api/qc', () => ({
  evaluateSichuanBundleQC: vi.fn(),
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
  },
}))

const ButtonStub = {
  template: '<button type="button" @click="$emit(\'click\')"><slot /></button>',
}

const TagStub = {
  template: '<span class="tag-stub"><slot /></span>',
}

const ModalStub = {
  props: ['open', 'title'],
  template: '<section v-if="open" class="modal-stub"><h2>{{ title }}</h2><slot /></section>',
}

const TransparentStub = {
  template: '<div><slot /></div>',
}

const iconStub = { template: '<i />' }

function buildBundleResponse(): BatchQCEvaluateResponse {
  return {
    success: true,
    data: {
      document_id: '9999-0000447180-2311318',
      evaluation_summary: {
        compliance_rate: 98.8,
        total_rules: 84,
        issues_found: 1,
        uncertain_count: 1,
        compliant_count: 83,
        not_applicable_count: 0,
      },
      evaluation_results: [
        {
          rule_id: 'SC-009',
          rule_name: '现病史记录完整性',
          is_compliant: false,
          status: 'uncertain',
          severity: 'medium',
          findings: '外伤现病史地点/场景完整性需复核。',
          suggestion: '请人工核对现病史是否记录受伤地点、场景和致伤机制。',
          evidence: '患者入院3+小时前，走路时踩滑摔倒，致左踝关节疼痛伴活动受限。',
          metadata: {
            subitem_anchors: [
              {
                parent_rule_id: 'SC-009',
                anchor_id: 'SC-009-trauma-location',
                subitem_id: 'SC-009-trauma-location',
                subitem_name: '外伤现病史地点/场景/致伤机制完整性',
                anchor_evidence_status: 'potential_missing_trauma_context',
                anchor_evidence: '患者入院3+小时前，走路时踩滑摔倒，致左踝关节疼痛伴活动受限。',
                anchor_decision_reason: '外伤现病史触发，但受伤地点/场景需人工核对。',
                display_status: 'needs_review',
                display_bucket: '待复核',
                can_show_as_defect: false,
                internal_only: false,
              },
            ],
          },
        },
      ],
      subitem_anchor_results: [
        {
          parent_rule_id: 'SC-009',
          anchor_id: 'SC-009-trauma-location',
          subitem_id: 'SC-009-trauma-location',
          subitem_name: '外伤现病史地点/场景/致伤机制完整性',
          anchor_evidence_status: 'potential_missing_trauma_context',
          anchor_evidence: '患者入院3+小时前，走路时踩滑摔倒，致左踝关节疼痛伴活动受限。',
          anchor_decision_reason: '外伤现病史触发，但受伤地点/场景需人工核对。',
          display_status: 'needs_review',
          display_bucket: '待复核',
          can_show_as_defect: false,
          internal_only: false,
        },
        {
          parent_rule_id: 'SC-070',
          anchor_id: 'SC-070-consultation-not-implemented',
          subitem_id: 'SC-070-consultation-not-implemented',
          subitem_name: '会诊意见落实与医嘱/执行闭环',
          anchor_evidence_status: 'consultation_and_execution_evidence_needs_review',
          anchor_evidence: '康复科会诊建议可见光治疗、超声波、运动功能训练等康复治疗。',
          anchor_decision_reason: '找到会诊意见及执行/病程相关片段，需人工核对医嘱闭环。',
          display_status: 'needs_review',
          display_bucket: '待复核',
          can_show_as_defect: false,
          internal_only: false,
        },
      ],
    },
  }
}

describe('ContentQCTab P0 子锚点页面展示', () => {
  it('将子锚点作为父规则附属待复核信息展示，且不计入确认缺陷数量', async () => {
    vi.mocked(evaluateSichuanBundleQC).mockResolvedValue(buildBundleResponse())

    const wrapper = mount(ContentQCTab, {
      props: {
        instituteId: '9999',
        patientId: '0000447180',
        visitId: '2311318',
        scene: 'final',
        documents: [
          {
            type: 'admission_record',
            label: '入院记录',
            content: '摔倒致左踝关节疼痛伴活动受限3+小时。',
            has_content: true,
            length: 21,
          },
        ],
      },
      global: {
        stubs: {
          'a-button': ButtonStub,
          'a-tag': TagStub,
          'a-modal': ModalStub,
          'a-radio-button': TransparentStub,
          'a-radio-group': TransparentStub,
          'a-switch': TransparentStub,
          'a-input': TransparentStub,
          'a-select': TransparentStub,
          'a-pagination': TransparentStub,
          'a-spin': true,
          SafetyCertificateOutlined: iconStub,
          ReloadOutlined: iconStub,
          ThunderboltOutlined: iconStub,
          CheckCircleOutlined: iconStub,
          SearchOutlined: iconStub,
        },
      },
    })

    await wrapper.find('button').trigger('click')
    await flushPromises()

    await wrapper.find('.summary-link').trigger('click')
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('发现问题1')
    expect(text).toContain('专项检查项2 项待复核')
    expect(text).toContain('父规则专项检查项')
    expect(text).toContain('外伤现病史地点/场景/致伤机制完整性')
    expect(text).toContain('专项检查项（待复核）')
    expect(text).toContain('外伤现病史触发，但受伤地点/场景需人工核对。')
    expect(text).not.toContain('建议重跑')
    expect(text).not.toContain('系统确认缺陷')
  })
})
