<template>
  <div
    class="llm-role-settings"
    data-testid="task-role-settings"
  >
    <header class="llm-role-header">
      <h3 class="llm-role-title">
        按任务用途选模型
      </h3>
      <p class="mq-field__hint">
        未单独指定的用途继承默认模型，不增加模型调用次数。
      </p>
    </header>
    <div class="mq-inset llm-role-list">
      <div
        v-for="role in roleRows"
        :key="role.key"
        class="llm-role-row"
      >
        <div class="mq-field">
          <span class="llm-role-label">{{ role.label }}</span>
          <span class="mq-field__hint">{{ role.hint }}</span>
        </div>
        <div class="llm-role-controls">
          <a-select
            :data-testid="`task-role-provider-${role.key}`"
            :aria-label="`${role.label}推理服务`"
            :value="value[role.key]?.provider_code || 'inherit'"
            :disabled="disabled"
            :options="providerOptions"
            class="llm-role-select"
            @change="selectProvider(role.key, String($event))"
          />
          <a-select
            v-if="value[role.key]"
            :data-testid="`task-role-model-${role.key}`"
            :aria-label="`${role.label}模型`"
            :value="value[role.key]?.model_code || undefined"
            :disabled="disabled || pending[value[role.key]?.provider_code || '']"
            :loading="pending[value[role.key]?.provider_code || '']"
            :options="modelOptions(value[role.key]?.provider_code || '')"
            show-search
            option-filter-prop="label"
            placeholder="选择该用途的模型"
            class="llm-role-select"
            @change="selectModel(role.key, String($event))"
          />
          <span
            v-else
            class="mq-field__hint llm-role-inherit"
          >使用默认模型</span>
          <span
            v-if="errors[value[role.key]?.provider_code || '']"
            role="alert"
            class="llm-role-error"
          >
            模型目录读取失败，请重新选择服务后重试。
          </span>
        </div>
      </div>
    </div>
    <p class="mq-field__hint llm-role-note">
      事实抽取已绑定检查检验与会诊意见；专项核验用于检查结果、阳性分析及检查理由。
      配置在新任务开始时固定，已有任务不受影响；角色调用失败不会自动切换服务。
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, watch } from 'vue'
import {
  llmConfigService,
  type LLMLocalProvider,
  type LLMModel,
  type LLMProvider,
  type LLMTaskRole,
  type LLMTaskRoleModels,
} from '@/services/llmConfigService'

const props = defineProps<{
  value: LLMTaskRoleModels
  providers: Array<Pick<LLMProvider, 'provider_code' | 'provider_name'>>
  localProviders: LLMLocalProvider[]
  defaultProvider: string
  disabled: boolean
}>()
const emit = defineEmits<{ 'update:value': [value: LLMTaskRoleModels] }>()
const roleRows: Array<{ key: LLMTaskRole; label: string; hint: string }> = [
  { key: 'fact_extraction', label: '病历事实抽取', hint: '抽取原文事实、事件和证据引用' },
  { key: 'judgment_analysis', label: '医学判断与分析', hint: '正式语义分析与尚未单独分工的调用' },
  { key: 'specialty_verification', label: '专项核验', hint: '核对检查结果记录、分析及检查理由' },
]
const catalog = reactive<Record<string, LLMModel[]>>({})
const pending = reactive<Record<string, boolean>>({})
const errors = reactive<Record<string, boolean>>({})
const versions: Record<string, number> = {}
let mounted = true
const local = (provider: string) => provider === 'strata' || provider === 'ollama'
const providerOptions = computed(() => [
  { label: '继承默认模型', value: 'inherit' },
  ...props.providers.filter((item) => !local(props.defaultProvider) || local(item.provider_code)).map((item) => ({
    label: item.provider_name, value: item.provider_code,
  })),
])

function modelOptions(provider: string) {
  const models = local(provider)
    ? props.localProviders.find((item) => item.provider_code === provider)?.models || []
    : catalog[provider] || []
  return models.map((item) => ({ label: item.model_name, value: item.model_code }))
}

async function loadModels(provider: string, refresh = false) {
  if (local(provider) || pending[provider] || (catalog[provider] && !refresh)) return
  const version = (versions[provider] || 0) + 1
  versions[provider] = version
  pending[provider] = true
  errors[provider] = false
  try {
    const models = await llmConfigService.getModelsByProvider(provider)
    if (mounted && versions[provider] === version) catalog[provider] = models
  } catch {
    if (mounted && versions[provider] === version) errors[provider] = true
  } finally {
    if (mounted && versions[provider] === version) pending[provider] = false
  }
}

function selectProvider(role: LLMTaskRole, provider: string) {
  if (props.disabled) return
  emit('update:value', { ...props.value, [role]: provider === 'inherit' ? null : { provider_code: provider, model_code: '' } })
  if (provider !== 'inherit') void loadModels(provider, true)
}

function selectModel(role: LLMTaskRole, model: string) {
  const selected = props.value[role]
  if (!props.disabled && selected) emit('update:value', { ...props.value, [role]: { ...selected, model_code: model } })
}

watch(() => props.value, (value) => {
  for (const selected of Object.values(value)) if (selected) void loadModels(selected.provider_code)
}, { immediate: true, deep: true })
onBeforeUnmount(() => { mounted = false })
</script>

<style scoped>
.llm-role-settings {
  min-width: 0;
}
.llm-role-header {
  margin-bottom: var(--mq-space-5);
}
.llm-role-title {
  margin: 0;
  color: var(--mq-text-primary);
  font-size: var(--mq-font-16);
  font-weight: 600;
  line-height: 1.5;
}
.llm-role-header p {
  margin: var(--mq-space-1) 0 0;
}
.llm-role-list {
  padding-inline: var(--mq-space-4);
}
.llm-role-row {
  display: grid;
  grid-template-columns: minmax(140px, 0.6fr) minmax(0, 1fr);
  align-items: center;
  gap: var(--mq-space-4);
  padding-block: var(--mq-space-4);
}
.llm-role-row + .llm-role-row {
  border-top: 1px solid var(--mq-border);
}
.llm-role-label {
  color: var(--mq-text-primary);
  font-size: var(--mq-font-13);
  font-weight: 600;
}
.llm-role-controls {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: center;
  gap: var(--mq-space-2);
  min-width: 0;
}
.llm-role-select {
  width: 100%;
  min-width: 0;
}
.llm-role-inherit {
  padding-inline: var(--mq-space-2);
}
.llm-role-error {
  grid-column: 1 / -1;
  color: var(--mq-danger-text);
  font-size: var(--mq-font-12);
}
.llm-role-note {
  margin: var(--mq-space-3) 0 0;
}
@container model-settings (max-width: 680px) {
  .llm-role-row {
    grid-template-columns: minmax(0, 1fr);
    gap: var(--mq-space-3);
  }
}
@container model-settings (max-width: 420px) {
  .llm-role-controls {
    grid-template-columns: minmax(0, 1fr);
  }
  .llm-role-inherit {
    padding-inline: 0;
  }
}
</style>
