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
          message="当前为只读模式（qc_manager）"
          description="仅 admin 可修改并保存配置。"
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
                  :min="0"
                  :max="100000"
                  :disabled="isReadonly || loading"
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
                :disabled="loading"
                @click="handleReload"
              >
                刷新
              </a-button>
              <a-button
                :disabled="isReadonly || loading"
                @click="handleReset"
              >
                恢复默认
              </a-button>
              <a-button
                type="primary"
                :loading="saving"
                :disabled="isReadonly || loading"
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
import { computed, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'

import {
  frontpageApi,
  type FrontpageExtractionSettings,
  type FrontpageExtractionSettingsUpdate,
} from '@/api/frontpage'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const loading = ref(false)
const saving = ref(false)
const source = ref<'default' | 'file' | string>('default')

const form = reactive<FrontpageExtractionSettings>({
  sql_prefill_enabled: true,
  llm_backfill_enabled: true,
  allow_force_llm_regenerate: true,
  include_demo_records: true,
  auto_hide_demo_when_real_data: false,
  demo_hide_threshold: 1,
  stream_progress_enabled: true,
  default_preview_tab: 'preview',
})

const isAdmin = computed(() => authStore.userRoles.includes('admin'))
const isReadonly = computed(() => !isAdmin.value)

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
  loading.value = true
  try {
    const resp = await frontpageApi.getExtractionSettings()
    patchForm(resp.settings)
    source.value = resp.source
  } catch (error) {
    console.error('加载首页抽取设置失败:', error)
    message.error('加载首页抽取设置失败')
  } finally {
    loading.value = false
  }
}

async function handleReload() {
  await loadSettings()
}

async function handleSave() {
  const payload: FrontpageExtractionSettingsUpdate = {
    sql_prefill_enabled: form.sql_prefill_enabled,
    llm_backfill_enabled: form.llm_backfill_enabled,
    allow_force_llm_regenerate: form.allow_force_llm_regenerate,
    include_demo_records: form.include_demo_records,
    auto_hide_demo_when_real_data: form.auto_hide_demo_when_real_data,
    demo_hide_threshold: form.demo_hide_threshold,
    stream_progress_enabled: form.stream_progress_enabled,
    default_preview_tab: form.default_preview_tab,
  }
  saving.value = true
  try {
    const resp = await frontpageApi.updateExtractionSettings(payload)
    patchForm(resp.settings)
    source.value = resp.source
    message.success('首页抽取设置已保存')
  } catch (error) {
    console.error('保存首页抽取设置失败:', error)
    message.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function handleReset() {
  saving.value = true
  try {
    const resp = await frontpageApi.resetExtractionSettings()
    patchForm(resp.settings)
    source.value = resp.source
    message.success('已恢复默认设置')
  } catch (error) {
    console.error('重置首页抽取设置失败:', error)
    message.error('重置失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void loadSettings()
})
</script>

<style scoped>
.ds-root {
  max-width: 1100px;
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
  color: #0f172a;
  margin: 0 0 6px;
}

.ds-section-desc {
  margin: 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.7;
}

.ds-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  overflow: hidden;
}

.ds-divide > * {
  border-bottom: 1px solid #f1f5f9;
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
  color: #64748b;
  letter-spacing: 0.06em;
  text-transform: uppercase;
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
  color: #0f172a;
  font-weight: 600;
}

.ds-row__hint {
  margin-top: 2px;
  font-size: 12px;
  color: #94a3b8;
}

.ds-card__footer {
  padding: 12px 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #f8fafc;
  border-top: 1px solid #e2e8f0;
}

.ds-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ds-footer-meta {
  font-size: 12px;
  color: #94a3b8;
}
</style>
