<template>
  <a-drawer :open="open" :width="760" title="智能业务助手" @close="open = false">
    <div class="business-agent">
      <section class="mq-soft">
        <strong>{{ context.view === 'doctor' ? '当前病例' : '管理问数范围' }}</strong>
        <p>{{ contextLabel }}</p>
        <template v-if="context.view === 'manager'">
          <label class="mq-field"
            >科室 <a-input v-model:value="department" placeholder="当前授权范围"
          /></label>
          <label class="mq-field"
            >病例范围 <a-select v-model:value="carePhase" :options="carePhaseOptions"
          /></label>
          <label class="mq-field"
            >质控完成日期 <a-range-picker v-model:value="dates" value-format="YYYY-MM-DD"
          /></label>
        </template>
        <p class="business-agent__muted">读取已保存结果和规范依据，保留正式结论与建议。</p>
      </section>
      <div class="business-agent__shortcuts">
        <a-button
          v-for="prompt in prompts"
          :key="prompt"
          :disabled="loading"
          @click="draft = prompt"
        >
          {{ prompt }}
        </a-button>
      </div>
      <section aria-live="polite" data-testid="business-agent-turns">
        <p v-if="!turns.length" class="business-agent__muted">
          先查看问题，再追问原文与规则依据。管理问数沿用现有统计口径。
        </p>
        <article v-for="turn in turns" :key="turn.run_id" class="business-agent__turn">
          <p class="business-agent__question">
            {{ turn.question }}
          </p>
          <p class="business-agent__answer">
            {{ turn.answer || turn.error || '本轮未完成，可重新查询。' }}
          </p>
          <p v-if="turn.reference_scope === 'prior_turns'" class="business-agent__muted">
            本轮沿用此前读取的来源，未刷新业务结果。
          </p>
          <div
            v-for="(reference, index) in turn.references"
            :key="reference.id"
            class="mq-inset business-agent__reference"
          >
            <strong>{{ index + 1 }}. {{ reference.title }}</strong>
            <span v-if="reference.status" class="mq-status">{{
              statusLabel(reference.status)
            }}</span>
            <p v-if="reference.conclusion">
              {{ reference.conclusion }}
            </p>
            <p v-if="reference.suggestion">建议：{{ reference.suggestion }}</p>
            <small v-if="reference.locator">{{ reference.locator }}</small>
            <a-button type="link" @click="openReference(reference.id)">
              查看{{ reference.kind === 'guideline' ? '规范原文' : '依据与详情' }}
            </a-button>
            <a-button
              v-if="reference.kind === 'saved_result'"
              type="link"
              :disabled="loading"
              @click="explainReference(reference)"
            >
              解释这条
            </a-button>
            <a-button
              v-if="reference.kind === 'record'"
              type="link"
              :disabled="loading"
              @click="explainReference(reference)"
            >
              查看病例问题
            </a-button>
          </div>
          <small class="business-agent__muted"
            >{{
              turn.status === 'stopped'
                ? '已停止'
                : turn.status === 'failed'
                  ? '部分步骤失败'
                  : '本轮完成'
            }}
            · {{ turn.tool_calls }} 次查询 · {{ (turn.elapsed_ms / 1000).toFixed(1) }} 秒</small
          >
        </article>
        <p v-if="loading">正在查询结果和依据…</p>
      </section>
      <a-alert v-if="error" type="warning" :message="error" show-icon />
      <div class="business-agent__composer">
        <a-textarea
          v-model:value="draft"
          :disabled="loading"
          :auto-size="{ minRows: 2, maxRows: 5 }"
          placeholder="查看当前病例问题，或追问某条结果的依据"
          @keydown.enter.exact.prevent="submit"
        />
        <div class="business-agent__shortcuts">
          <a-button @click="reset(context)"> 新建会话 </a-button>
          <a-button v-if="loading" @click="stop"> 停止 </a-button>
          <a-button type="primary" :disabled="loading || !draft.trim()" @click="submit">
            发送
          </a-button>
        </div>
      </div>
    </div>
    <a-modal
      v-model:open="referenceOpen"
      wrap-class-name="mq-modal"
      :title="selectedReference?.title || '依据详情'"
      :footer="null"
      :width="720"
    >
      <p v-if="referenceLoading">正在读取原文…</p>
      <a-alert v-else-if="referenceError" type="warning" :message="referenceError" />
      <template v-else-if="selectedReference">
        <p>{{ selectedReference.locator }}</p>
        <pre class="business-agent__answer">{{
          selectedReference.text ||
          selectedReference.conclusion ||
          '当前来源未提供原文，请核对材料范围。'
        }}</pre>
      </template>
    </a-modal>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  businessAgentApi,
  type BusinessAgentContext,
  type BusinessAgentReference,
} from '@/api/businessAgent'
import { useBusinessAgent } from '../composables/useBusinessAgent'

