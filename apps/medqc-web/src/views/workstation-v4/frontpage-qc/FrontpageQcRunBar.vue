<template>
  <section
    v-if="run || error"
    class="fpqc-run mq-card"
    role="status"
    aria-live="polite"
    data-testid="fpqc-run-bar"
  >
    <template v-if="run">
      <div class="fpqc-run__main">
        <span :class="['mq-status', `mq-status--${tone}`]">{{ statusLabel }}</span>
        <strong class="fpqc-run__title">{{ title }}</strong>
        <span class="fpqc-run__counts">
          已处理 {{ run.processed_records }}/{{ run.total_records }} 份
          <template v-if="run.issue_records"> · 有扣分问题 {{ run.issue_records }} 份</template>
          <template v-if="run.failed_count"> · 未能质控 {{ run.failed_count }} 份</template>
        </span>
        <div class="fpqc-run__actions">
          <button
            v-if="active"
            type="button"
            class="mq-btn fpqc-run__btn"
            :disabled="cancelling || run.cancel_requested"
            @click="emit('cancel')"
          >
            {{ run.cancel_requested ? '正在取消…' : '取消任务' }}
          </button>
          <button
            v-else
            type="button"
            class="mq-btn fpqc-run__btn"
            @click="emit('dismiss')"
          >
            关闭
          </button>
        </div>
      </div>
      <div
        class="fpqc-run__progress"
        role="progressbar"
        :aria-valuenow="percent"
        aria-valuemin="0"
        aria-valuemax="100"
      >
        <span :style="{ width: `${percent}%` }" />
      </div>
      <p
        v-if="run.error_message"
        class="fpqc-run__note fpqc-run__note--danger"
      >
        {{ run.error_message }}
      </p>
      <details
        v-if="run.failed_records.length"
        class="fpqc-run__failed"
      >
        <summary>查看未能质控的病历（{{ run.failed_count }} 份）</summary>
        <ul>
          <li
            v-for="item in run.failed_records"
            :key="`${item.institute_id}|${item.patient_id}|${item.visit_id}`"
          >
            住院号 {{ item.visit_id }}：{{ item.message || item.error }}
          </li>
        </ul>
      </details>
    </template>
    <p
      v-if="error"
      class="fpqc-run__note fpqc-run__note--warning"
    >
      {{ error }}
    </p>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import { isFrontpageQcRunActive, type FrontpageQcRun } from '@/services/frontpage-qc-v2-service'

import { RUN_STATUS_LABELS, runProgressPercent, runTone } from './presentation'

const props = defineProps<{ run: FrontpageQcRun | null; error: string; cancelling: boolean }>()
const emit = defineEmits<{ cancel: []; dismiss: [] }>()

const active = computed(() => isFrontpageQcRunActive(props.run))
const percent = computed(() => (props.run ? runProgressPercent(props.run) : 0))
const tone = computed(() => (props.run ? runTone(props.run.status) : 'neutral'))
const statusLabel = computed(() => (props.run ? RUN_STATUS_LABELS[props.run.status] : ''))
const title = computed(() => {
  const filters = props.run?.filters ?? {}
  if (filters.mode === 'selected') return `首页质控 · 所选 ${props.run?.total_records ?? 0} 份`
  const parts = [String(filters.department || '') || '全部科室']
  if (filters.start_date || filters.end_date) {
    parts.push(`出院 ${filters.start_date || '不限'} 至 ${filters.end_date || '不限'}`)
  }
  if (filters.keyword) parts.push(`关键词“${filters.keyword}”`)
  return `首页质控 · ${parts.join(' · ')}`
})
</script>

<style scoped>
.fpqc-run {
  display: grid;
  gap: 10px;
  padding: 14px 20px;
}

.fpqc-run__main {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 14px;
}

.fpqc-run__title {
  font-size: var(--mq-font-14);
  white-space: nowrap;
}

.fpqc-run__counts {
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-13);
}

.fpqc-run__actions {
  margin-left: auto;
}

.fpqc-run__btn {
  height: 32px;
  padding: 0 14px;
  font-size: var(--mq-font-13);
}

.fpqc-run__progress {
  height: 6px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--mq-bg-muted);
}

.fpqc-run__progress span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--mq-brand-gradient);
  transition: width 0.3s ease;
}

.fpqc-run__note {
  margin: 0;
  font-size: var(--mq-font-13);
}

.fpqc-run__note--danger {
  color: var(--mq-danger-text);
}

.fpqc-run__note--warning {
  color: var(--mq-warning-text);
}

.fpqc-run__failed summary {
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-13);
  cursor: pointer;
}

.fpqc-run__failed ul {
  margin: 6px 0 0;
  padding-left: 18px;
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-12);
}
</style>
