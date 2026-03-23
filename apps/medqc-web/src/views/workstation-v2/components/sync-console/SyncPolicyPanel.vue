<template>
  <div class="h-full flex flex-col bg-white overflow-hidden">
    <div class="px-5 py-3.5 border-b border-slate-100 flex items-center justify-between shrink-0">
      <h2 class="text-[13px] font-semibold text-slate-900 tracking-tight">
        同步调优策略
      </h2>
      <a-tooltip title="功能开发中">
        <button
          disabled
          class="text-[12px] font-medium text-slate-400 bg-slate-50 border border-slate-200 rounded px-2 py-0.5 cursor-not-allowed shadow-none"
        >
          应用修改
        </button>
      </a-tooltip>
    </div>

    <div class="p-5 flex-1 overflow-y-auto custom-scrollbar space-y-5">
      <!-- 基础维度 -->
      <div class="space-y-4">
        <div class="flex items-start justify-between">
          <div class="flex-1 pr-6">
            <label class="text-[12px] font-medium text-slate-800 block">出院稳定天数</label>
            <p class="text-[11px] text-slate-500 mt-1 leading-relaxed">
              病历归档 N 天后才开始抽取，避免业务并发锁。
            </p>
          </div>
          <div class="w-[70px] shrink-0">
            <a-input-number
              size="small"
              value="3"
              :min="0"
              :max="30"
              class="!w-full !text-[12px] !border-slate-200 !shadow-none font-mono"
            />
          </div>
        </div>

        <div class="flex items-start justify-between">
          <div class="flex-1 pr-6">
            <label class="text-[12px] font-medium text-slate-800 block">时钟漂移回看 (分)</label>
            <p class="text-[11px] text-slate-500 mt-1 leading-relaxed">
              前移查询水位线，对冲分布式系统时序差。
            </p>
          </div>
          <div class="w-[70px] shrink-0">
            <a-input-number
              size="small"
              value="5"
              :min="0"
              :max="120"
              class="!w-full !text-[12px] !border-slate-200 !shadow-none font-mono"
            />
          </div>
        </div>
      </div>

      <div class="h-px w-full bg-slate-100" />

      <!-- 性能控制 -->
      <div class="space-y-4">
        <div class="flex items-start justify-between">
          <div class="flex-1 pr-6">
            <label class="text-[12px] font-medium text-slate-800 block">QPS 抽取限流</label>
            <p class="text-[11px] text-slate-500 mt-1 leading-relaxed">
              保护源库性能，严禁突发超频请求。
            </p>
          </div>
          <div class="w-[70px] shrink-0">
            <a-input-number
              size="small"
              value="50"
              :min="10"
              :max="500"
              class="!w-full !text-[12px] !border-slate-200 !shadow-none font-mono"
            />
          </div>
        </div>
      </div>
      
      <!-- 告警状态 (高危操作区) 用白底灰框，避免刺眼的橘黄底色 -->
      <div class="mt-4 rounded border border-slate-200 bg-white p-4 shadow-sm relative overflow-hidden">
        <div class="absolute left-0 top-0 bottom-0 w-1 bg-slate-300" />
        <div class="flex items-center justify-between mb-2">
          <span class="text-[12px] font-semibold text-slate-800">全量重置 (Risk)</span>
        </div>
        <p class="text-[11px] text-slate-500 leading-relaxed mb-3">
          清空目的地集合强制源端全量拉取。需在非业务时间段 (01:00后) 获取运维特权。
        </p>
        <a-tooltip title="功能开发中">
          <button
            disabled
            class="w-full py-1.5 text-[11px] font-medium text-slate-400 bg-slate-50 border border-slate-200 rounded cursor-not-allowed shadow-none"
          >
            申请重扫特权
          </button>
        </a-tooltip>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
</script>
