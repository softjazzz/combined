<template>
  <a-drawer
    :open="visible"
    width="520"
    title="规则详情"
    placement="right"
    @close="emit('close')"
  >
    <a-spin :spinning="loading">
      <template v-if="localRule">
        <a-form layout="vertical">
          <a-form-item label="规则名称">
            <a-input
              v-model:value="localRule.name"
              :disabled="readonly"
              @change="onChange"
            />
          </a-form-item>
          <a-form-item label="规则描述">
            <a-textarea
              v-model:value="localRule.description"
              :disabled="readonly"
              :rows="3"
              @change="onChange"
            />
          </a-form-item>
          <a-form-item label="规则状态">
            <a-radio-group
              v-model:value="localRule.status"
              :disabled="readonly"
              @change="onChange"
            >
              <a-radio value="draft">
                草稿
              </a-radio>
              <a-radio value="published">
                已发布
              </a-radio>
              <a-radio value="disabled">
                停用
              </a-radio>
            </a-radio-group>
          </a-form-item>
          <a-form-item label="条件表达式（简化展示）">
            <a-textarea
              :value="conditionPreview"
              :rows="4"
              :disabled="readonly"
              @update:value="onConditionTextChange"
            />
          </a-form-item>
        </a-form>

        <div class="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
          <div class="text-[12px] font-semibold text-slate-700">
            示例命中预览
          </div>
          <div class="mt-2 space-y-1">
            <div
              v-for="item in samplePreview"
              :key="item.caseId"
              class="text-[12px]"
            >
              <a-tag :color="item.matched ? 'green' : 'default'">
                {{ item.matched ? '命中' : '未命中' }}
              </a-tag>
              {{ item.caseId }} {{ item.reason || '' }}
            </div>
          </div>
        </div>

        <a-space class="mt-4">
          <a-button
            type="primary"
            :disabled="readonly"
            @click="emit('save-draft', localRule)"
          >
            保存草稿
          </a-button>
          <a-button
            :disabled="readonly"
            @click="emit('preview-hit', { id: localRule.id })"
          >
            预览命中
          </a-button>
          <a-button
            danger
            :disabled="readonly"
            @click="emit('delete-rule', { id: localRule.id })"
          >
            删除
          </a-button>
        </a-space>
      </template>
    </a-spin>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { RuleDetail } from './types'

const props = defineProps<{
  visible: boolean
  loading: boolean
  rule?: RuleDetail
  readonly: boolean
  dirty: boolean
  samplePreview: Array<{ caseId: string; matched: boolean; reason?: string }>
}>()

const emit = defineEmits<{
  close: []
  change: [payload: Partial<RuleDetail>]
  'save-draft': [payload: RuleDetail]
  'toggle-status': [payload: { id: string; status: 'published' | 'disabled' }]
  'delete-rule': [payload: { id: string }]
  'preview-hit': [payload: { id: string }]
  'open-history': [payload: { id: string }]
}>()

const localRule = ref<RuleDetail | undefined>(undefined)

watch(
  () => props.rule,
  (value) => {
    localRule.value = value ? JSON.parse(JSON.stringify(value)) : undefined
  },
  { immediate: true },
)

const conditionPreview = computed(() =>
  JSON.stringify(localRule.value?.conditionTree || {}, null, 2),
)

function onChange() {
  if (!localRule.value) return
  emit('change', localRule.value)
}

function onConditionTextChange(text: string) {
  if (!localRule.value) return
  try {
    localRule.value.conditionTree = JSON.parse(text)
    emit('change', localRule.value)
  } catch {
    // 忽略非法 JSON，避免阻断输入
  }
}
</script>
