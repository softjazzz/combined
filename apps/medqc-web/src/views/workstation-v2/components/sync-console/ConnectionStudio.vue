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
      </div>
    </div>

    <div class="flex-1 overflow-y-auto custom-scrollbar px-5 pb-5">
      <div
        v-if="state.activeTab === 'pg_remote'"
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
          <label class="text-[12px] text-slate-600 block mb-1">主机地址</label>
          <input
            v-model="state.pgConnectionForm.remote_host"
            type="text"
            :disabled="isReadonly"
            class="w-full px-3 py-1.5 text-[13px] font-mono bg-white border border-slate-200/80 rounded-[8px] focus:border-[#1677FF] focus:ring-[3px] focus:ring-[#1677FF]/10 outline-none transition-all text-slate-700 disabled:bg-slate-50 disabled:text-slate-400"
          >
        </div>

        <div>
          <label class="text-[12px] text-slate-600 block mb-1">端口</label>
          <input
            v-model="state.pgConnectionForm.remote_port"
            type="number"
            :min="1"
            :max="65535"
            :disabled="isReadonly"
            class="w-full px-3 py-1.5 text-[13px] font-mono bg-white border border-slate-200/80 rounded-[8px] focus:border-[#1677FF] focus:ring-[3px] focus:ring-[#1677FF]/10 outline-none transition-all text-slate-700 disabled:bg-slate-50 disabled:text-slate-400"
          >
        </div>

        <div>
          <label class="text-[12px] text-slate-600 block mb-1">数据库名</label>
          <input
            v-model="state.pgConnectionForm.remote_database"
            type="text"
            :disabled="isReadonly"
            class="w-full px-3 py-1.5 text-[13px] font-mono bg-white border border-slate-200/80 rounded-[8px] focus:border-[#1677FF] focus:ring-[3px] focus:ring-[#1677FF]/10 outline-none transition-all text-slate-700 disabled:bg-slate-50 disabled:text-slate-400"
          >
        </div>

        <div>
          <label class="text-[12px] text-slate-600 block mb-1">用户名</label>
          <input
            v-model="state.pgConnectionForm.remote_username"
            type="text"
            :disabled="isReadonly"
            class="w-full px-3 py-1.5 text-[13px] font-mono bg-white border border-slate-200/80 rounded-[8px] focus:border-[#1677FF] focus:ring-[3px] focus:ring-[#1677FF]/10 outline-none transition-all text-slate-700 disabled:bg-slate-50 disabled:text-slate-400"
          >
        </div>

        <div>
          <label class="text-[12px] text-slate-600 block mb-1">密码（留空保持不变）</label>
          <input
            v-model="state.pgConnectionForm.remote_password"
            type="password"
            :disabled="isReadonly"
            class="w-full px-3 py-1.5 text-[13px] font-mono bg-white border border-slate-200/80 rounded-[8px] focus:border-[#1677FF] focus:ring-[3px] focus:ring-[#1677FF]/10 outline-none transition-all text-slate-700 disabled:bg-slate-50 disabled:text-slate-400"
          >
          <div class="text-[11px] text-slate-400 mt-1">
            当前密码状态：{{ state.pgConnectionForm.remote_password_set ? '已设置' : '未设置' }}
          </div>
        </div>

        <div class="pt-2">
          <button
            class="w-full px-4 py-2 mt-1 rounded-lg text-[13px] font-semibold text-white transition-all shadow-[0_2px_8px_rgba(59,130,246,0.25)] flex items-center justify-center gap-2"
            :class="
              isReadonly || state.isSavingPgConnection
                ? 'bg-slate-300 shadow-none cursor-not-allowed text-slate-100'
                : 'bg-gradient-to-r from-[#1890FF] to-[#40A9FF] hover:from-[#40A9FF] hover:to-[#69C0FF] hover:shadow-[0_4px_12px_rgba(59,130,246,0.35)] active:scale-[0.98]'
            "
            :disabled="isReadonly || state.isSavingPgConnection"
            @click="handleSavePg"
          >
            <span v-if="state.isSavingPgConnection">保存中...</span>
            <span v-else>保存配置</span>
          </button>
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
import { onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { useDataSync } from '../../composables/useDataSync'

const { state, isReadonly, testActiveConnection, savePgConnection } = useDataSync()

onMounted(() => {
  state.activeTab = 'pg_remote'
})

const tabClass = (tab: 'pg_remote' | 'pg_local') => [
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
