<template>
  <section
    v-if="task"
    class="qc-task-status"
    :class="[
      presentation?.statusClass,
      presentation?.normalizedStatus ? `is-${presentation.normalizedStatus}` : 'is-unknown',
      presentation?.isRunning ? 'is-expanded' : 'is-collapsed',
      { 'is-compact': isCompactActive },
    ]"
    data-testid="customer-sample-qc-task-status"
    aria-live="polite"
  >
    <a-spin :spinning="loading">
      <div class="qc-task-status__layout">
        <div class="qc-task-status__header">
          <div class="qc-task-status__heading">
            <span
              class="qc-task-status__indicator"
              aria-hidden="true"
            />
            <div class="qc-task-status__title">
              <div>
                <strong>{{ presentation?.statusTitle }}</strong>
                <span class="qc-task-status__badge">{{ presentation?.statusLabel }}</span>
                <span class="qc-task-status__rule-set">{{ presentation?.ruleSetText }}</span>
                <span
                  v-if="isCompactActive && presentation?.recordProgressText"
                  class="qc-task-status__compact-meta"
                >
                  {{ presentation.recordProgressText }}
                </span>
              </div>
              <p v-if="presentation?.isRunning">
                {{ presentation.phaseText }}
              </p>
            </div>
          </div>

          <div class="qc-task-status__actions">
            <a-button
              size="small"
              type="primary"
              data-testid="qc-task-view-result"
              @click="emit('view-result', task.id)"
            >
              {{ presentation?.isRunning ? '查看实时结果' : '查看结果' }}
            </a-button>
            <a-button
              v-if="presentation?.isRunning && !task.read_only"
              danger
              size="small"
              :loading="canceling"
              data-testid="qc-task-cancel"
              @click="emit('cancel', task.id)"
            >
              停止质控
            </a-button>
            <a-dropdown
              v-if="task.status === 'completed' && !task.read_only"
              placement="topRight"
            >
              <a-button
                size="small"
                data-testid="qc-task-more-actions"
              >
                更多
              </a-button>
              <template #overlay>
                <a-menu>
                  <a-menu-item
                    key="review"
                    data-testid="qc-task-review"
                    :disabled="reviewing"
                    @click="emit('review', task.id)"
                  >
                    {{ reviewing ? '复核中…' : '复核本次结果' }}
                  </a-menu-item>
                  <a-menu-item
                    key="export"
                    data-testid="qc-task-export"
                    @click="emit('export', task.id)"
                  >
                    导出 HTML
                  </a-menu-item>
                </a-menu>
              </template>
            </a-dropdown>
            <a-button
              type="link"
              size="small"
              data-testid="qc-task-open-history"
              @click="emit('open-history')"
            >
              质控记录
            </a-button>
            <a-button
              v-if="collapsible && !presentation?.isRunning"
              type="text"
              size="small"
              class="qc-task-status__collapse-toggle"
              data-testid="qc-task-toggle-compact"
              :aria-expanded="!isCompactActive"
              @click="emit('toggle-compact')"
            >
              {{ isCompactActive ? '展开任务栏' : '收起' }}
            </a-button>
          </div>
        </div>

        <div v-show="!isCompactActive" class="qc-task-status__body">
          <div
            v-if="presentation?.isRunning"
            class="qc-task-status__progress"
            :class="{
              'is-running': presentation.isRunning,
              'is-indeterminate': presentation.progressPercent <= 0,
            }"
            role="progressbar"
            aria-valuemin="0"
            aria-valuemax="100"
            :aria-valuenow="
              presentation.progressPercent > 0 ? presentation.progressPercent : undefined
            "
            :aria-label="
              presentation.progressPercent > 0
                ? `质控执行进度 ${presentation.progressPercent}%`
                : '质控执行中，等待首份病历完成'
            "
            data-testid="qc-task-running-progress"
          >
            <i :style="{ width: `${presentation.progressPercent}%` }" />
          </div>

          <div
            v-if="presentation?.isRunning"
            class="qc-task-status__progress-detail"
          >
            <strong>
              {{
                presentation.progressPercent > 0
                  ? `当前进度 ${presentation.progressPercent}%`
                  : presentation.resultCount > 0
                    ? `已有 ${presentation.resultCount} 项有效结果`
                    : presentation.liveExecutionPhase?.text || '正在准备首份结果'
              }}
            </strong>
            <span>{{ presentation.resultProgressText }}</span>
          </div>

          <div
            v-if="presentation?.isRunning"
            class="qc-task-status__live-result"
            data-testid="qc-task-live-result"
            aria-live="polite"
          >
            <div class="qc-task-status__live-result-label">
              <span aria-hidden="true" />
              {{
                presentation.liveResultLines.length
                  ? '已回写结果'
                  : presentation.liveExecutionPhase?.label || '执行进度'
              }}
            </div>
            <div class="qc-task-status__live-result-content">
              <Transition
                name="qc-live-result"
                mode="out-in"
              >
                <div
                  v-if="currentLiveResult"
                  :key="currentLiveResult.key"
                  class="qc-task-status__live-result-line"
                >
                  <strong>{{ currentLiveResult.ruleId }}</strong>
                  <span
                    :class="['qc-task-status__live-result-status', currentLiveResult.className]"
                  >
                    {{ currentLiveResult.statusLabel }}
                  </span>
                  <span class="qc-task-status__live-result-text">{{ currentLiveResult.text }}</span>
                </div>
                <div
                  v-else
                  :key="presentation.liveExecutionPhase?.text || 'waiting-for-first-result'"
                  :class="[
                    'qc-task-status__live-result-waiting',
                    { 'is-stage': Boolean(presentation.liveExecutionPhase) },
                  ]"
                >
                  {{
                    presentation.liveExecutionPhase?.text ||
                      (confirmedResultsOnly && presentation.resultCount > 0
                        ? `质控执行中，已回写 ${presentation.resultCount} 条结果`
                        : '等待首条质控结果回写…')
                  }}
                </div>
              </Transition>
            </div>
          </div>

          <div class="qc-task-status__details">
            <div
              class="qc-task-status__summary"
              :data-testid="
                presentation?.isRunning ? 'qc-task-running-summary' : 'qc-task-settled-summary'
              "
            >
              <span>{{ presentation?.recordProgressText }}</span>
              <span>{{ presentation?.resultProgressText }}</span>
              <span>{{ presentation?.scopeText }}</span>
              <span
                v-if="presentation?.diagnosticRuleFailureCount"
                class="qc-task-status__diagnostic-warning"
                data-testid="qc-task-diagnostic-warning"
              >
                {{ presentation.diagnosticRuleFailureCount }} 项规则未完成，请查看技术详情
              </span>
              <span>更新 {{ presentation?.updatedText }}</span>
            </div>

            <div
              v-if="attentionStatusChips.length || neutralStatusChips.length"
              class="qc-task-status__result-groups"
            >
              <div
                v-if="attentionStatusChips.length"
                class="qc-task-status__chips qc-task-status__chips--attention"
                data-testid="qc-task-attention-statuses"
              >
                <span
                  v-for="chip in attentionStatusChips"
                  :key="chip.key"
                  :class="chip.className"
                >
                  {{ chip.label }} <strong>{{ chip.value }}</strong>
                </span>
              </div>
              <div
                v-if="neutralStatusChips.length"
                class="qc-task-status__other-results"
                data-testid="qc-task-other-statuses"
              >
                <span>其他结果</span>
                <span
                  v-for="chip in neutralStatusChips"
                  :key="chip.key"
                  :class="chip.className"
                >
                  {{ chip.label }} <strong>{{ chip.value }}</strong>
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </a-spin>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { useQcResultVisibility } from '@/composables/useQcResultVisibility'
import { buildBatchJobPresentation } from './batchJobPresentation'
import type { SichuanBatchJob } from '@/views/workstation-v4/semantic-rules/types'

