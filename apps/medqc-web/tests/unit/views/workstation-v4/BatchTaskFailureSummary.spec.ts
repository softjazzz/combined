import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import Summary from '@/views/workstation-v4/semantic-rules/components/BatchTaskFailureSummary.vue'

describe('失败任务的已保存结果和原因', () => {
  it.each([
    ['model_request', false, '模型请求被拒绝', '不会自动重试'],
    ['model_timeout', true, '模型请求超时', '具备自动重试条件'],
    ['execution_contract', false, '任务冻结合同不满足', '不会自动重试'],
    ['execution_timeout', true, '规则执行超时', '具备自动重试条件'],
    ['SECRET-CATEGORY', undefined, '执行未完成', '自动重试属性未确认'],
  ])('安全展示错误类别 %s 和自动重试属性', (category, retryable, label, retryLabel) => {
    const wrapper = mount(Summary, { props: { job: {
      id: 'failed', status: 'failed', rule_code: 'LX0609', rule_name: '合成', scope: 'all',
      failed_records: [{ error_category: category, retryable, error: 'SECRET-RAW-ERROR' }],
    } } })
    expect(wrapper.text()).toContain(label)
    expect(wrapper.text()).toContain(retryLabel)
    expect(wrapper.text()).not.toContain('SECRET')
  })
  it('无通知或信封也展示部分结果数量和模型传输错误', () => {
    const wrapper = mount(Summary, {
      props: {
        job: {
          id: 'failed',
          status: 'failed',
          rule_code: 'LX0609',
          rule_name: '合成',
          scope: 'all',
          total_records: 1,
          items: [{ rule_id: 'R1', status: 'compliant', is_compliant: true }],
          failed_records: [
            {
              rule_id: 'R2',
              reason_code: 'model_transport_error',
              error_phase: 'evaluate_document',
            },
          ],
        },
      },
    })
    expect(wrapper.text()).toContain('已保存 1 条结果')
    expect(wrapper.text()).toContain('model_transport_error')
    expect(wrapper.text()).toContain('R2')
    expect(wrapper.text()).toContain('evaluate_document')
    expect(wrapper.text()).not.toContain('合规 1')
  })
  it('没有规则结果时展示取材错误，不伪装模型错误', () => {
    const wrapper = mount(Summary, {
      props: {
        job: {
          id: 'material',
          status: 'failed',
          rule_code: 'LX0609',
          rule_name: '合成',
          scope: 'all',
          total_records: 1,
          summary: {
            total_records: 1,
            success_count: 0,
            failed_count: 1,
            issue_records: 0,
            compliant_records: 0,
            total_tokens: 0,
            total_processing_time: 0,
            material_failure: {
              code: 'uncaptured_material_columns',
              stage: 'material_capture',
              message: '材料列信息缺失',
            },
          },
        },
      },
    })
    expect(wrapper.text()).toContain('uncaptured_material_columns')
    expect(wrapper.text()).toContain('材料列信息缺失')
    expect(wrapper.text()).toContain('已保存 0 条结果')
  })
  it('不展示原始异常文本或推断未知根因', () => {
    const wrapper = mount(Summary, { props: { job: { id: 'unknown', status: 'failed',
      rule_code: 'LX0609', rule_name: '合成', scope: 'all', error_message: 'SECRET-RAW-ERROR' } } })
    expect(wrapper.text()).not.toContain('SECRET')
    expect(wrapper.text()).toContain('后台未提供具体错误原因')
  })
  it('成功的历史任务不显示失败提示', () => {
    const wrapper = mount(Summary, {
      props: {
        job: {
          id: 'old',
          status: 'completed',
          rule_code: 'LX0609',
          rule_name: '合成',
          scope: 'all',
          total_records: 1,
        },
      },
    })
    expect(wrapper.text()).toBe('')
  })
})
