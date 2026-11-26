<template>
  <section
    class="mq-card mq-card--padded clinical-source-settings"
    aria-label="病历读取数据源"
  >
    <div class="mq-card__head">
      <div>
        <h2 class="mq-card__title">病历读取数据源</h2>
        <p class="mq-card__desc">
          普通病历固定读取东华CDM。1026材料和历史结果保留在业务库。
        </p>
      </div>
    </div>
    <p
      v-if="loading"
      class="source-notice source-notice--status"
      role="status"
    >
      正在读取数据源设置…
    </p>
    <p
      v-if="notice"
      :class="[
        'source-notice',
        noticeTone === 'error' ? 'source-notice--error' : 'source-notice--status',
      ]"
      :role="noticeTone === 'error' ? 'alert' : 'status'"
    >
      {{ notice }}
    </p>
    <form
      v-if="settings"
      @submit.prevent="save"
    >
      <p class="mq-card__desc">普通临床来源：东华CDM（只读）。此页面不提供原Homo／clinical_data切换。</p>
      <h3>东华CDM连接设置</h3>
      <div class="source-grid">
        <label
          >来源名称<input
            v-model="settings.cdm.name"
            required
            maxlength="100"
        /></label>
        <label class="source-toggle"
          ><input
            v-model="settings.cdm.enabled"
            type="checkbox"
          />启用独立 CDM</label
        >
        <label
          >主机<input
            v-model="settings.cdm.host"
            required
            aria-label="CDM主机"
        /></label>
        <label
          >端口<input
            v-model.number="settings.cdm.port"
            type="number"
            required
            min="1"
            max="65535"
        /></label>
        <label
          >数据库<input
            v-model="settings.cdm.database"
            required
            aria-label="CDM数据库"
        /></label>
        <label
          >只读用户名<input
            v-model="settings.cdm.username"
            :required="settings.cdm.enabled"
            autocomplete="off"
        /></label>
      </div>
      <p class="mq-card__desc">
        密码由部署侧的专用凭据文件提供，不在页面保存。保存不会连接源库、同步数据或启动质控；已有任务保留创建时的来源，不重新计算历史结果。
      </p>
      <div class="source-actions">
        <button
          type="submit"
          class="mq-btn mq-btn--primary"
          :disabled="busy"
        >
          保存数据源设置
        </button>
        <button
          type="button"
          class="mq-btn"
          :disabled="busy"
          @click="check"
        >
          只读检查 CDM
        </button>
        <button
          type="button"
          class="mq-btn"
          :disabled="busy"
          @click="load"
        >
          重新读取
        </button>
      </div>
    </form>
  </section>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { clinicalSourcesApi, type ClinicalSourceSettings } from '@/api/clinicalSources'
import { resetClinicalSourceOptionsCache } from '@/views/workstation-v4/composables/usePatientRecords'

const settings = ref<ClinicalSourceSettings | null>(null)
const loading = ref(false)
const busy = ref(false)
const notice = ref('')
const noticeTone = ref<'status' | 'error'>('status')
let disposed = false
let requestSeq = 0
let activeController: AbortController | null = null

interface ClinicalSourceErrorPayload {
  error?: unknown
  detail?: unknown
  code?: unknown
}

const KNOWN_CLINICAL_SOURCE_ERROR_MESSAGES: Record<string, string> = {
  clinical_source_credentials_unavailable:
    '部署凭据不可用：服务端尚未配置 CDM 只读凭据文件（CDM_PGPASSFILE），请联系实施人员处理',
  clinical_source_host_not_allowed:
    'CDM 主机地址不在服务端允许列表内，请核对主机地址或联系实施人员',
  at_least_one_clinical_source_required:
    '至少需要保留一个已启用的临床数据源，无法同时停用全部来源',
  clinical_source_configuration_changed:
    '配置已被其他管理员修改（版本冲突），请点击「重新读取」后再保存',
  clinical_source_username_required: '启用独立 CDM 或执行检查时，必须填写只读用户名',
  clinical_source_disabled: '所选默认数据源未启用，请先启用该数据源后再保存',
  clinical_source_connection_unavailable:
    '无法连接到 CDM 数据库，请核对主机、端口、数据库名与网络连通性；未切换来源',
}

function extractClinicalSourceError(cause: unknown): { status?: number; code: string } {
  const response = (
    cause as { response?: { status?: number; data?: ClinicalSourceErrorPayload } } | null
  )?.response
  const status = typeof response?.status === 'number' ? response.status : undefined
  const data = response?.data
  const rawCode = data?.error ?? data?.detail ?? data?.code
  const code = typeof rawCode === 'string' ? rawCode.trim() : ''
  return { status, code }
}

function resolveClinicalSourceErrorMessage(
  cause: unknown,
  action: 'load' | 'save' | 'check',
): string {
  const { status, code } = extractClinicalSourceError(cause)
  if (code && KNOWN_CLINICAL_SOURCE_ERROR_MESSAGES[code]) {
    return KNOWN_CLINICAL_SOURCE_ERROR_MESSAGES[code]
  }
  if (status === 409) {
    return '配置已被其他管理员修改（版本冲突），请点击「重新读取」后再保存'
  }
  if (action === 'load') {
    return '无法读取数据源配置，请稍后重试'
  }
  if (action === 'save') {
    return '保存失败，请检查来源、部署凭据，或重新读取后再保存'
  }
  return 'CDM检查未通过，请核对连接、只读权限和同步表结构；未切换来源'
}

