import { computed, onScopeDispose, ref, watch } from 'vue'

const MINIMUM_LOADING_MS = 2000

export function useMinimumLoading(loading: () => boolean, isOpen: () => boolean) {
  const holding = ref(false)
  let timer: ReturnType<typeof setTimeout> | undefined

  function clearHold() {
    clearTimeout(timer)
    timer = undefined
    holding.value = false
  }

  watch(
    [isOpen, loading],
    ([open, pending]) => {
      if (!open) {
        clearHold()
      } else if (pending && !holding.value) {
        holding.value = true
        timer = setTimeout(clearHold, MINIMUM_LOADING_MS)
      }
    },
    { immediate: true, flush: 'sync' },
  )
  onScopeDispose(clearHold)

  return computed(() => isOpen() && (loading() || holding.value))
}
