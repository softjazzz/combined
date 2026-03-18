<template>
  <div class="h-full bg-slate-50 flex overflow-hidden">
    <div class="flex-1 flex w-full max-w-[1440px] mx-auto p-6 gap-6">

      <!-- ========== 左侧：输入面板 ========== -->
      <div class="w-[420px] bg-white rounded-xl border border-slate-200/80 shadow-sm overflow-y-auto flex flex-col shrink-0">

        <!-- 患者病案特征 -->
        <div class="px-5 py-3.5 border-b border-slate-100">
          <h3 class="text-[13px] font-bold text-slate-800 mb-3 flex items-center gap-2">
            <svg class="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>
            患者病案特征
          </h3>
          <div class="grid grid-cols-2 gap-2.5">
            <div class="ghost-field">
              <div class="ghost-label">性别</div>
              <select v-model="formData.gender" class="ghost-select">
                <option value="1">男</option>
                <option value="2">女</option>
              </select>
            </div>
            <div class="ghost-field">
              <div class="ghost-label">年龄</div>
              <input v-model.number="formData.age" type="number" class="ghost-input font-mono font-semibold" placeholder="岁">
            </div>
            <div class="ghost-field">
              <div class="ghost-label">住院天数</div>
              <input v-model.number="formData.days" type="number" class="ghost-input font-mono font-semibold" placeholder="天">
            </div>
            <div class="ghost-field">
              <div class="ghost-label">离院方式</div>
              <select v-model="formData.leavingType" class="ghost-select">
                <option value="1">医嘱离院</option>
                <option value="5">死亡</option>
                <option value="2">医嘱转院</option>
                <option value="3">医嘱转社区</option>
                <option value="4">非医嘱离院</option>
              </select>
            </div>
          </div>
        </div>

        <!-- 诊断编码 -->
        <div class="px-5 py-3.5 border-b border-slate-100">
          <h3 class="text-[13px] font-bold text-slate-800 mb-3 flex items-center gap-2">
            <svg class="w-4 h-4 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" /></svg>
            诊断编码提取
          </h3>
          <div class="space-y-2">
            <div
              v-for="(_, index) in formData.zdList"
              :key="'zd-' + index"
              class="relative flex items-center rounded-lg p-1.5 group transition-colors"
              :class="index === 0
                ? 'bg-indigo-50/50 border border-indigo-100'
                : 'bg-slate-50/80 border border-slate-100 hover:bg-slate-100/80'"
            >
              <!-- 主诊断左侧竖线 -->
              <div v-if="index === 0" class="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-3/4 bg-indigo-500 rounded-r-full" />
              <span
                class="w-14 text-center text-[11px] font-bold shrink-0"
                :class="index === 0 ? 'text-indigo-600' : 'text-slate-500 font-medium'"
              >
                {{ index === 0 ? '主诊断' : `其他 ${index}` }}
              </span>
              <input
                v-model="formData.zdList[index]"
                type="text"
                class="flex-1 bg-white rounded py-1.5 px-3 text-[13px] font-mono text-slate-800 outline-none shadow-sm transition-all"
                :class="index === 0
                  ? 'border border-indigo-100/50 font-semibold focus:ring-1 focus:ring-indigo-400'
                  : 'border border-slate-200/60 focus:ring-1 focus:ring-blue-400'"
                placeholder="输入 ICD-10 编码"
                @keyup.enter="addDiagnosis"
              >
              <button
                v-if="index > 0"
                class="w-8 flex justify-center text-slate-300 opacity-0 group-hover:opacity-100 hover:text-rose-500 transition-all cursor-pointer"
                @click="formData.zdList.splice(index, 1)"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
              </button>
            </div>
            <button class="ghost-add-btn" @click="addDiagnosis">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
              增加其他诊断
            </button>
          </div>
        </div>

        <!-- 手术操作编码 -->
        <div class="px-5 py-3.5 border-b border-slate-100">
          <h3 class="text-[13px] font-bold text-slate-800 mb-3 flex items-center gap-2">
            <svg class="w-4 h-4 text-sky-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
            手术操作编码
          </h3>
          <div class="space-y-2">
            <div
              v-for="(_, index) in formData.ssList"
              :key="'ss-' + index"
              class="flex items-center bg-slate-50/80 border border-slate-100 rounded-lg p-1.5 group hover:bg-slate-100/80 transition-colors"
            >
              <span class="w-14 text-center text-[11px] font-medium text-slate-500 shrink-0">
                {{ index === 0 ? '主手术' : `其他 ${index}` }}
              </span>
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
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
              </button>
            </div>
            <button class="ghost-add-btn" @click="addProcedure">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
              增加手术操作
            </button>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="px-5 py-3.5 flex gap-3">
          <button
            class="flex-1 h-11 bg-gradient-to-r from-blue-600 to-blue-500 text-white font-bold text-[14px] rounded-lg shadow-[0_4px_14px_rgba(37,99,235,0.3)] hover:shadow-[0_6px_20px_rgba(37,99,235,0.4)] hover:from-blue-500 hover:to-blue-400 transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
            :disabled="grouping"
            @click="doGrouping"
          >
            <svg v-if="!grouping" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
            <svg v-else class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" /><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
            {{ grouping ? '分组中...' : 'DRG 分组' }}
          </button>
          <button class="h-11 px-4 border border-slate-200 rounded-lg text-[13px] text-slate-600 hover:bg-slate-50 transition-colors cursor-pointer" @click="resetForm">重置</button>
          <button class="h-11 px-4 border border-slate-200 rounded-lg text-[13px] text-slate-600 hover:bg-slate-50 transition-colors cursor-pointer" @click="fillTestCase">测试</button>
        </div>
      </div>

      <!-- ========== 右侧：结果区域 ========== -->
      <div class="flex-1 flex flex-col gap-5 overflow-y-auto">

        <!-- 空状态 -->
        <div v-if="!result && !grouping" class="flex-1 flex flex-col items-center justify-center text-slate-400">
          <div class="w-20 h-20 rounded-full bg-gradient-to-br from-blue-50 to-indigo-50 flex items-center justify-center mb-5">
            <svg class="w-9 h-9 text-blue-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" /></svg>
          </div>
          <h3 class="text-lg font-semibold text-slate-500 mb-1">等待分组</h3>
          <p class="text-[13px] text-slate-400">输入病案信息，点击「DRG 分组」开始</p>
        </div>

        <!-- 加载中 -->
        <div v-else-if="grouping" class="flex-1 flex flex-col items-center justify-center text-slate-400">
          <svg class="w-10 h-10 animate-spin text-blue-500 mb-4" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" /><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
          <p class="text-[13px]">分组计算中...</p>
        </div>

        <!-- 分组结果 -->
        <template v-else-if="result">

          <!-- 分组结果（Pipeline） -->
          <div class="bg-white rounded-xl border border-slate-200/80 shadow-[0_4px_20px_rgba(0,0,0,0.03)] p-8 relative overflow-hidden">
            <!-- 背景光晕 -->
            <div class="absolute right-0 top-0 w-64 h-64 rounded-full blur-3xl -translate-y-1/2 translate-x-1/3 pointer-events-none"
              :class="result.status === '分组成功' ? 'bg-emerald-50/50' : 'bg-rose-50/50'" />

            <div class="flex items-center gap-2 mb-10">
              <span v-if="result.status === '分组成功'"
                class="flex items-center justify-center w-6 h-6 rounded-full bg-emerald-100 text-emerald-600">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" /></svg>
              </span>
              <span v-else class="flex items-center justify-center w-6 h-6 rounded-full bg-rose-100 text-rose-600">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M6 18L18 6M6 6l12 12" /></svg>
              </span>
              <h2 class="text-[16px] font-bold text-slate-800">
                {{ result.status === '分组成功' ? 'DRG 分组成功' : '未能入组' }}
              </h2>
            </div>

            <!-- MDC → ADRG → DRG 管线 -->
            <div v-if="result.status === '分组成功'" class="flex items-center justify-center gap-4 relative z-10 py-4">
              <!-- MDC -->
              <div class="flex flex-col items-center group cursor-default">
                <div class="text-[11px] font-bold text-slate-400 mb-2 tracking-widest uppercase">MDC</div>
                <div class="w-16 h-16 rounded-2xl border-2 border-slate-200 bg-slate-50 flex items-center justify-center text-2xl font-black text-slate-700 font-mono shadow-sm group-hover:border-blue-400 transition-colors">
                  {{ result.mdc }}
                </div>
                <div class="text-[12px] font-medium text-slate-500 mt-3 text-center max-w-[120px] leading-snug">{{ mdcName }}</div>
              </div>

              <!-- 箭头 -->
              <div class="pipe-arrow" />

              <!-- ADRG -->
              <div class="flex flex-col items-center group cursor-default">
                <div class="text-[11px] font-bold text-slate-400 mb-2 tracking-widest uppercase">ADRG</div>
                <div class="w-20 h-16 rounded-2xl border-2 border-blue-200 bg-blue-50 flex items-center justify-center text-2xl font-black text-blue-700 font-mono shadow-sm group-hover:border-blue-500 transition-colors">
                  {{ result.adrg }}
                </div>
              </div>

              <!-- 箭头 -->
              <div class="pipe-arrow" />

              <!-- DRG (放大高亮) -->
              <div class="flex flex-col items-center transform scale-110 -translate-y-2">
                <div class="text-[12px] font-black text-emerald-600 mb-2 tracking-widest uppercase">DRG Result</div>
                <div class="px-8 h-20 rounded-2xl border-2 border-emerald-400 bg-emerald-500 flex items-center justify-center text-4xl font-black text-white font-mono shadow-[0_8px_30px_rgba(16,185,129,0.3)]">
                  {{ result.drg }}
                </div>
                <!-- DRG 名称 -->
                <div v-if="result.drgName" class="text-[13px] font-bold text-slate-800 mt-4 text-center max-w-[220px] leading-snug">
                  {{ result.drgName }}
                </div>
                <!-- RW 权重 -->
                <div v-if="result.rw" class="mt-2 inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-amber-50 border border-amber-200">
                  <span class="text-[11px] text-amber-600 font-medium">RW</span>
                  <span class="text-[15px] font-black text-amber-700 font-mono">{{ result.rw }}</span>
                </div>
              </div>
            </div>

            <!-- 未入组时的消息 -->
            <div v-else class="text-slate-500 text-[14px] py-4">
              <p v-for="(msg, idx) in result.messages" :key="idx">{{ msg }}</p>
            </div>
          </div>

          <!-- 分组过程 -->
          <div class="flex-1 bg-white rounded-xl border border-slate-200/80 shadow-sm p-6 flex flex-col overflow-hidden">
            <h3 class="text-[13px] font-bold text-slate-800 mb-5 flex items-center gap-2 uppercase tracking-wider">
              <svg class="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
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
                <div class="text-[13px] font-medium" :class="idx === result.messages.length - 1 ? 'text-slate-800 font-bold' : 'text-slate-700'">
                  {{ msg }}
                </div>
              </div>
            </div>
          </div>

          <!-- 质控提醒 -->
          <div v-if="result.qcMessages.length > 0" class="bg-amber-50 rounded-xl border border-amber-200/80 shadow-sm p-5">
            <h3 class="text-[13px] font-bold text-amber-800 mb-3 flex items-center gap-2">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" /></svg>
              质控提醒
            </h3>
            <div v-for="(msg, idx) in result.qcMessages" :key="idx" class="text-[13px] text-amber-700 py-1">
              ⚠ {{ msg }}
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
  performGrouping,
  getAvailableSchemes,
  getMdcName,
  type GrouperResult,
} from './drgGrouper'

