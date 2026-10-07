import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, provide } from 'vue'
import WorkstationConfirmDialog from '@/components/layout/WorkstationConfirmDialog.vue'
import {
  createWorkstationConfirmation,
  WORKSTATION_CONFIRMATION,
  useWorkstationConfirmation,
} from '@/components/layout/workstationConfirmation'

describe('工作台页面内确认弹窗', () => {
  it('同一操作等待完成期间不重复执行；成功后展示下一项', async () => {
    const controller = createWorkstationConfirmation()
    let finish: (() => void) | undefined
    const onOk = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          finish = resolve
        }),
    )
    controller.confirm({ title: '第一项', onOk })
    controller.confirm({ title: '第二项' })
    const pending = controller.accept()
    await controller.accept()
    controller.cancel()
    expect(onOk).toHaveBeenCalledTimes(1)
    expect(controller.current.value?.title).toBe('第一项')
    finish?.()
    await pending
    expect(controller.current.value?.title).toBe('第二项')
  })

  it('失败保留确认内容和错误，允许重试，不擅自声称成功', async () => {
    const controller = createWorkstationConfirmation()
    const onOk = vi
      .fn()
      .mockRejectedValueOnce(new Error('正式接口拒绝'))
      .mockResolvedValueOnce(undefined)
    controller.confirm({ title: '停止任务', onOk })
    await controller.accept()
    expect(controller.current.value?.title).toBe('停止任务')
    expect(controller.error.value).toBe('正式接口拒绝')
    await controller.accept()
    expect(controller.current.value).toBeUndefined()
  })

  it('取消和离开工作台释放等待确认的回调，不执行确认操作', () => {
    const controller = createWorkstationConfirmation()
    const onCancel = vi.fn()
    const onOk = vi.fn()
    controller.confirm({ title: '第一项', onCancel, onOk })
    controller.confirm({ title: '第二项', onCancel, onOk })
    controller.cancel()
    controller.dispose()
    expect(onCancel).toHaveBeenCalledTimes(2)
    expect(onOk).not.toHaveBeenCalled()
  })

  it('实际父子组件复用同一控制器，保留正文 VNode 和按钮回调', async () => {
    const controller = createWorkstationConfirmation()
    const onOk = vi.fn()
    const Trigger = defineComponent({
      setup() {
        const confirmation = useWorkstationConfirmation()
        return () =>
          h(
            'button',
            {
              onClick: () =>
                confirmation.confirm({
                  title: '执行前确认',
                  content: h('p', '保留原有范围说明'),
                  okText: '继续执行',
                  onOk,
                }),
            },
            '打开确认',
          )
      },
    })
    const Parent = defineComponent({
      setup() {
        provide(WORKSTATION_CONFIRMATION, controller)
        return () => h('div', [h(Trigger), h(WorkstationConfirmDialog, { controller })])
      },
    })
    const wrapper = mount(Parent, {
      global: {
        stubs: {
          'a-modal': {
            props: ['open', 'wrapClassName'],
            template: '<section v-if="open" :class="wrapClassName"><slot /></section>',
          },
          'a-button': { template: '<button><slot /></button>' },
        },
      },
    })
    await wrapper.get('button').trigger('click')
    expect(wrapper.get('.mq-modal').text()).toContain('保留原有范围说明')
    await wrapper
      .findAll('button')
      .find((button) => button.text() === '继续执行')
      ?.trigger('click')
    await flushPromises()
    expect(onOk).toHaveBeenCalledTimes(1)
    expect(wrapper.find('.mq-modal').exists()).toBe(false)
  })
})
