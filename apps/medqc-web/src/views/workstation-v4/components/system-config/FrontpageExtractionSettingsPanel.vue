<template>
  <div class="ds-root">
    <div class="ds-split">
      <div class="ds-split__aside">
        <h2 class="ds-section-title">
          首页抽取设置
        </h2>
        <p class="ds-section-desc">
          管理首页抽取策略、样例病历显隐与生成体验策略。配置由后端统一持久化并实时生效。
        </p>
      </div>
      <div class="ds-split__main">
        <a-alert
          v-if="isReadonly"
          type="info"
          show-icon
          message="当前为只读模式"
          description="当前账号仅可查看，需全局系统管理员（admin / sync_admin / super_admin）角色方可修改。"
          class="mb-3"
        />

        <div class="ds-card">
          <div class="ds-card__body ds-divide">
            <div class="ds-group">
              <div class="ds-group__title">
                抽取策略
              </div>

              <div class="ds-row">
                <div class="ds-row__left">
                  <div class="ds-row__label">
                    SQL 预填充
                  </div>
                  <div class="ds-row__hint">
                    优先使用 CDM 结构化字段填充首页。
                  </div>
                </div>
                <a-switch
                  v-model:checked="form.sql_prefill_enabled"
                  :disabled="isReadonly || loading"
                />
              </div>

              <div class="ds-row">
                <div class="ds-row__left">
                  <div class="ds-row__label">
                    LLM 补缺
                  </div>
                  <div class="ds-row__hint">
                    SQL 缺失字段允许 LLM 解析病历补齐。
                  </div>
                </div>
                <a-switch
                  v-model:checked="form.llm_backfill_enabled"
                  :disabled="isReadonly || loading"
                />
              </div>

              <div class="ds-row">
                <div class="ds-row__left">
                  <div class="ds-row__label">
                    允许强制重抽
                  </div>
                  <div class="ds-row__hint">
                    关闭后，“重新生成”将退化为普通重抽，不触发 force_llm。
                  </div>
                </div>
                <a-switch
                  v-model:checked="form.allow_force_llm_regenerate"
                  :disabled="isReadonly || loading"
                />
              </div>
            </div>

            <div class="ds-group">
              <div class="ds-group__title">
                样例数据策略
              </div>

              <div class="ds-row">
                <div class="ds-row__left">
                  <div class="ds-row__label">
                    显示样例病历
                  </div>
                  <div class="ds-row__hint">
                    控制首页是否合并展示样例病历。
                  </div>
                </div>
                <a-switch
                  v-model:checked="form.include_demo_records"
                  :disabled="isReadonly || loading"
                />
              </div>

              <div class="ds-row">
                <div class="ds-row__left">
                  <div class="ds-row__label">
                    真实数据阈值自动隐藏样例
                  </div>
                  <div class="ds-row__hint">
                    真实病历量达到阈值后自动隐藏样例病历。
                  </div>
                </div>
                <a-switch
                  v-model:checked="form.auto_hide_demo_when_real_data"
                  :disabled="isReadonly || loading"
                />
              </div>

              <div class="ds-row">
                <div class="ds-row__left">
                  <div class="ds-row__label">
                    自动隐藏阈值
                  </div>
                  <div class="ds-row__hint">
                    真实病历数量达到该值时触发自动隐藏。
                  </div>
                </div>
                <a-input-number
                  v-model:value="form.demo_hide_threshold"
                  data-testid="frontpage-demo-hide-threshold"
                  :min="0"
                  :max="100000"
                  :disabled="isReadonly || loading"
                  @blur="handleDemoHideThresholdBlur"
                />
              </div>
            </div>

            <div class="ds-group">
              <div class="ds-group__title">
                运行体验策略
              </div>

              <div class="ds-row">
                <div class="ds-row__left">
                  <div class="ds-row__label">
                    流式进度推送
                  </div>
                  <div class="ds-row__hint">
                    关闭后仅返回最终结果，不输出模块级 update 进度。
                  </div>
                </div>
                <a-switch
                  v-model:checked="form.stream_progress_enabled"
                  :disabled="isReadonly || loading"
                />
              </div>

              <div class="ds-row">
                <div class="ds-row__left">
                  <div class="ds-row__label">
                    默认预览标签
                  </div>
                  <div class="ds-row__hint">
                    首页抽取完成后默认切换到指定标签。
                  </div>
                </div>
                <a-select
                  v-model:value="form.default_preview_tab"
                  :disabled="isReadonly || loading"
                  style="width: 160px"
                  :options="[
                    { label: '字段视图', value: 'fields' },
                    { label: '打印预览', value: 'preview' },
                  ]"
                />
              </div>
            </div>
          </div>

          <div class="ds-card__footer">
            <span class="ds-footer-meta">来源：{{ source }}</span>
            <div class="ds-actions">
              <a-button
                :disabled="loading || saving || resetting"
                @click="handleReload"
              >
                刷新
              </a-button>
              <a-button
                data-testid="frontpage-settings-reset"
                :loading="resetting"
                :disabled="isReadonly || loading || saving || resetting"
                @click="handleReset"
              >
                恢复默认
              </a-button>
              <a-button
                type="primary"
                data-testid="frontpage-settings-save"
                :loading="saving"
                :disabled="isReadonly || loading || resetting"
                @click="handleSave"
              >
                保存配置
              </a-button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'

