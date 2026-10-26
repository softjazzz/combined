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
  it('同名医嘱显示来源完整医嘱号，未提供编号时不编造序号', () => {
    const wrapper = mount(ReadonlyMedicalOrderTable, {
      props: {
        documents: [
          order('a', '临时医嘱', { order_item: '血常规', order_id: 'safe-visit||68' }),
          order('b', '临时医嘱', { order_item: '血常规', order_id: 'safe-visit||91' }),
          order('c', '临时医嘱', { order_item: '血常规', order_id: 'safe-visit||112' }),
          order('unknown', '临时医嘱', { order_item: '血常规' }),
        ],
      },
    })
    const column = wrapper.findAll('th').findIndex((h) => h.text() === '医嘱号')
    expect(column).toBeGreaterThan(-1)
    expect(wrapper.findAll('tbody tr').map((r) => r.findAll('td')[column].text())).toEqual([
      'safe-visit||68',
      'safe-visit||91',
      'safe-visit||112',
      '-',
    ])
  })
  it('按实际医嘱类型、状态和项目关键词组合筛选，重置保留长临切换', async () => {
    const wrapper = mount(ReadonlyMedicalOrderTable, {
      props: {
        documents: [
          order('drug-a', '临时医嘱', {
            order_category: '用药',
            order_item: '示例药品甲',
            order_status: '停止',
          }),
          order('drug-b', '临时医嘱', {
            order_category: '用药',
            order_item: '示例药品乙',
            order_status: '新开',
          }),
          order('care', '临时医嘱', {
            order_category: '护理',
            order_item: 'II级护理',
            order_status: '新开',
          }),
          order('long', '长期医嘱', {
            order_category: '用药',
            order_item: '示例药品甲',
            order_status: '停止',
          }),
        ],
      },
    })
    await wrapper.get('[aria-label="医嘱类型筛选"]').setValue('用药')
    expect(wrapper.findAll('tbody tr')).toHaveLength(2)
    await wrapper.get('[aria-label="医嘱状态筛选"]').setValue('停止')
    await wrapper.get('[aria-label="搜索医嘱项目"]').setValue('  甲  ')
    expect(wrapper.findAll('tbody tr')).toHaveLength(1)
    expect(wrapper.get('tbody tr').text()).toContain('示例药品甲')
    expect(wrapper.get('[role="status"]').text()).toContain('1 / 3')
    await wrapper.findAll('button')[0].trigger('click')
    expect(wrapper.get('tbody tr').text()).toContain('示例药品甲')
    await wrapper.get('[aria-label="重置医嘱筛选"]').trigger('click')
    expect(wrapper.findAll('tbody tr')).toHaveLength(1)
    expect(wrapper.findAll('button')[0].classes()).toContain('is-active')
  })

  it('无匹配时明确提示且不隐藏资料截断提示，切换病历清除筛选', async () => {
    const wrapper = mount(ReadonlyMedicalOrderTable, {
      props: {
        documents: [
          order('first', '临时医嘱', { order_category: '护理', projection_incomplete: true }),
        ],
      },
    })
    await wrapper.get('[aria-label="搜索医嘱项目"]').setValue('不存在的项目')
    expect(wrapper.get('tbody').text()).toContain('暂无符合筛选条件的医嘱')
    expect(wrapper.find('[data-testid="readonly-medical-order-incomplete"]').exists()).toBe(true)
    await wrapper.setProps({ documents: [order('next', '临时医嘱', { order_category: '检验' })] })
    expect((wrapper.get('[aria-label="搜索医嘱项目"]').element as HTMLInputElement).value).toBe('')
    expect(wrapper.get('tbody').text()).toContain('检验')
  })
  it('分列显示计划结束与实际停止，医院时区转换后不互相补值', () => {
    const wrapper = mount(ReadonlyMedicalOrderTable, {
      props: {
        documents: [
          order('planned', '临时医嘱', {
            order_planned_end_time: '2026-09-22T14:00:00+00:00',
          }),
        ],
      },
    })
    const headers = wrapper.findAll('th').map((h) => h.text())
    const cells = wrapper
      .findAll('tbody tr')[0]
      .findAll('td')
      .map((c) => c.text())
    expect(headers).toContain('计划结束时间')
    expect(headers).toContain('实际停止时间')
    expect(cells[headers.indexOf('计划结束时间')]).toBe('2026-09-22 22:00:00')
    expect(cells[headers.indexOf('实际停止时间')]).toBe('未返回')
  })
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
