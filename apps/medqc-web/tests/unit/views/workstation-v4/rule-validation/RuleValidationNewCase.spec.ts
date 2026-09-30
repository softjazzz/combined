import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import * as api from '@/services/rule-validation-service'
import * as samples from '@/services/manual-case-sample-service'
import type { RuleDetail, ValidationCase } from '@/services/rule-validation-service'
import RuleValidationNewCaseView from '@/views/workstation-v4/rule-validation/RuleValidationNewCaseView.vue'
import {
  CASE_COPY_SOURCE_TYPE,
  buildCreatePayload,
  copyDocuments,
  emptyDraft,
  validateDraft,
} from '@/views/workstation-v4/rule-validation/caseDraft'
import type { EditableMedicalRecordDocument } from '@/views/workstation-v4/customer-sample-validation/types'

vi.mock('@/services/rule-validation-service', () => ({ getValidationRule: vi.fn(), saveCaseAnswer: vi.fn() }))
vi.mock('@/services/manual-case-sample-service', () => ({
  createManualTestMedicalRecord: vi.fn(),
  getEditableMedicalRecordDocuments: vi.fn(),
}))
vi.mock('ant-design-vue', () => ({ message: { success: vi.fn() } }))
const push = vi.fn()
const replace = vi.fn(() => Promise.resolve())
let query: Record<string, string> = {}
let leaveGuard: ((to: { fullPath: string }) => boolean) | null = null
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { ruleId: 'LX0609-09-01-02' }, query }),
  useRouter: () => ({ push, replace }),
  onBeforeRouteLeave: (guard: (to: { fullPath: string }) => boolean) => {
    leaveGuard = guard
  },
}))

const field = defineComponent({
  props: ['value'],
  emits: ['update:value'],
  template: `<input :value="value" @input="$emit('update:value', $event.target.value)" />`,
})
const area = defineComponent({
  props: ['value'],
  emits: ['update:value'],
  template: `<textarea :value="value" @input="$emit('update:value', $event.target.value)" />`,
})
const stubs = {
  ASpin: { template: '<div><slot /></div>' },
  AAlert: { props: ['message'], template: '<p class="alert">{{ message }}</p>' },
  AModal: { props: ['open'], template: '<div v-if="open"><slot /></div>' },
  AInput: field,
  ATextarea: area,
  ASelect: true,
  ARadioGroup: { template: '<div><slot /></div>' },
  ARadio: { template: '<label><slot /></label>' },
  RouterLink: { props: ['to'], template: '<a><slot /></a>' },
}

const rule = { rule_id: 'LX0609-09-01-02', name: '内容完整性', source_document: '抢救记录', release_scope: 'acceptance_only' as const, policy_summary: '' }
const source: ValidationCase = {
  item_id: 'ct-src', case_title: '【验收测试】抢救记录完整', record_ref: { institute_id: 'CUSTOMER_TEST', patient_id: 'P', visit_id: 'V' },
  department: '急诊内科', source_kind: 'synthetic', evaluation_as_of_date: '2026-07-05', expected_status: 'compliant',
  human_reason: '完整', purpose: 'development', answer_revision: 1,
}
const detail = { rule, cases: [source] } as unknown as RuleDetail

describe('caseDraft 表单模型', () => {
  it('校验必填项与时间先后', () => {
    const draft = { ...emptyDraft(new Date('2026-07-05T10:00:00')), title: 'x', department: '内科', reason: '依据' }
    expect(validateDraft(draft)).toBe('请至少填写一份有正文的文书')
    draft.documents = [{ key: 'k', type: 'rescue_record', time: '', title: '', content: '正文' }]
    draft.evaluationDate = '2026-06-01'
    expect(validateDraft(draft)).toBe('评价时间点不能早于入院日期')
    draft.evaluationDate = '2026-07-05'
    expect(validateDraft(draft)).toBe('')
  })

  it('复制只保留可映射的文书，登记等非文书行不带入', () => {
    const docs = [
      { document_type: 'rescue_record', title: '抢救记录', record_time: '2026-07-02 03:40:00', content: '正文' },
      { document_type: 'mr', title: '首页', content: '客户自建测试病历' },
      { document_type: '', source_table: 'inpat_nondrug_order', title: '医嘱', content: '小抢救' },
    ] as unknown as EditableMedicalRecordDocument[]
    expect(copyDocuments(docs).map((d) => [d.type, d.time])).toEqual([
      ['rescue_record', '2026-07-02T03:40'],
      ['medical_order', ''],
    ])
  })

  it('请求带固定前缀、评价时间点；复制来源标为测试病例复制（计为合成病例）', () => {
    const draft = {
      ...emptyDraft(), title: '缺职称', department: '急诊内科', evaluationDate: '2026-07-05', reason: 'r',
      documents: [{ key: 'k', type: 'rescue_record', time: '', title: '抢救记录', content: ' 正文 ' }],
    }
    const payload = buildCreatePayload(draft, 'LX0609-09-01-02', { itemId: 'ct-src' })
    expect(payload.case_title).toBe('【验收测试】缺职称')
    expect(payload.evaluation_as_of_date).toBe('2026-07-05')
    expect(payload.documents[0]?.content).toBe('正文')
    expect(payload.source?.type).toBe(CASE_COPY_SOURCE_TYPE)
    expect(payload.golden_answers).toBeUndefined()
  })
})

