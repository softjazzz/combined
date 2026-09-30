<template>
  <a-modal
    :open="open"
    :footer="null"
    :width="560"
    centered
    wrap-class-name="mq-modal"
    :mask-style="{ backdropFilter: 'blur(6px)' }"
    @cancel="emit('close')"
  >
    <div
      v-if="open"
      class="rv-answer"
      data-testid="case-answer-modal"
    >
      <div>
        <h2>{{ editing ? '编辑预期' : '关联测试病例' }}</h2>
        <p class="rv-muted">
          按本规则单独标注预期；人工预期只用于运行后比较，不会进入质控任务。
        </p>
      </div>

      <a-alert
        v-if="error"
        type="error"
        :message="error"
        show-icon
      />

      <label
        v-if="!editing"
        class="mq-field"
      >
        <span class="mq-field__label">测试病例<span class="mq-field__required">*</span></span>
        <a-select
          v-model:value="itemId"
          show-search
          option-filter-prop="label"
          aria-label="测试病例"
          placeholder="选择尚未关联本规则的测试病例"
          :loading="loadingCandidates"
          :options="candidateOptions"
        />
        <span class="mq-field__hint">没有合适的病例时，可先“新建测试病例”。</span>
      </label>
      <div
        v-else-if="current"
        class="mq-soft rv-answer__case"
      >
        <b>{{ current.case_title }}</b>
        <span class="rv-muted">{{ SOURCE_KINDS[current.source_kind] }} · 评价时间点 {{ current.evaluation_as_of_date || '未固定' }} · 当前修订 r{{ current.answer_revision }}</span>
      </div>

      <div class="mq-field">
        <span class="mq-field__label">预期状态<span class="mq-field__required">*</span></span>
        <a-radio-group
          v-model:value="expectedStatus"
          option-type="button"
          aria-label="预期状态"
        >
          <a-radio-button
            v-for="status in EXPECTED_STATUSES"
            :key="status"
            :value="status"
          >
            {{ STATUS[status].label }}
          </a-radio-button>
        </a-radio-group>
      </div>

      <div class="mq-field">
        <span class="mq-field__label">病例用途</span>
        <a-radio-group
          v-model:value="purpose"
          aria-label="病例用途"
        >
          <a-radio value="development">
            开发集
          </a-radio>
          <a-radio value="acceptance">
            独立验收集
          </a-radio>
        </a-radio-group>
        <span class="mq-field__hint">揭盲后修改了规则，需要新的独立验收病例；旧病例转为回归保护。</span>
      </div>

      <label class="mq-field">
        <span class="mq-field__label">人工预期依据<span class="mq-field__required">*</span></span>
        <a-textarea
          v-model:value="reason"
          aria-label="人工预期依据"
          :rows="3"
          :maxlength="4000"
          placeholder="写明判定所依据的原文事实"
        />
      </label>

      <div class="rv-answer__actions">
        <button
          v-if="editing"
          type="button"
          class="mq-btn"
          :disabled="busy"
          @click="remove"
        >
          取消关联
        </button>
        <button
          type="button"
          class="mq-btn"
          :disabled="busy"
          @click="emit('close')"
        >
          取消
        </button>
        <button
          type="button"
          class="mq-btn mq-btn--primary"
          data-testid="case-answer-save"
          :disabled="busy || !canSave"
          @click="save"
        >
          保存预期
        </button>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { listCandidateCases, removeCaseAnswer, saveCaseAnswer } from '@/services/rule-validation-service'
import type { CandidateCase, CasePurpose, ExpectedStatus, ValidationCase } from '@/services/rule-validation-service'
import { EXPECTED_STATUSES, SOURCE_KINDS, STATUS } from './presentation'

const props = defineProps<{ open: boolean; ruleId: string; current: ValidationCase | null }>()
const emit = defineEmits<{ close: []; saved: [] }>()

const itemId = ref<string>()
const expectedStatus = ref<ExpectedStatus>('non_compliant')
const purpose = ref<CasePurpose>('development')
const reason = ref('')
const candidates = ref<CandidateCase[]>([])
const loadingCandidates = ref(false)
const busy = ref(false)
const error = ref('')

const editing = computed(() => Boolean(props.current))
const candidateOptions = computed(() =>
  candidates.value.map((c) => ({
    value: c.item_id,
    label: `${c.case_title}（${SOURCE_KINDS[c.source_kind]}${c.evaluation_as_of_date ? '' : '，评价时间点未固定'}）`,
  })),
)
const canSave = computed(() => Boolean((editing.value || itemId.value) && reason.value.trim()))

watch(
  () => props.open,
  async (open) => {
    if (!open) return
    error.value = ''
    const current = props.current
    itemId.value = current?.item_id
    expectedStatus.value = current?.expected_status ?? 'non_compliant'
    purpose.value = current?.purpose ?? 'development'
    reason.value = current?.human_reason ?? ''
    if (current) return
    loadingCandidates.value = true
    const response = await listCandidateCases(props.ruleId)
    loadingCandidates.value = false
    if (!response.success) error.value = response.error || '候选病例加载失败'
    else candidates.value = response.data.items
  },
  { immediate: true },
)

async function save() {
  const target = props.current?.item_id ?? itemId.value
  if (!target) return
  busy.value = true
  error.value = ''
  const response = await saveCaseAnswer(props.ruleId, target, {
    revision: props.current?.answer_revision ?? 0,
    expected_status: expectedStatus.value,
    human_reason: reason.value.trim(),
    purpose: purpose.value,
  })
  busy.value = false
  if (!response.success) {
    error.value = response.error || '保存失败'
    return
  }
  emit('saved')
}

async function remove() {
  if (!props.current) return
  busy.value = true
  error.value = ''
  const response = await removeCaseAnswer(props.ruleId, props.current.item_id, props.current.answer_revision)
  busy.value = false
  if (!response.success) {
    error.value = response.error || '取消关联失败'
    return
  }
  emit('saved')
}
</script>

<style scoped>
.rv-answer {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.rv-answer h2 {
  margin: 0 0 4px;
  font-size: var(--mq-font-20);
}

.rv-answer p {
  margin: 0;
}

.rv-muted {
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
}

.rv-answer__case {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 14px;
}

.rv-answer__actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
