import { Modal } from 'ant-design-vue'
import { h } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import { confirmAction, openConfirmDialog } from './confirmDialog'

vi.mock('ant-design-vue', () => ({ Modal: { confirm: vi.fn() } }))

const confirm = vi.mocked(Modal.confirm)

describe('统一确认弹窗', () => {
  it('使用中文默认按钮，并将内容、回调和 Modal 实例透传', () => {
    const dialog = { destroy: vi.fn(), update: vi.fn() }
    confirm.mockReturnValue(dialog)
    const content = h('p', '范围说明')
    const onOk = vi.fn()

    expect(openConfirmDialog({ title: '执行前确认', content, onOk })).toBe(dialog)
    expect(confirm).toHaveBeenCalledWith({ title: '执行前确认', content, onOk, okText: '确定', cancelText: '取消' })
  })

  it('保留自定义按钮文案和属性，确认危险操作时返回 true', async () => {
    const result = confirmAction({ title: '确认覆盖', danger: true, okText: '覆盖', okButtonProps: { ghost: true } })
    const options = confirm.mock.lastCall![0]

    expect(options).toMatchObject({ okText: '覆盖', cancelText: '取消', okButtonProps: { ghost: true, danger: true } })
    options.onOk?.()
    await expect(result).resolves.toBe(true)
  })

  it('取消或关闭弹窗时返回 false', async () => {
    const cancelled = confirmAction({ title: '确认操作' })
    confirm.mock.lastCall![0].onCancel?.()
    await expect(cancelled).resolves.toBe(false)

    const closed = confirmAction({ title: '确认操作' })
    confirm.mock.lastCall![0].afterClose?.()
    await expect(closed).resolves.toBe(false)
  })
})
