import { afterEach, describe, expect, it } from 'vitest'
import { enableAutoUnmount, mount } from '@vue/test-utils'
import ReadonlyMedicalOrderTable from '@/views/workstation-v4/customer-sample-validation/ReadonlyMedicalOrderTable.vue'
import type { EditableMedicalRecordDocument } from '@/views/workstation-v4/customer-sample-validation/types'

enableAutoUnmount(afterEach)

function order(key: string, title: string, extra = {}) {
  return {
    key,
    title,
    document_type: 'temporary_order',
    content: title + '：合成项目',
    order_item: title + '合成项目',
    ...extra,
  }
}

describe('ReadonlyMedicalOrderTable', () => {
  it('任一医嘱未完整时在表格上方提示且切换后保留', async () => {
    const wrapper = mount(ReadonlyMedicalOrderTable, {
      props: {
        documents: [
          order('long', '长期医嘱', { projection_incomplete: true }),
          order('temp', '临时医嘱'),
        ],
      },
    })
    const notice = wrapper.get('[data-testid="readonly-medical-order-incomplete"]')
    expect(notice.text()).toContain('医嘱超过查看上限')
    expect(notice.text()).toContain('当前列表未完整')
    expect(notice.text()).toContain('不得据此判断医嘱缺失')
    expect(wrapper.html().indexOf('readonly-medical-order-incomplete')).toBeLessThan(
      wrapper.html().indexOf('<table'),
    )
    await wrapper.findAll('button')[0].trigger('click')
    expect(wrapper.find('[data-testid="readonly-medical-order-incomplete"]').exists()).toBe(true)
  })

  it('医嘱均为 false 或缺省时不显示提示，其他文书不影响', () => {
    const documents: EditableMedicalRecordDocument[] = [
      order('long', '长期医嘱', { projection_incomplete: false }),
      order('temp', '临时医嘱'),
      {
        key: 'course',
        title: '病程记录',
        document_type: 'daily_course_record',
        content: '合成病程',
        projection_incomplete: true,
      },
    ]
    const wrapper = mount(ReadonlyMedicalOrderTable, { props: { documents } })
    expect(wrapper.find('[data-testid="readonly-medical-order-incomplete"]').exists()).toBe(false)
  })

  it('长期临时切换、选中行及 select 事件保持正常', async () => {
    const wrapper = mount(ReadonlyMedicalOrderTable, {
      props: {
        documents: [order('long', '长期医嘱'), order('temp', '临时医嘱')],
        selectedKey: 'temp',
      },
    })
    expect(wrapper.get('tbody tr').classes()).toContain('is-active')
    await wrapper.get('tbody tr').trigger('click')
    await wrapper.findAll('button')[0].trigger('click')
    expect(wrapper.get('tbody tr').text()).toContain('长期')
    await wrapper.get('tbody tr').trigger('click')
    await wrapper.findAll('button')[1].trigger('click')
    expect(wrapper.get('tbody tr').text()).toContain('临时')
    expect(wrapper.emitted('select')).toEqual([['temp'], ['long']])
  })
})
