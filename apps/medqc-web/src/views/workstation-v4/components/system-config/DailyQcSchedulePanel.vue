<template>
  <section
    class="mq-card mq-card--padded"
    data-testid="daily-qc-panel"
  >
    <div class="mq-card__head">
      <div>
        <h2 class="mq-card__title">
          每日定时质控
        </h2>
        <p class="mq-card__desc">
          按机构、科室与滚动日期范围，从运行／终末病历池动态选取病历。
        </p>
      </div>
      <a-space>
        <a-button
          :loading="loading"
          @click="load"
        >
          刷新
        </a-button>
        <a-button
          type="primary"
          :disabled="!canManage || loading || Boolean(error)"
          @click="openEditor()"
        >
          新增计划
        </a-button>
      </a-space>
    </div>
    <a-alert
      v-if="error"
      type="error"
      show-icon
      :message="error"
      class="schedule-note"
    />
    <a-alert
      v-else
      :type="status.scheduler_enabled ? 'info' : 'warning'"
      show-icon
      :message="status.scheduler_enabled ? '后台调度开关已启用' : '后台自动触发未启用'"
      :description="status.scheduler_enabled
        ? '进程在线状态需结合部署监控核对；停机超过60分钟的周期记为错过，不批量追补。'
        : '计划默认关闭。部署需显式开启 QC_DAILY_SCHEDULER_ENABLED；不开启不会自动创建任务。'"
      class="schedule-note"
    />
    <p class="mq-card__desc">
      上一轮仍在排队或执行时，本轮跳过。没有符合条件的病历会单独记录；不覆盖既有结果。
    </p>
    <a-empty
      v-if="!loading && !error && !status.items.length"
      description="暂无每日质控计划"
    />
    <div
      v-for="plan in status.items"
      :key="plan.id"
      class="schedule-row"
      :data-testid="`schedule-${plan.id}`"
    >
      <div class="schedule-row__body">
        <div class="schedule-heading">
          <strong>{{ plan.name }}</strong>
          <a-tag :color="plan.enabled ? 'blue' : 'default'">
            {{ plan.enabled ? '已启用' : '已停用' }}
          </a-tag>
          <span>{{ plan.scope === 'running' ? '运行病历' : '终末病历' }}</span>
        </div>
        <p>{{ plan.institute_id }} · {{ plan.department || '全部科室' }} · 每日 {{ plan.time_of_day }}（{{ plan.timezone }}）</p>
        <p>下次计划时间：{{ formatTime(plan.next_run_at, plan.timezone) }} · 最近触发：{{ stateLabel(plan.last_status) }}</p>
      </div>
      <a-space wrap>
        <a-button
          :disabled="!canManage || saving"
          @click="openEditor(plan)"
        >
          编辑／启停
        </a-button>
        <a-button @click="showHistory(plan)">
          触发记录
        </a-button>
      </a-space>
    </div>

    <a-modal
      v-model:open="editing"
      :title="current ? '编辑每日质控计划' : '新增每日质控计划'"
      :confirm-loading="saving"
      :ok-button-props="{ disabled: !valid || !canManage || optionsLoading || Boolean(optionsError) }"
      @ok="save"
    >
      <a-form
        layout="vertical"
        class="schedule-form"
      >
        <a-form-item label="计划名称">
          <a-input
            v-model:value="form.name"
            :maxlength="100"
            data-testid="schedule-name"
          />
        </a-form-item>
        <a-form-item label="启用计划">
          <a-switch
            v-model:checked="form.enabled"
            data-testid="schedule-enabled"
          />
        </a-form-item>
        <div class="schedule-form__pair">
          <a-form-item label="每日启动时间">
            <a-input
              v-model:value="form.time_of_day"
              type="time"
              data-testid="schedule-time"
            />
          </a-form-item>
          <a-form-item label="执行时区">
            <a-select
              v-model:value="form.timezone"
              show-search
              :options="timezoneOptions"
            />
          </a-form-item>
        </div>
        <a-form-item label="机构">
          <a-select
            v-model:value="form.institute_id"
            :options="options.institutes.map(value => ({ value, label: value }))"
            @change="refreshOptions"
          />
        </a-form-item>
        <div class="schedule-form__pair">
          <a-form-item label="病历场景">
            <a-select
              v-model:value="form.scope"
              :options="sceneOptions"
              @change="changeScene"
            />
          </a-form-item>
          <a-form-item label="科室">
            <a-select
              v-model:value="form.department"
              :loading="optionsLoading"
              :options="[{ value: '', label: '全部科室' }, ...options.departments.map(value => ({ value, label: value }))]"
            />
          </a-form-item>
        </div>
        <a-form-item label="质控规则集">
          <a-select
            v-model:value="form.rule_set_key"
            :options="ruleOptions"
          />
        </a-form-item>
        <a-form-item label="日期依据">
          <a-select
            v-model:value="form.date_field"
            :options="[{ value: 'admission', label: '入院日期' }, { value: 'discharge', label: '出院日期' }]"
          />
        </a-form-item>
        <div class="schedule-form__pair">
          <a-form-item label="结束于执行日前几天">
            <a-input-number
              v-model:value="form.end_offset_days"
              :min="0"
              :max="365"
            />
          </a-form-item>
          <a-form-item label="向前覆盖天数">
            <a-input-number
              v-model:value="form.lookback_days"
              :min="1"
              :max="365"
            />
          </a-form-item>
        </div>
        <a-form-item label="单次病历上限">
          <a-input-number
            v-model:value="form.max_records"
            :min="1"
            :max="1000"
          />
        </a-form-item>
        <p class="mq-card__desc">
          {{ rangeHint }}。超出单次上限会阻止创建任务，不会静默截断。仅新周期采用编辑后的筛选条件。
        </p>
        <a-alert
          v-if="optionsError"
          type="error"
          :message="optionsError"
        />
        <a-alert
          v-if="submitError"
          type="error"
          :message="submitError"
        />
      </a-form>
    </a-modal>
    <a-drawer
      v-model:open="historyOpen"
      title="定时质控触发记录"
      width="min(620px, 100vw)"
    >
      <a-alert
        v-if="historyError"
        type="error"
        :message="historyError"
      />
      <a-empty
        v-else-if="!runs.length"
        description="尚无触发记录"
      />
      <div
        v-for="run in runs"
        :key="run.id"
        class="schedule-row"
      >
        <div>
          <strong>{{ run.local_date }} · {{ stateLabel(run.state) }}</strong>
          <p v-if="run.reason">
            {{ reasonLabel(run.reason) }}
          </p>
          <p v-if="run.job_id">
            质控任务：{{ run.job_id }}
          </p>
          <p>提交尝试：{{ run.attempts }} 次</p>
        </div>
      </div>
      <p class="mq-card__desc">
        “已提交”表示任务已进入现有质控链，不表示所有规则已成功完成。
      </p>
    </a-drawer>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { useAuthStore } from '@/stores/auth'
