<template>
  <div class="flex flex-col h-full bg-white">
    <!-- Header -->
    <div class="px-5 py-4 border-b border-[#E5E7EB] flex items-center justify-between shrink-0">
      <h2 class="text-[14px] font-semibold text-slate-800 tracking-tight">
        连接配置
      </h2>
      <a-tooltip title="功能开发中">
        <button
          disabled
          class="text-[12px] font-medium text-slate-300 cursor-not-allowed transition-colors"
        >
          检测连通性
        </button>
      </a-tooltip>
    </div>

    <!-- Segmented Tabs (滑动滑块胶囊) -->
    <div class="px-5 py-3 shrink-0 relative">
      <div class="flex p-1 rounded-[8px] bg-slate-100/80 border border-slate-200/50 relative">
        <button 
          :class="['flex-1 py-1.5 rounded-[6px] text-[12px] font-medium transition-all duration-300 relative z-10', state.activeTab === 'pg_local' ? 'bg-white text-slate-800 shadow-[0_1px_4px_rgba(15,23,42,0.08)] ring-1 ring-slate-900/5' : 'text-slate-500 hover:text-slate-700']" 
          @click="state.activeTab = 'pg_local'"
        >
          本地库
        </button>
        <button 
          :class="['flex-1 py-1.5 rounded-[6px] text-[12px] font-medium transition-all duration-300 relative z-10', state.activeTab === 'pg_remote' ? 'bg-white text-slate-800 shadow-[0_1px_4px_rgba(15,23,42,0.08)] ring-1 ring-slate-900/5' : 'text-slate-500 hover:text-slate-700']" 
          @click="state.activeTab = 'pg_remote'"
        >
          前端 PG
        </button>
        <button 
          :class="['flex-1 py-1.5 rounded-[6px] text-[12px] font-medium transition-all duration-300 relative z-10', state.activeTab === 'mongo' ? 'bg-white text-slate-800 shadow-[0_1px_4px_rgba(15,23,42,0.08)] ring-1 ring-slate-900/5' : 'text-slate-500 hover:text-slate-700']" 
          @click="state.activeTab = 'mongo'"
        >
          Mongo 源
        </button>
      </div>
    </div>

    <!-- Form Area -->
    <div class="flex-1 overflow-y-auto custom-scrollbar px-6 pb-6 relative">
      <div class="space-y-5 animate-fade-in mt-2">
        <!-- Title and Status Line -->
        <div class="flex items-center justify-between pb-3 border-b border-slate-100/50">
          <span class="font-bold text-slate-800 text-[13px] tracking-tight">
            {{ state.activeTab === 'pg_local' ? '本地核心仓 (CDM)' : state.activeTab === 'pg_remote' ? '业务流水库 (PG)' : '病床文档库 (Mongo)' }}
          </span>
          <div
            v-if="state.activeTab !== 'pg_remote'"
            class="flex items-center gap-1.5 bg-emerald-50 w-fit px-2 py-0.5 rounded-full border border-emerald-100"
          >
            <span class="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            <span class="text-[10px] font-bold text-emerald-600 tracking-wide uppercase">Connected</span>
          </div>
          <div
            v-else
            class="flex items-center gap-1.5 bg-amber-50 w-fit px-2 py-0.5 rounded-full border border-amber-100"
          >
            <span class="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
            <span class="text-[10px] font-bold text-amber-600 tracking-wide uppercase">Testing</span>
          </div>
        </div>

        <!-- Unified Form Styling -->
        <div class="space-y-4">
          <template v-if="state.activeTab === 'pg_local'">
            <div class="space-y-1.5">
              <label class="text-[11px] font-medium text-slate-500 block">连接地址</label>
              <div class="bg-slate-50 rounded-md border border-slate-200 px-3 py-2 flex items-center justify-between">
                <span class="text-[12px] font-mono text-slate-500">127.0.0.1:5432</span>
                <button class="text-slate-400 hover:text-[#1890FF]">
                  <svg
                    class="w-3.5 h-3.5"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  ><path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                  /></svg>
                </button>
              </div>
            </div>
            <div class="space-y-1.5">
              <label class="text-[11px] font-medium text-slate-500 block">数据库名称</label>
              <a-input
                size="small"
                value="medqc_cdm"
                disabled
                class="!text-[12px] !font-mono !text-slate-500 !bg-slate-50 !border-slate-200 !shadow-none !py-1.5"
              />
            </div>
          </template>

          <template v-else-if="state.activeTab === 'pg_remote'">
            <!-- Similar minimalist forms -->
            <div class="space-y-1.5">
              <label class="text-[11px] font-medium text-slate-500 block">读库地址</label>
              <div class="flex gap-2">
                <a-input
                  size="small"
                  placeholder="192.168.x.x"
                  class="!text-[12px] !font-mono flex-1 !border-slate-200 !shadow-none text-slate-700 !py-1.5 focus:!border-[#1890FF] focus:!shadow-[0_0_0_2px_rgba(24,144,255,0.1)] hover:!border-[#1890FF]"
                />
                <a-input
                  size="small"
                  value="5432"
                  class="!text-[12px] !font-mono w-[65px] !border-slate-200 !shadow-none text-slate-700 text-center !py-1.5"
                />
              </div>
            </div>
            <div class="space-y-1.5">
              <label class="text-[11px] font-medium text-slate-500 block">数据库</label>
              <a-input
                size="small"
                placeholder="database_name"
                class="!text-[12px] !font-mono !border-slate-200 !shadow-none text-slate-700 !py-1.5 focus:!border-[#1890FF] focus:!shadow-[0_0_0_2px_rgba(24,144,255,0.1)]"
              />
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div class="space-y-1.5">
                <label class="text-[11px] font-medium text-slate-500 block">用户名</label>
                <a-input
                  size="small"
                  placeholder="db_user"
                  class="!text-[12px] !font-mono !border-slate-200 !shadow-none text-slate-700 !py-1.5 focus:!border-[#1890FF] focus:!shadow-[0_0_0_2px_rgba(24,144,255,0.1)]"
                />
              </div>
              <div class="space-y-1.5">
                <label class="text-[11px] font-medium text-slate-500 block">密码</label>
                <a-input-password
                  size="small"
                  placeholder="••••••••"
                  class="!text-[12px] !border-slate-200 !shadow-none text-slate-700 !py-1.5 focus:!border-[#1890FF] focus:!shadow-[0_0_0_2px_rgba(24,144,255,0.1)]"
                />
              </div>
            </div>
          </template>

          <template v-else-if="state.activeTab === 'mongo'">
            <div class="space-y-1.5">
              <label class="text-[11px] font-medium text-slate-500 block flex items-center justify-between">
                <span>连接字符串 URI</span>
                <span class="text-[10px] text-slate-400 font-normal">优先 secondary</span>
              </label>
              <!-- 代码块风格的输入框 -->
              <div class="relative group">
                <textarea
                  v-model="mongoUri"
                  rows="3"
                  class="w-full bg-[#1e293b] text-[#cdd6f4] font-mono text-[11px] p-3 rounded-[6px] border border-slate-700 focus:border-[#1890FF] focus:ring-1 focus:ring-[#1890FF] outline-none resize-none leading-relaxed transition-colors shadow-inner"
                  spellcheck="false"
                  placeholder="mongodb://user:***@host:port/db?tls=false"
                />
                <div class="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    class="bg-white/10 hover:bg-white/20 p-1.5 rounded text-white backdrop-blur-sm"
                    title="复制"
                  >
                    <svg
                      class="w-3 h-3"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    ><path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                    /></svg>
                  </button>
                </div>
              </div>
            </div>
            <div class="space-y-1.5">
              <label class="text-[11px] font-medium text-slate-500 block">指定集合空间</label>
              <a-input
                size="small"
                value="his_emr"
                class="!text-[12px] !font-mono !border-slate-200 !shadow-none text-slate-700 !py-1.5 focus:!border-[#1890FF] focus:!shadow-[0_0_0_2px_rgba(24,144,255,0.1)]"
              />
            </div>
          </template>

          <div
            v-if="state.activeTab !== 'pg_local'"
            class="pt-4"
          >
            <a-tooltip title="功能开发中">
              <button
                disabled
                class="w-full py-2 rounded-lg border border-slate-200 bg-slate-50 text-[12px] font-medium text-slate-400 cursor-not-allowed shadow-none"
              >
                验证并保存
              </button>
            </a-tooltip>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useDataSync } from '../../composables/useDataSync'

const { state } = useDataSync()
const mongoUri = ref('mongodb://user:***@host:port/db?tls=false')
</script>

<style scoped>
.animate-fade-in {
  animation: fadeIn 0.15s ease-out forwards;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(2px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
