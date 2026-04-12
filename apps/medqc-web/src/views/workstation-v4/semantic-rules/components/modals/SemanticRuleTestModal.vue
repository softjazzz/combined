<template>
  <a-modal
    :open="open"
    title="规则测试"
    width="920px"
    :footer="null"
    centered
    :destroy-on-close="true"
    @update:open="emit('update:open', $event)"
  >
    <div
      v-if="rule"
      class="test-wrap"
    >
      <div class="test-head">
        <div>
          <div class="test-rule-title">
            {{ rule.name }}
          </div>
          <div class="test-rule-subtitle">
            选择示例或输入病历文本，验证该规则识别结果。
          </div>
        </div>
        <div class="test-example-switch">
          <button
            class="test-example-btn"
            :class="{ active: exampleType === 'negative' }"
            @click="emit('update:exampleType', 'negative')"
          >
            反例（有缺陷）
          </button>
          <button
            class="test-example-btn"
            :class="{ active: exampleType === 'positive' }"
            @click="emit('update:exampleType', 'positive')"
          >
            正例（无缺陷）
          </button>
        </div>
      </div>

      <a-textarea
        :value="medicalText"
        :rows="9"
        class="test-textarea"
        placeholder="请输入病历文本"
        @update:value="emit('update:medicalText', String($event || ''))"
      />

      <div class="test-actions">
        <a-button
          type="primary"
          :loading="loading"
          @click="emit('execute')"
        >
          开始测试
        </a-button>
      </div>

      <div
        v-if="result"
        class="test-result"
      >
        <div class="test-result-head">
          <h4>测试结果</h4>
          <span class="test-confidence">置信度 {{ Math.round(result.confidence * 100) }}%</span>
        </div>
        <div class="test-result-main">
          <a-alert
            :type="result.is_compliant ? 'success' : 'error'"
            :message="result.is_compliant ? '符合规则要求' : '不符合规则要求'"
            :description="result.findings || '暂无详细说明'"
            show-icon
          />
          <div
            v-if="result.evidence"
            class="test-result-block"
          >
            <div class="test-result-block-title">
              证据引用
            </div>
            <div class="test-result-block-content">
              {{ result.evidence }}
            </div>
          </div>
          <div
            v-if="result.suggestion"
            class="test-result-block"
          >
            <div class="test-result-block-title">
              建议
            </div>
            <div class="test-result-block-content">
              {{ result.suggestion }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import type { SemanticRuleItem, SemanticRuleTestResult } from '../../types'

defineProps<{
  open: boolean
  rule: SemanticRuleItem | null
  exampleType: 'positive' | 'negative'
  medicalText: string
  loading: boolean
  result: SemanticRuleTestResult | null
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'update:exampleType': [value: 'positive' | 'negative']
  'update:medicalText': [value: string]
  execute: []
}>()
</script>

<style scoped>
.test-wrap {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.test-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  border: 1px solid #dbeafe;
  border-radius: 14px;
  background: #f8fbff;
  padding: 12px 14px;
}

.test-rule-title {
  color: #0f172a;
  font-size: 16px;
  font-weight: 700;
}

.test-rule-subtitle {
  margin-top: 4px;
  color: #64748b;
  font-size: 12px;
}

.test-example-switch {
  display: inline-flex;
  gap: 8px;
}

.test-example-btn {
  border: 1px solid #cbd5e1;
  background: #ffffff;
  color: #475569;
  border-radius: 10px;
  height: 30px;
  padding: 0 10px;
  font-size: 12px;
  cursor: pointer;
}

.test-example-btn.active {
  border-color: #93c5fd;
  color: #1d4ed8;
  background: #eff6ff;
}

.test-actions {
  display: flex;
  justify-content: flex-end;
}

.test-result {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  overflow: hidden;
}

.test-result-head {
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
}

.test-result-head h4 {
  margin: 0;
  font-size: 14px;
  color: #0f172a;
}

.test-confidence {
  color: #1d4ed8;
  font-weight: 600;
  font-size: 12px;
}

.test-result-main {
  padding: 12px;
  display: grid;
  gap: 12px;
}

.test-result-block {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #ffffff;
}

.test-result-block-title {
  padding: 8px 10px;
  border-bottom: 1px solid #e2e8f0;
  color: #475569;
  font-size: 12px;
  font-weight: 600;
}

.test-result-block-content {
  padding: 10px;
  color: #334155;
  line-height: 1.6;
  font-size: 13px;
  white-space: pre-wrap;
}
</style>
