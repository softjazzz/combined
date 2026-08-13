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
    ).toBe('false')
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
