<template>
  <a-drawer
    :open="Boolean(itemId)"
    title="规则测试验收"
    :width="820"
    @close="emit('close')"
  >
    <a-alert
      v-if="error"
      type="error"
      :message="error"
      show-icon
      class="mb-4"
    />
    <a-spin :spinning="busy">
      <p class="text-slate-500">
        先保存人工预期，再启动验证。状态一致后仍需核对证据与建议；验收通过不会自动上线规则。
      </p>
      <p class="text-slate-500">
        测试病例创建后固定，如需修改请复制为新病例。评价时间点：{{ state?.evaluation_as_of_date || '未固定（结果随运行日期变化，不能验收通过）' }}
      </p>
      <template v-if="state">
        <h3>人工预期 · 修订 {{ state.revision }}</h3>
        <div
          v-for="(answer, index) in answers"
          :key="index"
          class="validation-answer"
        >
          <a-select
            v-model:value="answer.qc_point_id"
            aria-label="质控点"
            show-search
            option-filter-prop="label"
            :options="ruleOptions"
            class="w-full"
          />
          <div class="flex gap-3 mt-2">
            <a-select
              v-model:value="answer.expected_status"
              aria-label="预期状态"
              :options="statusOptions"
              class="w-40"
            />
            <a-button @click="answers.splice(index, 1)">
              移除
            </a-button>
          </div>
          <a-textarea
            v-model:value="answer.human_reason"
            aria-label="人工预期依据"
            placeholder="人工预期依据（必填）"
            :maxlength="4000"
            class="mt-2"
          />
        </div>
        <div class="flex flex-wrap gap-2 my-4">
          <a-button
            :disabled="busy || answers.length >= 20"
            @click="addAnswer"
          >
            添加规则
          </a-button>
          <a-button
            :disabled="busy || !answers.length"
            @click="save"
          >
            保存预期
          </a-button>
          <a-button
            type="primary"
            :disabled="busy || dirty || !answers.length"
            @click="start"
          >
            按已保存预期启动验证
          </a-button>
        </div>
        <p
          v-if="dirty"
          class="text-amber-700"
        >
          预期已修改，请先保存。
        </p>
        <h3>验收运行</h3>
        <a-select
          v-model:value="runId"
          aria-label="验收运行"
          :options="runOptions"
          class="w-full"
          @change="refreshResult"
        />
        <a-button
          :disabled="busy || !runId"
          class="my-3"
          @click="refreshResult"
        >
          刷新结果
        </a-button>
        <template v-if="result">
          <p>任务状态：{{ jobLabel(result.job_status) }} · 预期修订 {{ result.run.revision }}</p>
          <p class="text-slate-500">
            评价时间点：{{ result.run.evaluation_as_of_date || '未固定，不能验收通过' }}
          </p>
          <p class="text-slate-500">
            执行版本：{{ executionVersionLabel }} · 模型：{{ result.run.execution_version?.lx0609_task_runtime?.first_pass?.model || '未记录' }}
          </p>
          <a-button
            v-if="result.run.job_id"
            type="link"
            @click="emit('view-job', result.run.job_id)"
          >
            查看本次质控证据与建议
          </a-button>
          <a-table
            :data-source="result.comparisons"
            :columns="columns"
            row-key="qc_point_id"
            :pagination="false"
            size="small"
            :scroll="{ x: 600 }"
          />
          <a-textarea
            v-model:value="note"
            aria-label="复核意见"
            placeholder="请核对原文、证据和修改建议后填写意见"
            :maxlength="4000"
            class="my-3"
          />
          <div class="flex gap-2">
            <a-button
              :disabled="busy || !canAccept || !note.trim()"
              @click="review('accepted')"
            >
              人工确认通过
            </a-button>
            <a-button
              :disabled="busy || result.job_status !== 'completed' || !note.trim()"
              @click="review('rejected')"
            >
              记录不通过
            </a-button>
          </div>
          <ul class="mt-4">
            <li
              v-for="(entry, index) in result.run.reviews"
              :key="index"
            >
              {{ entry.reviewed_at }} · {{ entry.decision === 'accepted' ? '通过' : '不通过' }}：{{ entry.note }}
            </li>
          </ul>
        </template>
      </template>
    </a-spin>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { readValidation, saveValidation, startValidation, readValidationResult, reviewValidation } from '@/services/test-case-validation-service'
import type { ValidationState, ValidationResult } from '@/services/test-case-validation-service'
import type { SyntheticCaseGoldenAnswer } from './types'

