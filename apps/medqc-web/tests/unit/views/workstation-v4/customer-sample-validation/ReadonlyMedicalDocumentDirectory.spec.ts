import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ReadonlyMedicalDocumentDirectory from '@/views/workstation-v4/customer-sample-validation/ReadonlyMedicalDocumentDirectory.vue'
import type { EditableMedicalRecordDocument } from '@/views/workstation-v4/customer-sample-validation/types'

const documents: EditableMedicalRecordDocument[] = [
  {
    key: 'admission-1',
    document_type: 'admission_record',
    title: '入院记录',
    record_time: '2026-07-29 08:00:00',
    content: '入院记录正文',
  },
  {
    key: 'first-course-1',
    document_type: 'first_course_record',
    title: '首次病程记录',
    record_time: '2026-07-29 09:00:00',
    content: '首次病程记录正文',
  },
  {
    key: 'order-drug-1',
    source_table: 'inpat_drug_order',
    document_type: 'inpat_drug_order',
    title: '阿司匹林肠溶片',
    order_item: '阿司匹林肠溶片',
    content: '',
  },
  {
    key: 'order-exam-1',
    source_table: 'inpat_nondrug_order',
    document_type: 'inpat_nondrug_order',
    title: '头颅CT平扫',
    order_item: '头颅CT平扫',
    content: '',
  },
]