const props = withDefaults(
  defineProps<{
    task: SichuanBatchJob | null
    loading?: boolean
    canceling?: boolean
    reviewing?: boolean
    compact?: boolean
    collapsible?: boolean
  }>(),
  {
    loading: false,
    canceling: false,
    reviewing: false,
    compact: false,
    collapsible: false,
  },
)

const emit = defineEmits<{
  'view-result': [jobId: string]
  cancel: [jobId: string]
  review: [jobId: string]
  export: [jobId: string]
  'open-history': []
  'toggle-compact': []
}>()

const { confirmedResultsOnly } = useQcResultVisibility()
const presentation = computed(() =>
  props.task
    ? buildBatchJobPresentation(props.task, {
        confirmedResultsOnly: confirmedResultsOnly.value,
      })
    : null,
)
const isCompactActive = computed(() => Boolean(props.compact && !presentation.value?.isRunning))
const attentionStatusKeys = new Set([
  'technical_error',
  'non_compliant',
  'data_gap',
  'data_quality_gap',
  'uncertain',
  'ai_suggested_non_compliant',
  'not_executed',
])
const attentionStatusChips = computed(() =>
  (presentation.value?.statusChips || []).filter((chip) => attentionStatusKeys.has(chip.key)),
)
const neutralStatusChips = computed(() =>
  (presentation.value?.statusChips || []).filter((chip) => !attentionStatusKeys.has(chip.key)),
)
const liveResultIndex = ref(0)
let liveResultTimer: ReturnType<typeof setInterval> | null = null

