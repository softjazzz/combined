<template>
  <div class="h-full flex flex-col bg-white">
    <div class="px-5 py-3 border-b border-[#E5E7EB] flex items-center justify-between shrink-0 relative z-10 h-[52px]">
      <!-- 左右保证严格居中对齐 -->
      <div class="flex items-center gap-2 h-full">
        <h2 class="text-[14px] font-semibold text-slate-800 tracking-tight leading-none">
          结构浏览器
        </h2>
      </div>
      <div class="flex items-center gap-2 h-full">
        <div class="relative flex items-center">
          <svg
            class="w-3.5 h-3.5 absolute left-2.5 text-slate-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          ><path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          /></svg>
          <input
            type="text"
            placeholder="搜索表或字段"
            class="w-[180px] pl-8 pr-3 py-[5px] text-[12px] bg-slate-50 border border-slate-200 rounded-[6px] focus:bg-white focus:border-[#1890FF] focus:ring-1 focus:ring-[#1890FF] outline-none transition-colors text-slate-700 placeholder:text-slate-400 leading-tight"
          >
        </div>
      </div>
    </div>

    <!-- Inner Split Layout -->
    <div class="flex-1 flex overflow-hidden min-h-0">
      <!-- Left: Database Tree -->
      <div class="w-[220px] shrink-0 border-r border-slate-100/80 bg-slate-50/30 flex flex-col">
        <div class="flex-1 overflow-y-auto custom-scrollbar p-3">
          <!-- Tree Nodes (Minimalist) -->
          <div class="space-y-1">
            <!-- Database Node -->
            <div class="flex items-center gap-2 px-2 py-1.5 hover:bg-slate-100 rounded-md cursor-pointer text-slate-700 transition-colors group">
              <svg
                class="w-3.5 h-3.5 text-slate-400 group-hover:text-slate-600 transition-colors"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              ><path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M19 9l-7 7-7-7"
              /></svg>
              <svg
                class="w-4 h-4 text-slate-500"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              ><path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="1.5"
                d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4"
              /></svg>
              <span class="text-[12.5px] font-semibold tracking-tight text-slate-800">his_emr</span>
            </div>
            
            <!-- Table Nodes -->
            <div class="pl-6 space-y-1 mt-1">
              <div class="flex items-center gap-2 px-3 py-1.5 bg-white shadow-[0_1px_3px_rgba(0,0,0,0.04)] border border-slate-200/80 rounded-[6px] cursor-pointer">
                <svg
                  class="w-3.5 h-3.5 text-[#1890FF]"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                ><path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="1.5"
                  d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
                /></svg>
                <span class="text-[12px] font-semibold text-[#1890FF] font-mono">Patient_Info</span>
              </div>
              <div class="flex items-center gap-2 px-3 py-1.5 hover:bg-slate-100/80 rounded-[6px] cursor-pointer transition-colors group">
                <svg
                  class="w-3.5 h-3.5 text-slate-400 group-hover:text-slate-600 transition-colors"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                ><path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="1.5"
                  d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
                /></svg>
                <span class="text-[12px] text-slate-600 font-mono group-hover:text-slate-800 transition-colors">Diagnosis_Record</span>
              </div>
              <div class="flex items-center gap-2 px-3 py-1.5 hover:bg-slate-100/80 rounded-[6px] cursor-pointer transition-colors group">
                <svg
                  class="w-3.5 h-3.5 text-slate-400 group-hover:text-slate-600 transition-colors"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                ><path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="1.5"
                  d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
                /></svg>
                <span class="text-[12px] text-slate-600 font-mono group-hover:text-slate-800 transition-colors">Surgery_Details</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Right: Content View -->
      <div class="flex-1 flex flex-col min-w-0 bg-white">
        <!-- Inner Tabs (Modern Underlined) -->
        <div class="flex border-b border-slate-100/80 px-6 pt-2">
          <button class="px-3 py-2.5 border-b-[2px] border-[#1890FF] text-[12px] font-bold text-[#1890FF] mr-4 transition-colors">
            表结构 (Schema)
          </button>
          <button class="px-3 py-2.5 border-b-[2px] border-transparent text-[12px] font-medium text-slate-500 hover:text-slate-700 hover:border-slate-300 transition-colors">
            样本数据 (Limit 100)
          </button>
        </div>

        <!-- Inner Content (Refined high density table) -->
        <div class="flex-1 overflow-auto custom-scrollbar bg-white">
          <table class="w-full text-left border-collapse">
            <thead class="bg-white sticky top-0 z-10 shadow-[0_1px_0_rgba(226,232,240,1)]">
              <tr class="text-slate-400 font-semibold text-[11px] uppercase tracking-wider">
                <th class="px-6 py-3 w-[35%] font-medium">
                  字段基名
                </th>
                <th class="px-6 py-3 w-[25%] font-medium">
                  系统类型
                </th>
                <th class="px-6 py-3 w-[15%] text-center font-medium">
                  Null
                </th>
                <th class="px-6 py-3 w-[25%] font-medium">
                  配置元
                </th>
              </tr>
            </thead>
            <tbody class="font-mono text-[12px] text-slate-700">
              <tr class="hover:bg-slate-50/60 transition-colors border-b border-slate-100/50">
                <td class="px-6 py-3.5 font-semibold text-slate-900">
                  _id
                </td>
                <td class="px-6 py-3.5 text-slate-500">
                  ObjectId
                </td>
                <td class="px-6 py-3.5 text-center text-slate-300">
                  -
                </td>
                <td class="px-6 py-3.5">
                  <span class="inline-flex items-center gap-1 rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold text-amber-600 border border-amber-200/60 leading-none">
                    <svg
                      class="w-3 h-3"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                    ><path
                      fill-rule="evenodd"
                      d="M18 8a6 6 0 01-7.743 5.743L10 14l-1 1-1 1H6v-2H4l2-2v-2l2-2.257A6 6 0 1118 8zm-6-4a1 1 0 100 2 2 2 0 012 2 1 1 0 102 0 4 4 0 00-4-4z"
                      clip-rule="evenodd"
                    /></svg> 
                    PK
                  </span>
                </td>
              </tr>
              <tr class="hover:bg-slate-50/60 transition-colors border-b border-slate-100/50">
                <td class="px-6 py-3.5 font-medium text-slate-900">
                  patient_id
                </td>
                <td class="px-6 py-3.5 text-slate-500">
                  String
                </td>
                <td class="px-6 py-3.5 text-center text-slate-300">
                  -
                </td>
                <td class="px-6 py-3.5">
                  <span class="inline-flex items-center rounded bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-500 border border-slate-200/80 leading-none">Index</span>
                </td>
              </tr>
              <tr class="hover:bg-slate-50/60 transition-colors border-b border-slate-100/50">
                <td class="px-6 py-3.5 font-medium text-slate-800">
                  name
                </td>
                <td class="px-6 py-3.5 text-slate-500">
                  String
                </td>
                <td class="px-6 py-3.5 text-center text-slate-400">
                  Yes
                </td>
                <td class="px-6 py-3.5" />
              </tr>
              <tr class="hover:bg-slate-50/60 transition-colors">
                <td class="px-6 py-3.5 font-medium text-slate-800">
                  admission_date
                </td>
                <td class="px-6 py-3.5 text-slate-500">
                  ISODate
                </td>
                <td class="px-6 py-3.5 text-center text-slate-400">
                  Yes
                </td>
                <td class="px-6 py-3.5">
                  <span class="inline-flex items-center rounded bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-500 border border-slate-200/80 leading-none">Index</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
</script>