describe('ReadonlyMedicalDocumentDirectory', () => {
  it('活动PDF操作文书显示原题名、原日期和来源页码', () => {
    const wrapper = mount(ReadonlyMedicalDocumentDirectory, {
      props: {
        documents: [{ key: 'pdf-active', document_type: 'daily_course_record', title: '气管插管操作记录',
          content: '合成操作原文', record_time: '2026-08-10T18:21+08:00',
          pdf_source_file_id: 'SYN-PDF', pdf_source_pages: [4, 5] }],
        selectedKey: 'pdf-active',
      },
    })
    expect(wrapper.get('.record-document-item strong').text()).toBe('气管插管操作记录')
    expect(wrapper.get('.readonly-medical-document-new').text()).toBe('new')
    expect(wrapper.get('.readonly-medical-document-new').attributes('title')).toBe('新增文书')
    expect(wrapper.get('.record-document-item small').text()).toContain('PDF第4–5页')
    expect(wrapper.get('.record-document-item small').text()).toContain('08月10日')
    wrapper.unmount()
  })

  it.each(['daily_course_record', 'consultation_record'])(
    '%s仅正式补入文书显示new，原PG和候选不标记',
    async (documentType) => {
      const pgTitle = documentType === 'daily_course_record' ? '日常病程记录' : '请会诊执行记录'
      const wrapper = mount(ReadonlyMedicalDocumentDirectory, {
        props: {
          documents: [
            { key: 'pg', document_type: documentType, title: pgTitle, content: '原PG正文' },
            { key: 'added', document_type: documentType, title: '新增文书', content: '新增正文', pdf_source_file_id: 'SYN-PDF' },
            { key: 'pending', document_type: 'pdf_candidate', title: '候选文书', content: '候选正文', pdf_source_file_id: 'SYN-PDF' },
          ],
          selectedKey: 'added',
        },
      })
      expect(wrapper.findAll('.readonly-medical-document-new')).toHaveLength(1)
      const pg = wrapper.findAll('.record-document-item').find((item) => item.get('strong').text() === pgTitle)
      expect(pg).toBeDefined()
      expect(pg!.find('.readonly-medical-document-new').exists()).toBe(false)
      await wrapper.get('[data-testid="record-document-group-toggle-pdf_review"]').trigger('click')
      expect(wrapper.text()).toContain('候选文书')
      expect(wrapper.findAll('.readonly-medical-document-new')).toHaveLength(1)
      await wrapper.findAll('.record-document-item').find((item) => item.text().includes('新增文书'))!.trigger('click')
      expect(wrapper.emitted('select')).toEqual([['added']])
      wrapper.unmount()
    },
  )

  it('同一文书只占一项，PDF版本折叠在原文书下并可切换', async () => {
    const original = {
      key: 'original',
      document_type: 'consultation_record',
      title: '会诊记录',
      content: '原文书正文',
    }
    const pdf: EditableMedicalRecordDocument = {
      key: 'pdf',
      document_type: 'pdf_candidate',
      title: '请会诊执行记录（PDF待核对）',
      content: 'PDF对照正文',
      pdf_review_parent_key: 'original',
      pdf_review_relation: 'same_content',
      pdf_source_pages: [20, 20],
    }
    const wrapper = mount(ReadonlyMedicalDocumentDirectory, {
      props: { documents: [original, pdf], selectedKey: 'original' },
    })
    expect(wrapper.get('.readonly-medical-document-directory-head span').text()).toBe('1 / 1')
    expect(wrapper.findAll('.record-document-item')).toHaveLength(1)
    expect(wrapper.find('[data-testid="pdf-version-pdf"]').exists()).toBe(false)
    await wrapper.get('[data-testid="pdf-versions-toggle-original"]').trigger('click')
    expect(wrapper.get('[data-testid="pdf-version-pdf"]').text()).toContain('正文一致')
    expect(wrapper.get('[data-testid="pdf-version-pdf"]').text()).toContain('第20页')
    await wrapper.get('[data-testid="pdf-version-pdf"]').trigger('click')
    expect(wrapper.emitted('select')).toEqual([['pdf']])
    wrapper.unmount()
  })

  it('未对应或悬空关联的PDF单列待核对，搜索PDF正文仍能找到父文书', async () => {
    const original = {
      key: 'original',
      document_type: 'consultation_record',
      title: '会诊记录',
      content: '原文书正文',
    }
    const linked: EditableMedicalRecordDocument = {
      key: 'pdf-linked',
      document_type: 'pdf_candidate',
      title: 'PDF版本',
      content: '候选独有检索词',
      pdf_review_parent_key: 'original',
      pdf_review_relation: 'version_difference',
    }
    const orphan: EditableMedicalRecordDocument = {
      key: 'pdf-orphan',
      document_type: 'pdf_candidate',
      title: '未对应PDF',
      content: '另一份正文',
      pdf_review_parent_key: 'missing',
      pdf_review_relation: 'unmatched',
    }
    const wrapper = mount(ReadonlyMedicalDocumentDirectory, {
      props: { documents: [original, linked, orphan], selectedKey: 'original' },
    })
    expect(wrapper.get('[data-testid="record-document-group-toggle-pdf_review"]').text()).toContain(
      'PDF待核对',
    )
    expect(wrapper.get('.readonly-medical-document-directory-head span').text()).toBe('2 / 2')
    await wrapper.get('[data-testid="record-document-search"]').setValue('候选独有检索词')
    expect(wrapper.find('[data-testid="pdf-version-pdf-linked"]').exists()).toBe(true)
    expect(wrapper.findAll('.record-document-item')).toHaveLength(1)
    await wrapper.get('[data-testid="record-document-search"]').setValue('')
    await wrapper.setProps({ selectedKey: 'pdf-linked' })
    expect(
      wrapper.get('[data-testid="pdf-versions-toggle-original"]').attributes('aria-expanded'),
    ).toBe('true')
    wrapper.unmount()
  })

  it('入院记录与首次病程记录直接并列在一级目录下', () => {
    const wrapper = mount(ReadonlyMedicalDocumentDirectory, {
      props: { documents, selectedKey: 'admission-1' },
    })

    const admissionGroup = wrapper.get('[data-testid="record-document-group-toggle-admission"]')
    expect(admissionGroup.text()).toContain('入院与首次病程')
    expect(admissionGroup.text()).toContain('2')
    expect(
      wrapper.find('[data-testid="record-document-group-toggle-admission.record"]').exists(),
    ).toBe(false)
    expect(
      wrapper.find('[data-testid="record-document-group-toggle-admission.first"]').exists(),
    ).toBe(false)
    expect(wrapper.text()).toContain('入院记录')
    expect(wrapper.text()).toContain('首次病程记录')
  })

  it('将多条医嘱折叠为一个目录项，点击后选择真实医嘱 key', async () => {
    const wrapper = mount(ReadonlyMedicalDocumentDirectory, {
      props: { documents, selectedKey: 'order-drug-1' },
    })

    const orderItem = wrapper.get('[data-testid="record-document-order-group"]')
    expect(wrapper.findAll('[data-testid="record-document-order-group"]')).toHaveLength(1)
    expect(orderItem.text()).toContain('医嘱（2条）')
    expect(wrapper.text()).not.toContain('阿司匹林肠溶片')
    expect(wrapper.text()).not.toContain('头颅CT平扫')

    await orderItem.trigger('click')
    expect(wrapper.emitted('select')).toEqual([['order-drug-1']])

    await wrapper.setProps({ selectedKey: 'order-exam-1' })
    expect(orderItem.classes()).toContain('is-active')
  })

  it('在搜索和医嘱筛选下仍显示唯一医嘱入口', async () => {
    const wrapper = mount(ReadonlyMedicalDocumentDirectory, {
      props: { documents, selectedKey: 'order-drug-1' },
    })

    await wrapper.get('[data-testid="record-document-search"]').setValue('头颅')
    expect(wrapper.get('[data-testid="record-document-order-group"]').text()).toContain(
      '医嘱（1条）',
    )
    await wrapper.get('[data-testid="record-document-order-group"]').trigger('click')
    expect(wrapper.emitted('select')).toEqual([['order-exam-1']])

    await wrapper.get('[data-testid="record-document-search"]').setValue('')
    await wrapper.get('[data-testid="record-document-filter-order"]').trigger('click')
    expect(wrapper.findAll('[data-testid="record-document-order-group"]')).toHaveLength(1)
    expect(wrapper.get('[data-testid="record-document-order-group"]').text()).toContain(
      '医嘱（2条）',
    )
  })

  it('默认仅展开当前选中文书所在分组，点击一级分组可切换展开状态', async () => {
    const wrapper = mount(ReadonlyMedicalDocumentDirectory, {
      props: { documents, selectedKey: 'admission-1' },
    })

    const admissionToggle = wrapper.get('[data-testid="record-document-group-toggle-admission"]')
    const orderToggle = wrapper.get('[data-testid="record-document-group-toggle-order"]')
    expect(admissionToggle.attributes('aria-expanded')).toBe('true')
    expect(orderToggle.attributes('aria-expanded')).toBe('false')
    expect(wrapper.find('[data-testid="record-document-order-group"]').exists()).toBe(false)

    await orderToggle.trigger('click')
    expect(orderToggle.attributes('aria-expanded')).toBe('true')
    expect(wrapper.get('[data-testid="record-document-order-group"]').text()).toContain(
      '医嘱（2条）',
    )

    await admissionToggle.trigger('click')
    expect(admissionToggle.attributes('aria-expanded')).toBe('false')
    expect(wrapper.text()).not.toContain('入院记录正文')
  })

  it('搜索时自动展开命中分组，切换当前文书时自动展开其分组', async () => {
    const wrapper = mount(ReadonlyMedicalDocumentDirectory, {
      props: { documents, selectedKey: 'admission-1' },
    })

    await wrapper.get('[data-testid="record-document-search"]').setValue('头颅')
    expect(
      wrapper.get('[data-testid="record-document-group-toggle-order"]').attributes('aria-expanded'),
    ).toBe('true')
    expect(wrapper.find('[data-testid="record-document-order-group"]').exists()).toBe(true)

    await wrapper.get('[data-testid="record-document-search"]').setValue('')
    await wrapper.setProps({ selectedKey: 'order-exam-1' })
    expect(
      wrapper.get('[data-testid="record-document-group-toggle-order"]').attributes('aria-expanded'),
    ).toBe('true')
    expect(
      wrapper
        .get('[data-testid="record-document-group-toggle-admission"]')
        .attributes('aria-expanded'),
    ).toBe('true')
  })

  it('切换病历时清空搜索词，点击医嘱筛选自动展开医嘱组，切换选中文书保留已展开分组', async () => {
    const wrapper = mount(ReadonlyMedicalDocumentDirectory, {
      props: { documents, selectedKey: 'admission-1', loading: false },
    })

    // 点击医嘱筛选标签立即展开医嘱分组
    await wrapper.get('[data-testid="record-document-filter-order"]').trigger('click')
    expect(
      wrapper.get('[data-testid="record-document-group-toggle-order"]').attributes('aria-expanded'),
    ).toBe('true')
    expect(wrapper.find('[data-testid="record-document-order-group"]').exists()).toBe(true)

    // 切回全部后，切换 selectedKey 会叠加展开目标分组而不是收起用户已展开的分组
    await wrapper.get('[data-testid="record-document-filter-all"]').trigger('click')
    await wrapper.setProps({ selectedKey: 'order-exam-1' })
    expect(
      wrapper.get('[data-testid="record-document-group-toggle-admission"]').attributes('aria-expanded'),
    ).toBe('true')
    expect(
      wrapper.get('[data-testid="record-document-group-toggle-order"]').attributes('aria-expanded'),
    ).toBe('true')

    // 输入搜索词后，loading 变为 true 时自动清空搜索词
    await wrapper.get('[data-testid="record-document-search"]').setValue('入院')
    expect((wrapper.get('[data-testid="record-document-search"]').element as HTMLInputElement).value).toBe('入院')
    await wrapper.setProps({ loading: true })
    await wrapper.setProps({ loading: false })
    expect((wrapper.get('[data-testid="record-document-search"]').element as HTMLInputElement).value).toBe('')

    // 文书集合整体切换为另一份病历时也清空搜索词
    await wrapper.get('[data-testid="record-document-search"]').setValue('首次')
    await wrapper.setProps({
      documents: [
        {
          key: 'record-2-admission',
          document_type: 'admission_record',
          title: '入院记录',
          content: '第二份病历正文',
        },
      ],
      selectedKey: 'record-2-admission',
    })
    expect((wrapper.get('[data-testid="record-document-search"]').element as HTMLInputElement).value).toBe('')
    wrapper.unmount()
  })

  it('PDF版本连续页码合并为区间且切换父文书时重置展开态', async () => {
    const docA: EditableMedicalRecordDocument = {
      key: 'doc-a',
      document_type: 'consultation_record',
      title: '会诊记录',
      content: '正文A',
    }
    const pdfA: EditableMedicalRecordDocument = {
      key: 'pdf-a',
      document_type: 'pdf_candidate',
      title: 'PDF版本A',
      content: 'PDF正文A',
      pdf_review_parent_key: 'doc-a',
      pdf_review_relation: 'version_difference',
      pdf_source_pages: [1, 2, 3, 4],
    }
    const pdfB: EditableMedicalRecordDocument = {
      key: 'pdf-b',
      document_type: 'pdf_candidate',
      title: 'PDF版本B',
      content: 'PDF正文B',
      pdf_review_parent_key: 'doc-a',
      pdf_review_relation: 'same_content',
      pdf_source_pages: [1, 2, 3, 5, 6],
    }
    const wrapper = mount(ReadonlyMedicalDocumentDirectory, {
      props: { documents: [docA, pdfA, pdfB], selectedKey: 'doc-a' },
    })

    await wrapper.get('[data-testid="pdf-versions-toggle-doc-a"]').trigger('click')
    expect(wrapper.get('[data-testid="pdf-version-pdf-a"]').text()).toContain('第1–4页')
    expect(wrapper.get('[data-testid="pdf-version-pdf-a"]').text()).not.toContain('1–2–3–4')
    expect(wrapper.get('[data-testid="pdf-version-pdf-b"]').text()).toContain('第1–3、5–6页')

    // 切换父文书 key 后应重置 PDF 版本折叠状态
    await wrapper.setProps({
      documents: [
        { ...docA, key: 'doc-b' },
        { ...pdfA, key: 'pdf-c', pdf_review_parent_key: 'doc-b' },
      ],
      selectedKey: 'doc-b',
    })
    expect(
      wrapper.get('[data-testid="pdf-versions-toggle-doc-b"]').attributes('aria-expanded'),
    ).toBe('false')
    wrapper.unmount()
  })

  it('摘要文书标记有正文时允许点击并按需读取', async () => {
    const summaryDocument: EditableMedicalRecordDocument = {
      key: 'senior-summary',
      source_table: 'senior_course_record',
      document_type: 'senior_course_record',
      title: '上级医师查房记录',
      record_time: '2026-07-16 10:30:02',
      content: '',
      has_content: true,
      content_loaded: false,
      execution_domain: 'course',
    }
    const wrapper = mount(ReadonlyMedicalDocumentDirectory, {
      props: { documents: [summaryDocument], selectedKey: '' },
    })

    const item = wrapper.get('.record-document-item')
    expect(item.attributes('disabled')).toBeUndefined()
    await item.trigger('click')
    expect(wrapper.emitted('select')).toEqual([['senior-summary']])
  })
})
