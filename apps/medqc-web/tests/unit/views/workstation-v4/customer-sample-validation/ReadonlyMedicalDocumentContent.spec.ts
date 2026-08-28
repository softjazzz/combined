import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ReadonlyMedicalDocumentContent from '@/views/workstation-v4/customer-sample-validation/ReadonlyMedicalDocumentContent.vue'

describe('ReadonlyMedicalDocumentContent report rendering', () => {
  it('renders one lab report with metadata and all result rows', () => {
    const wrapper = mount(ReadonlyMedicalDocumentContent, {
      props: {
        document: {
          key: 'labtest_item_report::LAB-1',
          document_type: 'labtest_item_report',
          title: '血常规检验报告',
          content: '检验结果',
          report_metadata: {
            request_datetime: '2026-02-20 21:55:46',
            report_datetime: '2026-02-21 07:45:30',
            specimen: '外周血',
          },
          report_items: [
            {
              item_no: '1',
              item_name: '白细胞计数',
              result: '4.95',
              reference_range: '3.5-9.5',
              unit: '*10^9/L',
            },
            {
              item_no: '2',
              item_name: '血小板计数',
              result: '254',
              reference_range: '125-350',
              unit: '*10^9/L',
            },
          ],
        },
      },
    })

    expect(wrapper.text()).toContain('申请时间')
    expect(wrapper.text()).toContain('2026-02-21 07:45:30')
    expect(wrapper.findAll('tbody tr')).toHaveLength(2)
    expect(wrapper.text()).toContain('白细胞计数')
    expect(wrapper.text()).toContain('血小板计数')
  })

  it('renders grouped examination findings and impression', () => {
    const wrapper = mount(ReadonlyMedicalDocumentContent, {
      props: {
        document: {
          key: 'exam_item_report::EXAM-1',
          document_type: 'exam_item_report',
          title: '胸部CT平扫检查报告',
          content: '检查结果',
          report_items: [
            {
              item_no: '1',
              item_name: '胸部CT平扫',
              findings: '双肺纹理增多。',
              impression: '双肺炎症可能。',
            },
          ],
        },
      },
    })

    expect(wrapper.findAll('.readonly-exam-item')).toHaveLength(1)
    expect(wrapper.text()).toContain('双肺纹理增多')
    expect(wrapper.text()).toContain('双肺炎症可能')
  })

  it('does not render the same structured section twice when the source also returns a 正文 projection', () => {
    const text = '手术时间：2026年07月07日 15:55；麻醉方式：静吸复合全麻。'
    const wrapper = mount(ReadonlyMedicalDocumentContent, {
      props: {
        document: {
          key: 'postsurg_firstcourse_record::5038135||15',
          document_type: 'postsurg_firstcourse_record',
          title: '术后首次病程记录',
          content: text,
          sections: [
            { key: 'new_s_section', label: '新建S章节', text, order_index: 0 },
            { key: 'record_content', label: '正文', text, order_index: 1 },
          ],
        },
      },
    })

    expect(wrapper.findAll('.readonly-medical-document-section')).toHaveLength(1)
    expect(wrapper.findAll('h5').map((node) => node.text())).toEqual(['新建S章节'])
  })
})
