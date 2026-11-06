<template>
  <section
    class="mq-card mq-card--padded pipeline-panel"
    aria-labelledby="pipeline-title"
  >
    <div class="mq-card__head">
      <div>
        <h2
          id="pipeline-title"
          class="mq-card__title"
        >
          数据抽取链路
        </h2>
        <p class="mq-card__desc">
          东华独立同步服务发布临床材料；应用侧原PG同步已停用。
        </p>
      </div>
      <a-button
        :loading="loading"
        :disabled="busy"
        @click="load"
      >
        重新加载配置
      </a-button>
    </div>
    <a-alert
      v-if="error"
      type="error"
      show-icon
      :message="error"
      role="alert"
    />
    <template v-if="configuration">
      <div
        class="pipeline-options"
        role="group"
        aria-label="选择数据抽取链路"
      >
        <button
          v-for="option in options"
          :key="option.value"
          type="button"
          class="pipeline-option"
          :class="{ 'is-active': selected === option.value }"
          :aria-pressed="selected === option.value"
          :disabled="busy || loading"
          :data-testid="`pipeline-${option.value}`"
          @click="select(option.value)"
        >
          <strong>{{ option.label }}</strong><span>{{ option.description }}</span>
        </button>
      </div>
      <div class="pipeline-toolbar">
        <label><input
          v-model="draft.independent_enabled"
          type="checkbox"
          :disabled="busy || loading"
        >
          启用独立同步任务入口</label>
        <a-button
          :loading="saving"
          :disabled="busy || loading"
          @click="save"
        >
          保存为默认链路
        </a-button>
        <span
          v-if="saved"
          role="status"
        >已保存；未启动同步或质控。</span>
      </div>
      <p class="pipeline-source">
        当前临床读取：<strong>{{
          configuration.runtime.clinical_read_source === 'independent_cdm'
            ? '独立CDM（已配置入口）'
            : '原业务库CDM'
        }}</strong>。
        抽取链路的选择不自动切换读取来源；读取连接由部署配置启用。PDF材料副本继续读取原登记材料。
      </p>
      <p class="pipeline-note">
        {{ configuration.runtime.read_scope }}。业务库继续保存用户、质控任务、结果和缓存。
      </p>
      <a-alert
        v-if="configuration.runtime.cdm_configuration_valid === false"
        type="error"
        show-icon
        message="独立CDM读取配置无效，请由部署人员核对URL和凭据文件；不会回退读取原业务库。"
      />
      <template v-if="selected === 'independent_cdm'">
        <div class="pipeline-independent">
          <div class="pipeline-toolbar">
            <h3>Caché → 独立同步服务 → 独立CDM</h3>
            <a-button
              :loading="checking"
              :disabled="busy || loading"
              @click="check"
            >
              检查服务与可用接口
            </a-button>
            <a-button
              :loading="refreshing"
              :disabled="busy || loading"
              @click="refresh"
            >
              刷新任务记录
            </a-button>
          </div>
          <p>
            服务连接{{
              configuration.runtime.control_configured ? '已配置' : '未配置'
            }}；API地址与访问凭据由部署配置提供，页面不保存密码。
          </p>
          <p class="pipeline-note">
            仅人工按接口日期抽取，最多7天且不含医院当天。该范围不代表完整住院期资料；不启用定时抽取、不联动质控。
          </p>
          <div class="pipeline-fields">
            <label>开始日期<input
              v-model="startDate"
              type="date"
              :disabled="scopeLocked"
              data-testid="pipeline-start"
            ></label>
            <label>结束日期<input
              v-model="endDate"
              type="date"
              :disabled="scopeLocked"
              data-testid="pipeline-end"
            ></label>
            <label>执行方式<select
              v-model="mode"
              :disabled="scopeLocked"
            >
              <option value="dry">只做预检</option>
              <option value="replay">抽取并发布至独立CDM</option>
            </select></label>
          </div>
          <label
            v-if="catalog"
            class="pipeline-interface-label"
          >本次来源（已批准 {{ catalog.interfaces.length }} 项）
            <a-select
              v-model:value="interfaces"
              mode="multiple"
              :disabled="scopeLocked"
              :max-tag-count="3"
              :options="catalog.interfaces.map((value) => ({ value, label: value }))"
              placeholder="选择本次抽取来源"
            />
          </label>
          <p v-else>
            尚未检查服务，请先获取批准的接口清单。
          </p>
          <label class="pipeline-confirm"><input
            v-model="confirmed"
            type="checkbox"
            :disabled="busy"
          > 已核对日期和来源；{{
            mode === 'dry' ? '本次仅预检' : '本次允许服务抽取并发布至独立CDM'
          }}
          </label>
          <div class="pipeline-toolbar">
            <a-button
              type="primary"
              :loading="submitting"
              :disabled="!canSubmit || busy"
              @click="submit"
            >
              {{
                unresolvedOperation
                  ? '使用原操作标识重试提交'
                  : mode === 'dry'
                    ? '提交预检任务'
                    : '提交同步任务'
              }}
            </a-button>
            <span v-if="!configuration.settings.independent_enabled">请先启用并保存独立链路配置。</span>
          </div>
          <p
            v-if="unresolvedOperation"
            class="pipeline-note"
          >
            上次提交尚未确认。重试将保留原范围和幂等标识；请先刷新任务记录，避免重复操作。
          </p>
          <p
            v-if="historyError"
            role="alert"
          >
            {{ historyError }}
          </p>
          <div
            v-if="jobs !== null"
            class="pipeline-history"
          >
            <p v-if="jobs.length === 0">
              服务未返回本链路任务记录。
            </p>
            <article
              v-for="job in jobs"
              :key="job.job_id"
              class="pipeline-job"
            >
              <div>
                <strong>{{ statusLabels[job.status] }}</strong><span>{{ job.mode === 'dry' ? '预检任务' : '同步任务' }}</span>
                <span>{{ job.updated_at || job.created_at || '时间未返回' }}</span>
              </div>
              <p>任务 {{ job.job_id }}</p>
              <p>
                日期单元：{{ job.counts.units_completed ?? '未返回' }} /
                {{ job.counts.units_total ?? '未返回' }}；发布行数：{{
                  job.counts.written ?? '未返回'
                }}
              </p>
              <p v-if="job.error?.code">
                失败原因：{{ job.error.code }}
              </p>
              <div class="pipeline-toolbar">
                <a-button
                  v-if="['queued', 'running', 'recovery_required'].includes(job.status)"
                  :disabled="busy || job.cancel_requested"
                  @click="act(job, 'cancel')"
                >
                  {{ job.cancel_requested ? '取消已请求' : '取消任务' }}
                </a-button>
                <a-button
                  v-if="['failed', 'recovery_required'].includes(job.status)"
                  :disabled="busy || !configuration.settings.independent_enabled"
                  @click="act(job, 'retry')"
                >
                  重试失败任务
                </a-button>
              </div>
            </article>
          </div>
        </div>
      </template>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { isAxiosError } from 'axios'
