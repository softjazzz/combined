import { effectScope, ref, type EffectScope } from 'vue'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { useMinimumLoading } from '@/composables/useMinimumLoading'

let scope: EffectScope

beforeEach(() => {
  scope = effectScope()
  vi.useFakeTimers()
})
afterEach(() => {
  scope.stop()
  vi.useRealTimers()
})

it('慢请求结束后立即取消加载标识', () => {
  const pending = ref(true)
  const showLoading = scope.run(() => useMinimumLoading(() => pending.value, () => true))!
  vi.advanceTimersByTime(2400)
  expect(showLoading.value).toBe(true)

  pending.value = false
  expect(showLoading.value).toBe(false)
})

it('关闭取消计时，重新打开从头计时，卸载清理计时器', () => {
  const open = ref(true)
  const pending = ref(true)
  const showLoading = scope.run(() => useMinimumLoading(() => pending.value, () => open.value))!

  vi.advanceTimersByTime(600)
  open.value = false
  expect(showLoading.value).toBe(false)
  expect(vi.getTimerCount()).toBe(0)

  open.value = true
  pending.value = false
  vi.advanceTimersByTime(1999)
  expect(showLoading.value).toBe(true)
  vi.advanceTimersByTime(1)
  expect(showLoading.value).toBe(false)

  pending.value = true
  expect(vi.getTimerCount()).toBe(1)
  scope.stop()
  expect(vi.getTimerCount()).toBe(0)
})