const schemes = getAvailableSchemes()
const currentScheme = schemes[0]

const formData = reactive({
  gender: '2',
  age: 30,
  days: 15,
  leavingType: '1',
  zdList: [''] as string[],
  ssList: [''] as string[],
})

const grouping = ref(false)
const result = ref<GrouperResult | null>(null)

const mdcName = computed(() => {
  if (!result.value?.mdc) return ''
  return getMdcName(result.value.mdc)
})

function addDiagnosis() { formData.zdList.push('') }
function addProcedure() { formData.ssList.push('') }

function resetForm() {
  formData.gender = '2'
  formData.age = 30
  formData.days = 15
  formData.leavingType = '1'
  formData.zdList = ['']
  formData.ssList = ['']
  result.value = null
}

function fillTestCase() {
  formData.gender = '2'
  formData.age = 30
  formData.days = 15
  formData.leavingType = '1'
  formData.zdList = ['K80.501', 'K80.100x001', 'K83.109', 'K72.905', 'E11.900']
  formData.ssList = ['51.8803', '51.8701', '51.2300']
  result.value = null
  message.success('已填入测试用例')
}

async function doGrouping() {
  const zdList = formData.zdList.filter(z => z.trim())
  const ssList = formData.ssList.filter(s => s.trim())
  if (zdList.length === 0) { message.warning('请至少输入一个诊断编码'); return }

  grouping.value = true
  result.value = null
  try {
    result.value = await performGrouping({
      gender: formData.gender, age: formData.age, zdList, ssList,
      days: formData.days, leavingType: formData.leavingType,
    })
    if (result.value.status === '分组成功') {
      message.success(`分组成功: ${result.value.drg}`)
    } else {
      message.warning('未入组')
    }
  } catch (err) {
    message.error('分组失败: ' + (err instanceof Error ? err.message : String(err)))
  } finally {
    grouping.value = false
  }
}
</script>

