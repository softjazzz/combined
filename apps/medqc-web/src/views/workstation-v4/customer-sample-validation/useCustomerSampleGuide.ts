import { computed, nextTick, ref } from 'vue'
import type { CSSProperties } from 'vue'
import { useRoute } from 'vue-router'
import {
  CUSTOMER_SAMPLE_GUIDE_STORAGE_KEY,
  customerSampleGuideSteps,
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

  const currentCustomerSampleGuideStep = computed(
    () =>
      customerSampleGuideSteps[customerSampleGuideStepIndex.value] || customerSampleGuideSteps[0],
  )
  const isLastCustomerSampleGuideStep = computed(
    () => customerSampleGuideStepIndex.value >= customerSampleGuideSteps.length - 1,
  )

  function hasCustomerSampleGuideTourQuery(): boolean {
    const raw = route?.query?.tour
    return Array.isArray(raw) ? raw.includes('1') : raw === '1'
  }

  function hasSeenCustomerSampleGuide(): boolean {
    try {
      return window.localStorage?.getItem(CUSTOMER_SAMPLE_GUIDE_STORAGE_KEY) === 'true'
    } catch {
      return false
    }
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
    const target = currentCustomerSampleGuideStep.value.target
    void nextTick(() => {
      const element = document.querySelector(`[data-customer-guide="${target}"]`)
      if (typeof element?.scrollIntoView === 'function') {
        element.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' })
      }
      scheduleCustomerSampleTourCardPositionUpdate()
    })
  }

  function openCustomerSampleGuide() {
    customerSampleGuideStepIndex.value = 0
    customerSampleGuideOpen.value = true
    scrollCustomerSampleGuideTarget()
  }

  function closeCustomerSampleGuide() {
    customerSampleGuideOpen.value = false
    customerSampleTourCardStyle.value = {}
    markCustomerSampleGuideSeen()
  }

  function startSyntheticCaseFromGuide() {
    closeCustomerSampleGuide()
    openTestRecordDrawer()
  }

  function goToCustomerSampleGuideStep(index: number) {
    customerSampleGuideStepIndex.value = Math.min(
      Math.max(index, 0),
      customerSampleGuideSteps.length - 1,
    )
    scrollCustomerSampleGuideTarget()
  }

  function goToPreviousCustomerSampleGuideStep() {
    goToCustomerSampleGuideStep(customerSampleGuideStepIndex.value - 1)
  }

  function goToNextCustomerSampleGuideStep() {
    if (isLastCustomerSampleGuideStep.value) {
      closeCustomerSampleGuide()
      return
    }
    goToCustomerSampleGuideStep(customerSampleGuideStepIndex.value + 1)
  }

  function openInitialCustomerSampleGuide() {
    if (hasCustomerSampleGuideTourQuery() || !hasSeenCustomerSampleGuide()) {
      openCustomerSampleGuide()
    }
  }

  function stopCustomerSampleGuidePositionTimer() {
    if (!customerSampleGuidePositionTimer) return
    clearTimeout(customerSampleGuidePositionTimer)
    customerSampleGuidePositionTimer = null
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
