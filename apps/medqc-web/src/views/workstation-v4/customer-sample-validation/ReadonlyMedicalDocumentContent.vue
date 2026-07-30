<template>
  <div class="readonly-medical-document-content" data-testid="readonly-medical-document-content">
    <template v-if="sectionViews.length">
      <section
        v-for="section in sectionViews"
        :key="section.key"
        class="readonly-medical-document-section"
      >
        <h5 class="readonly-medical-document-section-title">
          {{ section.label }}
        </h5>
        <pre class="readonly-medical-document-section-text">{{ section.text }}</pre>
      </section>
    </template>
    <pre v-else class="readonly-medical-document-fallback">{{ document.content || '未记录' }}</pre>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { EditableMedicalRecordDocument, EditableMedicalRecordSection } from './types'

const props = defineProps<{
  document: EditableMedicalRecordDocument
}>()

type SectionView = {
  key: string
  label: string
  text: string
  orderIndex: number
  sourceIndex: number
}

function normalizeLine(value: string): string {
  return value.replace(/\s+/g, '').replace(/[：:]+$/u, '')
}

function removeDuplicateSectionTitle(section: EditableMedicalRecordSection): string {
  const text = String(section.text || '').trim()
  if (!text) return '未记录'

  const lines = text.split(/\r?\n/u)
  if (lines.length > 1 && normalizeLine(lines[0] || '') === normalizeLine(section.label)) {
    return lines.slice(1).join('\n').trim() || '未记录'
  }
  return text
}

const sectionViews = computed<SectionView[]>(() =>
  (props.document.sections || [])
    .map((section, sourceIndex) => ({
      key: section.key || `section-${sourceIndex}`,
      label: String(section.label || '').trim() || '未命名章节',
      text: removeDuplicateSectionTitle(section),
      orderIndex: Number.isFinite(section.order_index)
        ? Number(section.order_index)
        : Number.MAX_SAFE_INTEGER,
      sourceIndex,
    }))
    .sort(
      (left, right) => left.orderIndex - right.orderIndex || left.sourceIndex - right.sourceIndex,
    ),
)
</script>

<style scoped>
.readonly-medical-document-content {
  min-height: 420px;
  max-height: 62vh;
  overflow-y: auto;
  padding: 2px 20px 20px;
  border: 1px solid #dce6f0;
  border-radius: 10px;
  background: #fff;
  color: #172033;
}

.readonly-medical-document-section {
  padding: 20px 0;
  border-bottom: 1px solid #edf1f5;
}

.readonly-medical-document-section:last-child {
  border-bottom: 0;
}

.readonly-medical-document-section-title {
  position: relative;
  margin: 0 0 10px;
  padding-left: 12px;
  color: #1264a3;
  font-size: 15px;
  font-weight: 700;
  line-height: 1.5;
}

.readonly-medical-document-section-title::before {
  position: absolute;
  top: 4px;
  bottom: 4px;
  left: 0;
  width: 3px;
  border-radius: 999px;
  background: #4096ff;
  content: '';
}

.readonly-medical-document-section-text,
.readonly-medical-document-fallback {
  margin: 0;
  color: #27364a;
  font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif;
  font-size: 15px;
  line-height: 1.9;
  white-space: pre-wrap;
  word-break: break-word;
}

.readonly-medical-document-fallback {
  min-height: 380px;
  padding: 20px 0;
}
</style>