import { useWorkstationConfirmation } from '@/components/layout/workstationConfirmation'
import {
  frontpageApi,
  type FrontpageExtractionSettings,
  type FrontpageExtractionSettingsUpdate,
} from '@/api/frontpage'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const workstationConfirmation = useWorkstationConfirmation()
const loading = ref(false)
const saving = ref(false)
const resetting = ref(false)
const confirmPending = ref(false)
const source = ref<'default' | 'file' | string>('default')

let disposed = false
let loadSeq = 0
let loadController: AbortController | null = null
let mutationController: AbortController | null = null

type FrontpageExtractionSettingsForm = Omit<FrontpageExtractionSettings, 'demo_hide_threshold'> & {
  demo_hide_threshold: number | null
}

const form = reactive<FrontpageExtractionSettingsForm>({
  sql_prefill_enabled: true,
  llm_backfill_enabled: true,
  allow_force_llm_regenerate: true,
  include_demo_records: true,
  auto_hide_demo_when_real_data: false,
  demo_hide_threshold: 1,
  stream_progress_enabled: true,
  default_preview_tab: 'preview',
})

function normalizeDemoHideThreshold(value: unknown): number {
  if (value === null || value === undefined || value === '') return 0
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return 0
  return Math.min(100000, Math.max(0, Math.trunc(parsed)))
}

function handleDemoHideThresholdBlur() {
  form.demo_hide_threshold = normalizeDemoHideThreshold(form.demo_hide_threshold)
}

const canManageFrontpageConfig = computed(() => {
  const roles = authStore.userRoles || []
  if (roles.some((role) => ['sync_admin', 'super_admin'].includes(role))) {
    return true
  }
  if (roles.includes('admin')) {
    const instituteId = String(
      (authStore.user as { institute_id?: string | null } | null)?.institute_id ?? '',
    ).trim()
    return !instituteId
  }
  return false
})
const isReadonly = computed(() => !canManageFrontpageConfig.value)

function patchForm(payload: FrontpageExtractionSettings) {
  form.sql_prefill_enabled = payload.sql_prefill_enabled
  form.llm_backfill_enabled = payload.llm_backfill_enabled
  form.allow_force_llm_regenerate = payload.allow_force_llm_regenerate
  form.include_demo_records = payload.include_demo_records
  form.auto_hide_demo_when_real_data = payload.auto_hide_demo_when_real_data
  form.demo_hide_threshold = payload.demo_hide_threshold
  form.stream_progress_enabled = payload.stream_progress_enabled
  form.default_preview_tab = payload.default_preview_tab
}

async function loadSettings() {
  if (saving.value || resetting.value) return
  const seq = ++loadSeq
  loadController?.abort()
  const controller = new AbortController()
  loadController = controller
  loading.value = true
  try {
    const resp = await frontpageApi.getExtractionSettings({ signal: controller.signal })
    if (disposed || seq !== loadSeq || controller.signal.aborted) return
    patchForm(resp.settings)
    source.value = resp.source
  } catch (error) {
    if (disposed || seq !== loadSeq || controller.signal.aborted) return
    console.error('加载首页抽取设置失败:', error)
    message.error('加载首页抽取设置失败')
  } finally {
    if (!disposed && seq === loadSeq && loadController === controller) {
      loading.value = false
      loadController = null
    }
  }
}

async function handleReload() {
  await loadSettings()
}

async function handleSave() {
  if (isReadonly.value || loading.value || saving.value || resetting.value) return
  loadSeq += 1
  loadController?.abort()
  loadController = null
  mutationController?.abort()
  const controller = new AbortController()
  mutationController = controller
  const normalizedThreshold = normalizeDemoHideThreshold(form.demo_hide_threshold)
  form.demo_hide_threshold = normalizedThreshold
  const payload: FrontpageExtractionSettingsUpdate = {
    sql_prefill_enabled: form.sql_prefill_enabled,
    llm_backfill_enabled: form.llm_backfill_enabled,
    allow_force_llm_regenerate: form.allow_force_llm_regenerate,
    include_demo_records: form.include_demo_records,
    auto_hide_demo_when_real_data: form.auto_hide_demo_when_real_data,
    demo_hide_threshold: normalizedThreshold,
    stream_progress_enabled: form.stream_progress_enabled,
    default_preview_tab: form.default_preview_tab,
  }
  saving.value = true
  try {
    const resp = await frontpageApi.updateExtractionSettings(payload, { signal: controller.signal })
    if (disposed || controller.signal.aborted) return
    patchForm(resp.settings)
    source.value = resp.source
    message.success('首页抽取设置已保存')
  } catch (error) {
    if (disposed || controller.signal.aborted) return
    console.error('保存首页抽取设置失败:', error)
    message.error('保存失败')
  } finally {
    if (mutationController === controller) mutationController = null
    if (!disposed) saving.value = false
  }
}

