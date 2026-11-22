import { Modal } from 'ant-design-vue'

type ConfirmDialogOptions = Parameters<typeof Modal.confirm>[0] & { danger?: boolean }

export function openConfirmDialog({ danger, ...options }: ConfirmDialogOptions) {
  const config = {
    ...options,
    okText: options.okText ?? '确定',
    cancelText: options.cancelText ?? '取消',
  }
  if (danger) config.okButtonProps = { ...options.okButtonProps, danger: true }

  return Modal.confirm(config) // hygiene-ignore: 唯一权威确认弹窗封装
}

export function confirmAction(options: Omit<ConfirmDialogOptions, 'onOk' | 'onCancel'>): Promise<boolean> {
  return new Promise((resolve) => {
    openConfirmDialog({
      ...options,
      onOk: () => { resolve(true) },
      onCancel: () => { resolve(false) },
      afterClose: () => {
        resolve(false)
        options.afterClose?.()
      },
    })
  })
}
