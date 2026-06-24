<template>
  <a-drawer
    v-model:open="visible"
    :title="null"
    placement="right"
    :width="760"
    :closable="false"
    :destroy-on-close="true"
    :body-style="{ padding: 0 }"
  >
    <div class="h-full flex flex-col bg-slate-50/50">
      <!-- 头部 -->
      <div class="px-7 py-6 bg-white border-b border-slate-200 flex justify-between items-start sticky top-0 z-10 shadow-sm">
        <div>
          <div class="flex items-center gap-3 mb-2">
            <h2 class="text-xl font-bold text-slate-800 leading-none">
              {{ formData.rule_name || '新建规则配置' }}
            </h2>
            <span class="px-2 py-0.5 rounded text-[11px] font-bold bg-blue-50 text-blue-600 border border-blue-100 uppercase tracking-wider">
              {{ formData.rule_id || 'NEW' }}
            </span>
          </div>
          <p class="text-[13px] text-slate-500 mt-1 max-w-xl">
            {{ formData.description || '在此配置规则的触发条件、执行逻辑和返回结果。支持 Python 语法子集进行逻辑判定。' }}
          </p>
        </div>
        <button
          class="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer shrink-0"
          @click="closeDrawer"
        >
          <svg
            class="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          ><path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M6 18L18 6M6 6l12 12"
          /></svg>
        </button>
      </div>

      <!-- 主体内容区 -->
      <div class="flex-1 overflow-y-auto p-7 space-y-7">
        <!-- 基本参数卡片 -->
        <div class="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div class="px-5 py-3.5 border-b border-slate-100 bg-slate-50/80 flex items-center gap-2">
            <svg
              class="w-4 h-4 text-slate-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            ><path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"
            /></svg>
            <h3 class="font-semibold text-slate-700 text-sm tracking-wide">
              基本参数 <span class="text-slate-300 font-normal ml-1">| Parameters</span>
            </h3>
          </div>
          <div class="p-6 grid grid-cols-2 gap-6">
            <div class="col-span-2">
              <label class="block text-[13px] font-semibold text-slate-600 mb-2">规则别名</label>
              <input
                v-model="formData.rule_name"
                type="text"
                class="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:bg-white focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10 outline-none transition-all placeholder:text-slate-400"
                placeholder="例如：主诊断缺失引发的医保拒付风险"
              >
            </div>
            <div>
              <label class="block text-[13px] font-semibold text-slate-600 mb-2">数据来源 (Field Key)</label>
              <div class="relative">
                <span class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 font-mono text-[11px] select-none">data.</span>
                <input
                  v-model="formData.field_name"
                  type="text"
                  class="w-full pl-11 pr-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm font-mono text-blue-600 focus:bg-white focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10 outline-none transition-all placeholder:text-slate-400"
                  placeholder="primary_diagnosis"
                >
              </div>
            </div>
            <div>
              <label class="block text-[13px] font-semibold text-slate-600 mb-2">归属业务域</label>
              <select
                v-model="formData.category"
                class="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-700 focus:bg-white focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10 outline-none transition-all appearance-none cursor-pointer"
              >
                <option value="required">
                  完整性检查
                </option>
                <option value="format">
                  数据格式规范
                </option>
                <option value="logic">
                  业务逻辑校验
                </option>
                <option value="consistency">
                  跨表单一致性
                </option>
              </select>
            </div>
          </div>
        </div>

        <!-- 极客风逻辑构建器 -->
        <div class="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
          <div class="px-5 py-3.5 border-b border-slate-100 bg-slate-50/80 flex items-center justify-between">
            <div class="flex items-center gap-2">
              <svg
                class="w-4 h-4 text-blue-500"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              ><path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
              /></svg>
              <h3 class="font-semibold text-slate-700 text-sm tracking-wide">
                运算逻辑引擎 <span class="text-slate-300 font-normal ml-1">| Logic Runtime</span>
              </h3>
            </div>
            <div class="flex items-center gap-1.5 text-[12px]">
              <span class="flex items-center gap-1.5 text-slate-600 bg-white px-2.5 py-1 border border-slate-200 rounded-md shadow-sm font-medium tracking-wide">
                <div class="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.5)]" /> 引擎就绪
              </span>
            </div>
          </div>
          
          <div class="relative bg-[#1e1e2e]">
            <div class="absolute right-4 top-4 text-[#6c7086] text-[10px] font-mono uppercase tracking-widest border border-[#313244] px-2 py-1 rounded bg-[#181825]">
              Readonly AST
            </div>
            <div class="p-5 font-mono text-[13px] leading-relaxed text-slate-300 overflow-x-auto selection:bg-[#45475a]">
              <div class="flex">
                <div class="text-[#6c7086] text-[12px] select-none text-right border-r border-[#313244] pr-4 mr-4 py-1 leading-[1.6]">
                  1<br>2<br>3<br>4<br>5<br>6
                </div>
                <div class="flex-1 whitespace-pre py-1 leading-[1.6]">
                  <span class="text-[#cba6f7]">def</span> <span class="text-[#89b4fa]">evaluate</span>(<span class="text-[#f38ba8] italic">context</span>):
                  <span class="text-[#585b70] italic"># Extract target field from patient record</span>
                  <span class="text-[#f38ba8]">val</span> <span class="text-[#89dceb]">=</span> context.get(<span class="text-[#a6e3a1]">'{{ formData.field_name || "target_field" }}'</span>)
                  <span class="text-[#cba6f7]">if</span> <span class="text-[#89dceb]">not</span> <span class="text-[#f38ba8]">val</span>:
                  <span class="text-[#cba6f7]">return</span> <span class="text-[#fab387] italic">False</span>, <span class="text-[#a6e3a1]">'约束违背：字段内容不允许为空'</span>
                  <span class="text-[#cba6f7]">return</span> <span class="text-[#fab387] italic">True</span>, <span class="text-[#a6e3a1]">'校验通过'</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 拦截动作配置 -->
        <div class="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div class="px-5 py-3.5 border-b border-slate-100 bg-slate-50/80 flex items-center gap-2">
            <svg
              class="w-4 h-4 text-slate-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            ><path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            /></svg>
            <h3 class="font-semibold text-slate-700 text-sm tracking-wide">
              拦截行为与级别 <span class="text-slate-300 font-normal ml-1">| Interception</span>
            </h3>
          </div>
          <div class="p-6 space-y-4">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <!-- Error -->
              <label
                class="relative flex p-4 border rounded-xl cursor-pointer hover:bg-slate-50 transition-all group overflow-hidden"
                :class="formData.severity === 'error' ? 'border-rose-300 bg-rose-50/20' : 'border-slate-200'"
              >
                <div
                  v-if="formData.severity !== 'error'"
                  class="absolute inset-0 bg-gradient-to-br from-rose-50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"
                />
                <input
                  v-model="formData.severity"
                  type="radio"
                  value="error"
                  class="w-4 h-4 text-rose-500 focus:ring-rose-400 border-slate-300 mt-1 cursor-pointer absolute opacity-0"
                >
                
                <div class="flex items-start gap-4 z-10">
                  <div
                    class="w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0 mt-0.5 transition-colors"
                    :class="formData.severity === 'error' ? 'border-rose-500' : 'border-slate-300'"
                  >
                    <div
                      class="w-2.5 h-2.5 rounded-full bg-rose-500 scale-0 transition-transform"
                      :class="{'scale-100': formData.severity === 'error'}"
                    />
                  </div>
                  <div>
                    <span class="block text-sm font-bold text-rose-600 mb-1">强制阻断 (Error)</span>
                    <span class="block text-[12px] text-slate-500 leading-relaxed">拦截当前表单保存并强制要求医生进行修正，否则流程死锁。</span>
                  </div>
                </div>
              </label>
              
              <!-- Warning -->
              <label
                class="relative flex p-4 border rounded-xl cursor-pointer hover:bg-slate-50 transition-all group overflow-hidden"
                :class="formData.severity === 'warning' ? 'border-amber-300 bg-amber-50/20' : 'border-slate-200'"
              >
                <div
                  v-if="formData.severity !== 'warning'"
                  class="absolute inset-0 bg-gradient-to-br from-amber-50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"
                />
                <input
                  v-model="formData.severity"
                  type="radio"
                  value="warning"
                  class="w-4 h-4 text-amber-500 focus:ring-amber-400 border-slate-300 mt-1 cursor-pointer absolute opacity-0"
                >
                
                <div class="flex items-start gap-4 z-10">
                  <div
                    class="w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0 mt-0.5 transition-colors"
                    :class="formData.severity === 'warning' ? 'border-amber-500' : 'border-slate-300'"
                  >
                    <div
                      class="w-2.5 h-2.5 rounded-full bg-amber-500 scale-0 transition-transform"
                      :class="{'scale-100': formData.severity === 'warning'}"
                    />
                  </div>
                  <div>
                    <span class="block text-sm font-bold text-amber-500 mb-1">柔性警告 (Warning)</span>
                    <span class="block text-[12px] text-slate-500 leading-relaxed">系统弹出气泡提示指出风险，但允许用户确认后跳过该规则继续。</span>
                  </div>
                </div>
              </label>

              <!-- Info -->
              <label
                class="relative flex p-4 border rounded-xl cursor-pointer hover:bg-slate-50 transition-all group overflow-hidden md:col-span-2"
                :class="formData.severity === 'info' ? 'border-blue-300 bg-blue-50/20' : 'border-slate-200'"
              >
                <div
                  v-if="formData.severity !== 'info'"
                  class="absolute inset-0 bg-gradient-to-br from-blue-50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"
                />
                <input
                  v-model="formData.severity"
                  type="radio"
                  value="info"
                  class="w-4 h-4 text-blue-500 focus:ring-blue-400 border-slate-300 mt-1 cursor-pointer absolute opacity-0"
                >
                
                <div class="flex items-start gap-4 z-10 w-full">
                  <div
                    class="w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0 mt-0.5 transition-colors"
                    :class="formData.severity === 'info' ? 'border-blue-500' : 'border-slate-300'"
                  >
                    <div
                      class="w-2.5 h-2.5 rounded-full bg-blue-500 scale-0 transition-transform"
                      :class="{'scale-100': formData.severity === 'info'}"
                    />
                  </div>
                  <div>
                    <span class="block text-sm font-bold text-blue-500 mb-1">静默记录 (Info)</span>
                    <span class="block text-[12px] text-slate-500 leading-relaxed">对用户前端无感知，仅在数据大盘或审计日志中记录该缺陷特征，用于统计与复盘。</span>
                  </div>
                </div>
              </label>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部操作区 -->
      <div class="px-7 py-5 bg-white border-t border-slate-200 flex justify-between items-center sticky bottom-0 z-10 shadow-sm">
        <div class="flex items-center gap-3 text-[13px] text-slate-600 font-semibold cursor-pointer group">
          <div class="relative w-10 h-6 bg-blue-500 rounded-full shadow-inner transition-colors">
            <div class="absolute top-1 left-5 w-4 h-4 bg-white rounded-full shadow-sm" />
          </div>
          规则已激活
        </div>
        <div class="flex gap-3">
          <button
            class="px-5 py-2.5 text-sm font-semibold text-slate-600 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 focus:outline-none focus:ring-4 focus:ring-slate-100 transition-all cursor-pointer"
            @click="closeDrawer"
          >
            取消修改
          </button>
          <button
            class="px-6 py-2.5 text-sm font-bold text-white bg-blue-600 border border-transparent rounded-lg hover:bg-blue-700 hover:shadow-md focus:outline-none focus:ring-4 focus:ring-blue-500/20 transition-all shadow-sm flex items-center gap-2 cursor-pointer"
            @click="handleSave"
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
              d="M5 13l4 4L19 7"
            /></svg>
            发布配置
          </button>
        </div>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps({
  open: {
    type: Boolean,
    default: false
  },
  record: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['update:open', 'save'])

const visible = ref(false)
const formData = ref<any>({})

watch(() => props.open, (val) => {
  visible.value = val
  if (val) {
    formData.value = { ...props.record }
  }
})

watch(visible, (val) => {
  emit('update:open', val)
})

const closeDrawer = () => {
  visible.value = false
}

const handleSave = () => {
  emit('save', formData.value)
  closeDrawer()
}
</script>