async function handleReset() {
  if (isReadonly.value || loading.value || saving.value || resetting.value || confirmPending.value) {
    return
  }
  confirmPending.value = true
  let confirmed = false
  try {
    confirmed = await new Promise<boolean>((resolve) => {
      workstationConfirmation.confirm({
        title: '确认恢复默认首页抽取设置？',
        content: '将把抽取策略、样例数据策略和运行体验策略恢复为系统默认值，当前修改将被覆盖。',
        okText: '确认恢复',
        cancelText: '取消',
        okType: 'danger',
        onOk: () => resolve(true),
        onCancel: () => resolve(false),
      })
    })
  } finally {
    confirmPending.value = false
  }
  if (!confirmed || disposed || isReadonly.value || saving.value || resetting.value) return

  loadSeq += 1
  loadController?.abort()
  loadController = null
  mutationController?.abort()
  const controller = new AbortController()
  mutationController = controller
  resetting.value = true
  try {
    const resp = await frontpageApi.resetExtractionSettings({ signal: controller.signal })
    if (disposed || controller.signal.aborted) return
    patchForm(resp.settings)
    source.value = resp.source
    message.success('已恢复默认设置')
  } catch (error) {
    if (disposed || controller.signal.aborted) return
    console.error('重置首页抽取设置失败:', error)
    message.error('重置失败')
  } finally {
    if (mutationController === controller) mutationController = null
    if (!disposed) resetting.value = false
  }
}

onMounted(() => {
  void loadSettings()
})

onBeforeUnmount(() => {
  disposed = true
  loadSeq += 1
  loadController?.abort()
  loadController = null
  mutationController?.abort()
  mutationController = null
})
</script>

<style scoped>
.ds-root {
  max-width: 1100px;
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

.ds-split {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

@media (min-width: 960px) {
  .ds-split {
    grid-template-columns: 260px 1fr;
    gap: 28px;
  }
}

.ds-section-title {
  font-size: 16px;
  font-weight: 700;
  color: #1d1d1f;
  margin: 0 0 6px;
}

.ds-section-desc {
  margin: 0;
  color: var(--mq-text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.ds-card {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.86);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  box-shadow:
    0 1px 4px rgba(0, 0, 0, 0.045),
    0 2px 8px rgba(0, 0, 0, 0.035);
  overflow: hidden;
  transition:
    border-color 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    transform 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.ds-card:hover {
  border-color: rgba(0, 0, 0, 0.14);
  box-shadow:
    0 2px 12px rgba(0, 0, 0, 0.1),
    0 6px 22px rgba(0, 0, 0, 0.075);
  transform: translateY(-2px);
}

.ds-divide > * {
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.ds-divide > *:last-child {
  border-bottom: none;
}

.ds-group {
  padding: 6px 0;
}

.ds-group__title {
  font-size: 13px;
  font-weight: 700;
  color: var(--mq-text-secondary);
  letter-spacing: 0;
  padding: 10px 18px;
}

.ds-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 12px 18px;
}

.ds-row__left {
  min-width: 0;
}

.ds-row__label {
  font-size: 14px;
  color: var(--mq-text-primary);
  font-weight: 600;
}

.ds-row__hint {
  margin-top: 2px;
  font-size: 12px;
  color: var(--mq-text-tertiary);
}

.ds-card__footer {
  padding: 12px 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(245, 245, 247, 0.68);
  border-top: 1px solid rgba(0, 0, 0, 0.08);
}

.ds-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ds-footer-meta {
  font-size: 12px;
  color: var(--mq-text-tertiary);
}

.ds-root :deep(.ant-btn) {
  border-radius: 8px;
  font-weight: 600;
}

.ds-root :deep(.ant-btn-primary) {
  background: #0a6cff;
  border-color: #0a6cff;
  box-shadow: 0 5px 14px rgba(10, 108, 255, 0.18);
}

.ds-root :deep(.ant-switch-checked) {
  background: #0a6cff;
}

.ds-root :deep(.ant-alert) {
  border-color: rgba(10, 108, 255, 0.14);
  border-radius: 12px;
  background: rgba(10, 108, 255, 0.06);
  color: #1d1d1f;
}

.ds-root :deep(.ant-alert-message) {
  color: #1d1d1f;
  font-weight: 600;
}

.ds-root :deep(.ant-alert-description) {
  color: var(--mq-text-secondary);
}

.ds-root :deep(.ant-input-number),
.ds-root :deep(.ant-select-selector) {
  border-color: rgba(0, 0, 0, 0.08) !important;
  border-radius: 8px !important;
  background: rgba(255, 255, 255, 0.9) !important;
  box-shadow: none !important;
}
</style>
