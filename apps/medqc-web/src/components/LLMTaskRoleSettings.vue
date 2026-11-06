<template>
  <div
    class="ds-group"
    data-testid="task-role-settings"
  >
    <div class="ds-group__title">
      按任务用途选模型
    </div>
    <p class="ds-row__hint">
      默认继承当前模型，不增加调用次数。事实抽取用于检查检验主抽取及会诊意见；
      专项核验用于检查结果、阳性分析和检查理由核验。其余正式语义调用使用判断分析模型。
    </p>
    <div
      v-for="role in roleRows"
      :key="role.key"
      class="ds-row ds-row--top"
    >
      <div class="ds-row__left">
        <div class="ds-row__label">
          {{ role.label }}
        </div>
        <div class="ds-row__hint">
          {{ role.hint }}
        </div>
      </div>
      <div class="task-role-controls">
        <a-select
          :data-testid="`task-role-provider-${role.key}`"
          :value="value[role.key]?.provider_code || 'inherit'"
          :disabled="disabled"
          :options="providerOptions"
          style="width: 220px"
          @change="selectProvider(role.key, String($event))"
        />
        <a-select
          v-if="value[role.key]"
          :data-testid="`task-role-model-${role.key}`"
          :value="value[role.key]?.model_code || undefined"
          :disabled="disabled || pending[value[role.key]?.provider_code || '']"
          :loading="pending[value[role.key]?.provider_code || '']"
          :options="modelOptions(value[role.key]?.provider_code || '')"
          show-search
          option-filter-prop="label"
          placeholder="选择该用途的模型"
          style="width: 280px"
          @change="selectModel(role.key, String($event))"
        />
        <span
          v-else
          class="ds-row__hint"
        >继承默认模型（保留现有运行配置）</span>
        <span
          v-if="errors[value[role.key]?.provider_code || '']"
          role="alert"
        >
          模型目录读取失败，请重新选择服务后重试。
        </span>
      </div>
    </div>
    <p class="ds-row__hint">
      配置在新任务开始时固定；修改不影响在途任务。角色调用失败不会自动切换其他服务。
      保存只校验配置，连接测试只请求默认模型。
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
.ds-group { padding: 20px 0; }
.ds-group__title { font-size: 15px; font-weight: 600; margin-bottom: 12px; }
.ds-row { display: flex; justify-content: space-between; gap: 16px; padding: 12px 0; }
.ds-row__left { min-width: 150px; }
.ds-row__label { font-weight: 500; }
.ds-row__hint { color: var(--mq-text-secondary, #64748b); font-size: 13px; line-height: 1.6; }
.task-role-controls { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
@media (max-width: 800px) { .ds-row { flex-direction: column; } }
</style>
