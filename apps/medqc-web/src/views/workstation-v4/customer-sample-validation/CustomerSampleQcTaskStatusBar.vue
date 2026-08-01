<template>
  <section
    v-if="task"
    class="qc-task-status"
    :class="[
      presentation?.statusClass,
      presentation?.normalizedStatus ? `is-${presentation.normalizedStatus}` : 'is-unknown',
    ]"
    data-testid="customer-sample-qc-task-status"
    aria-live="polite"
  >
    <a-spin :spinning="loading">
      <div class="qc-task-status__layout">
        <div class="qc-task-status__main">
          <div class="qc-task-status__heading">
            <span
              class="qc-task-status__indicator"
              aria-hidden="true"
            />
            <div class="qc-task-status__title">
              <div>
                <strong>{{ presentation?.statusTitle }}</strong>
                <span class="qc-task-status__badge">{{ presentation?.statusLabel }}</span>
              </div>
              <p>{{ presentation?.phaseText }}</p>
            </div>
          </div>

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
            :aria-valuenow="presentation.progressPercent > 0 ? presentation.progressPercent : undefined"
            :aria-label="
              presentation.progressPercent > 0
                ? `质控执行进度 ${presentation.progressPercent}%`
                : '质控执行中，等待首份病历完成'
            "
            data-testid="qc-task-running-progress"
          >
            <i :style="{ width: `${presentation.progressPercent}%` }" />
          </div>

          <div class="qc-task-status__summary">
            <strong>{{ presentation?.ruleSetText }}</strong>
            <span>{{ presentation?.recordProgressText }}</span>
            <span>{{ presentation?.resultProgressText }}</span>
            <span>{{ presentation?.scopeText }}</span>
            <span>更新 {{ presentation?.updatedText }}</span>
          </div>

          <div
            v-if="presentation?.statusChips.length"
            class="qc-task-status__chips"
          >
            <span
              v-for="chip in presentation.statusChips"
              :key="chip.key"
              :class="chip.className"
            >
              {{ chip.label }} <strong>{{ chip.value }}</strong>
            </span>
          </div>
        </div>

        <div class="qc-task-status__actions">
          <a-button
            size="small"
            data-testid="qc-task-view-result"
            @click="emit('view-result', task.id)"
          >
            {{ presentation?.isRunning ? '查看实时结果' : '查看结果' }}
          </a-button>
          <a-button
            v-if="presentation?.isRunning"
            danger
            size="small"
            :loading="canceling"
            data-testid="qc-task-cancel"
            @click="emit('cancel', task.id)"
          >
            停止质控
          </a-button>
          <a-button
            v-if="task.status === 'completed'"
            size="small"
            :loading="reviewing"
            data-testid="qc-task-review"
            @click="emit('review', task.id)"
          >
            复核本次结果
          </a-button>
          <a-button
            v-if="task.status === 'completed'"
            size="small"
            data-testid="qc-task-export"
            @click="emit('export', task.id)"
          >
            导出 HTML
          </a-button>
          <a-button
            type="link"
            size="small"
            data-testid="qc-task-open-history"
            @click="emit('open-history')"
          >
            质控记录
          </a-button>
        </div>
      </div>
    </a-spin>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import { buildBatchJobPresentation } from './batchJobPresentation'
import type { SichuanBatchJob } from '@/views/workstation-v4/semantic-rules/types'

const props = withDefaults(
  defineProps<{
    task: SichuanBatchJob | null
    loading?: boolean
    canceling?: boolean
    reviewing?: boolean
  }>(),
  {
    loading: false,
    canceling: false,
    reviewing: false,
  },
)

const emit = defineEmits<{
  'view-result': [jobId: string]
  cancel: [jobId: string]
  review: [jobId: string]
  export: [jobId: string]
  'open-history': []
}>()

const presentation = computed(() =>
  props.task ? buildBatchJobPresentation(props.task) : null,
)
</script>

