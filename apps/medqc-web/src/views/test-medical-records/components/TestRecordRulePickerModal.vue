<template>
  <a-modal
    :open="open"
    :title="title"
    :ok-text="okText"
    cancel-text="取消"
    :confirm-loading="submitting"
    :ok-button-props="{ disabled: !catalog || (requireSelection && !selectedRuleIds.length) }"
    width="720px"
    @ok="emit('confirm', [...selectedRuleIds])"
    @cancel="emit('cancel')"
  >
    <a-alert
      v-if="catalogError"
      type="warning"
      show-icon
      :message="catalogError"
      description="当前规则集版本不可用时不能关联或运行质控点。"
      class="rule-picker__alert"
    />
    <template v-else-if="catalog">
      <p class="rule-picker__meta">
        规则集 {{ catalog.rule_set_key }} · 当前版本 {{ catalog.version }} · 共
        {{ catalog.entries.length }} 条
      </p>
      <p
        v-if="hint"
        class="rule-picker__hint"
      >
        {{ hint }}
      </p>
      <a-select
        v-model:value="selectedRuleIds"
        mode="multiple"
        allow-clear
        show-search
        option-filter-prop="label"
        placeholder="搜索并选择质控点"
        class="rule-picker__select"
        :options="options"
      />
      <p
        v-if="staleRuleIds.length"
        class="rule-picker__stale"
      >
        以下规则不在当前版本中，保存前请移除：{{ staleRuleIds.join('、') }}
      </p>
    </template>
    <a-skeleton
      v-else
      active
    />
  </a-modal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { CurrentRuleSetCatalog } from '@/types/test-medical-records'
import { buildRuleOptions } from './testRecordPresentation'

const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    okText: string
    catalog: CurrentRuleSetCatalog | null
    catalogError?: string
    initialRuleIds: string[]
    submitting?: boolean
    requireSelection?: boolean
    hint?: string
  }>(),
  { catalogError: '', submitting: false, requireSelection: false, hint: '' },
)

const emit = defineEmits<{
  (event: 'confirm', ruleIds: string[]): void
  (event: 'cancel'): void
}>()

const selectedRuleIds = ref<string[]>([])

watch(
  () => [props.open, props.initialRuleIds] as const,
  ([open]) => {
    if (open) selectedRuleIds.value = [...props.initialRuleIds]
  },
  { immediate: true },
)

const options = computed(() => buildRuleOptions(props.catalog, selectedRuleIds.value))
const staleRuleIds = computed(() => {
  const known = new Set((props.catalog?.entries || []).map((entry) => entry.rule_id))
  return selectedRuleIds.value.filter((ruleId) => !known.has(ruleId))
})
</script>

<style scoped>
.rule-picker__alert {
  margin-bottom: 12px;
}

.rule-picker__meta,
.rule-picker__hint {
  margin: 0 0 8px;
  color: var(--ant-color-text-secondary, #64748b);
  font-size: 12px;
}

.rule-picker__select {
  width: 100%;
}

.rule-picker__stale {
  margin: 8px 0 0;
  color: var(--ant-color-warning, #d97706);
  font-size: 12px;
}
</style>
