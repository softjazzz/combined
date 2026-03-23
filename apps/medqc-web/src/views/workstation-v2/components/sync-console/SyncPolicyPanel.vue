<template>
  <div class="h-full flex flex-col bg-white overflow-hidden">
    <div class="px-5 py-3.5 border-b border-slate-100 flex items-center justify-between shrink-0">
      <h2 class="text-[13px] font-semibold text-slate-900 tracking-tight">
        同步调优策略
      </h2>
      <a-tooltip :title="isReadonly ? '仅 admin 可保存' : '应用同步策略修改'">
        <a-button
          size="small"
          type="primary"
          :disabled="isReadonly"
          :loading="state.isSavingPolicy"
          @click="handleSave"
        >
          应用修改
        </a-button>
      </a-tooltip>
    </div>

    <div class="p-5 flex-1 overflow-y-auto custom-scrollbar space-y-5">
      <div class="rounded border border-slate-200 bg-slate-50 p-3">
        <div class="flex items-center justify-between">
          <div>
            <div class="text-[12px] font-semibold text-slate-800">
              全局同步总开关
            </div>
            <div class="text-[11px] text-slate-500 mt-1">
              关闭后仅允许查看，不执行增量同步任务。
            </div>
          </div>
          <a-switch
            v-model:checked="state.policyForm.enabled"
            :disabled="isReadonly"
            checked-children="启用"
            un-checked-children="关闭"
          />
        </div>
      </div>

      <div class="space-y-4">
        <div class="flex items-start justify-between gap-4">
          <div class="flex-1">
            <label class="text-[12px] font-medium text-slate-800 block">出院稳定天数</label>
            <p class="text-[11px] text-slate-500 mt-1">
              出院后等待 N 天才纳入终末抽取。
            </p>
          </div>
          <a-input-number
            v-model:value="state.policyForm.discharge_stable_days"
            :disabled="isReadonly"
            :min="0"
            :max="60"
            size="small"
          />
        </div>

        <div class="flex items-start justify-between gap-4">
          <div class="flex-1">
            <label class="text-[12px] font-medium text-slate-800 block">时钟漂移回看 (分)</label>
            <p class="text-[11px] text-slate-500 mt-1">
              回退查询水位线，对冲分布式时钟偏差。
            </p>
          </div>
          <a-input-number
            v-model:value="state.policyForm.lookback_minutes"
            :disabled="isReadonly"
            :min="0"
            :max="240"
            size="small"
          />
        </div>

        <div class="flex items-start justify-between gap-4">
          <div class="flex-1">
            <label class="text-[12px] font-medium text-slate-800 block">滚动重扫天数</label>
            <p class="text-[11px] text-slate-500 mt-1">
              最近 N 天修订的病历强制重拉。
            </p>
          </div>
          <a-input-number
            v-model:value="state.policyForm.rescan_recent_days"
            :disabled="isReadonly"
            :min="0"
            :max="60"
            size="small"
          />
        </div>

        <div class="flex items-start justify-between gap-4">
          <div class="flex-1">
            <label class="text-[12px] font-medium text-slate-800 block">Tier1 调度间隔 (分)</label>
            <p class="text-[11px] text-slate-500 mt-1">
              索引发现频率，建议 15~60 分钟。
            </p>
          </div>
          <a-input-number
            v-model:value="state.policyForm.tier1_interval_minutes"
            :disabled="isReadonly"
            :min="5"
            :max="1440"
            size="small"
          />
        </div>

        <div class="flex items-start justify-between gap-4">
          <div class="flex-1">
            <label class="text-[12px] font-medium text-slate-800 block">Tier2 调度间隔 (分)</label>
            <p class="text-[11px] text-slate-500 mt-1">
              结构化拉取频率，建议 60~240 分钟。
            </p>
          </div>
          <a-input-number
            v-model:value="state.policyForm.tier2_interval_minutes"
            :disabled="isReadonly"
            :min="5"
            :max="1440"
            size="small"
          />
        </div>

        <div>
          <label class="text-[12px] font-medium text-slate-800 block">Tier3 定时 (Cron)</label>
          <a-input
            v-model:value="state.policyForm.tier3_cron"
            :disabled="isReadonly"
            class="mt-1"
            placeholder="0 2 * * *"
          />
        </div>

        <div class="flex items-start justify-between gap-4">
          <div class="flex-1">
            <label class="text-[12px] font-medium text-slate-800 block">单批处理量</label>
            <p class="text-[11px] text-slate-500 mt-1">
              每批次处理的最大 visit 数。
            </p>
          </div>
          <a-input-number
            v-model:value="state.policyForm.max_batch_size"
            :disabled="isReadonly"
            :min="10"
            :max="5000"
            size="small"
          />
        </div>

        <div class="flex items-start justify-between gap-4">
          <div class="flex-1">
            <label class="text-[12px] font-medium text-slate-800 block">请求间隔 (ms)</label>
            <p class="text-[11px] text-slate-500 mt-1">
              请求节流，保护源端性能。
            </p>
          </div>
          <a-input-number
            v-model:value="state.policyForm.inter_request_delay_ms"
            :disabled="isReadonly"
            :min="0"
            :max="10000"
            size="small"
          />
        </div>

        <div class="grid grid-cols-2 gap-2">
          <div>
            <label class="text-[12px] font-medium text-slate-800 block">夜间窗口开始</label>
            <a-input
              v-model:value="state.policyForm.night_window_start"
              :disabled="isReadonly"
              placeholder="22:00"
            />
          </div>
          <div>
            <label class="text-[12px] font-medium text-slate-800 block">夜间窗口结束</label>
            <a-input
              v-model:value="state.policyForm.night_window_end"
              :disabled="isReadonly"
              placeholder="06:00"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { message } from 'ant-design-vue'
import { useDataSync } from '../../composables/useDataSync'

const { state, isReadonly, savePolicy } = useDataSync()

const handleSave = async () => {
  try {
    await savePolicy()
    message.success('同步策略保存成功')
  } catch {
    message.error('同步策略保存失败')
  }
}
</script>
