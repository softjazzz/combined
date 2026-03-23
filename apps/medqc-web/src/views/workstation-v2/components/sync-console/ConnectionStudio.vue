<template>
  <div class="flex flex-col h-full bg-white">
    <div class="px-5 py-4 border-b border-[#E5E7EB] flex items-center justify-between shrink-0">
      <h2 class="text-[14px] font-semibold text-slate-800 tracking-tight">
        连接配置
      </h2>
      <a-tooltip :title="isReadonly ? '仅 admin 可执行' : '测试当前标签连接'">
        <button
          class="text-[12px] font-medium text-slate-500 hover:text-slate-700 transition-colors"
          :disabled="isReadonly || state.isTestingActive"
          @click="handleTestCurrent"
        >
          检测连通性
        </button>
      </a-tooltip>
    </div>

    <div class="px-5 py-3 shrink-0 relative">
      <div class="flex p-1 rounded-[8px] bg-slate-100/80 border border-slate-200/50 relative">
        <button
          :class="tabClass('pg_local')"
          @click="state.activeTab = 'pg_local'"
        >
          本地库
        </button>
        <button
          :class="tabClass('pg_remote')"
          @click="state.activeTab = 'pg_remote'"
        >
          前端 PG
        </button>
        <button
          :class="tabClass('mongo')"
          @click="state.activeTab = 'mongo'"
        >
          Mongo 源
        </button>
      </div>
    </div>

    <div class="flex-1 overflow-y-auto custom-scrollbar px-5 pb-5">
      <div
        v-if="state.activeTab === 'mongo'"
        class="space-y-4"
      >
        <div class="pt-2 pb-3 border-b border-slate-100">
          <div class="text-[13px] font-semibold text-slate-800">
            病历文档库 (Mongo)
          </div>
          <div class="text-[11px] text-slate-500 mt-1">
            当前状态：{{ state.mongoSyncState.connected ? '已连接' : '未连接' }}
          </div>
        </div>

        <div>
          <label class="text-[12px] text-slate-600">连接 URI（留空表示保持不变）</label>
          <a-textarea
            v-model:value="state.mongoConnectionForm.mongo_uri"
            :rows="3"
            :disabled="isReadonly"
            placeholder="mongodb://user:pass@host:27017/db"
          />
          <div class="text-[11px] text-slate-400 mt-1">
            当前配置：{{ state.mongoConfigRaw.mongo_uri_display || '未配置' }}
          </div>
        </div>

        <div>
          <label class="text-[12px] text-slate-600">数据库名</label>
          <a-input
            v-model:value="state.mongoConnectionForm.mongo_database"
            :disabled="isReadonly"
          />
        </div>

        <div>
          <label class="text-[12px] text-slate-600">读偏好</label>
          <a-select
            v-model:value="state.mongoConnectionForm.read_preference"
            :disabled="isReadonly"
            style="width: 100%"
            :options="readPreferenceOptions"
          />
        </div>

        <div>
          <label class="text-[12px] text-slate-600">连接超时 (ms)</label>
          <a-input-number
            v-model:value="state.mongoConnectionForm.connect_timeout_ms"
            :disabled="isReadonly"
            :min="1000"
            :max="60000"
            style="width: 100%"
          />
        </div>

        <div class="pt-2">
          <a-button
            type="primary"
            block
            :disabled="isReadonly"
            :loading="state.isSavingMongoConnection"
            @click="handleSaveMongo"
          >
            保存并测试
          </a-button>
        </div>
      </div>

      <div
        v-else-if="state.activeTab === 'pg_remote'"
        class="space-y-4"
      >
        <div class="pt-2 pb-3 border-b border-slate-100">
          <div class="text-[13px] font-semibold text-slate-800">
            业务流水库 (PG 远端)
          </div>
          <div class="text-[11px] text-slate-500 mt-1">
            仅 admin 可修改，qc_manager 只读。
          </div>
        </div>

        <div>
          <label class="text-[12px] text-slate-600">主机地址</label>
          <a-input
            v-model:value="state.pgConnectionForm.remote_host"
            :disabled="isReadonly"
          />
        </div>

        <div>
          <label class="text-[12px] text-slate-600">端口</label>
          <a-input-number
            v-model:value="state.pgConnectionForm.remote_port"
            :disabled="isReadonly"
            :min="1"
            :max="65535"
            style="width: 100%"
          />
        </div>

        <div>
          <label class="text-[12px] text-slate-600">数据库名</label>
          <a-input
            v-model:value="state.pgConnectionForm.remote_database"
            :disabled="isReadonly"
          />
        </div>

        <div>
          <label class="text-[12px] text-slate-600">用户名</label>
          <a-input
            v-model:value="state.pgConnectionForm.remote_username"
            :disabled="isReadonly"
          />
        </div>

        <div>
          <label class="text-[12px] text-slate-600">密码（留空保持不变）</label>
          <a-input-password
            v-model:value="state.pgConnectionForm.remote_password"
            :disabled="isReadonly"
          />
          <div class="text-[11px] text-slate-400 mt-1">
            当前密码状态：{{ state.pgConnectionForm.remote_password_set ? '已设置' : '未设置' }}
          </div>
        </div>

        <div class="pt-2">
          <a-button
            type="primary"
            block
            :disabled="isReadonly"
            :loading="state.isSavingPgConnection"
            @click="handleSavePg"
          >
            保存配置
          </a-button>
        </div>
      </div>

      <div
        v-else
        class="space-y-4"
      >
        <div class="pt-2 pb-3 border-b border-slate-100">
          <div class="text-[13px] font-semibold text-slate-800">
            本地核心仓 (PG 本地)
          </div>
          <div class="text-[11px] text-slate-500 mt-1">
            本地连接只读，支持检测连通性。
          </div>
        </div>

        <a-alert
          type="info"
          show-icon
          message="本地库配置由部署环境管理，不在控制台中修改。"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { message } from 'ant-design-vue'
