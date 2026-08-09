import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import QcRecordResultListView from '@/views/workstation-v4/QcRecordResultListView.vue'

describe('QcRecordResultListView', () => {
  it.each([
    ['inpatient', '运行病历质控', '固定范围：在院'],
    ['discharged', '终末病历质控', '固定范围：已出院'],
  ] as const)('按 %s 路由 props 渲染正确的病历阶段', (carePhase, title, scope) => {
    const wrapper = mount(QcRecordResultListView, { props: { carePhase } })

    expect(wrapper.text()).toContain(title)
    expect(wrapper.text()).toContain(scope)
    expect(wrapper.text()).toContain('仅展示最新已完成质控结果')
  })

  it('在数据接入前只显示空汇总与禁用筛选壳，不伪造结果', () => {
    const wrapper = mount(QcRecordResultListView, { props: { carePhase: 'inpatient' } })

    expect(wrapper.findAll('.qc-record-result-list-view__metric strong')).toHaveLength(4)
    expect(
      wrapper.findAll('.qc-record-result-list-view__metric strong').map((item) => item.text()),
    ).toEqual(['—', '—', '—', '—'])
    expect(wrapper.findAll('input:disabled')).toHaveLength(2)
    expect(wrapper.find('select:disabled').exists()).toBe(true)
    expect(wrapper.text()).toContain('数据接入后可筛选')
  })

  it('不展示任务、批量、生成、编码、结算或整改入口', () => {
    const wrapper = mount(QcRecordResultListView, { props: { carePhase: 'discharged' } })
    const text = wrapper.text()

    ;['开始质控', '重新质控', '批量', '生成首页', '编码质控', '结算质控', '整改'].forEach(
      (forbidden) => {
        expect(text).not.toContain(forbidden)
      },
    )
  })

  it('详情点击明确提示将在下一闭环接入', async () => {
    const wrapper = mount(QcRecordResultListView, { props: { carePhase: 'inpatient' } })

    await wrapper
      .findComponent({ name: 'QcRecordResultTable' })
      .vm.$emit('open-result', '["H","P","V"]')

    expect(wrapper.text()).toContain('质控结果详情将在下一闭环接入')
  })
})
