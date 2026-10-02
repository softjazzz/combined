import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'
import QcColumnQuerySettings from '@/views/workstation-v4/components/qc/QcColumnQuerySettings.vue'

describe('双列表列查询偏好', () => {
  beforeEach(() => localStorage.clear())

  it('保存逐列关键词、排序方向，并按用户、场景、列表隔离恢复', async () => {
    const wrapper = mount(QcColumnQuerySettings, {
      props: { userId: 'a', carePhase: 'inpatient', resultView: 'records' },
    })
    await wrapper.get('[data-testid="column-filter-patient"]').setValue('患者甲')
    await wrapper.get('[data-testid="column-sort"]').setValue('score')
    await wrapper.get('[data-testid="column-direction"]').setValue('desc')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('change')?.at(-1)?.[0]).toMatchObject({
      filters: { patient: '患者甲' },
      sort: 'score',
      direction: 'desc',
    })
    for (const props of [
      { userId: 'b' },
      { userId: 'a', carePhase: 'discharged' },
      { carePhase: 'inpatient', resultView: 'defects' as const },
    ]) {
      await wrapper.setProps(props)
      expect(wrapper.emitted('change')?.at(-1)?.[0]).toMatchObject({ filters: {}, sort: '' })
    }
    await wrapper.setProps({ userId: 'a', carePhase: 'inpatient', resultView: 'records' })
    expect(wrapper.emitted('change')?.at(-1)?.[0]).toMatchObject({
      filters: { patient: '患者甲' },
      sort: 'score',
      direction: 'desc',
    })
    await wrapper.get('[data-testid="column-direction"]').setValue('asc')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('change')?.at(-1)?.[0]).toMatchObject({ direction: 'asc' })
    await wrapper.get('button[type="button"]').trigger('click')
    expect(wrapper.emitted('change')?.at(-1)?.[0]).toMatchObject({ filters: {}, sort: '' })
    wrapper.unmount()
  })

  it('缺陷列显隐持久化，恶意或过时存储列被忽略', async () => {
    localStorage.setItem(
      'medqc:qc-column-query:v1:a:inpatient:defects',
      JSON.stringify({ filters: { unknown: 'x' }, sort: 'unknown', hidden: ['unknown', 'source'] }),
    )
    const wrapper = mount(QcColumnQuerySettings, {
      props: { userId: 'a', carePhase: 'inpatient', resultView: 'defects' },
    })
    expect(wrapper.emitted('change')?.at(-1)?.[0]).toEqual({
      filters: {},
      sort: '',
      direction: 'asc',
      hidden: ['source'],
    })
    await wrapper.get('[aria-label="显示来源"]').setValue(true)
    expect(wrapper.emitted('change')?.at(-1)?.[0]).toMatchObject({ hidden: [] })
    expect(
      JSON.parse(localStorage.getItem('medqc:qc-column-query:v1:a:inpatient:defects') || '{}')
        .hidden,
    ).toEqual([])
    wrapper.unmount()
  })
})