import { useDataSync } from '../../composables/useDataSync'

const { state, isReadonly, testActiveConnection, saveMongoConnection, savePgConnection } = useDataSync()

const readPreferenceOptions = [
  { label: 'secondaryPreferred（推荐）', value: 'secondaryPreferred' },
  { label: 'secondary', value: 'secondary' },
  { label: 'primaryPreferred', value: 'primaryPreferred' },
  { label: 'primary', value: 'primary' },
  { label: 'nearest', value: 'nearest' },
]

const tabClass = (tab: 'mongo' | 'pg_remote' | 'pg_local') => [
  'flex-1 py-1.5 rounded-[6px] text-[12px] font-medium transition-all duration-300 relative z-10',
  state.activeTab === tab
    ? 'bg-white text-slate-800 shadow-[0_1px_4px_rgba(15,23,42,0.08)] ring-1 ring-slate-900/5'
    : 'text-slate-500 hover:text-slate-700',
]

const handleTestCurrent = async () => {
  try {
    const result = await testActiveConnection()
    if (result.connected) {
      message.success('连接成功')
    } else {
      message.warning(result.error || '连接失败')
    }
  } catch {
    message.error('连接测试失败')
  }
}

const handleSaveMongo = async () => {
  try {
    const testResult = await saveMongoConnection()
    if (testResult.connected) {
      message.success('Mongo 配置已保存并验证通过')
    } else {
      message.warning(`配置已保存，但连接失败：${testResult.error || '未知错误'}`)
    }
  } catch {
    message.error('Mongo 配置保存失败')
  }
}

const handleSavePg = async () => {
  try {
    const result = await savePgConnection()
    if (result.connection?.connected) {
      message.success('PG 配置已保存并连通')
    } else {
      message.warning(`PG 配置已保存，但连接失败：${result.connection?.error || '未知错误'}`)
    }
  } catch {
    message.error('PG 配置保存失败')
  }
}
</script>
