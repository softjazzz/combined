<template>
  <div class="h-full bg-slate-50 flex overflow-hidden">
    <div class="flex-1 flex w-full max-w-[1440px] mx-auto p-6 gap-6">
      <!-- ========== 左侧：输入面板 ========== -->
      <div class="w-[420px] bg-white rounded-xl border border-slate-200/80 shadow-sm overflow-y-auto flex flex-col shrink-0">
        <!-- 诊断编码 -->
        <div class="p-6 border-b border-slate-100">
          <h3 class="text-[13px] font-bold text-slate-800 mb-4 flex items-center gap-2">
            <svg
              class="w-4 h-4 text-indigo-500"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            ><path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
            /></svg>
            诊断编码提取
          </h3>
          <div class="space-y-2">
            <div
              v-for="(_, index) in formData.zdList"
              :key="'zd-' + index"
              class="relative flex items-center rounded-lg p-1.5 group transition-colors"
              :class="index === 0 ? 'bg-indigo-50/50 border border-indigo-100' : 'bg-slate-50/80 border border-slate-100 hover:bg-slate-100/80'"
            >
              <div
                v-if="index === 0"
                class="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-3/4 bg-indigo-500 rounded-r-full"
              />
              <span
                class="w-14 text-center text-[11px] shrink-0"
                :class="index === 0 ? 'font-bold text-indigo-600' : 'font-medium text-slate-500'"
              >
                {{ index === 0 ? '主诊断' : `其他 ${index}` }}
              </span>
              <input
                v-model="formData.zdList[index]"
                type="text"
                class="flex-1 bg-white rounded py-1.5 px-3 text-[13px] font-mono text-slate-800 outline-none shadow-sm transition-all"
                :class="index === 0 ? 'border border-indigo-100/50 font-semibold focus:ring-1 focus:ring-indigo-400' : 'border border-slate-200/60 focus:ring-1 focus:ring-blue-400'"
                placeholder="输入 ICD-10 编码"
                @keyup.enter="addDiagnosis"
              >
              <button
                v-if="index > 0"
                class="w-8 flex justify-center text-slate-300 opacity-0 group-hover:opacity-100 hover:text-rose-500 transition-all cursor-pointer"
                @click="formData.zdList.splice(index, 1)"
              >
                <svg
                  class="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                ><path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                /></svg>
              </button>
            </div>
            <button
              class="ghost-add-btn"
              @click="addDiagnosis"
            >
              <svg
                class="w-3.5 h-3.5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              ><path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M12 4v16m8-8H4"
              /></svg>
              增加其他诊断
            </button>
          </div>
        </div>

        <!-- 手术操作编码 -->
        <div class="p-6 border-b border-slate-100">
          <h3 class="text-[13px] font-bold text-slate-800 mb-4 flex items-center gap-2">
            <svg
              class="w-4 h-4 text-sky-500"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            ><path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
            /><path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
            /></svg>
            手术操作编码
          </h3>
          <div class="space-y-2">
            <div
              v-for="(_, index) in formData.ssList"
              :key="'ss-' + index"
              class="flex items-center bg-slate-50/80 border border-slate-100 rounded-lg p-1.5 group hover:bg-slate-100/80 transition-colors"
            >
              <span class="w-14 text-center text-[11px] font-medium text-slate-500 shrink-0">{{ index === 0 ? '主手术' : `其他 ${index}` }}</span>
              <input
                v-model="formData.ssList[index]"
                type="text"
                class="flex-1 bg-white border border-slate-200/60 rounded py-1.5 px-3 text-[13px] font-mono text-slate-700 outline-none focus:ring-1 focus:ring-blue-400 shadow-sm"
                placeholder="输入手术操作编码"
                @keyup.enter="addProcedure"
              >
              <button
                v-if="formData.ssList.length > 1 || (formData.ssList.length === 1 && formData.ssList[0])"
                class="w-8 flex justify-center text-slate-300 opacity-0 group-hover:opacity-100 hover:text-rose-500 transition-all cursor-pointer"
                @click="formData.ssList.splice(index, 1)"
              >
                <svg
                  class="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                ><path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                /></svg>
              </button>
            </div>
            <button
              class="ghost-add-btn"
              @click="addProcedure"
            >
              <svg
                class="w-3.5 h-3.5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              ><path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M12 4v16m8-8H4"
              /></svg>
              增加手术操作
            </button>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="p-6 flex gap-3">
          <button
            class="flex-1 h-11 bg-gradient-to-r from-emerald-600 to-emerald-500 text-white font-bold text-[14px] rounded-lg shadow-[0_4px_14px_rgba(5,150,105,0.3)] hover:shadow-[0_6px_20px_rgba(5,150,105,0.4)] hover:from-emerald-500 hover:to-emerald-400 transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
            :disabled="grouping"
            @click="doGrouping"
          >
            <svg
              v-if="!grouping"
              class="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            ><path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M13 10V3L4 14h7v7l9-11h-7z"
            /></svg>
            <svg
              v-else
              class="w-4 h-4 animate-spin"
              fill="none"
              viewBox="0 0 24 24"
            ><circle
              class="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              stroke-width="4"
            /><path
              class="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            /></svg>
            {{ grouping ? '分组中...' : 'DIP 分组' }}
          </button>
          <button
            class="h-11 px-4 border border-slate-200 rounded-lg text-[13px] text-slate-600 hover:bg-slate-50 transition-colors cursor-pointer"
            @click="resetForm"
          >
            重置
          </button>
          <button
            class="h-11 px-4 border border-slate-200 rounded-lg text-[13px] text-slate-600 hover:bg-slate-50 transition-colors cursor-pointer"
            @click="fillTestCase"
          >
            测试
          </button>
        </div>
      </div>

      <!-- ========== 右侧：结果区域 ========== -->
      <div class="flex-1 flex flex-col gap-5 overflow-y-auto">
        <!-- 空状态 -->
        <div
          v-if="!result && !grouping"
          class="flex-1 flex flex-col items-center justify-center text-slate-400"
        >
          <div class="w-20 h-20 rounded-full bg-gradient-to-br from-emerald-50 to-teal-50 flex items-center justify-center mb-5">
            <svg
              class="w-9 h-9 text-emerald-300"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            ><path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="1.5"
              d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
            /></svg>
          </div>
          <h3 class="text-lg font-semibold text-slate-500 mb-1">
            等待分组
          </h3>
          <p class="text-[13px] text-slate-400">
            输入病案编码，点击「DIP 分组」开始匹配
          </p>
        </div>

        <!-- 加载中 -->
        <div
          v-else-if="grouping"
          class="flex-1 flex flex-col items-center justify-center text-slate-400"
        >
          <svg
            class="w-10 h-10 animate-spin text-emerald-500 mb-4"
            fill="none"
            viewBox="0 0 24 24"
          ><circle
            class="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            stroke-width="4"
          /><path
            class="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          /></svg>
          <p class="text-[13px]">
            病种匹配中...
          </p>
        </div>

        <!-- 分组结果 -->
        <template v-else-if="result">
          <!-- DIP 分组结果卡片 -->
          <div class="bg-white rounded-xl border border-slate-200/80 shadow-[0_4px_20px_rgba(0,0,0,0.03)] p-8 relative overflow-hidden">
            <div
              class="absolute right-0 top-0 w-64 h-64 rounded-full blur-3xl -translate-y-1/2 translate-x-1/3 pointer-events-none"
              :class="result.status === '分组成功' ? 'bg-emerald-50/50' : 'bg-rose-50/50'"
            />

            <div class="flex items-center gap-2 mb-8">
              <span
                v-if="result.status === '分组成功'"
                class="flex items-center justify-center w-6 h-6 rounded-full bg-emerald-100 text-emerald-600"
              >
                <svg
                  class="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                ><path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="3"
                  d="M5 13l4 4L19 7"
                /></svg>
              </span>
              <span
                v-else
                class="flex items-center justify-center w-6 h-6 rounded-full bg-rose-100 text-rose-600"
              >
                <svg
                  class="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                ><path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="3"
                  d="M6 18L18 6M6 6l12 12"
                /></svg>
              </span>
              <h2 class="text-[16px] font-bold text-slate-800">
                {{ result.status === '分组成功' ? 'DIP 病种匹配成功' : '未能入组' }}
              </h2>
            </div>

            <div
              v-if="result.status === '分组成功'"
              class="relative z-10"
            >
              <!-- DIP 编码大字展示 -->
              <div class="text-center mb-8">
                <div class="text-[11px] font-bold text-slate-400 tracking-widest uppercase mb-3">
                  DIP Code
                </div>
                <div class="inline-block px-10 py-5 rounded-2xl border-2 border-emerald-400 bg-emerald-500 text-white shadow-[0_8px_30px_rgba(16,185,129,0.3)]">
                  <div class="text-3xl font-black font-mono tracking-wide">
                    {{ result.dipCode }}
                  </div>
                </div>
              </div>

              <!-- 匹配详情网格 -->
              <div class="grid grid-cols-1 gap-2">
                <div class="flex items-start gap-3 px-4 py-3 bg-slate-50 rounded-lg">
                  <span class="text-[11px] text-slate-400 font-medium w-20 shrink-0 pt-0.5">病种名称</span>
                  <span class="text-[13px] text-slate-800 font-semibold">{{ result.dipName }}</span>
                </div>
                <div class="flex items-start gap-3 px-4 py-3 bg-slate-50 rounded-lg">
                  <span class="text-[11px] text-slate-400 font-medium w-20 shrink-0 pt-0.5">主诊断</span>
                  <span class="text-[13px] text-slate-700 font-mono">{{ result.primaryZd }} <span class="font-sans text-slate-500">{{ result.primaryZdName }}</span></span>
                </div>
                <div
                  v-if="result.matchedSs"
                  class="flex items-start gap-3 px-4 py-3 bg-slate-50 rounded-lg"
                >
                  <span class="text-[11px] text-slate-400 font-medium w-20 shrink-0 pt-0.5">匹配手术</span>
                  <span class="text-[13px] text-slate-700 font-mono">{{ result.matchedSs }}</span>
                </div>
                <div
                  v-if="result.matchedRelSs"
                  class="flex items-start gap-3 px-4 py-3 bg-slate-50 rounded-lg"
                >
                  <span class="text-[11px] text-slate-400 font-medium w-20 shrink-0 pt-0.5">相关手术</span>
                  <span class="text-[13px] text-slate-700 font-mono">{{ result.matchedRelSs }}</span>
                </div>
                <div class="flex items-center gap-3 px-4 py-3 bg-slate-50 rounded-lg">
                  <span class="text-[11px] text-slate-400 font-medium w-20 shrink-0">匹配方式</span>
                  <span
                    class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[12px] font-bold"
                    :class="matchTypeStyle"
                  >
                    <span
                      class="w-1 h-1 rounded-full"
                      :class="matchTypeDot"
                    />
                    {{ result.matchType }}
                  </span>
                </div>
              </div>
            </div>

            <div
              v-else
              class="text-slate-500 text-[14px] py-4"
            >
              <p
                v-for="(msg, idx) in result.messages"
                :key="idx"
              >
                {{ msg }}
              </p>
            </div>
          </div>

          <!-- 分组过程 -->
          <div class="flex-1 bg-white rounded-xl border border-slate-200/80 shadow-sm p-6 flex flex-col overflow-hidden">
            <h3 class="text-[13px] font-bold text-slate-800 mb-5 flex items-center gap-2 uppercase tracking-wider">
              <svg
                class="w-4 h-4 text-slate-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              ><path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
              /></svg>
              分组过程 (Execution Trace)
            </h3>
            <div class="flex-1 overflow-y-auto space-y-0 pl-2">
              <div
                v-for="(msg, idx) in result.messages"
                :key="idx"
                class="relative pl-6 pb-5 last:pb-0"
                :class="idx < result.messages.length - 1 ? 'border-l-2 border-slate-200' : 'border-l-2 border-transparent'"
              >
                <span
                  class="absolute top-1 w-2.5 h-2.5 rounded-full ring-4 ring-white"
                  :class="idx === result.messages.length - 1
                    ? (result.status === '分组成功' ? 'left-[-6px] bg-emerald-500 shadow-sm' : 'left-[-6px] bg-rose-500 shadow-sm')
                    : idx === 0 ? 'left-[-5px] bg-slate-400' : 'left-[-6px] bg-blue-500 shadow-sm'"
                />
                <div
                  class="text-[13px] font-medium"
                  :class="idx === result.messages.length - 1 ? 'text-slate-800 font-bold' : 'text-slate-700'"
                >
                  {{ msg }}
                </div>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { message } from 'ant-design-vue'
