<template>
  <a-popover placement="bottomRight" trigger="click">
    <template #content>
      <section class="runtime-build-details" aria-label="运行版本详情">
        <div class="runtime-build-heading">运行版本</div>
        <dl>
          <dt>前端构建号</dt>
          <dd>{{ frontend.buildId || (frontend.development ? '开发环境' : '前端未标记') }}</dd>
          <dt>前端提交</dt>
          <dd>{{ frontend.gitCommit || '未标记' }}</dd>
          <dt>后端构建号</dt>
          <dd>{{ backend?.build_id || '暂无版本信息' }}</dd>
          <dt>后端提交</dt>
          <dd>{{ backend?.git_commit || '未标记' }}</dd>
          <dt>后端启动时间</dt>
          <dd>{{ startedAt }}</dd>
          <dt>后端进程</dt>
          <dd>{{ backend ? `PID ${backend.pid}` : '—' }}</dd>
        </dl>
        <p v-if="detailMessage" class="runtime-build-message">
          {{ detailMessage }}
        </p>
        <a-button size="small" :loading="loading" @click="refresh"> 刷新版本 </a-button>
      </section>
    </template>
    <button
      type="button"
      :class="['runtime-build-status', `is-${state}`]"
      :aria-label="`运行版本：${label}，前端${frontend.buildId || '未标记'}`"
    >
      <span class="runtime-build-dot" aria-hidden="true" />
      <span>{{ label }}</span>
      <span class="runtime-build-short" :title="frontend.buildId || '前端未标记'">{{
        shortBuildId
      }}</span>
    </button>
  </a-popover>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  compareRuntimeBuild,
  fetchRuntimeBuild,
  getFrontendBuildIdentity,
  type RuntimeBuildResult,
} from '@/services/runtime-build-service'

const frontend = getFrontendBuildIdentity()
const result = ref<RuntimeBuildResult | null>(null)
const loading = ref(false)
const state = computed(() => compareRuntimeBuild(frontend, result.value))
const labels = {
  development: '开发环境',
  matching: '版本一致',
  mismatch: '版本不一致',
  unknown: '无法核对',
  error: '连接失败',
}
const label = computed(() => labels[state.value])
const shortBuildId = frontend.buildId
  ? frontend.buildId.slice(-15)
  : frontend.development
    ? '本地开发'
    : '前端未标记'
const backend = computed(() => (result.value?.kind === 'ready' ? result.value.data : null))
const startedAt = computed(() =>
  backend.value
    ? new Date(backend.value.started_at).toLocaleString('zh-CN', { hour12: false })
    : '—',
)
const detailMessage = computed(() => {
  if (result.value && result.value.kind !== 'ready') return result.value.message
  if (frontend.development) return '当前使用开发服务器，不进行发布版本一致性确认。'
  if (!frontend.buildId || !frontend.gitCommit) return '前端未标记完整构建信息，无法核对版本。'
  if (backend.value && !backend.value.available) return '后端未提供可核对的构建信息。'
  if (state.value === 'mismatch') return '前后端版本不一致，请核对部署版本并刷新页面。'
  return ''
})

let active = true
let timer: ReturnType<typeof setInterval> | undefined
async function refresh() {
  // 同一组件仅允许一个请求；卸载后的响应不再写入状态。
  if (loading.value || !active) return
  loading.value = true
  try {
    const next = await fetchRuntimeBuild()
    if (active) result.value = next
  } catch {
    if (active) result.value = { kind: 'connection_error', message: '无法读取后端版本信息' }
  } finally {
    if (active) loading.value = false
  }
}
function refreshWhenVisible() {
  if (document.visibilityState === 'visible') void refresh()
}
onMounted(() => {
  void refresh()
  timer = setInterval(refreshWhenVisible, 60000)
  document.addEventListener('visibilitychange', refreshWhenVisible)
})
onBeforeUnmount(() => {
  active = false
  clearInterval(timer)
  document.removeEventListener('visibilitychange', refreshWhenVisible)
})
</script>

<style scoped>
.runtime-build-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 240px;
  height: 30px;
  min-height: 0;
  box-sizing: border-box;
  line-height: 18px;
  align-self: center;
  padding: 5px 8px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 8px;
  background: transparent;
  color: #64748b;
  font-size: 12px;
  white-space: nowrap;
  cursor: pointer;
}
.runtime-build-status:hover {
  background: #f5f5f7;
}
.runtime-build-status:focus-visible {
  outline: 2px solid #2b6cf6;
  outline-offset: 2px;
}
.runtime-build-dot {
  flex: none;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}
.runtime-build-short {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  color: #64748b;
  font-variant-numeric: tabular-nums;
}
.is-matching {
  color: #15803d;
}
.is-mismatch {
  color: #b45309;
  border-color: #fcd34d;
  background: #fffbeb;
}
.is-error {
  color: #b91c1c;
}
.runtime-build-details {
  width: min(360px, calc(100vw - 48px));
  font-size: 12px;
  color: #1d1d1f;
}
.runtime-build-heading {
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 600;
}
.runtime-build-details dl {
  display: grid;
  grid-template-columns: 90px minmax(0, 1fr);
  gap: 8px 12px;
  margin: 0 0 12px;
}
.runtime-build-details dt {
  color: #64748b;
}
.runtime-build-details dd {
  margin: 0;
  overflow-wrap: anywhere;
}
.runtime-build-message {
  margin: 8px 0 12px;
  line-height: 1.6;
  color: #64748b;
}
@media (max-width: 640px) {
  .runtime-build-status {
    max-width: 160px;
    flex-wrap: wrap;
    gap: 2px 5px;
    font-size: 11px;
  }
  .runtime-build-short {
    flex-basis: 100%;
    text-align: left;
    font-size: 10px;
  }
}
</style>