const currentLiveResult = computed(() => {
  const lines = presentation.value?.liveResultLines || []
  if (!lines.length) return null
  return lines[liveResultIndex.value % lines.length]
})

function stopLiveResultRotation() {
  if (!liveResultTimer) return
  clearInterval(liveResultTimer)
  liveResultTimer = null
}

function startLiveResultRotation() {
  stopLiveResultRotation()
  const lines = presentation.value?.liveResultLines || []
  if (!presentation.value?.isRunning || lines.length <= 1) return
  liveResultTimer = setInterval(() => {
    const currentLines = presentation.value?.liveResultLines || []
    if (!presentation.value?.isRunning || currentLines.length <= 1) {
      stopLiveResultRotation()
      return
    }
    liveResultIndex.value = (liveResultIndex.value + 1) % currentLines.length
  }, 3600)
}

watch(
  () => [
    presentation.value?.isRunning || false,
    (presentation.value?.liveResultLines || []).map((item) => item.key).join('||'),
  ],
  () => {
    liveResultIndex.value = 0
    startLiveResultRotation()
  },
  { immediate: true },
)

onBeforeUnmount(stopLiveResultRotation)
</script>

<style scoped>
.qc-task-status {
  border: 1px solid rgba(10, 108, 255, 0.18);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 8px 22px rgba(37, 99, 235, 0.08);
}

.qc-task-status.is-failed {
  border-color: rgba(239, 68, 68, 0.25);
}

.qc-task-status.is-canceled {
  border-color: rgba(100, 116, 139, 0.2);
}

.qc-task-status__layout {
  padding: 14px 16px;
}

.qc-task-status.is-expanded .qc-task-status__layout {
  padding-block: 16px;
}

.qc-task-status.is-compact .qc-task-status__layout {
  padding: 10px 16px;
}

.qc-task-status.is-compact .qc-task-status__header {
  align-items: center;
}

.qc-task-status.is-compact .qc-task-status__title strong {
  font-size: 14px;
  line-height: 22px;
}

.qc-task-status__compact-meta {
  color: rgba(29, 29, 31, 0.56);
  font-size: 12px;
  font-weight: 500;
  line-height: 20px;
  white-space: nowrap;
}

.qc-task-status__header,
.qc-task-status__details,
.qc-task-status__result-groups {
  display: flex;
  min-width: 0;
}

.qc-task-status__header {
  justify-content: space-between;
  gap: 16px;
}

.qc-task-status__body {
  min-width: 0;
}

.qc-task-status__details {
  justify-content: space-between;
  align-items: center;
  gap: 14px 24px;
  margin-top: 10px;
}

.qc-task-status__heading,
.qc-task-status__title > div,
.qc-task-status__summary,
.qc-task-status__chips,
.qc-task-status__actions {
  display: flex;
  align-items: center;
}

.qc-task-status__heading {
  gap: 9px;
}

.qc-task-status__indicator {
  width: 9px;
  height: 9px;
  flex: none;
  border-radius: 50%;
  background: #0a6cff;
  box-shadow: 0 0 0 5px rgba(10, 108, 255, 0.1);
}

.is-running .qc-task-status__indicator {
  animation: qc-task-indicator-pulse 1.8s ease-in-out infinite;
}

.is-completed .qc-task-status__indicator {
  background: #10b981;
  box-shadow: 0 0 0 5px rgba(16, 185, 129, 0.1);
}

.is-failed .qc-task-status__indicator {
  background: #ef4444;
  box-shadow: 0 0 0 5px rgba(239, 68, 68, 0.1);
}

.is-canceled .qc-task-status__indicator {
  background: #64748b;
  box-shadow: 0 0 0 5px rgba(100, 116, 139, 0.1);
}

.qc-task-status__title {
  min-width: 0;
}

.qc-task-status__title > div {
  flex-wrap: wrap;
  gap: 8px;
}

.qc-task-status__title strong {
  color: #1d1d1f;
  font-size: 16px;
  font-weight: 650;
  line-height: 24px;
}

