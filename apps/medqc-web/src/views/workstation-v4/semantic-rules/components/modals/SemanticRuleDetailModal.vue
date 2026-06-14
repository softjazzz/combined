<template>
  <a-modal
    :open="open"
    title="规则详情"
    width="960px"
    :footer="null"
    centered
    class="semantic-modal"
    @update:open="emit('update:open', $event)"
  >
    <div v-if="rule" class="detail-wrap">
      <div class="detail-summary">
        <div class="detail-summary-head">
          <div class="detail-title-block">
            <span class="detail-kicker">质控规则</span>
            <h3 class="detail-title">
              {{ rule.name }}
            </h3>
          </div>
          <span class="detail-code">{{ rule.rule_code || rule.rule_id }}</span>
        </div>
        <p class="detail-desc">
          {{ rule.description || '暂无描述' }}
        </p>
      </div>

      <a-descriptions :column="2" size="small" class="detail-descriptions">
        <a-descriptions-item label="分类">
          {{ getCategoryZh(rule.category) }}
        </a-descriptions-item>
        <a-descriptions-item label="复杂度">
          <span class="tag tag-plain">{{ rule.complexity }}</span>
        </a-descriptions-item>
        <a-descriptions-item label="缺陷级别">
          <span class="tag tag-danger">{{ getSeverityZh(rule.defect_level) }}</span>
        </a-descriptions-item>
        <a-descriptions-item label="扣分"> {{ rule.score_deduction }} 分 </a-descriptions-item>
        <a-descriptions-item label="适用文书">
          <div class="doc-list">
            <span v-for="doc in rule.applicable_documents" :key="doc" class="doc-pill">
              {{ getDocTypeZh(doc) }}
            </span>
          </div>
        </a-descriptions-item>
      </a-descriptions>

      <div v-if="isLuxianRule" class="luxian-panel">
        <div class="luxian-section">
          <h4>客户质控点口径</h4>
          <p>{{ rule.customer_text || rule.description || '暂无客户原文' }}</p>
        </div>

        <div class="luxian-grid">
          <div class="luxian-section">
            <h4>触发条件</h4>
            <p>{{ rule.trigger_condition || '暂无触发条件' }}</p>
          </div>
          <div class="luxian-section">
            <h4>不触发条件</h4>
            <p>{{ rule.non_trigger_condition || '暂无不触发条件' }}</p>
          </div>
        </div>

        <div class="luxian-section">
          <h4>映射执行规则</h4>
          <div class="rule-chip-list">
            <span
              v-for="ruleId in rule.mapped_rule_ids || []"
              :key="ruleId"
              class="rule-chip"
              :class="{ primary: ruleId === rule.primary_execution_rule_id }"
            >
              {{ ruleId }}{{ ruleId === rule.primary_execution_rule_id ? ' · 主执行' : '' }}
            </span>
          </div>
        </div>

        <div class="luxian-grid compact">
          <div class="luxian-section">
            <h4>执行依赖</h4>
            <p>{{ formatDependencyType(rule.dependency_type) }}</p>
            <p class="muted">
              {{ rule.required_documents_label || '文书范围待确认' }}
            </p>
          </div>
          <div class="luxian-section">
            <h4>数据状态</h4>
            <p>{{ formatDataStatus(rule.data_status) }}</p>
            <p class="muted">
              {{ formatImplementationStatus(rule.implementation_status) }}
            </p>
          </div>
        </div>

        <div class="example-grid">
          <div v-if="rule.negative_example" class="example-card danger">
            <h4>反例</h4>
            <strong>{{ rule.negative_example.title }}</strong>
            <p>{{ rule.negative_example.summary }}</p>
            <ul>
              <li v-for="item in rule.negative_example.focusPoints || []" :key="item">
                {{ item }}
              </li>
            </ul>
          </div>
          <div v-if="rule.positive_example" class="example-card safe">
            <h4>正例</h4>
            <strong>{{ rule.positive_example.title }}</strong>
            <p>{{ rule.positive_example.summary }}</p>
            <ul>
              <li v-for="item in rule.positive_example.focusPoints || []" :key="item">
                {{ item }}
              </li>
            </ul>
          </div>
        </div>
      </div>

      <div v-if="isAdmin || isLuxianRule" class="prompt-panel">
        <div class="prompt-header">
          <div>
            <h4 class="prompt-title">检查模板管理</h4>
            <p v-if="isLuxianRule" class="prompt-subtitle">
              泸县0609客户专项规则包使用只读模板；如需调整执行逻辑，请修改映射的底层规则或规则包配置。
            </p>
          </div>
          <div class="prompt-actions">
            <a-button
              v-if="!isEditingPrompt && !isLuxianRule"
              type="link"
              size="small"
              @click="emit('startEditPrompt')"
            >
              编辑
            </a-button>
            <span v-else-if="isLuxianRule" class="readonly-badge"> 只读模板 </span>
            <template v-else>
              <a-button size="small" @click="emit('cancelEditPrompt')"> 取消 </a-button>
              <a-button
                type="primary"
                size="small"
                :loading="promptLoading"
                @click="emit('savePrompt')"
              >
                保存
              </a-button>
            </template>
          </div>
        </div>

        <div v-if="!isEditingPrompt" class="prompt-content">
          {{ currentPrompt || '// 暂无检查模板，使用系统默认逻辑' }}
        </div>
        <a-textarea
          v-else
          :value="editingPrompt"
          :rows="10"
          class="prompt-editor"
          placeholder="请输入自定义检查模板"
          @update:value="emit('update:editingPrompt', String($event || ''))"
        />
      </div>

      <div class="detail-footer">
        <a-button class="detail-secondary-btn" @click="emit('update:open', false)"> 关闭 </a-button>
        <a-button type="primary" class="detail-primary-btn" @click="emit('startTest')">
          开始测试
        </a-button>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { SemanticRuleItem } from '../../types'