const props = defineProps<{ itemId: string }>()
const emit = defineEmits<{ close: []; 'view-job': [jobId: string] }>()
const state = ref<ValidationState | null>(null)
const answers = ref<SyntheticCaseGoldenAnswer[]>([])
const result = ref<ValidationResult | null>(null)
const runId = ref('')
const note = ref('')
const busy = ref(false)
const error = ref('')
let generation = 0
let requestSequence = 0
const statusOptions = [
  { value: 'compliant', label: '合规' }, { value: 'non_compliant', label: '不合规' },
  { value: 'not_applicable', label: '不适用' }, { value: 'data_gap', label: '资料不足' },
]
const label = (value: string | null) => statusOptions.find(x => x.value === value)?.label || value || '—'
const comparisonLabels: Record<string, string> = { same: '状态一致，待人工核对', different: '状态不一致', missing: '缺少结果', ambiguous: '重复结果', pending: '等待完成', failed: '执行失败' }
const comparisonLabel = (value: string) => comparisonLabels[value] || value
const jobLabels: Record<string, string> = { completed: '已完成', failed: '失败', running: '执行中', queued: '排队中', canceled: '已取消', creating: '任务绑定中', creation_failed: '创建失败' }
const jobLabel = (value: string) => jobLabels[value] || value
const columns = [
  { title: '规则', dataIndex: 'qc_point_id' },
  { title: '本次冻结依据', dataIndex: 'human_reason' },
  { title: '预期', dataIndex: 'expected_status', customRender: ({ text }: { text: string }) => label(text) },
  { title: '实际', dataIndex: 'actual_status', customRender: ({ text }: { text: string }) => label(text) },
  { title: '核对', dataIndex: 'comparison', customRender: ({ text }: { text: string }) => comparisonLabel(text) },
]
const dirty = computed(() => JSON.stringify(answers.value) !== JSON.stringify(state.value?.answers || []))
const ruleOptions = computed(() => (state.value?.rule_options || []).map(r => ({ value: r.rule_id, label: `${r.rule_id} ${r.name}${r.release_scope === 'acceptance_only' ? '（待验收）' : ''}` })))
const runOptions = computed(() => [...(state.value?.runs || [])].reverse().map(r => ({ value: r.id, label: `${r.created_at} · 修订${r.revision}` })))
const executionVersionLabel = computed(() => {
  const version = result.value?.run.execution_version?.lx0609_task_runtime?.implementation
  return version?.kind === 'release' ? `${version.build_id} / ${version.git_commit}` : '本地进程版本，仅供开发验收；发布需固定构建后重跑'
})
const canAccept = computed(() => result.value?.job_status === 'completed' && Boolean(result.value.run.evaluation_as_of_date && result.value.run.execution_version) && Boolean(result.value.comparisons.length) && result.value.comparisons.every(r => r.comparison === 'same'))
function addAnswer() {
  answers.value.push({ qc_point_id: '', expected_status: 'non_compliant', human_reason: '', trigger_facts: [], evidence_keywords: [] })
}
async function perform<T>(action: () => Promise<{ success: boolean; data?: T; error?: string }>, apply: (value: T) => void) {
  const token = generation
  const sequence = ++requestSequence
  busy.value = true
  error.value = ''
  try {
    const response = await action()
    if (token !== generation || sequence !== requestSequence) return
    if (!response.success || !response.data) { error.value = response.error || '请求失败'; return }
    apply(response.data)
  } catch { if (token === generation && sequence === requestSequence) error.value = '请求失败，请刷新重试' }
  finally { if (token === generation && sequence === requestSequence) busy.value = false }
}
function applyState(value: ValidationState) {
  state.value = value
  answers.value = JSON.parse(JSON.stringify(value.answers)) as SyntheticCaseGoldenAnswer[]
}
async function load() { await perform(() => readValidation(props.itemId), applyState) }
async function save() {
  if (!state.value) return
  await perform(() => saveValidation(props.itemId, state.value!.revision, answers.value), applyState)
}
async function start() {
  if (!state.value || dirty.value) return
  const id = props.itemId
  const token = generation
  await perform(() => startValidation(id, state.value!.revision), value => { runId.value = value.run_id })
  if (token !== generation || error.value) return
  await load()
  if (token === generation) await refreshResult()
}
async function refreshResult() {
  result.value = null
  note.value = ''
  if (runId.value) await perform(() => readValidationResult(props.itemId, runId.value), value => { result.value = value })
}
async function review(decision: 'accepted' | 'rejected') {
  await perform(() => reviewValidation(props.itemId, runId.value, decision, note.value), value => { result.value = value; note.value = '' })
}
watch(() => props.itemId, () => {
  generation++
  state.value = null; result.value = null; answers.value = []; runId.value = ''; note.value = ''; error.value = ''; busy.value = false
  if (props.itemId) void load()
}, { immediate: true })
</script>

<style scoped>
.validation-answer { padding: 12px 0; border-bottom: 1px solid var(--mq-glass-border); }
h3 { margin: 20px 0 12px; font-size: 16px; }
</style>
