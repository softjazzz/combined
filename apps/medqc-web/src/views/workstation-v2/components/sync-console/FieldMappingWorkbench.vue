<template>
  <div class="h-full flex flex-col bg-white overflow-hidden">
    <!-- Top Header -->
    <div class="px-6 py-4 border-b border-slate-100 flex flex-col sm:flex-row justify-between sm:items-center gap-3 shrink-0">
      <div class="flex items-center gap-3">
        <h2 class="text-[15px] font-bold text-slate-900 tracking-tight">
          字段清洗与映射规则
        </h2>
        <span class="rounded-[4px] bg-slate-100 px-2 py-0.5 text-[11px] font-mono font-medium text-slate-600 hidden sm:inline-block border border-slate-200/60">his_emr.Patient_Info → CDM.patient</span>
      </div>
      <div class="flex items-center gap-4">
        <div class="flex flex-col text-right mr-2">
          <span class="text-[11px] font-medium text-red-500 leading-tight">1 处严重校验失败</span>
          <span class="text-[10px] text-slate-400">请优先修复拦截项</span>
        </div>
        <a-tooltip title="功能开发中">
          <button
            disabled
            class="px-4 py-2 rounded-lg text-[12px] font-medium text-slate-400 bg-slate-50 border border-slate-200 cursor-not-allowed shadow-none"
          >
            导出映射 (JSON)
          </button>
        </a-tooltip>
        <a-tooltip title="功能开发中">
          <button
            disabled
            class="px-4 py-2 rounded-lg text-[12px] font-medium text-slate-400 bg-slate-50 border border-slate-200 cursor-not-allowed shadow-none"
          >
            从模板导入
          </button>
        </a-tooltip>
      </div>
    </div>

    <!-- Mapping Flow Area (High-end SaaS Style) -->
    <div class="flex-1 overflow-auto custom-scrollbar p-6 bg-[#F8F9FA] relative">
      <div class="flex flex-col gap-3 min-w-[800px] max-w-[1200px] mx-auto">
        <!-- List Header -->
        <div class="flex px-4 text-[11px] font-medium text-slate-500 uppercase tracking-wider mb-1">
          <div class="w-[35%] pl-2">
            源端系统 (Source)
          </div>
          <div class="flex-1 text-center">
            清洗通道 (Pipeline)
          </div>
          <div class="w-[35%] pl-4">
            中心舱 (Target CDM)
          </div>
          <div class="w-[8%] text-right pr-2">
            校验
          </div>
        </div>

        <!-- Flow Item: Direct Pass -->
        <div class="flex items-center bg-white rounded-[8px] border border-[#E5E7EB] p-3 relative transition-all">
          <div class="w-[35%] flex flex-col pl-4">
            <span class="text-[13px] font-bold text-slate-800 font-mono">patient_id</span>
            <span class="text-[11px] text-slate-400 font-medium mt-0.5">String</span>
          </div>
          <!-- Arrow & Badge -->
          <div class="flex-1 flex items-center justify-center relative">
            <div class="absolute w-full h-[1px] bg-[#E5E7EB]" />
            <div class="relative z-10 bg-white border border-[#E5E7EB] px-3 py-1 rounded-[6px] flex items-center gap-1.5 min-w-[100px] justify-center text-slate-600">
              <span class="text-[11px] font-medium tracking-tight">Direct Pass</span>
            </div>
          </div>
          <!-- Target -->
          <div class="w-[35%] flex flex-col pl-6">
            <div class="flex items-center gap-2">
              <span class="text-[13px] font-bold text-[#1890FF] font-mono">patient_uid</span>
              <span class="bg-amber-50 border border-amber-200 text-amber-600 px-1.5 py-0.5 rounded text-[9px] font-bold leading-none">PK</span>
            </div>
            <span class="text-[11px] text-slate-400 font-medium mt-0.5">String</span>
          </div>
          <!-- Status -->
          <div class="w-[8%] text-right pr-4">
            <div class="w-6 h-6 rounded-full bg-emerald-50 flex items-center justify-center ml-auto">
              <svg
                class="w-3.5 h-3.5 text-emerald-500"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              ><path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2.5"
                d="M5 13l4 4L19 7"
              /></svg>
            </div>
          </div>
        </div>

        <!-- Flow Item: Masking -->
        <div class="flex items-center bg-white rounded-[8px] border border-[#E5E7EB] p-3 relative transition-all">
          <div class="w-[35%] flex flex-col pl-4">
            <span class="text-[13px] font-bold text-slate-800 font-mono">name</span>
            <span class="text-[11px] text-slate-400 font-medium mt-0.5">String</span>
          </div>
          <div class="flex-1 flex items-center justify-center relative">
            <div class="absolute w-full h-[1px] bg-[#E5E7EB]" />
            <div class="relative z-10 bg-white border border-[#E5E7EB] px-3 py-1 rounded-[6px] flex items-center gap-1.5 min-w-[120px] justify-center text-slate-700">
              <span class="text-[11px] font-medium tracking-tight">Desensitize_CN</span>
            </div>
          </div>
          <div class="w-[35%] flex flex-col pl-6">
            <span class="text-[13px] font-bold text-[#1890FF] font-mono">patient_name</span>
            <span class="text-[11px] text-slate-400 font-medium mt-0.5">String</span>
          </div>
          <div class="w-[8%] text-right pr-4">
            <div class="w-6 h-6 rounded-full bg-emerald-50 flex items-center justify-center ml-auto">
              <svg
                class="w-3.5 h-3.5 text-emerald-500"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              ><path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2.5"
                d="M5 13l4 4L19 7"
              /></svg>
            </div>
          </div>
        </div>

        <!-- Flow Item: Warning -->
        <div class="flex items-center bg-white rounded-[8px] border border-amber-200/50 p-3 relative transition-all">
          <div class="absolute left-0 top-0 bottom-0 w-[3px] rounded-l-[8px] bg-amber-400" />
          <div class="w-[35%] flex flex-col pl-4">
            <span class="text-[13px] font-bold text-slate-800 font-mono">age_str</span>
            <span class="text-[11px] text-slate-400 font-medium mt-0.5">String</span>
          </div>
          <div class="flex-1 flex flex-col items-center justify-center relative">
            <div class="absolute w-full h-[1px] bg-[#E5E7EB] top-1/2 -translate-y-1/2" />
            <div class="relative z-10 bg-white border border-[#E5E7EB] px-3 py-1 rounded-[6px] flex items-center gap-1.5 min-w-[100px] justify-center text-slate-700">
              <span class="text-[11px] font-medium tracking-tight">Cast.Int()</span>
            </div>
          </div>
          <div class="w-[35%] flex flex-col pl-6">
            <div class="flex items-center gap-2">
              <span class="text-[13px] font-bold text-[#1890FF] font-mono">age</span>
            </div>
            <div class="flex items-center gap-1.5 mt-0.5">
              <span class="text-[11px] text-slate-400 font-medium">Integer</span>
              <span class="bg-slate-100 px-1 py-0.5 rounded text-[9px] font-medium text-slate-500 leading-none">类型有差异</span>
            </div>
          </div>
          <div class="w-[8%] text-right pr-4">
            <div
              class="w-6 h-6 rounded-full bg-amber-50 flex items-center justify-center ml-auto"
              title="具有运行期风险"
            >
              <svg
                class="w-4 h-4 text-amber-500"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              ><path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              /></svg>
            </div>
          </div>
        </div>

        <!-- Flow Item: Critical Error (MISSING TARGET) -->
        <div class="flex items-center bg-red-50/60 rounded-[8px] border border-red-200 p-3 relative transition-all">
          <div class="absolute left-0 top-0 bottom-0 w-[3px] rounded-l-[8px] bg-red-500" />
          <div class="w-[35%] flex flex-col pl-4 opacity-70 relative">
            <span class="text-[13px] font-bold text-slate-500 font-mono line-through">_missing_</span>
            <span class="text-[11px] text-slate-400 font-medium mt-0.5">N/A</span>
          </div>
          <div class="flex-1 flex flex-col items-center justify-center relative">
            <div class="absolute w-full h-[1px] bg-red-200 top-1/2 -translate-y-1/2" />
            <div class="relative z-10 bg-white border border-red-300 px-3 py-1 rounded-[6px] flex items-center gap-1.5 min-w-[100px] justify-center text-red-600 shadow-[0_1px_2px_0_rgba(220,38,38,0.05)]">
              <svg
                class="w-3.5 h-3.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              ><path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              /></svg>
              <span class="text-[11px] font-bold tracking-tight">Fallback(Val)</span>
            </div>
          </div>
          <div class="w-[35%] flex flex-col pl-6">
            <div class="flex items-center gap-2">
              <span class="text-[13px] font-bold text-slate-800 font-mono">gender</span>
              <span class="bg-red-100/50 border border-red-200 text-red-600 px-1.5 py-0.5 rounded text-[9px] font-bold leading-none">缺少必填数据</span>
            </div>
            <span class="text-[11px] text-slate-400 font-medium mt-0.5">String</span>
          </div>
          <div class="w-[8%] text-right pr-4">
            <a-tooltip title="功能开发中">
              <button
                disabled
                class="px-3 py-1.5 rounded-[6px] text-[11.5px] font-medium text-slate-400 bg-slate-50 border border-slate-200 cursor-not-allowed shadow-none w-full"
              >
                修复
              </button>
            </a-tooltip>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
</script>
