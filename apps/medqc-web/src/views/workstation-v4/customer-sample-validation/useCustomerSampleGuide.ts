import { computed, getCurrentInstance, nextTick, onBeforeUnmount, ref } from 'vue'
import type { CSSProperties } from 'vue'
import { useRoute } from 'vue-router'
import {
  CUSTOMER_SAMPLE_GUIDE_STORAGE_KEY,
  customerSampleGuideSteps as allCustomerSampleGuideSteps,
  type CustomerSampleGuideTarget,
} from './customerSampleValidationConfig'

export interface CustomerSampleGuideDependencies {
  openTestRecordDrawer: () => void
}

export function useCustomerSampleGuide(dependencies: CustomerSampleGuideDependencies) {
  const route = useRoute()
  const { openTestRecordDrawer } = dependencies
  let customerSampleGuidePositionTimer: ReturnType<typeof setTimeout> | null = null

  const customerSampleGuideOpen = ref(false)
  const customerSampleGuideStepIndex = ref(0)
  const customerSampleTourCardStyle = ref<CSSProperties>({})
  const customerSampleGuideSteps = ref([...allCustomerSampleGuideSteps])

  function isGuideDomMounted(): boolean {
    return typeof document !== 'undefined' && Boolean(document.querySelector('[data-customer-guide]'))
  }

  function hasGuideTargetInDom(target: CustomerSampleGuideTarget): boolean {
    if (!isGuideDomMounted()) return true
    return Boolean(document.querySelector(`[data-customer-guide="${target}"]`))
  }

  function resolveAvailableGuideSteps() {
    if (!isGuideDomMounted()) {
      return [...allCustomerSampleGuideSteps]
    }
    const available = allCustomerSampleGuideSteps.filter((step) =>
      Boolean(document.querySelector(`[data-customer-guide="${step.target}"]`)),
    )
    return available.length ? available : [...allCustomerSampleGuideSteps]
  }

  function syncAvailableGuideSteps(preferredTarget?: CustomerSampleGuideTarget) {
    const nextSteps = resolveAvailableGuideSteps()
    customerSampleGuideSteps.value = nextSteps
    if (preferredTarget) {
      const matchedIndex = nextSteps.findIndex((step) => step.target === preferredTarget)
      if (matchedIndex >= 0) {
        customerSampleGuideStepIndex.value = matchedIndex
        return
      }
    }
    customerSampleGuideStepIndex.value = Math.min(
      Math.max(customerSampleGuideStepIndex.value, 0),
      Math.max(0, nextSteps.length - 1),
    )
  }

  function findAvailableStepIndex(startIndex: number, direction: 1 | -1): number {
    const steps = customerSampleGuideSteps.value
    let cursor = startIndex
    while (cursor >= 0 && cursor < steps.length) {
      if (hasGuideTargetInDom(steps[cursor].target)) {
        return cursor
      }
      cursor += direction
    }
    return -1
  }

  const currentCustomerSampleGuideStep = computed(
    () =>
      customerSampleGuideSteps.value[customerSampleGuideStepIndex.value] ||
      customerSampleGuideSteps.value[0] ||
      allCustomerSampleGuideSteps[0],
  )
  const isLastCustomerSampleGuideStep = computed(
    () => customerSampleGuideStepIndex.value >= customerSampleGuideSteps.value.length - 1,
  )

  function handleCustomerSampleGuideKeydown(event: KeyboardEvent) {
    if (event.key !== 'Escape' || !customerSampleGuideOpen.value) return
    event.preventDefault()
    closeCustomerSampleGuide()
  }

  function attachCustomerSampleGuideKeydownListener() {
    if (typeof window === 'undefined') return
    window.removeEventListener('keydown', handleCustomerSampleGuideKeydown)
    window.addEventListener('keydown', handleCustomerSampleGuideKeydown)
  }

  function detachCustomerSampleGuideKeydownListener() {
    if (typeof window === 'undefined') return
    window.removeEventListener('keydown', handleCustomerSampleGuideKeydown)
  }

  function hasCustomerSampleGuideTourQuery(): boolean {
    const raw = route?.query?.tour
    return Array.isArray(raw) ? raw.includes('1') : raw === '1'
  }

  function markCustomerSampleGuideSeen() {
    try {
      window.localStorage?.setItem(CUSTOMER_SAMPLE_GUIDE_STORAGE_KEY, 'true')
    } catch {
      // localStorage 可能被浏览器策略禁用，不影响导览关闭。
    }
  }

  function customerSampleGuideTargetClass(target: CustomerSampleGuideTarget) {
    return {
      'customer-sample-tour-target': customerSampleGuideOpen.value,
      'is-current-tour-target':
        customerSampleGuideOpen.value && currentCustomerSampleGuideStep.value.target === target,
    }
  }

  function clampTourPosition(value: number, min: number, max: number): number {
    return Math.min(Math.max(value, min), max)
  }

  function updateCustomerSampleTourCardPosition() {
    if (!customerSampleGuideOpen.value) return
    const target = currentCustomerSampleGuideStep.value.target
    const element = document.querySelector(`[data-customer-guide="${target}"]`)
    if (!element) return

    const rect = element.getBoundingClientRect()
    const gap = 18
    const viewportWidth = window.innerWidth
    const viewportHeight = window.innerHeight
    const cardWidth = Math.min(420, Math.max(280, viewportWidth - 32))
    const cardHeight = 238
    const maxLeft = Math.max(gap, viewportWidth - cardWidth - gap)
    const maxTop = Math.max(gap, viewportHeight - cardHeight - gap)

    let left = rect.right + gap
    let top = rect.top

    if (left + cardWidth > viewportWidth - gap) {
      left = rect.left - cardWidth - gap
    }
    if (left < gap) {
      left = clampTourPosition(rect.left, gap, maxLeft)
      top = rect.bottom + gap
      if (top + cardHeight > viewportHeight - gap) {
        top = rect.top - cardHeight - gap
      }
    }

    customerSampleTourCardStyle.value = {
      width: `${cardWidth}px`,
      left: `${clampTourPosition(left, gap, maxLeft)}px`,
      top: `${clampTourPosition(top, gap, maxTop)}px`,
    }
  }

  function scheduleCustomerSampleTourCardPositionUpdate() {
    if (customerSampleGuidePositionTimer) {
      clearTimeout(customerSampleGuidePositionTimer)
    }
    updateCustomerSampleTourCardPosition()
    customerSampleGuidePositionTimer = setTimeout(updateCustomerSampleTourCardPosition, 320)
  }

  function scrollCustomerSampleGuideTarget() {
    void nextTick(() => {
      if (!customerSampleGuideOpen.value) return
      let target = currentCustomerSampleGuideStep.value.target
      if (isGuideDomMounted() && !hasGuideTargetInDom(target)) {
        syncAvailableGuideSteps()
        target = currentCustomerSampleGuideStep.value.target
      }
      const element = document.querySelector(`[data-customer-guide="${target}"]`)
      if (typeof element?.scrollIntoView === 'function') {
        element.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' })
      }
      scheduleCustomerSampleTourCardPositionUpdate()
    })
  }

  function openCustomerSampleGuide() {
    customerSampleGuideSteps.value = resolveAvailableGuideSteps()
    customerSampleGuideStepIndex.value = 0
    customerSampleGuideOpen.value = true
    attachCustomerSampleGuideKeydownListener()
    scrollCustomerSampleGuideTarget()
  }

  function closeCustomerSampleGuide() {
    customerSampleGuideOpen.value = false
    customerSampleTourCardStyle.value = {}
    detachCustomerSampleGuideKeydownListener()
    stopCustomerSampleGuidePositionTimer()
    markCustomerSampleGuideSeen()
  }

  function startSyntheticCaseFromGuide() {
    closeCustomerSampleGuide()
    openTestRecordDrawer()
  }

  function goToCustomerSampleGuideStep(index: number, direction: 1 | -1 = 1) {
    const steps = customerSampleGuideSteps.value
    if (!steps.length) {
      closeCustomerSampleGuide()
      return
    }
    const clamped = Math.min(Math.max(index, 0), steps.length - 1)
    let resolvedIndex = findAvailableStepIndex(clamped, direction)
    if (resolvedIndex < 0) {
      resolvedIndex = findAvailableStepIndex(clamped, direction === 1 ? -1 : 1)
    }
    if (resolvedIndex < 0) {
      closeCustomerSampleGuide()
      return
    }
    customerSampleGuideStepIndex.value = resolvedIndex
    scrollCustomerSampleGuideTarget()
  }

  function goToPreviousCustomerSampleGuideStep() {
    goToCustomerSampleGuideStep(customerSampleGuideStepIndex.value - 1, -1)
  }

  function goToNextCustomerSampleGuideStep() {
    if (isLastCustomerSampleGuideStep.value) {
      closeCustomerSampleGuide()
      return
    }
    const nextIndex = findAvailableStepIndex(customerSampleGuideStepIndex.value + 1, 1)
    if (nextIndex < 0) {
      closeCustomerSampleGuide()
      return
    }
    customerSampleGuideStepIndex.value = nextIndex
    scrollCustomerSampleGuideTarget()
  }

  // 首次进入不再自动弹出导览（会与加载提示叠加遮挡操作区）；
  // 只在演示链接显式带 ?tour=1 时打开，其余由工具栏「功能导览」手动开启。
  function openInitialCustomerSampleGuide() {
    if (hasCustomerSampleGuideTourQuery()) {
      openCustomerSampleGuide()
    }
  }

  function stopCustomerSampleGuidePositionTimer() {
    detachCustomerSampleGuideKeydownListener()
    if (!customerSampleGuidePositionTimer) return
    clearTimeout(customerSampleGuidePositionTimer)
    customerSampleGuidePositionTimer = null
  }

  if (getCurrentInstance()) {
    onBeforeUnmount(() => {
      stopCustomerSampleGuidePositionTimer()
    })
  }

  return {
    customerSampleGuideOpen,
    customerSampleGuideStepIndex,
    customerSampleTourCardStyle,
    customerSampleGuideSteps,
    currentCustomerSampleGuideStep,
    isLastCustomerSampleGuideStep,
    customerSampleGuideTargetClass,
    updateCustomerSampleTourCardPosition,
    openCustomerSampleGuide,
    closeCustomerSampleGuide,
    startSyntheticCaseFromGuide,
    goToCustomerSampleGuideStep,
    goToPreviousCustomerSampleGuideStep,
    goToNextCustomerSampleGuideStep,
    openInitialCustomerSampleGuide,
    stopCustomerSampleGuidePositionTimer,
  }
}
