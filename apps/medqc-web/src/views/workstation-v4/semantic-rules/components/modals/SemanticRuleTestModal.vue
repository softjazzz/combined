<template>
  <a-modal
    :open="open"
    title="规则测试"
    width="960px"
    :footer="null"
    centered
    :destroy-on-close="true"
    class="semantic-test-modal"
    @update:open="emit('update:open', $event)"
  >
    <div
      v-if="rule"
      class="test-wrap"
    >
      <div class="test-head">
        <div>
          <div class="test-kicker">
            规则评估
          </div>
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
        <span class="test-action-hint">仅用于规则验证，不写入正式质控结果。</span>
        <a-button
          type="primary"
          class="test-primary-btn"
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
          <div>
            <span class="test-result-kicker">评估输出</span>
            <h4>测试结果</h4>
          </div>
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
            v-if="
              result.error_message || result.error_detail || result.trace_id || result.status_code
            "
            class="test-result-block"
          >
            <div class="test-result-block-title">
              调试信息
            </div>
            <div class="test-result-block-content test-result-debug">
              <p v-if="result.error_category">
                错误分类：{{ result.error_category }}
              </p>
              <p v-if="result.status_code">
                状态码：{{ result.status_code }}
              </p>
              <p v-if="result.trace_id">
                Trace ID：{{ result.trace_id }}
              </p>
              <p v-if="result.error_detail">
                错误详情：{{ result.error_detail }}
              </p>
            </div>
          </div>
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
:global(.semantic-test-modal .ant-modal-content) {
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.9);
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.14);
}

:global(.semantic-test-modal .ant-modal-header) {
  margin: 0;
  padding: 18px 22px 12px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.82);
}

:global(.semantic-test-modal .ant-modal-title) {
  color: #1d1d1f;
  font-family:
    'San Francisco', 'SF Pro Text', 'Source Han Sans SC', 'PingFang SC', 'Microsoft YaHei UI',
    system-ui, sans-serif;
  font-size: 17px;
  font-weight: 600;
}

:global(.semantic-test-modal .ant-modal-body) {
  max-height: min(78vh, 760px);
  overflow-y: auto;
  padding: 18px 22px 20px;
  background: #f5f5f7;
}

.test-wrap {
  display: flex;
  flex-direction: column;
  gap: 12px;
  color: #1d1d1f;
  font-family:
    'San Francisco', 'SF Pro Text', 'Source Han Sans SC', 'PingFang SC', 'Microsoft YaHei UI',
    system-ui, sans-serif;
}

.test-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.86);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  padding: 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.045);
}

.test-kicker {
  margin-bottom: 5px;
  color: #0a6cff;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.test-rule-title {
  color: #1d1d1f;
  font-size: 18px;
  font-weight: 650;
  line-height: 1.35;
}

.test-rule-subtitle {
  margin-top: 4px;
  color: rgba(29, 29, 31, 0.52);
  font-size: 13px;
}

.test-example-switch {
  display: inline-flex;
  flex: none;
  gap: 4px;
  border-radius: 999px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(0, 0, 0, 0.04);
  padding: 3px;
}

.test-example-btn {
  border: none;
  background: transparent;
  color: rgba(29, 29, 31, 0.62);
  border-radius: 999px;
  height: 28px;
  padding: 0 12px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition:
    background-color 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    color 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.test-example-btn.active {
  color: #0a6cff;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

.test-textarea {
  border-radius: 16px;
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.88);
  color: #1d1d1f;
  font-size: 13px;
  line-height: 1.7;
  box-shadow: none;
}

.test-textarea:focus,
.test-textarea:hover {
  border-color: rgba(10, 108, 255, 0.32);
  box-shadow: 0 0 0 3px rgba(10, 108, 255, 0.08);
}

.test-actions {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.test-action-hint {
  color: rgba(29, 29, 31, 0.46);
  font-size: 12px;
}

.test-primary-btn {
  height: 34px;
  border-radius: 8px;
  background: #0a6cff;
  border-color: #0a6cff;
  font-size: 13px;
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(10, 108, 255, 0.16);
}

.test-result {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.86);
  overflow: hidden;
}

.test-result-head {
  background: rgba(255, 255, 255, 0.9);
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
}

.test-result-kicker {
  color: rgba(29, 29, 31, 0.42);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.test-result-head h4 {
  margin: 2px 0 0;
  font-size: 14px;
  color: #1d1d1f;
  font-weight: 650;
}

.test-confidence {
  border-radius: 999px;
  border: 1px solid rgba(10, 108, 255, 0.18);
  background: rgba(10, 108, 255, 0.08);
  padding: 4px 9px;
  color: #0a6cff;
  font-weight: 700;
  font-size: 12px;
}

.test-result-main {
  padding: 12px;
  display: grid;
  gap: 12px;
}

.test-result-block {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.86);
  overflow: hidden;
}

.test-result-block-title {
  padding: 8px 10px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  color: rgba(29, 29, 31, 0.52);
  font-size: 12px;
  font-weight: 600;
}

.test-result-block-content {
  padding: 10px;
  color: rgba(29, 29, 31, 0.74);
  line-height: 1.6;
  font-size: 13px;
  white-space: pre-wrap;
}

.test-result-debug p {
  margin: 0;
}

.test-result-debug p + p {
  margin-top: 4px;
}
</style>