import {
  getCategoryZh,
  getDataStatusZh,
  getDependencyTypeZh,
  getDocTypeZh,
  getImplementationStatusZh,
  getSeverityZh,
} from '../../types'

const props = defineProps<{
  open: boolean
  rule: SemanticRuleItem | null
  isAdmin: boolean
  promptLoading: boolean
  isEditingPrompt: boolean
  currentPrompt: string
  editingPrompt: string
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  startEditPrompt: []
  cancelEditPrompt: []
  savePrompt: []
  'update:editingPrompt': [value: string]
  startTest: []
}>()

const isLuxianRule = computed(() => props.rule?.rule_id.startsWith('LX0609-') || false)

function formatImplementationStatus(value?: string): string {
  return getImplementationStatusZh(value)
}

function formatDependencyType(value?: string): string {
  return getDependencyTypeZh(value)
}

function formatDataStatus(value?: string): string {
  return getDataStatusZh(value)
}
</script>

<style scoped>
:global(.semantic-modal .ant-modal-content) {
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.9);
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.14);
}

:global(.semantic-modal .ant-modal-header) {
  margin: 0;
  padding: 18px 22px 12px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.82);
}

:global(.semantic-modal .ant-modal-title) {
  color: #1d1d1f;
  font-family:
    'San Francisco', 'SF Pro Text', 'Source Han Sans SC', 'PingFang SC', 'Microsoft YaHei UI',
    system-ui, sans-serif;
  font-size: 17px;
  font-weight: 600;
}

:global(.semantic-modal .ant-modal-body) {
  max-height: min(78vh, 760px);
  overflow-y: auto;
  padding: 18px 22px 20px;
  background: #f5f5f7;
}

.detail-wrap {
  display: flex;
  flex-direction: column;
  gap: 12px;
  color: #1d1d1f;
  font-family:
    'San Francisco', 'SF Pro Text', 'Source Han Sans SC', 'PingFang SC', 'Microsoft YaHei UI',
    system-ui, sans-serif;
}

.detail-summary {
  border-radius: 18px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.86);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  padding: 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.045);
}

.detail-summary-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.detail-title-block {
  min-width: 0;
}

.detail-kicker {
  display: block;
  margin-bottom: 5px;
  color: #0066cc;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.detail-title {
  margin: 0;
  color: #1d1d1f;
  font-size: 20px;
  font-weight: 650;
  line-height: 1.35;
}

.detail-code {
  display: inline-flex;
  align-items: center;
  flex: none;
  border-radius: 999px;
  border: 1px solid rgba(0, 102, 204, 0.18);
  background: rgba(0, 102, 204, 0.08);
  padding: 5px 10px;
  color: #0066cc;
  font-size: 12px;
  font-weight: 700;
}

.detail-desc {
  margin: 12px 0 0;
  color: rgba(29, 29, 31, 0.6);
  font-size: 13px;
  line-height: 1.6;
}

.detail-descriptions {
  padding: 12px 14px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.82);
}

.detail-descriptions :deep(.ant-descriptions-item-label) {
  color: rgba(29, 29, 31, 0.46);
  font-size: 12px;
}

.detail-descriptions :deep(.ant-descriptions-item-content) {
  color: rgba(29, 29, 31, 0.78);
  font-size: 13px;
}