import { useAuthStore } from '@/stores/auth'
import {
  dataPipelinesApi,
  type DataPipeline,
  type DataPipelineConfiguration,
  type IndependentCatalog,
  type IndependentSyncJob,
  type IndependentSyncRequest,
} from '@/api/dataPipelines'

const emit = defineEmits<{ selection: [value: DataPipeline]; ready: [value: boolean] }>()
const auth = useAuthStore()
const configuration = ref<DataPipelineConfiguration | null>(null)
const draft = reactive({
  version: 0,
  default_pipeline: 'legacy_pg' as DataPipeline,
  independent_enabled: false,
})
const selected = ref<DataPipeline>('legacy_pg')
const options: { value: DataPipeline; label: string; description: string }[] = [
  { value: 'independent_cdm', label: '独立CDM同步', description: 'Caché → 独立同步服务 → 独立CDM' },
]
const loading = ref(false),
  saving = ref(false),
  checking = ref(false),
  refreshing = ref(false),
  submitting = ref(false),
  acting = ref(false)
const busy = computed(
  () => saving.value || checking.value || submitting.value || acting.value || refreshing.value,
)
const error = ref(''),
  historyError = ref(''),
  saved = ref(false)
const catalog = ref<IndependentCatalog | null>(null)
const jobs = ref<IndependentSyncJob[] | null>(null)
const startDate = ref(''),
  endDate = ref(''),
  interfaces = ref<string[]>([]),
  mode = ref<'dry' | 'replay'>('dry'),
  confirmed = ref(false)