const open = defineModel<boolean>('open', { default: false })
const props = defineProps<{ userContext?: BusinessAgentContext }>()
const department = ref(props.userContext?.department || '')
const carePhase = ref<'inpatient' | 'discharged'>('discharged')
const dates = ref<[string, string]>()
const carePhaseOptions = [
  { value: 'inpatient', label: '在院' },
  { value: 'discharged', label: '已出院' },
]
const context = computed<BusinessAgentContext>(() =>
  props.userContext?.view === 'doctor'
    ? props.userContext
    : {
        view: 'manager',
        department: department.value || undefined,
        care_phase: carePhase.value,
        completed_from: dates.value ? `${dates.value[0]}T00:00:00+08:00` : undefined,
        completed_to: dates.value ? `${dates.value[1]}T23:59:59+08:00` : undefined,
      },
)
const contextLabel = computed(() =>
  context.value.view === 'doctor'
    ? `${context.value.patient_name || '当前患者'} · 住院 ${context.value.visit_id || '未选定'}`
    : `${context.value.department || '当前账号可见科室'} · 按质控完成时间统计`,
)
const prompts = computed(() =>
  context.value.view === 'doctor'
    ? ['这份病历有哪些已保存的质控问题？', '第二条为什么不合规？', '这条规则的要求来自哪里？']
    : ['当前范围哪些质控问题最多？', '列出这些问题对应的病例', '查询规则的当前启用状态'],
)
const draft = ref('')
const { sessionId, turns, loading, error, activate, send, stop, reset } = useBusinessAgent()
watch(
  context,
  (value) => {
    draft.value = ''
    void activate(value)
  },
  { immediate: true, deep: true },
)
async function submit() {
  const message = draft.value
  draft.value = ''
  await send(message, context.value)
}
async function explainReference(reference: BusinessAgentReference) {
  await send(
    reference.kind === 'record'
      ? `查看“${reference.title}”的保存质控问题`
      : `解释“${reference.title}”，查看病历证据与规则依据`,
    context.value,
    reference.id,
  )
}
const labels: Record<string, string> = {
  non_compliant: '不合规',
  compliant: '合规',
  data_gap: '资料不足',
  needs_review: '待复核',
  not_applicable: '不适用',
  not_executed: '未执行',
}
function statusLabel(status: string) {
  return labels[status] || '状态待核对'
}
const selectedReference = ref<BusinessAgentReference>()
const referenceOpen = ref(false)
const referenceLoading = ref(false)
const referenceError = ref('')
let referenceGeneration = 0
watch(context, () => {
  referenceGeneration += 1
  referenceOpen.value = false
  selectedReference.value = undefined
})
async function openReference(referenceId: string) {
  const epoch = ++referenceGeneration
  referenceOpen.value = true
  referenceLoading.value = true
  referenceError.value = ''
  selectedReference.value = undefined
  try {
    const reference = await businessAgentApi.reference(sessionId.value, referenceId)
    if (epoch === referenceGeneration) selectedReference.value = reference
  } catch {
    if (epoch === referenceGeneration) referenceError.value = '依据读取失败，未取得原文。'
  } finally {
    if (epoch === referenceGeneration) referenceLoading.value = false
  }
}
</script>

<style scoped src="../styles/business-agent.css"></style>
