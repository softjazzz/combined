<template>
  <a-drawer :open="open" :width="760" title="智能业务助手" @close="open = false">
    <div class="business-agent">
      <section class="mq-soft">
        <div
          v-if="allowCaseSelection && caseOptions.length && scopeOptions.length"
          class="business-agent__shortcuts"
        >
          <a-button
            :type="activeView === 'doctor' ? 'primary' : 'default'"
            @click="selectedView = 'doctor'"
          >
            病例问题
          </a-button>
          <a-button
            :type="activeView === 'manager' ? 'primary' : 'default'"
            @click="selectedView = 'manager'"
          >
            科室问数
          </a-button>
        </div>
        <strong>{{ context.view === 'doctor' ? '当前病例' : '管理问数范围' }}</strong>
        <p>{{ contextLabel }}</p>
        <label v-if="allowCaseSelection && context.view === 'doctor'" class="mq-field"
          >授权病例
          <a-select
            v-model:value="selectedCase"
            :options="caseOptions"
            :loading="accessLoading"
            placeholder="选择已授权病例"
            data-testid="business-agent-case-scope"
          />
        </label>
        <p
          v-if="
            allowCaseSelection && context.view === 'doctor' && !caseOptions.length && !accessLoading
          "
          class="business-agent__muted"
        >
          当前入口没有可选择的授权病例，请从已授权病历详情进入或核对访问范围。
        </p>
        <template v-if="context.view === 'manager'">
          <label class="mq-field"
            >机构/科室
            <a-select
              v-model:value="selectedScope"
              :options="scopeOptions"
              :loading="accessLoading"
              placeholder="选择已授权科室"
              data-testid="business-agent-manager-scope"
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
      <a-alert v-if="accessError" type="warning" :message="accessError" show-icon />
      <div class="business-agent__shortcuts">
        <a-button
          v-for="prompt in prompts"
          :key="prompt"
          :disabled="loading || !canQuery"
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
          <div
            v-for="(page, pageIndex) in turn.result_pages || []"
            :key="pageIndex"
            class="mq-inset business-agent__reference"
            data-testid="business-agent-result-page"
          >
            <p>
              读取范围：{{
                page.statuses.length ? page.statuses.map(statusLabel).join('、') : '全部状态'
              }}
              · 第 {{ page.page }} 页；本页 {{ page.returned }} 条，匹配共
              {{ page.matched_total }} 条，保存结果共 {{ page.total }} 条。
            </p>
            <p class="business-agent__muted">
              {{
                Object.entries(page.status_counts)
                  .map(([status, count]) => `${statusLabel(status)} ${count} 条`)
                  .join(' · ')
              }}
            </p>
            <p v-if="page.has_more">此范围还有后续页，可继续查询下一页。</p>
          </div>
          <p v-if="turn.reference_scope === 'prior_turns'" class="business-agent__muted">
            本轮沿用此前读取的来源，未刷新业务结果。
          </p>
          <p
            v-if="turn.references.some((reference) => reference.kind === 'guideline')"
            class="business-agent__muted"
            data-testid="business-agent-retrieval-notice"
          >
            规范检索资料：以下命中或读取的资料不代表均支持上方回答，请核对条款及适用范围。
          </p>
          <div
            v-for="(reference, index) in turn.references"
            :key="reference.id"
            class="mq-inset business-agent__reference"
          >
            <strong>{{ reference.position || index + 1 }}. {{ reference.title }}</strong>
            <p
              v-if="reference.kind === 'guideline'"
              class="business-agent__muted"
              data-testid="business-agent-guideline-candidate"
            >
              检索资料 · 待核对适用性
            </p>
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
              :disabled="loading || !canQuery"
              @click="explainReference(reference)"
            >
              解释这条
            </a-button>
            <a-button
              v-if="reference.kind === 'record'"
              type="link"
              :disabled="loading || !canQuery"
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
          :disabled="loading || !canQuery"
          :auto-size="{ minRows: 2, maxRows: 5 }"
          placeholder="查看当前病例问题，或追问某条结果的依据"
          @keydown.enter.exact.prevent="submit"
        />
        <div class="business-agent__shortcuts">
          <a-button @click="reset(context)"> 新建会话 </a-button>
          <a-button v-if="loading" @click="stop"> 停止 </a-button>
          <a-button
            type="primary"
            :disabled="loading || !canQuery || !draft.trim()"
            @click="submit"
          >
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
        <template v-if="selectedReference.evidence?.length">
          <p>{{ selectedReference.conclusion }}</p>
          <p v-if="selectedReference.suggestion">建议：{{ selectedReference.suggestion }}</p>
          <article
            v-for="(evidence, index) in selectedReference.evidence"
            :key="index"
            class="mq-inset business-agent__reference"
          >
            <small v-if="evidence.record_time">{{ evidence.record_time }}</small>
            <p class="business-agent__answer">
              {{ evidence.evidence_excerpt || '该证据未提供摘录。' }}
            </p>
            <a-button type="link" @click="openEvidenceDocument(selectedReference.id, index)">
              查看对应文书原文
            </a-button>
          </article>
        </template>
        <template v-else>
          <p>{{ selectedReference.locator }}</p>
          <pre class="business-agent__answer">{{
            selectedReference.text ||
            selectedReference.conclusion ||
            '当前来源未提供原文，请核对材料范围。'
          }}</pre>
        </template>
      </template>
    </a-modal>
    <a-modal
      v-model:open="documentOpen"
      wrap-class-name="mq-modal"
      :title="evidenceDocument?.title || '对应文书原文'"
      :footer="null"
      :width="800"
    >
      <p v-if="documentLoading">正在读取对应文书…</p>
      <a-alert v-else-if="documentError" type="warning" :message="documentError" />
      <template v-else-if="evidenceDocument">
        <a-alert
          :type="evidenceDocument.state === 'located' ? 'info' : 'warning'"
          :message="evidenceDocument.note"
        />
        <p class="business-agent__muted">
          当前文书 · {{ evidenceDocument.record_time || '未提供记录时间' }}
        </p>
        <p>保存结果中的摘录：</p>
        <p class="mq-inset business-agent__answer">
          {{ evidenceDocument.quote || '未提供摘录' }}
        </p>
        <pre
          v-if="evidenceDocument.content"
          class="business-agent__answer business-agent__document"
          data-testid="business-agent-document">{{ documentSegments.before }}<mark
