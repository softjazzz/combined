import { inject, shallowRef, type InjectionKey } from 'vue'
import { Modal } from 'ant-design-vue'
import type { VNode } from 'vue'

export interface WorkstationConfirmOptions {
  title: string
  content?: string | VNode
  okText?: string
  cancelText?: string
  okType?: 'danger'
  okButtonProps?: { danger?: boolean }
  onOk?: () => unknown
  onCancel?: () => unknown
}

/** 仅管理确认弹窗的展示和回调，不接管业务提交或权限校验。 */
export function createWorkstationConfirmation() {
  const current = shallowRef<WorkstationConfirmOptions>()
  const busy = shallowRef(false)
  const error = shallowRef('')
  const queue: WorkstationConfirmOptions[] = []
  function advance() {
    error.value = ''
    current.value = queue.shift()
  }
  function confirm(options: WorkstationConfirmOptions) {
    queue.push(options)
    if (!current.value) advance()
  }
  async function accept() {
    if (!current.value || busy.value) return
    busy.value = true
    try {
      await current.value.onOk?.()
      advance()
    } catch (reason) {
      error.value = reason instanceof Error ? reason.message : '操作未完成，请重试。'
    } finally {
      busy.value = false
    }
  }
  function cancel() {
    if (!current.value || busy.value) return
    current.value.onCancel?.()
    advance()
  }
  function dispose() {
    // 离开工作台时释放等待确认的 Promise；不取消已经开始的业务操作。
    for (const options of [...(busy.value ? [] : current.value ? [current.value] : []), ...queue]) {
      options.onCancel?.()
    }
    queue.length = 0
    current.value = undefined
  }
  return { current, busy, error, confirm, accept, cancel, dispose }
}

export type WorkstationConfirmation = ReturnType<typeof createWorkstationConfirmation>
export const WORKSTATION_CONFIRMATION: InjectionKey<WorkstationConfirmation> =
  Symbol('工作台确认弹窗')

export function useWorkstationConfirmation() {
  const controller = inject(WORKSTATION_CONFIRMATION, undefined)
  // 旧 Dashboard / demo 入口继续沿用其原有主题；工作台入口由 Layout 提供页面内弹窗。
  return controller ?? { confirm: (options: WorkstationConfirmOptions) => Modal.confirm(options) }
}
