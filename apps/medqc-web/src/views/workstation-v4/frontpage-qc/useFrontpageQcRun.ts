/** 首页质控任务：创建、轮询进度、取消。进入页面时恢复自己进行中的任务。 */
import { onBeforeUnmount, ref } from 'vue'

import {
  cancelFrontpageQcRun,
  createFrontpageQcRun,
  FrontpageQcRequestError,
  getFrontpageQcRun,
  isFrontpageQcAbortError,
  isFrontpageQcRunActive,
  listActiveFrontpageQcRuns,
  type FrontpageQcRef,
  type FrontpageQcRun,
  type FrontpageQcScopeFilters,
} from '@/services/frontpage-qc-v2-service'

export const POLL_INTERVAL_MS = 1500
/** 连续读取失败达到上限后停止轮询，避免网络或服务异常时无限请求 */
export const MAX_POLL_FAILURES = 12

function adoptedRun(error: unknown): FrontpageQcRun | null {
  if (!(error instanceof FrontpageQcRequestError) || error.status !== 409) return null
  const payload = error.payload as { run?: FrontpageQcRun } | null
  return payload && payload.run ? payload.run : null
}

export function useFrontpageQcRun(onFinished: (run: FrontpageQcRun) => void) {
  const run = ref<FrontpageQcRun | null>(null)
  const starting = ref(false)
  const cancelling = ref(false)
  const pollStopped = ref(false)
  const error = ref('')
  let timer: ReturnType<typeof setTimeout> | null = null
  let pollController: AbortController | null = null
  let failures = 0
  let disposed = false
  let generation = 0

  function isCurrent(gen: number): boolean {
    return !disposed && gen === generation
  }

  function clearTimer() {
    if (timer) clearTimeout(timer)
    timer = null
  }

  function stop() {
    clearTimer()
    pollController?.abort()
    pollController = null
  }

  function schedule(gen: number) {
    clearTimer()
    if (!isCurrent(gen)) return
    timer = setTimeout(() => {
      void tick(gen)
    }, POLL_INTERVAL_MS)
  }

  function track(next: FrontpageQcRun, gen: number) {
    if (!isCurrent(gen)) return
    run.value = next
    failures = 0
    pollStopped.value = false
    if (isFrontpageQcRunActive(next)) {
      schedule(gen)
    } else {
      stop()
      onFinished(next)
    }
  }

  async function tick(gen: number) {
    if (!isCurrent(gen)) return
    const current = run.value
    if (!current) return
    pollController?.abort()
    const controller = new AbortController()
    pollController = controller
    try {
      const next = await getFrontpageQcRun(current.id, { signal: controller.signal })
      if (!isCurrent(gen) || controller.signal.aborted) return
      if (pollStopped.value) error.value = ''
      track(next, gen)
    } catch (err) {
      if (!isCurrent(gen) || controller.signal.aborted || isFrontpageQcAbortError(err)) return
      if (err instanceof FrontpageQcRequestError && (err.status === 403 || err.status === 404)) {
        error.value = err.message
        pollStopped.value = true
        stop()
        return
      }
      failures += 1
      if (failures >= MAX_POLL_FAILURES) {
        error.value = '暂时无法读取任务进度，已停止自动刷新，请稍后点“重新检查”或“刷新”查看结果'
        pollStopped.value = true
        stop()
        return
      }
      schedule(gen)
    } finally {
      if (pollController === controller) pollController = null
    }
  }

  async function start(body: { record_refs: FrontpageQcRef[] } | FrontpageQcScopeFilters) {
    if (starting.value || disposed) return
    starting.value = true
    error.value = ''
    pollStopped.value = false
    stop()
    const gen = ++generation
    try {
      const created = await createFrontpageQcRun(body)
      if (!isCurrent(gen)) return
      track(created, gen)
    } catch (err) {
      if (!isCurrent(gen)) return
      const existing = adoptedRun(err)
      if (existing) {
        error.value = '你已有进行中的首页质控任务，已切换到该任务的进度'
        track(existing, gen)
      } else {
        error.value = err instanceof Error ? err.message : '创建首页质控任务失败'
      }
    } finally {
      if (!disposed) starting.value = false
    }
  }

  async function cancel() {
    const current = run.value
    if (!current || cancelling.value || disposed) return
    cancelling.value = true
    stop()
    const gen = ++generation
    try {
      const next = await cancelFrontpageQcRun(current.id)
      if (!isCurrent(gen)) return
      run.value = next
      pollStopped.value = false
      if (!isFrontpageQcRunActive(next)) {
        stop()
        onFinished(next)
      } else {
        failures = 0
        schedule(gen)
      }
    } catch (err) {
      if (!isCurrent(gen)) return
      error.value = err instanceof Error ? err.message : '取消任务失败'
      if (run.value && isFrontpageQcRunActive(run.value) && !pollStopped.value) {
        schedule(gen)
      }
    } finally {
      if (!disposed) cancelling.value = false
    }
  }

  async function retryPoll() {
    const current = run.value
    if (!current || disposed) return
    error.value = ''
    failures = 0
    pollStopped.value = false
    stop()
    const gen = ++generation
    await tick(gen)
  }

  async function resume() {
    if (disposed || starting.value || cancelling.value) return
    stop()
    const gen = ++generation
    const controller = new AbortController()
    pollController = controller
    try {
      const { items } = await listActiveFrontpageQcRuns({ signal: controller.signal })
      if (!isCurrent(gen) || controller.signal.aborted) return
      if (items[0]) {
        if (pollStopped.value) error.value = ''
        track(items[0], gen)
      } else if (run.value && isFrontpageQcRunActive(run.value)) {
        const latest = await getFrontpageQcRun(run.value.id, { signal: controller.signal })
        if (!isCurrent(gen) || controller.signal.aborted) return
        error.value = ''
        track(latest, gen)
      }
    } catch {
      // 恢复进行中任务失败不影响页面其他功能；若原任务仍在正常轮询则继续
      if (isCurrent(gen) && run.value && isFrontpageQcRunActive(run.value) && !pollStopped.value) {
        schedule(gen)
      }
    } finally {
      if (pollController === controller) pollController = null
    }
  }

  function dismiss() {
    if (run.value && isFrontpageQcRunActive(run.value) && !pollStopped.value) return
    generation += 1
    stop()
    run.value = null
    pollStopped.value = false
    error.value = ''
  }

  onBeforeUnmount(() => {
    disposed = true
    generation += 1
    stop()
  })

  return { run, starting, cancelling, pollStopped, error, start, cancel, resume, retryPoll, dismiss }
}
