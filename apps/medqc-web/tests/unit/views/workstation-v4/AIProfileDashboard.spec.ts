import { shallowMount, flushPromises } from '@vue/test-utils'
import { afterEach, expect, it, vi } from 'vitest'
import AIProfileDashboard from '@/views/workstation-v4/frontpage/components/AIProfileDashboard.vue'
vi.mock('@ant-design/icons-vue', () =>
  Object.fromEntries(
    [
      'CheckCircleOutlined',
      'ClockCircleOutlined',
      'ExclamationCircleOutlined',
      'FileTextOutlined',
      'QuestionCircleOutlined',
      'ScanOutlined',
      'HeartOutlined',
      'ToolOutlined',
      'MedicineBoxOutlined',
      'ExperimentOutlined',
      'ArrowRightOutlined',
      'RobotOutlined',
      'ThunderboltOutlined',
    ].map((name) => [name, { template: '<i />' }]),
  ),
)
vi.mock('@/utils/auth-token', () => ({ getAccessToken: () => '' }))
vi.mock('ant-design-vue', () => ({
  message: { success: vi.fn(), warning: vi.fn(), error: vi.fn() },
}))
afterEach(() => vi.unstubAllGlobals())
it.each(['material', 'scope'])('切换%s后A响应不能污染B或结束B加载', async (change) => {
  let resolveA!: (value: Response) => void
  const fetcher = vi
    .fn()
    .mockImplementationOnce(
      () =>
        new Promise<Response>((resolve) => {
          resolveA = resolve
        }),
    )
    .mockImplementationOnce(() => new Promise<Response>(() => undefined))
  vi.stubGlobal('fetch', fetcher)
  const wrapper = shallowMount(AIProfileDashboard, {
    props: { medicalText: 'A材料', scopeKey: '["H","A","V"]' },
  })
  await wrapper.get('button').trigger('click')
  await wrapper.setProps(
    change === 'material' ? { medicalText: 'B材料' } : { scopeKey: '["H","B","V"]' },
  )
  expect(wrapper.find('button').exists()).toBe(true)
  await wrapper.get('button').trigger('click')
  resolveA(
    new Response(
      JSON.stringify({
        success: true,
        data: { diagnosis_timeline: [{ diagnosis_name: 'A病例诊断' }] },
      }),
    ),
  )
  await flushPromises()
  expect(wrapper.text()).not.toContain('A病例诊断')
  expect(wrapper.find('button').exists()).toBe(false)
  wrapper.unmount()
})
it('失败不能回填模拟患者画像', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(new Response(JSON.stringify({ success: false }))),
  )
  const wrapper = shallowMount(AIProfileDashboard, { props: { medicalText: '真实材料' } })
  await wrapper.get('button').trigger('click')
  await flushPromises()
  expect(wrapper.text()).not.toContain('胸闷心悸')
  expect(wrapper.text()).not.toContain('85')
  wrapper.unmount()
})