async function load() {
  if (busy.value) return
  const seq = ++requestSeq
  activeController?.abort()
  const controller = new AbortController()
  activeController = controller
  loading.value = true
  try {
    const loaded = await clinicalSourcesApi.configuration({ signal: controller.signal })
    if (disposed || seq !== requestSeq || controller.signal.aborted) return
    settings.value = loaded
    notice.value = ''
    noticeTone.value = 'status'
  } catch (cause) {
    if (disposed || seq !== requestSeq || controller.signal.aborted) return
    noticeTone.value = 'error'
    notice.value = resolveClinicalSourceErrorMessage(cause, 'load')
  } finally {
    if (!disposed && seq === requestSeq && activeController === controller) {
      loading.value = false
      activeController = null
    }
  }
}
async function save() {
  if (!settings.value || busy.value) return
  const seq = ++requestSeq
  activeController?.abort()
  const controller = new AbortController()
  activeController = controller
  busy.value = true
  try {
    const saved = await clinicalSourcesApi.save(
      {
        ...settings.value,
        cdm: { ...settings.value.cdm },
      },
      { signal: controller.signal },
    )
    if (disposed || seq !== requestSeq || controller.signal.aborted) return
    settings.value = saved
    resetClinicalSourceOptionsCache()
    noticeTone.value = 'status'
    notice.value = '设置已保存，已有任务继续使用创建时的来源'
  } catch (cause) {
    if (disposed || seq !== requestSeq || controller.signal.aborted) return
    noticeTone.value = 'error'
    notice.value = resolveClinicalSourceErrorMessage(cause, 'save')
  } finally {
    if (!disposed && seq === requestSeq && activeController === controller) {
      busy.value = false
      activeController = null
    }
  }
}
async function check() {
  if (!settings.value || busy.value) return
  const seq = ++requestSeq
  activeController?.abort()
  const controller = new AbortController()
  activeController = controller
  busy.value = true
  try {
    const report = await clinicalSourcesApi.check(settings.value, { signal: controller.signal })
    if (disposed || seq !== requestSeq || controller.signal.aborted) return
    if (!report.ok) {
      const failures = report.dependencies.filter((row) => !['structure_ready', 'rows_present', 'zero_rows'].includes(row.status)
        && (row.required || row.status !== 'table_missing'))
      noticeTone.value = 'error'
      notice.value = `只读预检未通过：${failures.length ? failures.map((row) => `${row.table} (${row.status})`).join('、') : '账号权限或只读事务不符合要求'}`
      return
    }
    noticeTone.value = 'status'
    const publicationNote =
      report.publication_ready === true
        ? '同步发布已就绪'
        : report.publication_ready === false
          ? '同步发布尚未就绪'
          : '发布就绪仍待确认'
    notice.value = `CDM完整依赖只读检查通过；${publicationNote}，未保存配置`
  } catch (cause) {
    if (disposed || seq !== requestSeq || controller.signal.aborted) return
    noticeTone.value = 'error'
    notice.value = resolveClinicalSourceErrorMessage(cause, 'check')
  } finally {
    if (!disposed && seq === requestSeq && activeController === controller) {
      busy.value = false
      activeController = null
    }
  }
}
onMounted(load)
onBeforeUnmount(() => {
  disposed = true
  requestSeq += 1
  activeController?.abort()
  activeController = null
})
</script>

<style scoped>
.clinical-source-settings {
  margin-bottom: 20px;
}
.source-notice {
  margin: 12px 0;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: var(--mq-font-13, 13px);
  line-height: 1.5;
  font-weight: 500;
}
.source-notice--status {
  border: 1px solid var(--mq-info-border, rgba(10, 108, 255, 0.16));
  background: var(--mq-info-bg, rgba(10, 108, 255, 0.08));
  color: var(--mq-info-text, #0a5fd6);
}
.source-notice--error {
  border: 1px solid var(--mq-danger-border, rgba(255, 59, 48, 0.22));
  background: var(--mq-danger-bg, rgba(255, 59, 48, 0.1));
  color: var(--mq-danger-text, #c41c30);
  font-weight: 600;
}
.source-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 16px;
  margin: 16px 0;
}
label {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 13px;
  color: var(--mq-text-secondary, #515154);
}
input:not([type='checkbox']),
select {
  height: 36px;
  padding: 0 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: white;
  color: var(--mq-text-primary, #1d1d1f);
}
input:focus-visible,
select:focus-visible {
  outline: 2px solid var(--mq-brand-600, #0a6cff);
  outline-offset: 2px;
  border-color: var(--mq-brand-600, #0a6cff);
  box-shadow: 0 0 0 3px rgba(10, 108, 255, 0.14);
}
.source-toggle {
  flex-direction: row;
  align-items: center;
}
.source-actions {
  display: flex;
  gap: 12px;
  margin-top: 16px;
  flex-wrap: wrap;
}
</style>
