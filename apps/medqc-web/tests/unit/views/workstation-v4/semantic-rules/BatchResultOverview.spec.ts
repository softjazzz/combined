import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import BatchResultOverview from '@/views/workstation-v4/semantic-rules/components/BatchResultOverview.vue'

describe('BatchResultOverview', () => {
  it('没有展示模型时不渲染结果总览', () => {
    const wrapper = mount(BatchResultOverview, {
      props: { model: null },
    })

    expect(wrapper.text()).toBe('')
  })

  it('只按父组件提供的展示模型渲染任务、统计和状态分布', () => {
    const wrapper = mount(BatchResultOverview, {
      props: {
        model: {
          title: '泸县0609质控点验证 v1',
          statusClass: 'status-completed',
          statusText: '已完成',
          createdAtText: '2026-07-31 10:00:00',
          finishedAtText: '2026-07-31 10:02:00',
          recordCount: 2,
          customerRuleCount: 49,
          resultCount: 98,
          outcomeText: '任务已完成，可查看结果。',
          scopeText: '未限定，执行全量 0609 质控点。',
          statusPills: [
            { key: 'non_compliant', label: '确定问题', value: 9, className: 'is-danger' },
            { key: 'compliant', label: '合规', value: 5, className: 'is-success' },
          ],
        },
      },
    })

    expect(wrapper.text()).toContain('泸县0609质控点验证 v1')
    expect(wrapper.text()).toContain('已完成')
    expect(wrapper.text()).toContain('创建时间：2026-07-31 10:00:00')
    expect(wrapper.text()).toContain('执行病历：2 份')
    expect(wrapper.text()).toContain('客户质控点')
    expect(wrapper.text()).toContain('49')
    expect(wrapper.text()).toContain('结果')
    expect(wrapper.text()).toContain('98')
    expect(wrapper.text()).toContain('确定问题 9')
    expect(wrapper.find('.result-review-status-pill.is-danger').exists()).toBe(true)
  })
})