describe('新建测试病例页', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    query = {}
    leaveGuard = null
    vi.mocked(api.getValidationRule).mockResolvedValue({ success: true, data: detail })
  })

  it('保存时先建病例再为本规则保存预期，然后回到规则详情', async () => {
    vi.mocked(samples.createManualTestMedicalRecord).mockResolvedValue({ success: true, data: { item: { id: 'ct-new' } } } as never)
    vi.mocked(api.saveCaseAnswer).mockResolvedValue({ success: true, data: {} as never })
    const wrapper = mount(RuleValidationNewCaseView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.findAll('[data-testid="draft-document"]')).toHaveLength(1)
    await wrapper.find('[aria-label="病例标题"]').setValue('新病例')
    await wrapper.find('[aria-label="科室"]').setValue('急诊内科')
    await wrapper.find('[aria-label="文书1正文"]').setValue('合成正文')
    await wrapper.find('[aria-label="人工预期依据"]').setValue('依据')
    await wrapper.find('[data-testid="save-case"]').trigger('click')
    await flushPromises()

    expect(samples.createManualTestMedicalRecord).toHaveBeenCalledWith(
      expect.objectContaining({ case_title: '【验收测试】新病例', selected_rule_ids: ['LX0609-09-01-02'] }),
    )
    expect(api.saveCaseAnswer).toHaveBeenCalledWith('LX0609-09-01-02', 'ct-new', {
      revision: 0, expected_status: 'non_compliant', human_reason: '依据', purpose: 'development',
    })
    expect(push).toHaveBeenCalledWith({ name: 'WorkstationV4RuleValidationDetail', params: { ruleId: 'LX0609-09-01-02' } })
  })

  it('复制时按 source_view=current 读取源病例，带入科室、入院时间、文书与评价时间点', async () => {
    query = { copyFrom: 'ct-src' }
    vi.mocked(samples.getEditableMedicalRecordDocuments).mockResolvedValue({
      success: true,
      data: {
        current_record: { admission_time: '2026-07-01T08:00:00', admission_time_source: '', admission_time_state: '' },
        documents: [{ document_type: 'rescue_record', title: '抢救记录', record_time: '2026-07-02 03:40:00', content: '正文' }],
      },
    } as never)
    const wrapper = mount(RuleValidationNewCaseView, { global: { stubs } })
    await flushPromises()

    expect(samples.getEditableMedicalRecordDocuments).toHaveBeenCalledWith('V', expect.objectContaining({ source_view: 'current' }))
    expect(wrapper.find('[data-testid="copy-banner"]').text()).toContain('【验收测试】抢救记录完整')
    expect((wrapper.find('[aria-label="科室"]').element as HTMLInputElement).value).toBe('急诊内科')
    expect((wrapper.find('[aria-label="入院时间"]').element as HTMLInputElement).value).toBe('2026-07-01T08:00')
    expect((wrapper.find('[aria-label="评价时间点"]').element as HTMLInputElement).value).toBe('2026-07-05')
    expect(wrapper.findAll('[data-testid="draft-document"]')).toHaveLength(1)
  })

  it('有未保存内容时离开需确认，确认后才跳转', async () => {
    const wrapper = mount(RuleValidationNewCaseView, { global: { stubs } })
    await flushPromises()
    expect(leaveGuard?.({ fullPath: '/elsewhere' })).toBe(true)  // 未改动可直接离开

    await wrapper.find('[aria-label="病例标题"]').setValue('填了一半')
    expect(leaveGuard?.({ fullPath: '/elsewhere' })).toBe(false)
    await flushPromises()
    const dialog = wrapper.find('[data-testid="leave-confirm"]')
    expect(dialog.exists()).toBe(true)
    await dialog.findAll('button').find((b) => b.text() === '放弃并离开')!.trigger('click')
    expect(push).toHaveBeenCalledWith('/elsewhere')
    expect(leaveGuard?.({ fullPath: '/elsewhere' })).toBe(true)
  })
})