import {
  performDipGrouping,
  getDipSchemeInfo,
  type DipGrouperResult,
} from './dipGrouper'

const schemeInfo = getDipSchemeInfo()

const formData = reactive({
  zdList: [''] as string[],
  ssList: [''] as string[],
})

const grouping = ref(false)
const result = ref<DipGrouperResult | null>(null)

const matchTypeStyle = computed(() => {
  switch (result.value?.matchType) {
    case '诊断+手术+相关手术': return 'bg-purple-50 text-purple-700 border border-purple-200'
    case '诊断+手术': return 'bg-blue-50 text-blue-700 border border-blue-200'
    case '纯诊断': return 'bg-emerald-50 text-emerald-700 border border-emerald-200'
    default: return 'bg-slate-50 text-slate-700 border border-slate-200'
  }
})

const matchTypeDot = computed(() => {
  switch (result.value?.matchType) {
    case '诊断+手术+相关手术': return 'bg-purple-500'
    case '诊断+手术': return 'bg-blue-500'
    case '纯诊断': return 'bg-emerald-500'
    default: return 'bg-slate-500'
  }
})

function addDiagnosis() { formData.zdList.push('') }
function addProcedure() { formData.ssList.push('') }

function resetForm() {
  formData.zdList = ['']
  formData.ssList = ['']
  result.value = null
}

