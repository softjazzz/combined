import { ref, watch, type Ref } from 'vue'
import { businessAgentApi, type BusinessAgentReference } from '@/api/businessAgent'

// 操作卡（复检/专项任务预览）的最新状态只来自确认/回读接口，不改写会话历史中的原卡片。
export function useBusinessAgentActions(sessionId: Ref<string | undefined>, error: Ref<string>) {
  const actionUpdates = ref<Record<string, BusinessAgentReference>>({})
  const actionBusy = ref('')
  function actionView(reference: BusinessAgentReference) {
    return actionUpdates.value[reference.id] || reference
  }
  function canConfirm(reference: BusinessAgentReference) {
    return (
      reference.status === 'previewed' &&
      reference.allowed === true &&
      !!reference.confirmation_hash &&
      !!reference.expires_at &&
      Date.parse(reference.expires_at) > Date.now()
    )
  }
  watch(sessionId, () => {
    actionUpdates.value = {}
    actionBusy.value = ''
  })
  async function confirmAction(reference: BusinessAgentReference) {
    const current = actionView(reference)
    const owner = sessionId.value
    if (!owner || !current.action_id || !current.confirmation_hash) return
    actionBusy.value = reference.id
    error.value = ''
    try {
      const updated = await businessAgentApi.confirmAction(
        owner,
        current.action_id,
        current.confirmation_hash,
      )
      // 切换会话后迟到的响应不写入新会话。
      if (owner === sessionId.value)
        actionUpdates.value = { ...actionUpdates.value, [reference.id]: updated }
    } catch (cause) {
      if (owner !== sessionId.value) return
      const status = (cause as { response?: { status?: number } })?.response?.status
      error.value =
        status === 423
          ? '当前环境未启用助手创建质控任务，本次未提交任务；如需复检请在正式任务页面发起。'
          : status === 409
            ? '授权、范围、规则或材料状态已变化，预览已失效；请重新发起预览。本次未提交任务。'
            : '确认请求未完成，未能确认是否已提交；请点击刷新查看该操作状态，不要重复发起新预览。'
    } finally {
      actionBusy.value = ''
    }
  }
  async function refreshAction(reference: BusinessAgentReference) {
    const current = actionView(reference)
    const owner = sessionId.value
    if (!owner || !current.action_id) return
    actionBusy.value = reference.id
    error.value = ''
    try {
      const updated = await businessAgentApi.readAction(owner, current.action_id)
      if (owner === sessionId.value)
        actionUpdates.value = { ...actionUpdates.value, [reference.id]: updated }
    } catch {
      if (owner !== sessionId.value) return
      error.value = '任务进度读取失败；任务状态以正式任务列表为准。'
    } finally {
      actionBusy.value = ''
    }
  }
  return { actionBusy, actionView, canConfirm, confirmAction, refreshAction }
}