.tag {
  display: inline-flex;
  align-items: center;
  height: 24px;
  border-radius: 999px;
  padding: 0 8px;
  border: 1px solid transparent;
  font-size: 12px;
  font-weight: 600;
}

.tag-plain {
  background: rgba(0, 0, 0, 0.04);
  color: rgba(29, 29, 31, 0.62);
  border-color: rgba(0, 0, 0, 0.08);
}

.tag-danger {
  background: rgba(255, 69, 58, 0.1);
  color: #d92d20;
  border-color: rgba(255, 69, 58, 0.18);
}

.doc-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.doc-pill {
  display: inline-flex;
  align-items: center;
  height: 22px;
  border-radius: 999px;
  border: 1px solid rgba(0, 102, 204, 0.18);
  background: rgba(0, 102, 204, 0.08);
  color: #0066cc;
  padding: 0 8px;
  font-size: 12px;
  font-weight: 600;
}

.luxian-panel {
  display: grid;
  gap: 12px;
  border-radius: 18px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.72);
  padding: 14px;
}

.luxian-grid,
.example-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.luxian-grid.compact {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.luxian-section,
.example-card {
  border-radius: 14px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.86);
  padding: 12px;
}

.luxian-section h4,
.example-card h4 {
  margin: 0 0 8px;
  color: #1d1d1f;
  font-size: 13px;
  font-weight: 650;
}

.luxian-section p,
.example-card p {
  margin: 0;
  color: rgba(29, 29, 31, 0.62);
  font-size: 13px;
  line-height: 1.65;
}

.luxian-section .muted {
  margin-top: 4px;
  color: rgba(29, 29, 31, 0.38);
  font-size: 12px;
}

.rule-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.rule-chip {
  display: inline-flex;
  align-items: center;
  height: 24px;
  border-radius: 999px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(0, 0, 0, 0.04);
  padding: 0 9px;
  color: rgba(29, 29, 31, 0.62);
  font-size: 12px;
  font-weight: 600;
}

.rule-chip.primary {
  border-color: rgba(0, 102, 204, 0.18);
  background: rgba(0, 102, 204, 0.08);
  color: #0066cc;
}

.example-card strong {
  display: block;
  margin-bottom: 6px;
  color: #1d1d1f;
  font-size: 13px;
}

.example-card ul {
  margin: 8px 0 0;
  padding-left: 18px;
  color: rgba(29, 29, 31, 0.56);
  font-size: 12px;
  line-height: 1.6;
}

.example-card.danger {
  border-color: rgba(255, 69, 58, 0.16);
  background: rgba(255, 69, 58, 0.04);
}

.example-card.safe {
  border-color: rgba(16, 185, 129, 0.16);
  background: rgba(16, 185, 129, 0.04);
}

.prompt-panel {
  border-radius: 18px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.82);
  padding: 14px;
}

.prompt-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.prompt-title {
  margin: 0;
  color: #1d1d1f;
  font-size: 15px;
  font-weight: 650;
}

.prompt-subtitle {
  margin: 4px 0 0;
  color: rgba(29, 29, 31, 0.52);
  font-size: 12px;
  line-height: 1.5;
}

.prompt-actions {
  display: inline-flex;
  gap: 8px;
}

.readonly-badge {
  display: inline-flex;
  align-items: center;
  height: 24px;
  border-radius: 999px;
  border: 1px solid rgba(0, 102, 204, 0.18);
  background: rgba(0, 102, 204, 0.08);
  padding: 0 8px;
  color: #0066cc;
  font-size: 12px;
  font-weight: 700;
}

.prompt-content {
  margin-top: 10px;
  border-radius: 12px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(29, 29, 31, 0.94);
  color: rgba(255, 255, 255, 0.78);
  padding: 12px;
  white-space: pre-wrap;
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New',
    monospace;
  font-size: 12px;
  max-height: 260px;
  overflow-y: auto;
}

.prompt-editor {
  margin-top: 10px;
}

.detail-footer {
  border-top: 1px solid rgba(0, 0, 0, 0.08);
  padding-top: 12px;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.detail-primary-btn,
.detail-secondary-btn {
  height: 34px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
}

.detail-primary-btn {
  background: #0066cc;
  border-color: #0066cc;
  box-shadow: 0 2px 8px rgba(0, 102, 204, 0.16);
}

.detail-secondary-btn {
  border-color: rgba(0, 0, 0, 0.08);
  color: rgba(29, 29, 31, 0.66);
}

@media (max-width: 768px) {
  .luxian-grid,
  .luxian-grid.compact,
  .example-grid {
    grid-template-columns: 1fr;
  }
}
</style>
