/** 首页质控任务：创建、轮询进度、取消。进入页面时恢复自己进行中的任务。 */
import { onBeforeUnmount, ref } from 'vue'

import {
  cancelFrontpageQcRun,
  createFrontpageQcRun,
  FrontpageQcRequestError,
  getFrontpageQcRun,
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
  const error = ref('')
  let timer: ReturnType<typeof setTimeout> | null = null
  let failures = 0
  let disposed = false

  function stop() {
    if (timer) clearTimeout(timer)
    timer = null
  }

  function schedule() {
    stop()
    if (!disposed) timer = setTimeout(tick, POLL_INTERVAL_MS)
  }

  function track(next: FrontpageQcRun) {
    run.value = next
    failures = 0
    if (isFrontpageQcRunActive(next)) schedule()
    else onFinished(next)
  }

  async function tick() {
    const current = run.value
    if (!current) return
    try {
      track(await getFrontpageQcRun(current.id))
    } catch (err) {
      if (err instanceof FrontpageQcRequestError && (err.status === 403 || err.status === 404)) {
        error.value = err.message
        stop()
        return
      }
      failures += 1
      if (failures >= MAX_POLL_FAILURES) {
        error.value = '暂时无法读取任务进度，已停止自动刷新，请稍后点“刷新”查看结果'
        stop()
        return
      }
      schedule()
    }
  }

  async function start(body: { record_refs: FrontpageQcRef[] } | FrontpageQcScopeFilters) {
    if (starting.value) return
    starting.value = true
    error.value = ''
    try {
      track(await createFrontpageQcRun(body))
    } catch (err) {
      const existing = adoptedRun(err)
      if (existing) {
        error.value = '你已有进行中的首页质控任务，已切换到该任务的进度'
        track(existing)
      } else {
        error.value = err instanceof Error ? err.message : '创建首页质控任务失败'
      }
    } finally {
      starting.value = false
    }
  }

  async function cancel() {
    const current = run.value
    if (!current || cancelling.value) return
    cancelling.value = true
    try {
      const next = await cancelFrontpageQcRun(current.id)
      run.value = next
      if (!isFrontpageQcRunActive(next)) {
        stop()
        onFinished(next)
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : '取消任务失败'
    } finally {
      cancelling.value = false
    }
  }

  async function resume() {
    try {
      const { items } = await listActiveFrontpageQcRuns()
      if (items[0]) track(items[0])
    } catch {
      // 恢复进行中任务失败不影响页面其他功能
    }
  }

  function dismiss() {
    if (run.value && isFrontpageQcRunActive(run.value)) return
    run.value = null
    error.value = ''
  }

  onBeforeUnmount(() => {
    disposed = true
    stop()
  })

  return { run, starting, cancelling, error, start, cancel, resume, dismiss }
}