const unresolvedOperation = ref<IndependentSyncRequest | null>(null)
const scopeLocked = computed(() => busy.value || unresolvedOperation.value !== null)
let epoch = 0,
  loadId = 0
const statusLabels: Record<IndependentSyncJob['status'], string> = {
  queued: '排队中',
  running: '执行中',
  recovery_required: '等待恢复',
  succeeded: '已完成',
  completed_with_source_limitations: '完成（来源受限）',
  failed: '执行失败',
  cancelled: '已取消',
}
const canSubmit = computed(() =>
  Boolean(
    configuration.value?.settings.independent_enabled &&
      catalog.value &&
      confirmed.value &&
      startDate.value &&
      endDate.value &&
      interfaces.value.length,
  ),
)

function select(value: DataPipeline) {
  if (value !== 'independent_cdm') return
  selected.value = value
  draft.default_pipeline = value
  saved.value = false
  emit('selection', value)
}
async function load() {
  const ticket = ++loadId,
    generation = epoch
  loading.value = true
  error.value = ''
  try {
    const data = await dataPipelinesApi.configuration()
    if (generation !== epoch || ticket !== loadId) return
    configuration.value = data
    Object.assign(draft, data.settings)
    select('independent_cdm')
    emit('ready', true)
  } catch {
    if (generation === epoch && ticket === loadId) {
      configuration.value = null
      emit('ready', false)
      error.value = '链路配置读取失败，未使用默认值冒充已加载配置。请重新加载。'
    }
  } finally {
    if (generation === epoch && ticket === loadId) loading.value = false
  }
}
async function save() {
  const generation = epoch
  saving.value = true
  error.value = ''
  saved.value = false
  try {
    const data = await dataPipelinesApi.save({ ...draft })
    if (generation !== epoch) return
    configuration.value = data
    Object.assign(draft, data.settings)
    saved.value = true
  } catch {
    if (generation === epoch)
      error.value = '保存失败，请检查部署配置；若配置已被其他管理员修改，请重新加载。'
  } finally {
    if (generation === epoch) saving.value = false
  }
}
async function check() {
  const generation = epoch
  checking.value = true
  error.value = ''
  catalog.value = null
  confirmed.value = false
  try {
    const data = await dataPipelinesApi.check()
    if (generation !== epoch) return
    catalog.value = data
    interfaces.value = interfaces.value.filter((value) => data.interfaces.includes(value))
  } catch {
    if (generation === epoch)
      error.value = '独立同步服务检查失败；请核对地址、凭据、批准范围及网络。未启动抽取。'
  } finally {
    if (generation === epoch) checking.value = false
  }
}
async function refresh() {
  const generation = epoch
  refreshing.value = true
  historyError.value = ''
  try {
    const data = await dataPipelinesApi.jobs()
    if (generation === epoch) jobs.value = data
  } catch {
    if (generation === epoch)
      historyError.value = '任务记录读取失败；保留上次已读取状态，请重试刷新。'
  } finally {
    if (generation === epoch) refreshing.value = false
  }
}
function remember(job: IndependentSyncJob) {
  jobs.value = [job, ...(jobs.value || []).filter((item) => item.job_id !== job.job_id)]
}
async function submit() {
  if (!canSubmit.value || busy.value) return
  const generation = epoch
  // 未确认应答时保留原始请求与ID；不能因网络重试另建一个同步任务。
  const payload = unresolvedOperation.value || {
    operation_id: crypto.randomUUID(),
    start_date: startDate.value,
    end_date: endDate.value,
    interfaces: [...interfaces.value],
    mode: mode.value,
    publish: mode.value === 'replay',
  }
  unresolvedOperation.value = payload
  submitting.value = true
  error.value = ''
  try {
    const job = await dataPipelinesApi.submit(payload)
    if (generation !== epoch) return
    remember(job)
    unresolvedOperation.value = null
    confirmed.value = false
  } catch (cause) {
    if (generation === epoch) {
      const status = isAxiosError(cause) ? cause.response?.status : undefined
      if (status && status >= 400 && status < 500 && status !== 408)
        unresolvedOperation.value = null
      error.value = unresolvedOperation.value
        ? '提交未确认；请先刷新任务记录，再使用原标识重试。没有自动创建质控任务。'
        : '提交被拒绝，请核对范围和权限；未自动重复提交或创建质控任务。'
    }
  } finally {
    if (generation === epoch) submitting.value = false
  }
}
async function act(job: IndependentSyncJob, action: 'cancel' | 'retry') {
  const generation = epoch
  acting.value = true
  error.value = ''
  try {
    const data = await dataPipelinesApi.action(job.job_id, action)
    if (generation === epoch) remember(data)
  } catch {
    if (generation === epoch) error.value = '操作尚未确认；请刷新任务状态，系统未自动重复提交。'
  } finally {
    if (generation === epoch) acting.value = false
  }
}
watch(
  [startDate, endDate, interfaces, mode],
  () => {
    confirmed.value = false
  },
  { deep: true },
)
watch(
  () => [auth.user?.id, ...auth.userRoles],
  () => {
    epoch++
    configuration.value = null
    catalog.value = null
    jobs.value = null
    unresolvedOperation.value = null
    loading.value = false
    saving.value = false
    checking.value = false
    refreshing.value = false
    submitting.value = false
    acting.value = false
    error.value = '账号权限已变化，请重新加载配置。'
    emit('ready', false)
  },
)
onMounted(load)
onUnmounted(() => {
  epoch++
})
</script>