function fillTestCase() {
  formData.zdList = ['K80.1', 'K83.1']
  formData.ssList = ['51.2300']
  result.value = null
  message.success('已填入测试用例：胆囊结石 + 腹腔镜胆囊切除')
}

function doGrouping() {
  const zdList = formData.zdList.filter(z => z.trim())
  const ssList = formData.ssList.filter(s => s.trim())
  if (zdList.length === 0) { message.warning('请至少输入一个诊断编码'); return }

  grouping.value = true
  result.value = null
  setTimeout(() => {
    try {
      result.value = performDipGrouping({ zdList, ssList })
      if (result.value.status === '分组成功') {
        message.success(`匹配成功: ${result.value.dipCode}`)
      } else {
        message.warning('未入组')
      }
    } catch (err) {
      message.error('分组失败: ' + (err instanceof Error ? err.message : String(err)))
    } finally {
      grouping.value = false
    }
  }, 100)
}
</script>

<style scoped>
.ghost-add-btn {
  @apply w-full mt-2 py-2 border border-dashed border-slate-300 rounded-lg text-xs font-medium text-slate-500
    hover:text-emerald-600 hover:border-emerald-400 hover:bg-emerald-50 transition-all cursor-pointer
    flex items-center justify-center gap-1.5;
}
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #d4d4d8; border-radius: 3px; }
</style>