.qc-task-status__rule-set {
  max-width: 280px;
  overflow: hidden;
  color: rgba(29, 29, 31, 0.7);
  font-size: 13px;
  font-weight: 600;
  line-height: 20px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.qc-task-status__title p {
  margin: 2px 0 0;
  color: rgba(29, 29, 31, 0.6);
  font-size: 13px;
  line-height: 20px;
}

.qc-task-status__badge {
  border-radius: 999px;
  background: rgba(10, 108, 255, 0.08);
  color: #0a6cff;
  font-size: 12px;
  font-weight: 600;
  line-height: 22px;
  padding: 0 9px;
}

.is-completed .qc-task-status__badge {
  background: rgba(16, 185, 129, 0.1);
  color: #047857;
}

.is-failed .qc-task-status__badge {
  background: rgba(239, 68, 68, 0.08);
  color: #dc2626;
}

.is-canceled .qc-task-status__badge {
  background: rgba(100, 116, 139, 0.1);
  color: #475569;
}

.qc-task-status__progress {
  position: relative;
  height: 8px;
  margin: 14px 0 7px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(10, 108, 255, 0.1);
}

.qc-task-status__progress-detail {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: rgba(29, 29, 31, 0.62);
  font-size: 12px;
  line-height: 18px;
}

.qc-task-status__progress-detail strong {
  color: #175d9c;
  font-weight: 650;
}

.qc-task-status__live-result {
  display: flex;
  min-height: 40px;
  align-items: center;
  gap: 10px;
  margin: 10px 0 0;
  padding: 7px 10px;
  overflow: hidden;
  border: 1px solid rgba(10, 108, 255, 0.12);
  border-radius: 8px;
  background: #f6faff;
}

.qc-task-status__live-result-label {
  display: flex;
  flex: none;
  align-items: center;
  gap: 6px;
  color: #175d9c;
  font-size: 12px;
  font-weight: 650;
}

.qc-task-status__live-result-label > span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #1684e8;
  box-shadow: 0 0 0 3px rgba(22, 132, 232, 0.12);
}

.qc-task-status__live-result-content {
  min-width: 0;
  flex: 1;
}

.qc-task-status__live-result-line {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 7px;
  color: #334155;
  font-size: 13px;
  line-height: 22px;
}

.qc-task-status__live-result-line > strong {
  flex: none;
  color: #1d4f7f;
  font-size: 12px;
  font-weight: 650;
}

.qc-task-status__live-result-status {
  display: inline-flex;
  flex: none;
  align-items: center;
  gap: 5px;
  border: 1px solid rgba(15, 23, 42, 0.1);
  border-radius: 999px;
  background: #ffffff;
  color: #0f172a;
  font-size: 11px;
  font-weight: 600;
  line-height: 18px;
  padding: 0 8px;
}

.qc-task-status__live-result-status::before {
  width: 6px;
  height: 6px;
  flex: none;
  border-radius: 999px;
  background: #94a3b8;
  content: '';
}

.qc-task-status__live-result-status.is-danger::before {
  background: #dc2626;
}

.qc-task-status__live-result-status.is-warning::before {
  background: #d97706;
}

.qc-task-status__live-result-status.is-review::before {
  background: #2563eb;
}

.qc-task-status__live-result-status.is-success::before {
  background: #059669;
}

.qc-task-status__live-result-text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.qc-task-status__live-result-waiting {
  color: #64748b;
  font-size: 13px;
  line-height: 22px;
}

.qc-live-result-enter-active,
.qc-live-result-leave-active {
  transition:
    opacity 180ms ease,
    transform 180ms ease;
}

.qc-live-result-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

.qc-live-result-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

.qc-task-status__progress i {
  position: relative;
  display: block;
  height: 100%;
  overflow: hidden;
  border-radius: inherit;
  background: linear-gradient(90deg, #0a6cff 0%, #1684e8 68%, #55adf7 100%);
  transition: width 280ms cubic-bezier(0.25, 0.1, 0.25, 1);
}

.qc-task-status__progress.is-running:not(.is-indeterminate) i::after {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    105deg,
    transparent 0%,
    rgba(255, 255, 255, 0.08) 38%,
    rgba(255, 255, 255, 0.72) 50%,
    rgba(255, 255, 255, 0.08) 62%,
    transparent 100%
  );
  content: '';
  transform: translateX(-110%);
  animation: qc-task-progress-shimmer 1.55s linear infinite;
}

