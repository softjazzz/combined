<template>
  <a-modal
    :open="open"
    title="规则详情"
    width="880px"
    :footer="null"
    centered
    class="semantic-modal"
    @update:open="emit('update:open', $event)"
  >
    <div
      v-if="rule"
      class="detail-wrap"
    >
      <div class="detail-summary">
        <div class="detail-summary-head">
          <h3 class="detail-title">
            {{ rule.name }}
          </h3>
          <span class="detail-code">{{ rule.rule_code || rule.rule_id }}</span>
        </div>
        <p class="detail-desc">
          {{ rule.description || '暂无描述' }}
        </p>
      </div>

      <a-descriptions
        :column="2"
        size="small"
        class="detail-descriptions"
      >
        <a-descriptions-item label="分类">
          {{ getCategoryZh(rule.category) }}
        </a-descriptions-item>
        <a-descriptions-item label="复杂度">
          <span class="tag tag-plain">{{ rule.complexity }}</span>
        </a-descriptions-item>
        <a-descriptions-item label="缺陷级别">
          <span class="tag tag-danger">{{ getSeverityZh(rule.defect_level) }}</span>
        </a-descriptions-item>
        <a-descriptions-item label="扣分">
          {{ rule.score_deduction }} 分
        </a-descriptions-item>
        <a-descriptions-item label="适用文书">
          <div class="doc-list">
            <span
              v-for="doc in rule.applicable_documents"
              :key="doc"
              class="doc-pill"
            >
              {{ getDocTypeZh(doc) }}
            </span>
          </div>
        </a-descriptions-item>
      </a-descriptions>

      <div
        v-if="isAdmin"
        class="prompt-panel"
      >
        <div class="prompt-header">
          <h4 class="prompt-title">
            Prompt 管理
          </h4>
          <div class="prompt-actions">
            <a-button
              v-if="!isEditingPrompt"
              type="link"
              size="small"
              @click="emit('startEditPrompt')"
            >
              编辑
            </a-button>
            <template v-else>
              <a-button
                size="small"
                @click="emit('cancelEditPrompt')"
              >
                取消
              </a-button>
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

        <div
          v-if="!isEditingPrompt"
          class="prompt-content"
        >
          {{ currentPrompt || '// 暂无提示词，使用系统默认模板' }}
        </div>
        <a-textarea
          v-else
          :value="editingPrompt"
          :rows="10"
          class="prompt-editor"
          placeholder="请输入自定义 Prompt"
          @update:value="emit('update:editingPrompt', String($event || ''))"
        />
      </div>

      <div class="detail-footer">
        <a-button @click="emit('update:open', false)">
          关闭
        </a-button>
        <a-button
          type="primary"
          @click="emit('startTest')"
        >
          开始测试
        </a-button>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import type { SemanticRuleItem } from '../../types'
import { getCategoryZh, getDocTypeZh, getSeverityZh } from '../../types'

defineProps<{
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
</script>

<style scoped>
.detail-wrap {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.detail-summary {
  border-radius: 14px;
  border: 1px solid #dbeafe;
  background: linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
  padding: 14px;
}

.detail-summary-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
}

.detail-title {
  margin: 0;
  color: #0f172a;
  font-size: 20px;
  font-weight: 700;
}

.detail-code {
  display: inline-flex;
  align-items: center;
  border-radius: 10px;
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  padding: 4px 8px;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 600;
}

.detail-desc {
  margin: 10px 0 0;
  color: #475569;
  font-size: 14px;
  line-height: 1.6;
}

.detail-descriptions :deep(.ant-descriptions-item-label) {
  color: #64748b;
}

.tag {
  display: inline-flex;
  align-items: center;
  height: 24px;
  border-radius: 8px;
  padding: 0 8px;
  border: 1px solid transparent;
  font-size: 12px;
  font-weight: 600;
}

.tag-plain {
  background: #f1f5f9;
  color: #475569;
  border-color: #cbd5e1;
}

.tag-danger {
  background: #fee2e2;
  color: #b91c1c;
  border-color: #fecaca;
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
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  color: #1d4ed8;
  padding: 0 8px;
  font-size: 12px;
}

.prompt-panel {
  border-top: 1px solid #e2e8f0;
  padding-top: 12px;
}

.prompt-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.prompt-title {
  margin: 0;
  color: #0f172a;
  font-size: 15px;
  font-weight: 700;
}

.prompt-actions {
  display: inline-flex;
  gap: 8px;
}

.prompt-content {
  margin-top: 10px;
  border-radius: 12px;
  border: 1px solid #1e293b;
  background: #0f172a;
  color: #cbd5e1;
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
  border-top: 1px solid #e2e8f0;
  padding-top: 12px;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