import { canManageSystemConfig } from '@/utils/systemConfigAccess'
import { dailyQcScheduleService, type DailyQcDefinition, type DailyQcList, type DailyQcOptions, type DailyQcPlan, type DailyQcRun } from '@/services/dailyQcScheduleService'

const auth = useAuthStore()
const canManage = computed(() => canManageSystemConfig(auth.userRoles))
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const optionsError = ref('')
const submitError = ref('')
const editing = ref(false)
const current = ref<DailyQcPlan>()
const status = ref<DailyQcList>({ items: [], scheduler_enabled: false, local_process_active: false })
const options = ref<DailyQcOptions>({ institutes: [], departments: [], rule_sets: [] })
const optionsLoading = ref(false)
const historyOpen = ref(false)
const historyError = ref('')
const runs = ref<DailyQcRun[]>([])
let active = true
let loadVersion = 0
let optionVersion = 0
let historyVersion = 0
let loadController: AbortController | null = null
let optionController: AbortController | null = null
let historyController: AbortController | null = null
const defaults = (): DailyQcDefinition => ({ name: '', enabled: false, time_of_day: '02:00', timezone: 'Asia/Shanghai', institute_id: '', scope: 'final', department: '', date_field: 'discharge', lookback_days: 1, end_offset_days: 1, rule_set_key: 'luxian_0609_qc_v1', rule_ids: [], max_records: 200 })
const form = reactive<DailyQcDefinition>(defaults())
const sceneOptions = [{ value: 'running', label: '运行病历' }, { value: 'final', label: '终末病历' }]
const timezoneOptions = [...new Set(['Asia/Shanghai', Intl.DateTimeFormat().resolvedOptions().timeZone, 'America/Chicago', 'UTC'])].map(value => ({ value, label: value }))
const ruleOptions = computed(() => options.value.rule_sets.filter(item => item.key === 'luxian_0609_qc_v1' || ['all', form.scope].includes(item.scope)).map(item => ({ value: item.key, label: item.name })))
const valid = computed(() => Boolean(form.name.trim() && form.institute_id && form.rule_set_key && /^([01]\d|2[0-3]):[0-5]\d$/.test(form.time_of_day)))
const rangeHint = computed(() => `按${form.date_field === 'admission' ? '入院' : '出院'}日期，结束于执行日之前${form.end_offset_days}天，向前覆盖${form.lookback_days}天`)

watch(
  form,
  () => {
    if (submitError.value) submitError.value = ''
  },
  { deep: true },
)