<style scoped>
.pipeline-panel {
  margin-bottom: 20px;
}
.pipeline-options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin: 16px 0;
}
.pipeline-option {
  padding: 16px;
  border: 1px solid var(--mq-border, #e2e8f0);
  border-radius: 12px;
  background: var(--mq-surface, #fff);
  text-align: left;
  color: inherit;
  cursor: pointer;
}
.pipeline-option strong,
.pipeline-option span {
  display: block;
}
.pipeline-option span {
  margin-top: 6px;
  font-size: 13px;
  color: var(--mq-text-muted, #64748b);
}
.pipeline-option.is-active {
  border-color: var(--mq-primary, #2563eb);
  background: var(--mq-primary-soft, #eaf2ff);
}
.pipeline-toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  margin: 14px 0;
}
.pipeline-toolbar h3 {
  margin: 0;
  margin-right: auto;
}
.pipeline-source {
  margin: 18px 0 8px;
  line-height: 1.7;
}
.pipeline-note {
  color: var(--mq-text-muted, #64748b);
  line-height: 1.7;
}
.pipeline-independent {
  border-top: 1px solid var(--mq-border, #e2e8f0);
  margin-top: 18px;
  padding-top: 12px;
}
.pipeline-fields {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin: 18px 0;
}
.pipeline-fields label {
  display: grid;
  gap: 6px;
}
.pipeline-fields input,
.pipeline-fields select {
  padding: 8px;
  border: 1px solid var(--mq-border, #e2e8f0);
  border-radius: 8px;
  background: white;
}
.pipeline-interface-label {
  display: grid;
  gap: 8px;
  margin-bottom: 16px;
}
.pipeline-confirm {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}
.pipeline-job {
  padding: 16px 0;
  border-top: 1px solid var(--mq-border, #e2e8f0);
  overflow-wrap: anywhere;
}
.pipeline-job > div:first-child {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
}
.pipeline-job p {
  margin: 6px 0;
}
@media (max-width: 760px) {
  .pipeline-options {
    grid-template-columns: 1fr;
  }
}
</style>
