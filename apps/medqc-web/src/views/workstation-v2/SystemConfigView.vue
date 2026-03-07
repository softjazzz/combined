<template>
  <div class="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50/30 dark:from-slate-900 dark:to-slate-800 p-6">
    <div class="max-w-5xl mx-auto space-y-6">

      <!-- 页面标题 -->
      <div class="flex items-center gap-3 mb-2">
        <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-lg">
          <SettingOutlined class="text-white text-lg" />
        </div>
        <div>
          <h1 class="text-xl font-bold text-slate-800 dark:text-slate-100">数据源配置</h1>
          <p class="text-sm text-slate-500 dark:text-slate-400">管理本地与远端数据库连接、数据同步</p>
        </div>
      </div>

      <!-- 数据库连接状态 -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
        <!-- 本地数据库 -->
        <div class="bg-white dark:bg-slate-800/60 rounded-2xl border border-slate-200/60 dark:border-slate-700/50 p-5 shadow-sm">
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center gap-2">
              <DatabaseOutlined class="text-blue-500 text-lg" />
              <span class="font-semibold text-slate-700 dark:text-slate-200">本地数据库</span>
            </div>
            <span :class="localDb.connected ? 'bg-emerald-50 text-emerald-600 border-emerald-200 dark:bg-emerald-900/20 dark:text-emerald-400' : 'bg-red-50 text-red-600 border-red-200'"
              class="text-xs px-2.5 py-1 rounded-full border font-medium">
              {{ localDb.connected ? '✅ 已连接' : '❌ 未连接' }}
            </span>
          </div>
          <div class="space-y-2.5 text-sm">
            <div class="flex justify-between">
              <span class="text-slate-500">连接地址</span>
              <span class="text-slate-700 dark:text-slate-300 font-mono text-xs">{{ localDb.url || '—' }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-slate-500">版本</span>
              <span class="text-slate-700 dark:text-slate-300 text-xs">{{ localDb.version || '—' }}</span>
            </div>
            <div v-if="localDb.tables" class="pt-2 border-t border-slate-100 dark:border-slate-700 space-y-1.5">
              <div class="text-xs text-slate-400 uppercase tracking-wider">表数据量</div>
              <div v-for="(count, name) in localDb.tables" :key="name" class="flex justify-between">
                <span class="text-slate-500 font-mono">{{ name }}</span>
                <span class="text-slate-700 dark:text-slate-300 font-semibold">{{ count }} 条</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 远端数据库 -->
        <div class="bg-white dark:bg-slate-800/60 rounded-2xl border border-slate-200/60 dark:border-slate-700/50 p-5 shadow-sm">
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center gap-2">
              <CloudServerOutlined class="text-indigo-500 text-lg" />
              <span class="font-semibold text-slate-700 dark:text-slate-200">远端数据库 (DHC)</span>
            </div>
            <div class="flex items-center gap-2">
              <span :class="remoteDb.connected ? 'bg-emerald-50 text-emerald-600 border-emerald-200 dark:bg-emerald-900/20 dark:text-emerald-400' : 'bg-amber-50 text-amber-600 border-amber-200 dark:bg-amber-900/20 dark:text-amber-400'"
                class="text-xs px-2.5 py-1 rounded-full border font-medium">
                {{ remoteDb.connected ? '✅ 已连接' : '⚠️ 未连接' }}
              </span>
              <a-button size="small" type="text" @click="showConfigModal = true" class="!text-blue-500">
                <template #icon><EditOutlined /></template>
                编辑
              </a-button>
            </div>
          </div>
          <div class="space-y-2.5 text-sm">
            <div class="flex justify-between">
              <span class="text-slate-500">主机</span>
              <span class="text-slate-700 dark:text-slate-300 font-mono text-xs">{{ dbConfig.remote_host }}:{{ dbConfig.remote_port }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-slate-500">数据库</span>
              <span class="text-slate-700 dark:text-slate-300 font-mono text-xs">{{ dbConfig.remote_database }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-slate-500">用户名</span>
              <span class="text-slate-700 dark:text-slate-300 font-mono text-xs">{{ dbConfig.remote_username }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-slate-500">密码</span>
              <span class="text-slate-700 dark:text-slate-300 text-xs">{{ dbConfig.remote_password_set ? '●●●●●●●● (已设置)' : '未设置' }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-slate-500">版本</span>
              <span class="text-slate-700 dark:text-slate-300 text-xs">{{ remoteDb.version || '—' }}</span>
            </div>
            <div v-if="!remoteDb.connected" class="pt-2 border-t border-slate-100 dark:border-slate-700">
              <div class="text-xs text-amber-600 bg-amber-50 dark:bg-amber-900/20 p-2 rounded-lg">
                💡 远端未连接是正常的 — 需要在医院内网环境才能访问
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 同步控制面板 -->
      <div class="bg-white dark:bg-slate-800/60 rounded-2xl border border-slate-200/60 dark:border-slate-700/50 p-5 shadow-sm">
        <div class="flex items-center justify-between mb-4">
          <div class="flex items-center gap-2">
            <SyncOutlined class="text-blue-500 text-lg" :spin="syncState.is_running" />
            <span class="font-semibold text-slate-700 dark:text-slate-200">数据同步</span>
          </div>
          <div class="flex gap-2">
            <a-date-picker v-model:value="syncDate" placeholder="同步日期" size="small" class="!w-36" />
            <a-button type="primary" size="small" @click="triggerSync" :loading="syncState.is_running"
              :disabled="!remoteDb.connected" class="!rounded-lg">
              <template #icon><SyncOutlined /></template>
              立即同步
            </a-button>
            <a-button size="small" @click="refreshStatus" class="!rounded-lg">
              <template #icon><ReloadOutlined /></template>
              刷新
            </a-button>
          </div>
        </div>

        <!-- 同步状态信息 -->
        <div class="grid grid-cols-4 gap-4 mb-4">
          <div class="text-center p-3 bg-slate-50 dark:bg-slate-700/30 rounded-xl">
            <div class="text-2xl font-bold text-slate-700 dark:text-slate-200">{{ syncState.total_records_synced }}</div>
            <div class="text-xs text-slate-500 mt-1">已同步记录数</div>
          </div>
          <div class="text-center p-3 bg-slate-50 dark:bg-slate-700/30 rounded-xl">
            <div class="text-sm font-semibold" :class="syncStatusColor">{{ syncStatusLabel }}</div>
            <div class="text-xs text-slate-500 mt-1">同步状态</div>
          </div>
          <div class="text-center p-3 bg-slate-50 dark:bg-slate-700/30 rounded-xl">
            <div class="text-sm font-semibold text-slate-700 dark:text-slate-200">{{ syncState.last_sync_time || '—' }}</div>
            <div class="text-xs text-slate-500 mt-1">上次同步时间</div>
          </div>
          <div class="text-center p-3 bg-slate-50 dark:bg-slate-700/30 rounded-xl">
            <div class="text-sm font-semibold text-slate-700 dark:text-slate-200">{{ syncTables.length }}</div>
            <div class="text-xs text-slate-500 mt-1">可同步表</div>
          </div>
        </div>

        <!-- 可同步表列表 -->
        <div class="border-t border-slate-100 dark:border-slate-700 pt-4">
          <div class="text-xs text-slate-400 uppercase tracking-wider mb-3">同步表配置</div>
          <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
            <div v-for="t in syncTables" :key="t.name"
              class="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 dark:bg-slate-700/30 border border-slate-100 dark:border-slate-600/30">
              <div>
                <span class="text-sm font-medium text-slate-700 dark:text-slate-200">{{ t.label }}</span>
                <span class="text-xs text-slate-400 ml-1 font-mono">{{ t.name }}</span>
              </div>
              <span class="text-xs text-slate-400 font-mono">{{ t.procedure }}</span>
            </div>
          </div>
        </div>

        <!-- 同步日志 -->
        <div v-if="syncState.logs && syncState.logs.length > 0" class="border-t border-slate-100 dark:border-slate-700 pt-4 mt-4">
          <div class="text-xs text-slate-400 uppercase tracking-wider mb-3">最近同步日志</div>
          <div class="space-y-2">
            <div v-for="(log, idx) in syncState.logs" :key="idx"
              class="flex items-center justify-between p-2.5 rounded-lg text-sm"
              :class="log.status === 'success' ? 'bg-emerald-50 dark:bg-emerald-900/10' : log.status === 'failed' ? 'bg-red-50 dark:bg-red-900/10' : 'bg-slate-50 dark:bg-slate-700/20'">
              <div class="flex items-center gap-2">
                <span v-if="log.status === 'success'" class="text-emerald-500">✅</span>
                <span v-else-if="log.status === 'failed'" class="text-red-500">❌</span>
                <span v-else class="text-blue-500"><SyncOutlined spin /></span>
                <span class="font-medium text-slate-700 dark:text-slate-300">{{ log.table_name }}</span>
                <span class="text-slate-400 font-mono text-xs">{{ log.stored_procedure }}</span>
              </div>
              <div class="flex items-center gap-3">
                <span v-if="log.record_count > 0" class="text-emerald-600 font-semibold">{{ log.record_count }} 条</span>
                <span v-if="log.error_msg" class="text-red-500 text-xs max-w-[200px] truncate">{{ log.error_msg }}</span>
                <span class="text-xs text-slate-400">{{ log.finished_at || '' }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

    </div>

    <!-- ========== 远端连接编辑弹窗 ========== -->
    <a-modal
      v-model:open="showConfigModal"
      title="远端数据库连接配置"
      :confirm-loading="configSaving"
      @ok="saveConfig"
      ok-text="保存并测试"
      cancel-text="取消"
      :width="500"
    >
      <div class="space-y-4 pt-2">
        <div class="text-xs text-slate-400 mb-2">
          修改后点击「保存并测试」将自动测试连接，配置保存到服务端（Docker 容器重启不丢失）
        </div>
        <div>
          <label class="text-sm text-slate-600 dark:text-slate-400 block mb-1">主机地址</label>
          <a-input v-model:value="configForm.remote_host" placeholder="192.168.140.4" />
        </div>
        <div>
          <label class="text-sm text-slate-600 dark:text-slate-400 block mb-1">端口</label>
          <a-input v-model:value="configForm.remote_port" placeholder="5432" />
        </div>
        <div>
          <label class="text-sm text-slate-600 dark:text-slate-400 block mb-1">数据库名</label>
          <a-input v-model:value="configForm.remote_database" placeholder="dhc-app" />
        </div>
        <div>
          <label class="text-sm text-slate-600 dark:text-slate-400 block mb-1">用户名</label>
          <a-input v-model:value="configForm.remote_username" placeholder="Baidu" />
        </div>
        <div>
          <label class="text-sm text-slate-600 dark:text-slate-400 block mb-1">
            密码
            <span v-if="dbConfig.remote_password_set" class="text-xs text-emerald-500 ml-1">(已设置，留空则保持不变)</span>
          </label>
          <a-input-password v-model:value="configForm.remote_password" placeholder="输入密码" />
        </div>

        <!-- 连接测试结果 -->
        <div v-if="configTestResult" class="mt-3 p-3 rounded-lg text-sm"
          :class="configTestResult.connected ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-red-50 text-red-700 border border-red-200'">
          <div class="font-medium">{{ configTestResult.connected ? '✅ 连接成功' : '❌ 连接失败' }}</div>
          <div v-if="configTestResult.version" class="text-xs mt-1 opacity-70">{{ configTestResult.version }}</div>
          <div v-if="configTestResult.error" class="text-xs mt-1">{{ configTestResult.error }}</div>
        </div>
      </div>
    </a-modal>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import { message } from 'ant-design-vue'
import {
  SettingOutlined,
  DatabaseOutlined,
  CloudServerOutlined,
  SyncOutlined,
  ReloadOutlined,
  EditOutlined,
} from '@ant-design/icons-vue'

// ========== 状态 ==========
const localDb = ref<any>({})
const remoteDb = ref<any>({})
const syncState = ref<any>({ is_running: false, logs: [], total_records_synced: 0 })
const syncTables = ref<any[]>([])
const syncDate = ref<string | null>(null)
const dbConfig = ref<any>({})

// 编辑弹窗
const showConfigModal = ref(false)
const configSaving = ref(false)
const configTestResult = ref<any>(null)
const configForm = ref({
  remote_host: '',
  remote_port: '5432',
  remote_database: '',
  remote_username: '',
  remote_password: '',
})

// ========== 同步状态计算 ==========
const syncStatusLabel = computed(() => {
  switch (syncState.value.last_sync_status) {
    case 'success': return '✅ 同步成功'
    case 'partial': return '⚠️ 部分成功'
    case 'failed': return '❌ 同步失败'
    default: return '—— 未同步'
  }
})

const syncStatusColor = computed(() => {
  switch (syncState.value.last_sync_status) {
    case 'success': return 'text-emerald-600 dark:text-emerald-400'
    case 'partial': return 'text-amber-600 dark:text-amber-400'
    case 'failed': return 'text-red-600 dark:text-red-400'
    default: return 'text-slate-400'
  }
})

// ========== API 调用 ==========
async function loadDbStatus() {
  try {
    const { data } = await axios.get('/api/system/db/status')
    localDb.value = data.local || {}
    remoteDb.value = data.remote || {}
  } catch (err) {
    console.error('获取数据库状态失败:', err)
  }
}

async function loadDbConfig() {
  try {
    const { data } = await axios.get('/api/system/db/config')
    dbConfig.value = data
    // 填充表单（密码字段留空）
    configForm.value = {
      remote_host: data.remote_host || '',
      remote_port: data.remote_port || '5432',
      remote_database: data.remote_database || '',
      remote_username: data.remote_username || '',
      remote_password: '',
    }
  } catch (err) {
    console.error('获取数据库配置失败:', err)
  }
}

async function saveConfig() {
  configSaving.value = true
  configTestResult.value = null
  try {
    const { data } = await axios.put('/api/system/db/config', configForm.value)
    configTestResult.value = data.connection
    if (data.connection?.connected) {
      message.success('连接配置已保存，远端数据库连接成功！')
      showConfigModal.value = false
      // 刷新所有状态
      await Promise.all([loadDbStatus(), loadDbConfig()])
    } else {
      message.warning('配置已保存，但远端连接失败（在医院内网才可连通）')
      // 仍然刷新配置展示
      await loadDbConfig()
    }
  } catch (err) {
    message.error('保存失败')
    console.error(err)
  } finally {
    configSaving.value = false
  }
}

async function loadSyncStatus() {
  try {
    const { data } = await axios.get('/api/system/sync/status')
    syncState.value = data
  } catch (err) {
    console.error('获取同步状态失败:', err)
  }
}

async function loadSyncTables() {
  try {
    const { data } = await axios.get('/api/system/sync/tables')
    syncTables.value = data.tables || []
  } catch (err) {
    console.error('获取同步表配置失败:', err)
  }
}

async function triggerSync() {
  try {
    const params: any = {}
    if (syncDate.value) params.sync_date = syncDate.value
    await axios.post('/api/system/sync/trigger', null, { params })

    // 轮询同步状态
    const poll = setInterval(async () => {
      await loadSyncStatus()
      if (!syncState.value.is_running) {
        clearInterval(poll)
        await loadDbStatus()
      }
    }, 1000)
  } catch (err) {
    console.error('触发同步失败:', err)
  }
}

async function refreshStatus() {
  await Promise.all([loadDbStatus(), loadSyncStatus()])
}

// ========== 初始化 ==========
onMounted(async () => {
  await Promise.all([loadDbStatus(), loadDbConfig(), loadSyncStatus(), loadSyncTables()])
})
</script>