<style scoped>
/* Ghost form field — 底线风格 */
.ghost-field {
  padding: 6px 2px 4px;
  border-bottom: 1.5px solid #e2e8f0;
  transition: border-color 0.2s;
}
.ghost-field:focus-within {
  border-bottom-color: #3b82f6;
}
.ghost-label {
  font-size: 11px; color: #94a3b8; font-weight: 500;
  margin-bottom: 2px; padding-left: 1px;
}
.ghost-input {
  width: 100%; background: transparent;
  font-size: 14px; color: #1e293b; font-weight: 600;
  padding: 2px 1px; outline: none; border: none;
}
.ghost-select {
  width: 100%; background: transparent;
  font-size: 14px; color: #1e293b; font-weight: 600;
  padding: 2px 1px; outline: none; border: none;
  appearance: none; cursor: pointer;
}
.ghost-add-btn {
  @apply w-full mt-2 py-2 border border-dashed border-slate-300 rounded-lg text-xs font-medium text-slate-500
    hover:text-blue-600 hover:border-blue-400 hover:bg-blue-50 transition-all cursor-pointer
    flex items-center justify-center gap-1.5;
}

/* Pipeline arrow */
.pipe-arrow {
  @apply w-14 h-px bg-slate-300 relative -translate-y-4;
}
.pipe-arrow::after {
  content: '';
  @apply absolute right-0 top-1/2 -translate-y-1/2 translate-x-0.5 w-2 h-2 border-t-2 border-r-2 border-slate-300 transform rotate-45;
}

/* Scrollbar */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #d4d4d8; border-radius: 3px; }
</style>
