import { computed, onBeforeUnmount, ref, watch, type Ref } from 'vue'

// 智能助手面板全站只保留一个：页面自带带病例上下文的面板时，布局层的全局助手让位。
const localCount = ref(0)

export const hasLocalAssistant = computed(() => localCount.value > 0)

// 页面在自己的助手面板可用（例如已选中病例）时登记；条件消失或页面卸载时自动注销。
export function useLocalAssistantRegistration(active: Ref<boolean>) {
  let registered = false
  const sync = (value: boolean) => {
    if (value === registered) return
    registered = value
    localCount.value += value ? 1 : -1
  }
  watch(active, sync, { immediate: true })
  onBeforeUnmount(() => sync(false))
}
