<template>
  <details class="qc-record-column-settings">
    <summary
      class="qc-record-column-settings__trigger"
      title="自定义列表列"
      aria-label="自定义列表列"
      data-testid="qc-record-column-settings-trigger"
    >
      <Settings2 :size="16" aria-hidden="true" />
    </summary>
    <div
      class="qc-record-column-settings__panel"
      data-testid="qc-record-column-settings-panel"
    >
      <div class="qc-record-column-settings__heading">
        <strong>自定义列表列</strong>
      </div>
      <div class="qc-record-column-settings__fixed" aria-label="固定列">
        <span>固定显示</span>
        <span>选择、患者身份、操作</span>
      </div>
      <label
        v-for="option in availableOptions"
        :key="option.key"
        class="qc-record-column-settings__option"
      >
        <input
          type="checkbox"
          :checked="modelValue.includes(option.key)"
          :data-testid="`qc-record-column-${option.key}`"
          @change="toggleColumn(option.key, $event)"
        />
        <span>{{ option.label }}</span>
      </label>
      <button
        class="qc-record-column-settings__restore"
        type="button"
        data-testid="qc-record-column-restore-default"
        @click="restoreDefaults"
      >
        恢复默认
      </button>
    </div>
  </details>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { message } from 'ant-design-vue'
import { Settings2 } from 'lucide-vue-next'

import type { QcRecordCarePhase } from './QcRecordResultTable.vue'
import {
  QC_RECORD_COLUMN_OPTIONS,
  loadQcRecordColumns,
  qcRecordColumnStorageKey,
  sanitizeQcRecordColumns,
  saveQcRecordColumns,
  type QcRecordOptionalColumn,
} from './qcRecordColumnPreferences'

const props = defineProps<{
  userId: string
  carePhase: QcRecordCarePhase
  modelValue: QcRecordOptionalColumn[]
  availableColumns: QcRecordOptionalColumn[]
  defaultColumns: QcRecordOptionalColumn[]
}>()

const emit = defineEmits<{
  'update:modelValue': [columns: QcRecordOptionalColumn[]]
}>()

const availableOptions = computed(() =>
  QC_RECORD_COLUMN_OPTIONS.filter((option) => props.availableColumns.includes(option.key)),
)

watch(
  () => [props.userId, props.carePhase] as const,
  () => {
    const defaults = sanitizeQcRecordColumns(
      props.defaultColumns,
      props.availableColumns,
      props.defaultColumns,
    )
    const key = qcRecordColumnStorageKey(props.userId, props.carePhase)
    if (!key) {
      emit('update:modelValue', defaults)
      return
    }
    const storage = browserLocalStorage()
    if (!storage) {
      emit('update:modelValue', defaults)
      return
    }
    emit(
      'update:modelValue',
      loadQcRecordColumns(storage, key, props.availableColumns, defaults),
    )
  },
  { immediate: true },
)

function applyColumns(columns: QcRecordOptionalColumn[]): boolean {
  const next = sanitizeQcRecordColumns(columns, props.availableColumns, props.defaultColumns)
  const key = qcRecordColumnStorageKey(props.userId, props.carePhase)
  if (key) {
    const storage = browserLocalStorage()
    if (!storage || !saveQcRecordColumns(storage, key, next)) {
      message.error('列设置无法保存，请检查浏览器存储权限')
      return false
    }
  }
  emit('update:modelValue', next)
  return true
}

function toggleColumn(column: QcRecordOptionalColumn, event: Event) {
  const checked = (event.target as HTMLInputElement).checked
  const next = new Set(props.modelValue)
  if (checked) next.add(column)
  else next.delete(column)
  const saved = applyColumns(props.availableColumns.filter((candidate) => next.has(candidate)))
  if (!saved) (event.target as HTMLInputElement).checked = props.modelValue.includes(column)
}

function restoreDefaults() {
  applyColumns([...props.defaultColumns])
}

function browserLocalStorage(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage
  } catch {
    return null
  }
}
</script>

<style scoped>
.qc-record-column-settings {
  position: relative;
}

.qc-record-column-settings__trigger {
  display: inline-flex;
  width: 34px;
  height: 34px;
  box-sizing: border-box;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 8px;
  background: #fff;
  color: rgba(29, 29, 31, 0.68);
  cursor: pointer;
  list-style: none;
  transition: 180ms ease;
}

.qc-record-column-settings__trigger::-webkit-details-marker {
  display: none;
}

.qc-record-column-settings__trigger:hover,
.qc-record-column-settings[open] .qc-record-column-settings__trigger {
  border-color: rgba(0, 122, 255, 0.38);
  background: rgba(0, 122, 255, 0.06);
  color: #007aff;
}

.qc-record-column-settings__trigger:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.1);
}

.qc-record-column-settings__panel {
  position: absolute;
  z-index: 30;
  top: calc(100% + 8px);
  right: 0;
  display: grid;
  width: 248px;
  box-sizing: border-box;
  gap: 4px;
  padding: 14px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 10px 28px rgba(15, 42, 74, 0.14);
  font-family: 'Source Han Sans SC', 'Microsoft YaHei UI', 'PingFang SC', sans-serif;
}

.qc-record-column-settings__heading {
  display: grid;
  gap: 2px;
  padding: 0 2px 8px;
}

.qc-record-column-settings__heading strong {
  color: #1d1d1f;
  font-size: 14px;
  font-weight: 600;
  line-height: 22px;
}

.qc-record-column-settings__heading span,
.qc-record-column-settings__fixed {
  color: rgba(29, 29, 31, 0.52);
  font-size: 12px;
  line-height: 18px;
}

.qc-record-column-settings__fixed {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 4px;
  padding: 7px 8px;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.035);
}

.qc-record-column-settings__option {
  display: flex;
  min-height: 34px;
  align-items: center;
  gap: 9px;
  padding: 0 8px;
  border-radius: 6px;
  color: rgba(29, 29, 31, 0.78);
  cursor: pointer;
  font-size: 14px;
  line-height: 22px;
}

.qc-record-column-settings__option:hover {
  background: rgba(0, 0, 0, 0.04);
}

.qc-record-column-settings__option input {
  width: 15px;
  height: 15px;
  margin: 0;
  accent-color: #007aff;
}

.qc-record-column-settings__restore {
  justify-self: end;
  margin-top: 8px;
  padding: 4px 6px;
  border: 0;
  background: transparent;
  color: #007aff;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
}
</style>
