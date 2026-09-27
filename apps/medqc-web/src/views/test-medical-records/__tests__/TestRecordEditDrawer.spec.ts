import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import Antd from 'ant-design-vue'

const loadTestRecordDocuments = vi.fn()
const saveTestRecordEdit = vi.fn()
vi.mock('@/services/test-medical-records', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/test-medical-records')>()
  return {
    ...actual,
    loadTestRecordDocuments: (...args: unknown[]) => loadTestRecordDocuments(...args),
    saveTestRecordEdit: (...args: unknown[]) => saveTestRecordEdit(...args),
  }
})

// jsdom 未实现 matchMedia，Ant Design 栅格响应式需要它。
window.matchMedia =
  window.matchMedia ||
  ((query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }) as unknown as MediaQueryList)

import TestRecordEditDrawer from '@/views/test-medical-records/components/TestRecordEditDrawer.vue'
import type { TestRecordItem } from '@/types/test-medical-records'

function makeItem(overrides: Partial<TestRecordItem> = {}): TestRecordItem {
  return {
    id: 'ct-1',
    institute_id: 'CUSTOMER_TEST',
    patient_id: 'CUSTOMER_PATIENT_1',
    visit_id: 'CUSTOMER_TEST_1',
    case_title: '测试病历一',
    patient_name: '测试患者',
    department: '心内科',
    mr_no: 'MR-1',
    document_count: 1,
    rule_ids: [],
    rule_count: 0,
    latest_job_id: '',
    bundle_status: 'ready',
    origin: 'created',
    source_item_id: '',
    sex: '女',
    age: 67,
    admission_time: '2026-09-01T08:30:00',
    state: 'active',
    removed: false,
    superseded_by: null,
    created_at: null,
    updated_at: '2026-09-27T08:00:00',
    ...overrides,
  }
}

async function mountDrawer(item: TestRecordItem) {
  const wrapper = mount(TestRecordEditDrawer, {
    props: { open: true, item },
    global: { plugins: [Antd] },
    attachTo: document.body,
  })
  await flushPromises()
  return wrapper
}

function saveButton(): HTMLButtonElement {
  return document.body.querySelector('[data-testid="edit-save"]') as HTMLButtonElement
}

describe('测试病历编辑抽屉', () => {
  beforeEach(() => {
    loadTestRecordDocuments.mockReset()
    saveTestRecordEdit.mockReset()
    loadTestRecordDocuments.mockResolvedValue({
      success: true,
      data: [{ key: 'a', document_type: 'admission_record', title: '入院记录', content: '正文', enabled: true }],
    })
  })

  it('用列表中的性别、年龄、入院时间预填，并可保存', async () => {
    saveTestRecordEdit.mockResolvedValue({ success: true, data: { item: { id: 'ct-2' } } })
    const wrapper = await mountDrawer(makeItem())
    const admission = document.body.querySelector('[data-testid="edit-admission-time"]') as HTMLInputElement
    expect(admission.value).toBe('2026-09-01 08:30:00')
    expect(document.body.textContent).not.toContain('源病历缺少该字段，请填写')
    expect(saveButton().disabled).toBe(false)
    saveButton().click()
    await flushPromises()
    const payload = saveTestRecordEdit.mock.calls[0][0]
    expect(payload.basic_info).toMatchObject({ sex: '女', age: 67, admission_time: '2026-09-01T08:30:00' })
    wrapper.unmount()
  })

  it('源病历缺少性别、年龄、入院时间时提示必填且不可保存，不使用默认值', async () => {
    const wrapper = await mountDrawer(makeItem({ sex: null, age: null, admission_time: null }))
    const hints = document.body.textContent?.match(/源病历缺少该字段，请填写/g) || []
    expect(hints).toHaveLength(3)
    const age = document.body.querySelector('[data-testid="edit-age"] input, input[data-testid="edit-age"]') as HTMLInputElement
    expect(age.value).toBe('')
    expect(saveButton().disabled).toBe(true)
    saveButton().click()
    await flushPromises()
    expect(saveTestRecordEdit).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
