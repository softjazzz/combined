<template>
  <div
    v-if="versions.length"
    class="readonly-pdf-versions"
  >
    <button
      type="button"
      class="readonly-pdf-toggle"
      :aria-expanded="isExpanded"
      :data-testid="`pdf-versions-toggle-${parentKey}`"
      @click="expanded = !isExpanded"
    >
      <span aria-hidden="true">{{ isExpanded ? '⌄' : '›' }}</span>
      {{
        versions.every((version) => version.pdf_review_relation === 'same_content')
          ? 'PDF对照文本'
          : 'PDF版本'
      }}（{{ versions.length }}）
    </button>
    <div
      v-if="isExpanded"
      class="readonly-pdf-version-list"
    >
      <button
        v-for="version in versions"
        :key="version.key"
        type="button"
        class="readonly-pdf-version"
        :class="{ 'is-active': selectedKey === version.key }"
        :data-testid="`pdf-version-${version.key}`"
        @click="emit('select', version.key)"
      >
        <strong>{{
          version.pdf_review_relation === 'same_content'
            ? 'PDF文本 · 正文一致'
            : 'PDF版本 · 差异待核对'
        }}</strong>
        <small>{{ formatMedicalDocumentTime(resolveMedicalDocumentTime(version))
        }}<template v-if="version.pdf_source_pages?.length">
          · 第{{ pageLabel(version) }}页</template></small>
        <small
          v-for="note in version.pdf_review_notes || []"
          :key="note"
        >{{ note }}</small>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { EditableMedicalRecordDocument } from './types'
import { formatMedicalDocumentTime, resolveMedicalDocumentTime } from './medicalDocumentDisplay'

const props = withDefaults(
  defineProps<{
    parentKey: string
    versions: EditableMedicalRecordDocument[]
    selectedKey?: string
    forceOpen?: boolean
  }>(),
  { selectedKey: '', forceOpen: false },
)
const emit = defineEmits<{ (event: 'select', key: string): void }>()
const expanded = ref(false)
const isExpanded = computed(() => expanded.value || props.forceOpen)
watch(
  () => props.selectedKey,
  (key) => {
    if (props.versions.some((version) => version.key === key)) expanded.value = true
  },
  { immediate: true },
)
function pageLabel(version: EditableMedicalRecordDocument) {
  const pages = [...new Set(version.pdf_source_pages || [])]
  return pages.length === 1 ? String(pages[0]) : pages.join('–')
}
</script>

<style scoped>
.readonly-pdf-versions {
  margin: -2px 12px 6px 24px;
}
.readonly-pdf-toggle {
  display: flex;
  gap: 6px;
  width: 100%;
  border: 0;
  padding: 5px 2px;
  background: transparent;
  color: var(--mq-text-tertiary, #6e6e73);
  font-size: 12px;
  text-align: left;
  cursor: pointer;
}
.readonly-pdf-version-list {
  margin-left: 5px;
  border-left: 1px solid var(--mq-glass-border, #e2e8f0);
}
.readonly-pdf-version {
  display: grid;
  gap: 4px;
  width: 100%;
  border: 0;
  padding: 8px 10px;
  background: transparent;
  text-align: left;
  cursor: pointer;
}
.readonly-pdf-version strong {
  color: var(--mq-text-secondary, #515154);
  font-size: 12px;
  font-weight: 600;
}
.readonly-pdf-version small {
  color: var(--mq-text-tertiary, #6e6e73);
  font-size: 11px;
  line-height: 1.5;
}
.readonly-pdf-version.is-active {
  border-radius: 8px;
  background: var(--mq-bg-muted, #eaf2ff);
}
.readonly-pdf-version.is-active strong {
  color: var(--mq-brand-600, #0a6cff);
}
</style>
