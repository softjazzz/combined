<template>
  <a-modal
    :open="open"
    title="诊断追踪"
    width="900px"
    :footer="null"
    @cancel="emit('close')"
  >
    <div class="result-trace-modal">
      <a-alert
        type="info"
        show-icon
        message="仅供管理员或实施人员排查使用"
        description="这里展示的是脱敏后的结果链路：最终客户点结果、聚合/后处理、门控依赖和可安全展示的底层线索，不返回模型原始输出或完整病历正文。"
      />
      <a-alert
        v-if="error"
        type="warning"
        show-icon
        :message="error"
      />
      <a-spin :spinning="loading">
        <div
          v-if="sections.length"
          class="result-trace-sections"
        >
          <section
            v-for="section in sections"
            :key="section.key"
            class="result-trace-section"
          >
            <div class="result-trace-section-head">
              <div>
                <h4>{{ section.title }}</h4>
                <p>{{ section.description }}</p>
              </div>
              <a-tag v-if="section.badge">
                {{ section.badge }}
              </a-tag>
            </div>
            <div
              v-if="section.rows.length"
              class="result-trace-grid"
            >
              <div
                v-for="row in section.rows"
                :key="`${section.key}-${row.key}`"
                class="result-trace-row"
              >
                <span>{{ row.label }}</span>
                <strong>{{ row.value }}</strong>
              </div>
            </div>
            <div
              v-else
              class="result-trace-empty"
            >
              当前结果未保存该层级的可展示诊断数据。
            </div>
          </section>
        </div>
      </a-spin>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
type ResultTraceRow = {
  key: string
  label: string
  value: string
}

type ResultTraceSection = {
  key: string
  title: string
  description: string
  badge?: string
  rows: ResultTraceRow[]
}

defineProps<{
  open: boolean
  loading: boolean
  error: string
  sections: ResultTraceSection[]
}>()

const emit = defineEmits<{
  close: []
}>()
</script>

<style scoped>
.result-trace-modal {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.result-trace-sections {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 14px;
}

.result-trace-section {
  border: 1px solid rgba(226, 232, 240, 0.92);
  border-radius: 10px;
  background: #fff;
  padding: 14px;
}

.result-trace-section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.result-trace-section-head h4 {
  margin: 0;
  color: #0f172a;
  font-size: 15px;
  font-weight: 700;
}

.result-trace-section-head p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.6;
}

.result-trace-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.result-trace-row {
  border-radius: 8px;
  background: #f8fafc;
  min-width: 0;
  padding: 8px 10px;
}

.result-trace-row span {
  display: block;
  color: #64748b;
  font-size: 12px;
  margin-bottom: 4px;
}

.result-trace-row strong {
  display: block;
  color: #0f172a;
  font-size: 13px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

.result-trace-empty {
  border-radius: 8px;
  background: #f8fafc;
  color: #64748b;
  font-size: 13px;
  padding: 12px;
}
</style>