v-if="documentSegments.quote"
                                                                                                                                              data-testid="business-agent-document-location"
        >{{ documentSegments.quote }}</mark>{{ documentSegments.after }}</pre>
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
  type BusinessAgentAccess,
  type BusinessEvidenceDocument,
} from '@/api/businessAgent'
import { useBusinessAgent } from '../composables/useBusinessAgent'

const open = defineModel<boolean>('open', { default: false })
const props = defineProps<{ userContext?: BusinessAgentContext; allowCaseSelection?: boolean }>()
const accessScope = ref<BusinessAgentAccess>()
const accessLoading = ref(false)
const accessError = ref('')
const selectedScope = ref('')
const selectedCase = ref('')
const selectedView = ref<'doctor' | 'manager'>('manager')
const activeView = computed(() =>
  props.allowCaseSelection ? selectedView.value : props.userContext?.view || 'manager',
)
const caseOptions = computed(() =>
  (accessScope.value?.doctor_cases || []).map((record) => ({
    value: JSON.stringify([record.institute_id, record.patient_id, record.visit_id]),
    label: `住院 ${record.visit_id} · 患者 ${record.patient_id} · ${record.institute_id}`,
  })),
)
const doctorCase = computed(() =>
  accessScope.value?.doctor_cases?.find(
    (record) =>
      JSON.stringify([record.institute_id, record.patient_id, record.visit_id]) ===
      selectedCase.value,
  ),
)
const scopeOptions = computed(() =>
  (accessScope.value?.manager_scopes || []).map((scope) => ({
    value: JSON.stringify([scope.institute_id, scope.department]),
    label: `${scope.department} · ${scope.institute_id}`,
  })),
)
const managerScope = computed(() =>
  accessScope.value?.manager_scopes.find(
    (scope) => JSON.stringify([scope.institute_id, scope.department]) === selectedScope.value,
  ),
)
let accessGeneration = 0
watch(
  open,
  async (visible) => {
    const epoch = ++accessGeneration
    accessScope.value = undefined
    selectedScope.value = ''
    selectedCase.value = ''
    accessError.value = ''
    accessLoading.value = false
    if (!visible) return
    accessLoading.value = true
    try {
      const result = await businessAgentApi.access()
      if (epoch !== accessGeneration) return
      accessScope.value = result
      if (props.allowCaseSelection)
        selectedView.value = result.manager_scopes.length ? 'manager' : 'doctor'
      const requested = result.manager_scopes.find(
        (scope) =>
          scope.institute_id === props.userContext?.institute_id &&
          scope.department === props.userContext?.department,
      )
      const initial =
        requested || (result.manager_scopes.length === 1 ? result.manager_scopes[0] : undefined)
      if (initial) selectedScope.value = JSON.stringify([initial.institute_id, initial.department])
      if (
        props.allowCaseSelection
          ? !result.doctor_case_count && !result.manager_scopes.length
          : props.userContext?.view === 'doctor'
            ? !result.doctor_case_count
            : !result.manager_scopes.length
      )
        accessError.value = '当前账号没有此入口的明确授权范围。'
    } catch {
      if (epoch === accessGeneration) accessError.value = '访问范围读取失败，请确认账号授权配置。'
    } finally {
      if (epoch === accessGeneration) accessLoading.value = false
    }
  },
  { immediate: true },
)
const carePhase = ref<'inpatient' | 'discharged'>('discharged')
const dates = ref<[string, string]>()
const carePhaseOptions = [
  { value: 'inpatient', label: '在院' },
  { value: 'discharged', label: '已出院' },
]
const context = computed<BusinessAgentContext>(() =>
  activeView.value === 'doctor'
    ? props.allowCaseSelection
      ? { view: 'doctor', ...doctorCase.value }
      : props.userContext || { view: 'doctor' }
    : {
        view: 'manager',
        institute_id: managerScope.value?.institute_id,
        department: managerScope.value?.department,
        care_phase: carePhase.value,
        completed_from: dates.value ? `${dates.value[0]}T00:00:00+08:00` : undefined,
        completed_to: dates.value ? `${dates.value[1]}T23:59:59+08:00` : undefined,
      },
)
const canQuery = computed(
  () =>
    !!accessScope.value &&
    !accessError.value &&
    (context.value.view === 'doctor'
      ? !!accessScope.value.doctor_case_count &&
        !!context.value.institute_id &&
        !!context.value.patient_id &&
        !!context.value.visit_id &&
        (!props.allowCaseSelection || !!doctorCase.value)
      : !!managerScope.value && !!dates.value?.[0] && !!dates.value?.[1]),
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
  if (!canQuery.value) return
  const message = draft.value
  draft.value = ''
  const candidates =
    turns.value
      .at(-1)
      ?.references.filter(
        (reference) => reference.kind === 'saved_result' && reference.position === 2,
      ) || []
  if (message === '第二条为什么不合规？' && candidates.length > 1) {
    error.value = '存在多个第二条，请点击具体问题卡片的“解释这条”。'
    return
  }
  error.value = ''
  // 固定快捷追问绑定页面可见的稳定问题，不要求模型再次排序。
  if (message === '第二条为什么不合规？' && candidates.length === 1)
    await send(message, context.value, candidates[0].id)
  else await send(message, context.value)
}
async function explainReference(reference: BusinessAgentReference) {
  if (!canQuery.value) return
  error.value = ''
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
const evidenceDocument = ref<BusinessEvidenceDocument>()
const documentOpen = ref(false)
const documentLoading = ref(false)
const documentError = ref('')
let documentGeneration = 0
const documentSegments = computed(() => {
  const document = evidenceDocument.value
  const content = document?.content || ''
  if (
    document?.state !== 'located' ||
    document.offset_unit !== 'unicode_code_points' ||
    document.start === undefined ||
    document.end === undefined
  )
    return { before: content, quote: '', after: '' }
  // 后端坐标按 Unicode 字符计算，避免表情等字符的 UTF-16 长度错位。
  const chars = Array.from(content)
  return {
    before: chars.slice(0, document.start).join(''),
    quote: chars.slice(document.start, document.end).join(''),
    after: chars.slice(document.end).join(''),
  }
})
watch([context, open, sessionId], () => {
  referenceGeneration += 1
  documentGeneration += 1
  referenceOpen.value = false
  documentOpen.value = false
  selectedReference.value = undefined
  evidenceDocument.value = undefined
})
async function openEvidenceDocument(referenceId: string, evidenceIndex: number) {
  const epoch = ++documentGeneration
  documentOpen.value = true
  documentLoading.value = true
  documentError.value = ''
  evidenceDocument.value = undefined
  try {
    const document = await businessAgentApi.evidenceDocument(
      sessionId.value,
      referenceId,
      evidenceIndex,
    )
    if (epoch === documentGeneration) evidenceDocument.value = document
  } catch {
    if (epoch === documentGeneration)
      documentError.value = '对应文书读取失败，请重新核对保存结果与授权范围。'
  } finally {
    if (epoch === documentGeneration) documentLoading.value = false
  }
}
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