const labels: Record<string, string> = { submitted: '已提交质控任务', submitting: '正在提交／等待恢复', missed: '错过执行时间', skipped_overlap: '上一轮未结束，已跳过', skipped_disabled: '已停用，未触发', empty: '无符合条件病历', failed: '触发失败' }
function stateLabel(value: string | null) { return value ? labels[value] || '状态待核对' : '尚未触发' }
function reasonLabel(value: string) { return labels[value] || ({ permission_denied: '账号已停用或权限不足', submission_interrupted: '提交回执中断，等待按原任务身份恢复', recovery_budget_exhausted: '恢复次数已达上限，未创建新任务', admission_rejected: '现有质控入口未接纳任务，请核对范围、规则及部署配置', disabled: '计划已停用' } as Record<string, string>)[value] || '需要管理员核对' }
function formatTime(value: string, timezone: string) {
  try { return new Intl.DateTimeFormat('zh-CN', { timeZone: timezone, dateStyle: 'short', timeStyle: 'short' }).format(new Date(value)) } catch { return '时间未返回' }
}

async function load() {
  if (!canManage.value) return
  const version = ++loadVersion
  loadController?.abort()
  const controller = new AbortController()
  loadController = controller
  loading.value = true
  error.value = ''
  try {
    const result = await dailyQcScheduleService.list()
    if (active && version === loadVersion && !controller.signal.aborted) status.value = result
  } catch {
    if (active && version === loadVersion && !controller.signal.aborted) error.value = '定时计划读取失败；请确认权限、接口及064迁移已就绪。'
  } finally {
    if (active && version === loadVersion && loadController === controller) {
      loading.value = false
      loadController = null
    }
  }
}
async function refreshOptions() {
  const version = ++optionVersion
  optionController?.abort()
  const controller = new AbortController()
  optionController = controller
  optionsLoading.value = true
  optionsError.value = ''
  submitError.value = ''
  try {
    const result = await dailyQcScheduleService.options(form.institute_id, form.scope)
    if (!active || version !== optionVersion || controller.signal.aborted) return
    options.value = result
    if (!form.institute_id && result.institutes.length === 1) { form.institute_id = result.institutes[0]; await refreshOptions() }
    else if (form.department && !result.departments.includes(form.department)) form.department = ''
  } catch { if (active && version === optionVersion && !controller.signal.aborted) optionsError.value = '机构、科室或规则选项读取失败，请重新打开计划。' }
  finally {
    if (active && version === optionVersion && optionController === controller) {
      optionsLoading.value = false
      optionController = null
    }
  }
}
function openEditor(plan?: DailyQcPlan) {
  if (!canManage.value) return
  current.value = plan
  optionsError.value = ''
  submitError.value = ''
  Object.assign(form, plan ? Object.fromEntries(Object.keys(defaults()).map(key => [key, plan[key as keyof DailyQcDefinition]])) : defaults())
  editing.value = true
  void refreshOptions()
}
function changeScene() {
  submitError.value = ''
  form.department = ''
  form.date_field = form.scope === 'running' ? 'admission' : 'discharge'
  form.lookback_days = form.scope === 'running' ? 30 : 1
  form.end_offset_days = form.scope === 'running' ? 0 : 1
  form.rule_ids = []
  form.rule_set_key = 'luxian_0609_qc_v1'
  void refreshOptions()
}
async function save() {
  if (!canManage.value || !valid.value || optionsLoading.value || saving.value || optionsError.value) return
  saving.value = true
  submitError.value = ''
  try {
    await dailyQcScheduleService.save({ ...form, rule_ids: [...form.rule_ids] }, current.value)
    if (active) { editing.value = false; message.success('计划已保存'); await load() }
  } catch { if (active) submitError.value = '保存失败；计划可能已被修改，请刷新并核对选项后重试。' }
  finally { if (active) saving.value = false }
}
async function showHistory(plan: DailyQcPlan) {
  const version = ++historyVersion
  historyController?.abort()
  const controller = new AbortController()
  historyController = controller
  historyOpen.value = true
  historyError.value = ''
  runs.value = []
  try {
    const result = await dailyQcScheduleService.history(plan.id)
    if (active && version === historyVersion && !controller.signal.aborted) runs.value = result
  } catch {
    if (active && version === historyVersion && !controller.signal.aborted) historyError.value = '触发记录读取失败，不能据此判断未执行。'
  } finally {
    if (historyController === controller) historyController = null
  }
}
onMounted(load)
onBeforeUnmount(() => {
  active = false
  loadVersion++
  optionVersion++
  historyVersion++
  loadController?.abort()
  optionController?.abort()
  historyController?.abort()
})
</script>

<style scoped>
.schedule-note { margin: 16px 0; }
.schedule-row { display: flex; justify-content: space-between; gap: 16px; align-items: center; padding: 18px 0; border-bottom: 1px solid var(--mq-glass-border); }
.schedule-row p { margin: 6px 0 0; color: var(--mq-text-secondary); font-size: 13px; }
.schedule-row__body { min-width: 0; overflow-wrap: anywhere; }
.schedule-heading { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.schedule-form { margin-top: 20px; }
.schedule-form__pair { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 700px) { .schedule-row { align-items: flex-start; flex-direction: column; } .schedule-form__pair { grid-template-columns: 1fr; } }
</style>