.qc-task-status__progress.is-indeterminate i {
  width: 24% !important;
  background: linear-gradient(90deg, rgba(10, 108, 255, 0.28), #0a6cff 50%, #45a4f2);
  box-shadow: 0 0 8px rgba(10, 108, 255, 0.3);
  animation: qc-task-progress-indeterminate 1.4s cubic-bezier(0.45, 0, 0.25, 1) infinite;
}

@keyframes qc-task-progress-indeterminate {
  0% {
    transform: translateX(-115%);
  }

  100% {
    transform: translateX(430%);
  }
}

@keyframes qc-task-progress-shimmer {
  0% {
    transform: translateX(-110%);
  }

  100% {
    transform: translateX(110%);
  }
}

@keyframes qc-task-indicator-pulse {
  0%,
  100% {
    box-shadow: 0 0 0 5px rgba(10, 108, 255, 0.08);
  }

  50% {
    box-shadow: 0 0 0 8px rgba(10, 108, 255, 0.16);
  }
}

.qc-task-status__summary {
  flex-wrap: wrap;
  gap: 2px 12px;
  margin: 0;
  color: rgba(29, 29, 31, 0.58);
  font-size: 12px;
  line-height: 20px;
}

.qc-task-status__diagnostic-warning {
  color: #b54708;
  font-weight: 600;
}

.qc-task-status__result-groups {
  flex: none;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 6px 10px;
}

.qc-task-status__chips {
  flex-wrap: wrap;
  gap: 5px;
  margin: 0;
}

.qc-task-status__chips--attention {
  display: flex;
  justify-content: flex-end;
}

.qc-task-status__chips > span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: 1px solid rgba(15, 23, 42, 0.1);
  border-radius: 999px;
  background: #ffffff;
  color: #0f172a;
  font-size: 12px;
  font-weight: 500;
  line-height: 20px;
  padding: 1px 9px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
}

.qc-task-status__chips > span::before {
  width: 6px;
  height: 6px;
  flex: none;
  border-radius: 999px;
  background: #94a3b8;
  content: '';
}

.qc-task-status__chips > span strong {
  color: #0f172a;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.qc-task-status__chips .is-danger,
.qc-task-status__chips .is-warning,
.qc-task-status__chips .is-review,
.qc-task-status__chips .is-success,
.qc-task-status__chips .is-muted {
  border-color: rgba(15, 23, 42, 0.1);
  background: #ffffff;
  color: #0f172a;
}

.qc-task-status__chips .is-danger::before {
  background: #dc2626;
}

.qc-task-status__chips .is-warning::before {
  background: #d97706;
}

.qc-task-status__chips .is-review::before {
  background: #2563eb;
}

.qc-task-status__chips .is-success::before {
  background: #059669;
}

.qc-task-status__chips .is-muted::before {
  background: #94a3b8;
}

.qc-task-status__other-results {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px 7px;
  color: rgba(29, 29, 31, 0.48);
  font-size: 12px;
  line-height: 20px;
}

.qc-task-status__other-results > span:not(:first-child) {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.88);
  color: #475569;
  padding: 0 8px;
}

.qc-task-status__actions {
  flex: none;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
  max-width: 520px;
}

.qc-task-status__actions :deep(.ant-btn) {
  border-radius: 8px;
}

.qc-task-status__collapse-toggle {
  color: rgba(29, 29, 31, 0.58);
  font-size: 12px;
  font-weight: 600;
}

.qc-task-status__collapse-toggle:hover,
.qc-task-status__collapse-toggle:focus {
  color: #0a6cff;
}

@media (max-width: 1080px) {
  .qc-task-status__header,
  .qc-task-status__details {
    align-items: stretch;
    flex-direction: column;
  }

  .qc-task-status__actions {
    justify-content: flex-start;
    max-width: none;
  }

  .qc-task-status__result-groups {
    justify-content: flex-start;
    width: 100%;
  }

  .qc-task-status__chips--attention {
    justify-content: flex-start;
  }
}

@media (max-width: 640px) {
  .qc-task-status__layout {
    padding: 14px;
  }

  .qc-task-status__actions {
    gap: 5px;
  }

  .qc-task-status__heading {
    align-items: flex-start;
  }

  .qc-task-status__rule-set {
    max-width: min(100%, 260px);
  }

  .qc-task-status__result-groups {
    align-items: flex-start;
    flex-direction: column;
  }

  .qc-task-status__progress-detail,
  .qc-task-status__live-result-line {
    align-items: flex-start;
    flex-direction: column;
    gap: 3px;
  }

  .qc-task-status__live-result {
    align-items: flex-start;
  }

  .qc-task-status__live-result-text {
    display: -webkit-box;
    overflow: hidden;
    white-space: normal;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
  }
}

@media (prefers-reduced-motion: reduce) {
  .is-running .qc-task-status__indicator,
  .qc-task-status__progress.is-running i,
  .qc-task-status__progress.is-running i::after {
    animation: none;
  }

  .qc-live-result-enter-active,
  .qc-live-result-leave-active {
    transition: none;
  }

  .qc-task-status__progress.is-indeterminate i {
    width: 12% !important;
    transform: none;
  }
}
</style>