<style scoped>
.qc-task-status {
  border: 1px solid rgba(0, 102, 204, 0.18);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 8px 24px rgba(37, 99, 235, 0.07);
}

.qc-task-status.is-failed {
  border-color: rgba(239, 68, 68, 0.25);
}

.qc-task-status.is-canceled {
  border-color: rgba(100, 116, 139, 0.2);
}

.qc-task-status__layout {
  display: flex;
  min-height: 82px;
  align-items: center;
  gap: 18px;
  padding: 14px 16px;
}

.qc-task-status__main {
  min-width: 0;
  flex: 1;
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
  gap: 10px;
}

.qc-task-status__indicator {
  width: 9px;
  height: 9px;
  flex: none;
  border-radius: 50%;
  background: #0066cc;
  box-shadow: 0 0 0 5px rgba(0, 102, 204, 0.1);
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
  gap: 8px;
}

.qc-task-status__title strong {
  color: #1d1d1f;
  font-size: 14px;
  font-weight: 650;
}

.qc-task-status__title p {
  margin: 2px 0 0;
  color: rgba(29, 29, 31, 0.6);
  font-size: 12px;
  line-height: 18px;
}

.qc-task-status__badge {
  border-radius: 999px;
  background: rgba(0, 102, 204, 0.08);
  color: #0066cc;
  font-size: 11px;
  font-weight: 600;
  line-height: 20px;
  padding: 0 8px;
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
  height: 3px;
  margin: 9px 0 8px 19px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(0, 102, 204, 0.1);
}

.qc-task-status__progress i {
  position: relative;
  display: block;
  height: 100%;
  overflow: hidden;
  border-radius: inherit;
  background: linear-gradient(90deg, #0066cc 0%, #1684e8 68%, #55adf7 100%);
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
  background: linear-gradient(90deg, rgba(0, 102, 204, 0.28), #0066cc 50%, #45a4f2);
  box-shadow: 0 0 8px rgba(0, 102, 204, 0.3);
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
    box-shadow: 0 0 0 5px rgba(0, 102, 204, 0.08);
  }

  50% {
    box-shadow: 0 0 0 8px rgba(0, 102, 204, 0.16);
  }
}

.qc-task-status__summary {
  flex-wrap: wrap;
  gap: 4px 12px;
  margin-top: 8px;
  color: rgba(29, 29, 31, 0.58);
  font-size: 12px;
  line-height: 18px;
}

.qc-task-status__summary strong {
  color: rgba(29, 29, 31, 0.82);
  font-weight: 600;
}

.qc-task-status__chips {
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.qc-task-status__chips > span {
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.035);
  color: rgba(29, 29, 31, 0.6);
  font-size: 11px;
  line-height: 22px;
  padding: 0 8px;
}

.qc-task-status__chips .is-danger {
  background: rgba(239, 68, 68, 0.07);
  color: #dc2626;
}

.qc-task-status__chips .is-warning {
  background: rgba(245, 158, 11, 0.09);
  color: #b45309;
}

.qc-task-status__chips .is-review {
  background: rgba(0, 102, 204, 0.07);
  color: #0066cc;
}

.qc-task-status__chips .is-success {
  background: rgba(16, 185, 129, 0.08);
  color: #047857;
}

.qc-task-status__actions {
  flex: none;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
  max-width: 360px;
}

.qc-task-status__actions :deep(.ant-btn) {
  border-radius: 8px;
}

@media (max-width: 1080px) {
  .qc-task-status__layout {
    align-items: stretch;
    flex-direction: column;
  }

  .qc-task-status__actions {
    justify-content: flex-start;
    max-width: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .is-running .qc-task-status__indicator,
  .qc-task-status__progress.is-running i,
  .qc-task-status__progress.is-running i::after {
    animation: none;
  }

  .qc-task-status__progress.is-indeterminate i {
    width: 12% !important;
    transform: none;
  }
}
</style>
