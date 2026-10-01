import { flushPromises, shallowMount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
const mocks = vi.hoisted(() => ({ list: vi.fn() }))
vi.mock('@/api/scoring', () => ({ listScoringStandards: mocks.list }))
import TaskScoreFilterFields from '@/components/qc/TaskScoreFilterFields.vue'

const mountFields = (scene: 'running' | 'final' | 'outpatient' = 'running') =>
  shallowMount(TaskScoreFilterFields, {
    props: { scene, modelValue: { standard_id: 'S', score_min: 0, score_max: 90 } },
    global: {
      stubs: {
        'a-form-item': { template: '<div><slot /></div>' },
        'a-select': { props: ['options'], template: '<div />' },
        'a-input-number': { props: ['value'], template: '<input />' },
      },
    },
  })
describe('任务评分范围', () => {
  it('读取同场景已启用标准并保留真实零分上下界', async () => {
    mocks.list.mockResolvedValue({
      success: true,
      data: {
        items: [
          { id: 'S', name: '合成标准', rule_set_key: 'luxian_0609_qc_v1' },
          { id: 'OLD', name: '旧标准', rule_set_key: 'legacy' },
        ],
      },
    })
    const wrapper = mountFields()
    await flushPromises()
    expect(mocks.list).toHaveBeenLastCalledWith({ scene: 'running', status: 'active' })
    expect(wrapper.findAll('input')).toHaveLength(2)
    const vm = wrapper.vm as unknown as {
      update: (key: string, value: unknown) => void
      selectStandard: (value?: string) => void
    }
    vm.update('score_min', 0)
    expect(wrapper.emitted('update:modelValue')?.[0]?.[0]).toEqual({
      standard_id: 'S',
      score_min: 0,
      score_max: 90,
    })
    vm.selectStandard()
    expect(wrapper.emitted('update:modelValue')?.[1]?.[0]).toBeUndefined()
  })
  it('门急诊不读取无来源评分标准', async () => {
    mocks.list.mockClear()
    mountFields('outpatient')
    await flushPromises()
    expect(mocks.list).not.toHaveBeenCalled()
  })
})
