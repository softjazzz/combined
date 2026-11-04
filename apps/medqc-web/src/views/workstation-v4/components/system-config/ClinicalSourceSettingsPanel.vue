<template>
  <section
    class="mq-card mq-card--padded clinical-source-settings"
    aria-label="病历读取数据源"
  >
    <div class="mq-card__head">
      <div>
        <h2 class="mq-card__title">病历读取数据源</h2>
        <p class="mq-card__desc">
          运行／终末病历池可按来源切换。1026材料副本和历史结果仍保留在业务库。
        </p>
      </div>
    </div>
    <p
      v-if="loading"
      role="status"
    >
      正在读取数据源设置…
    </p>
    <p
      v-if="notice"
      role="status"
    >
      {{ notice }}
    </p>
    <form
      v-if="settings"
      @submit.prevent="save"
    >
      <div class="source-grid">
        <label
          >默认数据源
          <select
            v-model="settings.default_source"
            aria-label="默认数据源"
          >
            <option
              value="legacy_pg"
              :disabled="!settings.legacy_enabled"
            >
              {{ settings.legacy_name }}
            </option>
            <option
              value="independent_cdm"
              :disabled="!settings.cdm.enabled"
            >
              {{ settings.cdm.name }}
            </option>
          </select>
        </label>
        <label
          >原有来源名称<input
            v-model="settings.legacy_name"
            required
            maxlength="100"
        /></label>
        <label class="source-toggle"
          ><input
            v-model="settings.legacy_enabled"
            type="checkbox"
          />启用原有数据源</label
        >
      </div>
      <h3>独立 CDM 只读来源</h3>
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
        密码由部署侧的专用凭据文件提供，不在页面保存。保存不会连接源库、同步数据或启动质控；默认源仅影响新打开的病历池。
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
import { onMounted, ref } from 'vue'
import { clinicalSourcesApi, type ClinicalSourceSettings } from '@/api/clinicalSources'

const settings = ref<ClinicalSourceSettings | null>(null)
const loading = ref(false)
const busy = ref(false)
const notice = ref('')
async function load() {
  loading.value = true
  try {
    settings.value = await clinicalSourcesApi.configuration()
    notice.value = ''
  } catch {
    notice.value = '无法读取数据源配置，请稍后重试'
  } finally {
    loading.value = false
  }
}
async function save() {
  if (!settings.value || busy.value) return
  busy.value = true
  try {
    settings.value = await clinicalSourcesApi.save(settings.value)
    notice.value = '设置已保存，已有任务继续使用创建时的来源'
  } catch {
    notice.value = '保存失败，请检查来源、部署凭据，或重新读取后再保存'
  } finally {
    busy.value = false
  }
}
async function check() {
  if (!settings.value || busy.value) return
  busy.value = true
  try {
    await clinicalSourcesApi.check(settings.value)
    notice.value = 'CDM连接及目录结构只读检查通过，未保存配置'
  } catch {
    notice.value = 'CDM检查未通过，请核对连接、只读权限和同步表结构；未切换来源'
  } finally {
    busy.value = false
  }
}
onMounted(load)
</script>

<style scoped>
.clinical-source-settings {
  margin-bottom: 20px;
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
  color: #475569;
}
input:not([type='checkbox']),
select {
  height: 36px;
  padding: 0 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: white;
  color: #0f172a;
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
