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
  it('目录在标题下显示后端来源版本与未选限制，保持版本定位键', async () => {
    const doc = { ...mockDocuments[1], doc_key: 'surgery_record::R::held-v1', version_id: 'held-v1', material_source_label: 'clinical', material_selected: false, material_rule_usable: false, material_notice: '状态待核（HELD）' }
    const tree = [{ ...mockTree[1], children: [{ ...mockTree[1].children[0], doc_key: doc.doc_key }] }]
    const wrapper = mount(DetailSidebar, { props: { record: mockRecord, documents: [doc], documentsTree: tree, documentsLoading: false, activeDocType: '' }, global: { stubs: { SyncOutlined: true, FileTextOutlined: true, EyeOutlined: true, CaretRightOutlined: true } } })
    expect(wrapper.text()).toContain('clinical · 版本：held-v1 · 仅展示，未选用 · 规则暂不可用 · 状态待核（HELD）')
    await wrapper.findAll('button').find(button => button.text().includes('版本：held-v1'))?.trigger('click')
    expect(wrapper.emitted('preview-doc')?.[0]?.[0]).toMatchObject({ doc_key: doc.doc_key, material_selected: false })
  })

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
          CaretRightOutlined: true,
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
          CaretRightOutlined: true,
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

  it('独立展示查房记录和日常病程记录分组', () => {
    const tree: DocTreeGroup[] = [
      {
        key: 'round_course',
        label: '查房记录',
        count: 1,
        children: [
          {
            id: 'round-1',
            doc_key: 'course::round-1',
            doc_type: 'course_note',
            title: '2026-03-03 主任医师查房记录',
            record_time: '2026-03-03 09:00:00',
            has_content: true,
            length: 18,
          },
        ],
      },
      {
        key: 'daily_course',
        label: '日常病程记录',
        count: 1,
        children: [
          {
            id: 'daily-1',
            doc_key: 'course::daily-1',
            doc_type: 'daily_course_note',
            title: '2026-03-04 日常病程记录',
            record_time: '2026-03-04 10:00:00',
            has_content: true,
            length: 16,
          },
        ],
      },
    ]

    const wrapper = mount(DetailSidebar, {
      props: {
        record: mockRecord,
        documents: [],
        documentsTree: tree,
        documentsLoading: false,
        activeDocType: '',
      },
      global: {
        stubs: {
          SyncOutlined: true,
          FileTextOutlined: true,
          EyeOutlined: true,
          CaretRightOutlined: true,
        },
      },
    })

    const text = wrapper.text()
    expect(text).toContain('查房记录')
    expect(text).toContain('主任医师查房记录')
    expect(text).toContain('日常病程记录')
  })

  it('多条同类型文书按日期和标题匹配，避免打开错正文', async () => {
    const documents: DocItem[] = [
      {
        id: 'round-0415',
        doc_key: 'senior_course_record::round-0415',
        doc_type: 'senior_course_record',
        type: 'senior_course_record',
        label: '王春萌主治医师查房记录',
        has_content: true,
        content: '04-15 查房正文',
        length: 12,
        record_time: '2026-04-15 08:35:46',
      },
      {
        id: 'round-0419',
        doc_key: 'senior_course_record::round-0419',
        doc_type: 'senior_course_record',
        type: 'senior_course_record',
        label: '王春萌主治医师查房记录',
        has_content: true,
        content: '04-19 查房正文',
        length: 12,
        record_time: '2026-04-19 08:31:00',
      },
    ]
    const tree: DocTreeGroup[] = [
      {
        key: 'round_course',
        label: '查房记录',
        count: 1,
        children: [
          {
            id: 'tree-node-0419',
            doc_key: 'legacy-tree-key-0419',
            doc_type: 'senior_course_record',
            title: '2026-04-19 王春萌主治医师查房记录',
            record_time: '2026-04-19 08:31:00',
            has_content: true,
            length: 12,
          },
        ],
      },
    ]

    const wrapper = mount(DetailSidebar, {
      props: {
        record: mockRecord,
        documents,
        documentsTree: tree,
        documentsLoading: false,
        activeDocType: '',
      },
      global: {
        stubs: {
          SyncOutlined: true,
          FileTextOutlined: true,
          EyeOutlined: true,
          CaretRightOutlined: true,
        },
      },
    })

    const target = wrapper
      .findAll('button')
      .find((btn) => btn.text().includes('王春萌主治医师查房记录'))
    expect(target).toBeTruthy()
    await target?.trigger('click')

    const emitted = wrapper.emitted('preview-doc')
    expect(emitted).toBeTruthy()
    const payload = ((emitted?.[0] || [])[0] || {}) as { doc_key?: string }
    expect(payload.doc_key).toBe('senior_course_record::round-0419')
  })

  it('对截断投影文书仅显示必要的更多标记，不把它当资料缺失', () => {
    const documents: DocItem[] = [
      {
        id: 'lab-1',
        doc_key: 'labtest_item_report::lab-1',
        doc_type: 'labtest_item_report',
        type: 'labtest_item_report',
        label: '血常规检验报告',
        has_content: true,
        content: '白细胞计数：4.5',
        length: 10,
        record_time: '2026-08-01 09:00:00',
        projection_incomplete: true,
        projection_notice: '已展示3条，仍有更多。',
      },
    ]
    const tree: DocTreeGroup[] = [
      {
        key: 'lab_results',
        label: '检验报告',
        count: 1,
        children: [
          {
            id: 'lab-1',
            doc_key: 'labtest_item_report::lab-1',
            doc_type: 'labtest_item_report',
            title: '血常规检验报告',
            record_time: '2026-08-01 09:00:00',
            has_content: true,
            length: 10,
            projection_incomplete: true,
            projection_notice: '已展示3条，仍有更多。',
          },
        ],
      },
    ]

    const wrapper = mount(DetailSidebar, {
      props: {
        record: mockRecord,
        documents,
        documentsTree: tree,
        documentsLoading: false,
        activeDocType: '',
      },
      global: {
        stubs: {
          SyncOutlined: true,
          FileTextOutlined: true,
          EyeOutlined: true,
          CaretRightOutlined: true,
        },
      },
    })

    expect(wrapper.text()).toContain('更多')
    expect(wrapper.text()).not.toContain('资料缺失')
  })
})
