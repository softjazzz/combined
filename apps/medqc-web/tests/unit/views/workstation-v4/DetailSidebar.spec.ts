import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import DetailSidebar from '@/views/workstation-v4/components/DetailSidebar.vue'
import type { DocItem, DocTreeGroup, PatientRecord } from '@/views/workstation-v4/types'

const mockRecord: PatientRecord = {
  id: 'VISIT-001',
  visitId: 'VISIT-001',
  instituteId: 'INST-1',
  patientId: 'PAT-1',
  bedNo: '12',
  name: '张三',
  sex: '男',
  age: 45,
  insurance: '医保',
  department: '普外科',
  admissionDate: '2026-03-01',
  dischargeDate: '2026-03-10',
  days: 9,
  diagnosis: '腹痛',
  diagnosisCode: 'R10',
  doctor: '李医生',
  status: 'pending',
}

const mockDocuments: DocItem[] = [
  {
    id: 'adm-1',
    doc_key: 'admission_record::adm-1',
    doc_type: 'admission_record',
    type: 'admission_record',
    label: '入院记录',
    has_content: true,
    content: '主诉：腹痛3天',
    length: 8,
    record_time: '2026-03-01 09:00:00',
  },
  {
    id: 'surg-1',
    doc_key: 'surgery_record::surg-1',
    doc_type: 'surgery_record',
    type: 'surgery_record',
    label: '手术记录',
    has_content: true,
    content: '手术经过：顺利',
    length: 10,
    record_time: '2026-03-02 10:00:00',
  },
]

const mockTree: DocTreeGroup[] = [
  {
    key: 'admission',
    label: '入院记录',
    count: 1,
    children: [
      {
        id: 'adm-1',
        doc_key: 'admission_record::adm-1',
        doc_type: 'admission_record',
        title: '入院记录',
        record_time: '2026-03-01 09:00:00',
        has_content: true,
        length: 8,
      },
    ],
  },
  {
    key: 'surgery',
    label: '手术相关单据',
    count: 1,
    children: [
      {
        id: 'surg-1',
        doc_key: 'surgery_record::surg-1',
        doc_type: 'surgery_record',
        title: '手术记录',
        record_time: '2026-03-02 10:00:00',
        has_content: true,
        length: 10,
      },
    ],
  },
]

describe('DetailSidebar', () => {
  it('优先渲染分组树并展示节点', () => {
    const wrapper = mount(DetailSidebar, {
      props: {
        record: mockRecord,
        documents: mockDocuments,
        documentsTree: mockTree,
        documentsLoading: false,
        activeDocType: '',
      },
      global: {
        stubs: {
          SyncOutlined: true,
          FileTextOutlined: true,
          EyeOutlined: true,
        },
      },
    })

    const text = wrapper.text()
    expect(text).toContain('入院记录')
    expect(text).toContain('手术相关单据')
    expect(text).toContain('手术记录')
  })

  it('点击树节点触发 preview-doc 事件', async () => {
    const wrapper = mount(DetailSidebar, {
      props: {
        record: mockRecord,
        documents: mockDocuments,
        documentsTree: mockTree,
        documentsLoading: false,
        activeDocType: '',
      },
      global: {
        stubs: {
          SyncOutlined: true,
          FileTextOutlined: true,
          EyeOutlined: true,
        },
      },
    })

    const buttons = wrapper.findAll('button')
    const target = buttons.find((btn) => btn.text().includes('手术记录'))
    expect(target).toBeTruthy()
    await target?.trigger('click')

    const emitted = wrapper.emitted('preview-doc')
    expect(emitted).toBeTruthy()
    const payload = ((emitted?.[0] || [])[0] || {}) as { doc_key?: string }
    expect(payload.doc_key).toBe('surgery_record::surg-1')
  })
})
